"""Resume checksum-pinned archives and extract exact native TIFF members only.

Full S2/map archive acquisition is separately authorized for this experiment.
Partial files are never accepted as raster sources. No tar extraction method
is allowed to choose output paths, follow archive links, or overwrite a cache.
"""

import hashlib
import json
import shutil
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import zstandard

from earth_observation.raster import patch_files


def verify_archive(path: Path, asset: dict, receipt_path: Path | None = None) -> dict:
    """Verify a complete archive against the published byte size and MD5.

    Parameters
    ----------
    path : Path
        Complete local archive; symbolic links are rejected.
    asset : dict
        Official filename, size_bytes and md5 from the pinned Zenodo record.
    receipt_path : Path, optional
        Local downloader's verified receipt. Reuse requires matching identity
        and archive modification/change times no later than the receipt.
        Receipts are trusted local outputs, not remote or user-supplied claims.
        Missing/stale receipts trigger hashing; they never excuse a mismatch.

    Returns
    -------
    dict
        Measured byte count, published MD5 and additional content SHA-256.

    Raises
    ------
    ValueError
        Incomplete archive, unsafe file, or published checksum mismatch.
    """
    if path.is_symlink() or not path.is_file():
        raise ValueError("Archive must be a regular local file")
    if path.stat().st_size != asset["size_bytes"]:
        raise ValueError("Archive is incomplete or has the wrong size")
    before = path.stat()
    if receipt_path is not None and receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text())
        if (
            receipt.get("status") == "verified"
            and receipt.get("name") == asset["name"]
            and receipt.get("size_bytes") == asset["size_bytes"]
            and receipt.get("md5") == asset["md5"]
            and isinstance(receipt.get("sha256"), str)
            and len(receipt["sha256"]) == 64
            and max(before.st_mtime_ns, before.st_ctime_ns)
            <= receipt_path.stat().st_mtime_ns
        ):
            return {k: receipt[k] for k in ("name", "size_bytes", "md5", "sha256")}
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(8 * 1024 * 1024):
            md5.update(block)
            sha256.update(block)
    if md5.hexdigest() != asset["md5"]:
        raise ValueError("Archive published MD5 mismatch; preserve and investigate")
    after = path.stat()
    identity_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(after, key) != getattr(before, key) for key in identity_fields):
        raise ValueError("Archive changed during checksum verification")
    return {
        "name": asset["name"],
        "size_bytes": path.stat().st_size,
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest(),
    }


