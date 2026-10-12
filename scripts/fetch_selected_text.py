"""Locate exact planned IDs through bounded official Parquet column ranges.

Only patch-ID column chunks are transferred. Original annotations are then
requested individually through the official rows endpoint, never synthesized
from catalog fields. The dataset-server revision is acquisition context only.
"""

import io
import json
import time
import urllib.error
import urllib.parse
from pathlib import Path

import pyarrow.parquet as pq

from earth_observation.data import fetch_asset
from earth_observation.text_access import acquire_text_asset, original_annotation

DATASET = "BIFOLD-BigEarthNetv2-0/BigEarthNet.txt"
LIMIT = 50_000_000


def main() -> None:
    """Fetch bounded source evidence and save exact response identities locally."""
    root = Path(__file__).resolve().parents[1]
    directory = root / "data/cache/archive-access-v2"
    manifest_path = root / "manifests/archive-data-access-v2.json"
    manifest = json.loads(manifest_path.read_text())
    ids = manifest["planned_patch_ids"]
    ledger_path = directory / "transfer-ledger.json"
    budget = (
        json.loads(ledger_path.read_text())
        if ledger_path.exists()
        else {
            "limit_bytes": LIMIT,
            "transferred_bytes": 200_000,
            "reserved_bytes": 200_000,
        }
    )
    if budget["limit_bytes"] != LIMIT or not (
        0 <= budget["transferred_bytes"] <= budget["reserved_bytes"] <= LIMIT
    ):
        raise ValueError("Invalid cumulative text transfer ledger")
    directory.mkdir(parents=True, exist_ok=True)
    # A clean reproduction bootstraps only the pinned inventory and footer.
    for asset in manifest.get("text_source_receipts", []):
        if asset["name"] not in {"parquet-inventory.json", "pinned-parquet-footer.bin"}:
            continue
        target = directory / asset["name"]
        if not target.exists():
            if budget["reserved_bytes"] + asset["size_bytes"] + 1 > LIMIT:
                raise ValueError("Bootstrap exceeds total text budget")
            budget["reserved_bytes"] += asset["size_bytes"] + 1
            ledger_path.write_text(json.dumps(budget, indent=2) + "\n")
            fetch_asset(asset, directory, max_bytes=asset["size_bytes"])
            budget["transferred_bytes"] += asset["size_bytes"]
            budget["reserved_bytes"] -= 1
            (directory / (asset["name"] + ".source.json")).write_text(
                json.dumps(asset, indent=2) + "\n"
            )
            ledger_path.write_text(json.dumps(budget, indent=2) + "\n")
        else:
            fetch_asset(asset, directory, max_bytes=asset["size_bytes"])
    inventory = json.loads((directory / "parquet-inventory.json").read_text())
    source = inventory["parquet_files"][0]
    footer_path = directory / "pinned-parquet-footer.bin"
    if not footer_path.exists():
        footer_path = directory / "parquet-footer.bin"
    footer = footer_path.read_bytes()
    metadata = pq.read_metadata(io.BytesIO(b"PAR1" + footer))
    receipts = []

    def acquire(
        url: str,
        name: str,
        size: int | None = None,
        byte_range: tuple[int, int] | None = None,
    ) -> bytes:
        for attempt in range(3):
            try:
                if not (directory / name).exists():
                    time.sleep(1.5)
                content, receipt = acquire_text_asset(
                    url,
                    directory,
                    name,
                    budget,
                    expected_size=size,
                    byte_range=byte_range,
                    total_size=source["size"],
                )
                receipts.append(receipt)
                return content
            except urllib.error.HTTPError as error:
                if error.code != 429 or attempt == 2:
                    raise
                delay = int(error.headers.get("Retry-After", "60"))
                print(f"Official rows rate limit; waiting {delay} seconds", flush=True)
                while delay > 0:
                    interval = min(30, delay)
                    time.sleep(interval)
                    delay -= interval
            except (OSError, urllib.error.URLError):
                if attempt == 2:
                    raise
            finally:
                ledger_path.write_text(json.dumps(budget, indent=2) + "\n")
        raise RuntimeError("Unreachable retry state")

    info_url = "https://huggingface.co/api/datasets/" + DATASET
    revision = json.loads(acquire(info_url, "repository-info.json"))["sha"]
    converted = json.loads(
        acquire(info_url + "/revision/refs%2Fconvert%2Fparquet", "converted-info.json")
    )["sha"]
    # Pin the converted source itself; rows responses have independent byte pins.
    source_url = source["url"].replace("refs%2Fconvert%2Fparquet", converted)
    pinned_footer = acquire(
        source_url + "?selected_footer=1",
        "pinned-parquet-footer.bin",
        len(footer),
        (source["size"] - len(footer), source["size"] - 1),
    )
    if pinned_footer != footer:
        raise ValueError("Converted source footer changed before acquisition")
    offsets, groups = {}, []
    base_row = 0
    for index in range(metadata.num_row_groups):
        group = metadata.row_group(index)
        column = group.column(2)
        if (
            column.path_in_schema != "patch_id"
            or not column.statistics
            or not column.statistics.has_min_max
        ):
            raise ValueError("Expected complete patch-ID min/max metadata")
        matches = [
            pid for pid in ids if column.statistics.min <= pid <= column.statistics.max
        ]
        if matches:
            groups.append((index, base_row, matches, column))
        base_row += group.num_rows
    expected = sum(c.total_compressed_size for _, _, _, c in groups)
    if expected + budget["reserved_bytes"] + len(ids) * 100_001 > LIMIT:
        raise ValueError("Preflight column/individual-row budget exceeds 50 MB")
    print(
        json.dumps(
            {
                "patch_column_bytes": expected,
                "groups": len(groups),
                "rows": metadata.num_rows,
                "revision": revision,
                "converted_revision": converted,
            }
        ),
        flush=True,
    )
    sparse = directory / "patch-id-columns.partial.parquet"
    with sparse.open("w+b") as destination:
        destination.write(b"PAR1")
        destination.seek(source["size"] - len(footer))
        destination.write(footer)
        for index, base, matches, column in groups:
            start = column.dictionary_page_offset
            if start is None:
                start = column.data_page_offset
            end = start + column.total_compressed_size - 1
            content = acquire(
                source_url + f"?selected_column={index}",
                f"patch-column-{index}.bin",
                column.total_compressed_size,
                (start, end),
            )
            destination.seek(start)
            destination.write(content)
            destination.flush()
            table = pq.ParquetFile(sparse).read_row_group(index, columns=["patch_id"])
            series = table.column(0).to_pandas()
            for pid in matches:
                locations = series.index[series.eq(pid)]
                if len(locations):
                    offsets[pid] = min(
                        offsets.get(pid, metadata.num_rows), base + int(locations[0])
                    )
            print(
                f"Indexed group {index}: {len(offsets)} exact selected IDs", flush=True
            )
    annotations, assets = [], []
    for position, pid in enumerate(ids):
        if pid not in offsets:
            continue
        params = {
            "dataset": DATASET,
            "config": "default",
            "split": "all_data",
            "offset": offsets[pid],
            "length": 1,
        }
        url = "https://datasets-server.huggingface.co/rows?" + urllib.parse.urlencode(
            params
        )
        content = acquire(url, f"text-selected-{position}.json")
        page = json.loads(content)
        annotations.append(original_annotation(page, pid, offsets[pid]))
        assets.append(receipts[-1])
        print(
            f"Original text {len(annotations)}/{len(ids)}; "
            f"transfer <= {budget['reserved_bytes']} bytes",
            flush=True,
        )
        result = {
            "repository_revision_observed": revision,
            "converted_parquet_revision": converted,
            "revision_limitation": (
                "Rows endpoint has no revision parameter; response digests "
                "pin actual annotation bytes independently."
            ),
            "transfer_bytes_upper_bound": budget["reserved_bytes"],
            "received_bytes_upper_bound": budget["transferred_bytes"],
            "patch_column_bytes": expected,
            "missing_patch_ids": [p for p in ids if p not in offsets],
            "text_annotations": annotations,
            "text_assets": assets,
            "source_receipts": receipts,
        }
        (directory / "text-results.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
    print("Complete exact text lookup", flush=True)


if __name__ == "__main__":
    main()