def download_archive(
    asset: dict,
    directory: Path,
    timeout: float = 60,
    attempts: int = 3,
    chunk_size_bytes: int = 67108864,
) -> dict:
    """Download or resume one archive without restarting a partial transfer.

    Parameters
    ----------
    asset : dict
        Pinned name, official HTTPS URL, size_bytes and published md5.
    directory : Path
        Git-ignored archive store. Partial data and source identity are retained.
    timeout : float
        Socket inactivity timeout in seconds, also applied to response headers.
    attempts : int
        Maximum consecutive failed network attempts. Completed chunks reset
        the failure count; retries resume the saved byte offset.
    chunk_size_bytes : int
        Maximum payload per exact HTTP Range request (default 64 MiB).

    Returns
    -------
    dict
        Complete verified identity, bytes transferred this invocation, reused
        bytes, and observed exact HTTP ranges. Logs progress every 30 seconds.

    Raises
    ------
    ValueError
        Unsafe path, incompatible partial cache, ignored Range, unexpected
        size/encoding, or checksum failure. No restart or repair is attempted.
    OSError
        Insufficient space or exhaustion of bounded network retries.
    """
    name = asset["name"]
    if (
        Path(name).name != name
        or name not in {"BigEarthNet-S2.tar.zst", "Reference_Maps.tar.zst"}
        or not asset["url"].startswith("https://zenodo.org/")
        or asset["size_bytes"] <= 0
        or attempts < 1
        or timeout <= 0
        or chunk_size_bytes <= 0
    ):
        raise ValueError("Expected an authorized official S2 or map archive")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    partial = directory / f"{name}.part"
    identity_path = directory / f"{name}.part.json"
    progress_path = directory / f"{name}.progress.json"
    if any(p.is_symlink() for p in (target, partial, identity_path, progress_path)):
        raise ValueError("Archive cache paths must not be symbolic links")
    if target.exists():
        return {
            **verify_archive(target, asset, progress_path),
            "downloaded_bytes": 0,
            "reused_bytes": asset["size_bytes"],
            "ranges": [],
        }
    if (identity_path.exists() and json.loads(identity_path.read_text()) != asset) or (
        partial.exists() and not identity_path.is_file()
    ):
        raise ValueError("Unidentified or incompatible partial archive")
    initial = partial.stat().st_size if partial.exists() else 0
    if initial > asset["size_bytes"]:
        raise ValueError("Partial archive exceeds expected size")
    if shutil.disk_usage(directory).free < asset["size_bytes"] - initial + 67108864:
        raise OSError("Insufficient free space for archive and 64 MiB reserve")
    identity_path.write_text(json.dumps(asset, indent=2) + "\n")
    ranges = []

    def progress(status: str, error: str | None = None) -> None:
        current = partial.stat().st_size if partial.exists() else 0
        measured = {
            "name": name,
            "status": status,
            "size_bytes": asset["size_bytes"],
            "received_bytes": current,
            "downloaded_bytes": current - initial,
            "reused_bytes": initial,
            "ranges": ranges,
            "error": error,
        }
        progress_path.write_text(json.dumps(measured, indent=2) + "\n")
        print(
            json.dumps(
                {k: v for k, v in measured.items() if k != "ranges"}
                | {"range_requests": len(ranges)}
            ),
            flush=True,
        )

    progress("starting")
    failures = 0
    last_report = time.monotonic()
    while True:
        offset = partial.stat().st_size if partial.exists() else 0
        if offset == asset["size_bytes"]:
            break
        end = min(offset + chunk_size_bytes, asset["size_bytes"]) - 1
        request = urllib.request.Request(
            asset["url"],
            headers={"Range": f"bytes={offset}-{end}", "Accept-Encoding": "identity"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                expected = f"bytes {offset}-{end}/{asset['size_bytes']}"
                if (
                    response.status != 206
                    or response.headers.get("Content-Range") != expected
                    or response.headers.get("Content-Encoding", "identity")
                    != "identity"
                    or (
                        response.headers.get("Content-Length") is not None
                        and int(response.headers["Content-Length"]) != end - offset + 1
                    )
                ):
                    raise ValueError("Server did not honor the exact resume range")
                ranges.append({"start": offset, "end": end, "status": 206})
                # Opening for append happens only after exact range validation.
                with partial.open("ab") as destination:
                    remaining = end - offset + 1
                    while remaining:
                        block = response.read(min(1024 * 1024, remaining))
                        if not block:
                            raise OSError("Archive response ended before expected size")
                        destination.write(block)
                        remaining -= len(block)
                        if time.monotonic() - last_report >= 30:
                            destination.flush()
                            progress("downloading")
                            last_report = time.monotonic()
                    if response.read(1):
                        raise ValueError("Archive response exceeds expected size")
            failures = 0
        except ValueError as error:
            progress("failed", str(error))
            raise
        except (OSError, urllib.error.URLError) as error:
            failures += 1
            progress("retrying" if failures < attempts else "failed", str(error))
            if failures == attempts:
                raise OSError(
                    f"Archive download exhausted {attempts} consecutive attempts"
                ) from error
            time.sleep(5)
    progress("verifying")
    try:
        verified = verify_archive(partial, asset)
    except ValueError as error:
        progress("failed", str(error))
        raise
    partial.rename(target)
    result = {
        **verified,
        "downloaded_bytes": asset["size_bytes"] - initial,
        "reused_bytes": initial,
        "ranges": ranges,
    }
    progress_path.write_text(json.dumps({**result, "status": "verified"}, indent=2))
    print(json.dumps({**result, "status": "verified"}), flush=True)
    return result


def selected_raster_members(patch_ids: list[str]) -> list[str]:
    """Resolve exactly B04/B03/B02 and one original map per unique patch ID.

    Parameters
    ----------
    patch_ids : list of str
        Exact predeclared S2 IDs, in manifest order; no substring matching.

    Returns
    -------
    list of str
        Four relative provider-native paths per patch in RGB/reference order.

    Raises
    ------
    ValueError
        Empty, duplicated or malformed patch identities.
    """
    if not patch_ids or len(set(patch_ids)) != len(patch_ids):
        raise ValueError("Expected nonempty unique patch IDs")
    return [
        str(path)
        for pid in patch_ids
        for path in patch_files(
            pid, Path("BigEarthNet-S2"), Path("Reference_Maps")
        ).values()
    ]


def extract_archive_selection(
    archive_path: Path,
    asset: dict,
    member_names: list[str],
    raw_root: Path,
    selected_budget_bytes: int = 67108864,
    verification_receipt: Path | None = None,
) -> dict:
    """Scan one verified archive sequentially and persist only exact TIFF names.

    Parameters
    ----------
    archive_path : Path
        Complete archive; published size/MD5 are verified before decompression.
    asset : dict
        Official archive identity accepted by verify_archive.
    member_names : list of str
        Exact paths belonging to this archive, generated from selected IDs.
    raw_root : Path
        Native data directory; existing equal bytes are reused, never repaired.
    selected_budget_bytes : int
        Maximum selected uncompressed payload bytes held in memory and saved.
        The full tar is scanned for missing/duplicate names without saving it.
    verification_receipt : Path, optional
        Unchanged archive's trusted local complete-download receipt. See
        verify_archive for identity and file-time checks before reuse.

    Returns
    -------
    dict
        Verified archive identity, exact member sizes/SHA-256, created/reused
        counts and selected payload bytes. A failure publishes no new TIFFs.

    Raises
    ------
    ValueError
        Unsafe/duplicate/missing member, link, incomplete archive, excessive
        selected payload or incompatible existing file. Paths are never chosen
        by tar extraction APIs. Unknown/missing members are not substituted.
    """
    verified = verify_archive(archive_path, asset, verification_receipt)
    prefix = asset["name"].removesuffix(".tar.zst")
    expected = set(member_names)
    if not expected or len(expected) != len(member_names):
        raise ValueError("Expected nonempty unique exact member names")
    raw_root.mkdir(parents=True, exist_ok=True)
    for name in member_names:
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[0] != prefix
            or relative.suffix != ".tif"
            or len(relative.parts) != 4
        ):
            raise ValueError("Unsafe or wrong-archive selected member")
        target = raw_root / relative
        if not target.resolve().is_relative_to(raw_root.resolve()) or any(
            p.is_symlink() for p in [target, *target.parents] if p != raw_root.parent
        ):
            raise ValueError("Selected output would follow a symbolic link")
    found = {}
    payload_bytes = 0
    last_report = time.monotonic()
    with archive_path.open("rb") as compressed:
        with zstandard.ZstdDecompressor().stream_reader(compressed) as stream:
            with tarfile.open(fileobj=stream, mode="r|") as archive:
                for member in archive:
                    # Python 3.12's streaming tar reader otherwise retains millions
                    # of TarInfo objects, even though only 100 files are requested.
                    archive.members.clear()
                    if time.monotonic() - last_report >= 30:
                        print(
                            json.dumps(
                                {
                                    "archive": asset["name"],
                                    "tar_scan_bytes": archive.offset,
                                    "selected_found": len(found),
                                }
                            ),
                            flush=True,
                        )
                        last_report = time.monotonic()
                    if member.name not in expected:
                        continue
                    if member.name in found or not member.isfile():
                        raise ValueError("Selected member is duplicated or a link")
                    if member.size <= 0 or payload_bytes + member.size > (
                        selected_budget_bytes
                    ):
                        raise ValueError("Selected raster payload exceeds byte budget")
                    with archive.extractfile(member) as source:
                        content = source.read(member.size + 1)
                    if len(content) != member.size:
                        raise ValueError("Incomplete selected TIFF")
                    found[member.name] = content
                    payload_bytes += len(content)
    missing = sorted(expected - found.keys())
    if missing:
        raise ValueError(f"Missing exact archive members: {missing}")
    reused = 0
    for name, content in found.items():
        target = raw_root / name
        if target.exists():
            if not target.is_file() or target.read_bytes() != content:
                raise ValueError(f"Existing raster identity mismatch: {name}")
            reused += 1
    # Check the entire selection before creating any final output file.
    for name, content in found.items():
        target = raw_root / name
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as destination:
                destination.write(content)
    return {
        "archive": verified,
        "created_files": len(found) - reused,
        "reused_files": reused,
        "selected_bytes": payload_bytes,
        "members": [
            {
                "name": name,
                "size_bytes": len(found[name]),
                "sha256": hashlib.sha256(found[name]).hexdigest(),
            }
            for name in member_names
        ],
    }
