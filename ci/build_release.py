#!/usr/bin/env python3
"""Build deterministic BSP release archives directly from Git objects."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile
import zipfile

VERSION_RE = re.compile(
    r"v[0-9]+(?:\.[0-9]+)*(?:-[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)?"
    r"(?:\+[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)?\Z"
)
SKILL_PREFIX = "skills/bsp/"
REQUIRED_PATHS = {"skills/bsp/SKILL.md", "skills/bsp/agents/openai.yaml", "install.sh", "install.ps1"}


class BuildError(RuntimeError):
    pass


def git(repo: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip()
        raise BuildError(f"Git command failed: {detail}") from exc


def _safe_archive_path(path: str) -> None:
    pure = PurePosixPath(path)
    parts = path.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if (not path or "\\" in path or path.startswith("/") or
            any(part in ("", ".", "..") or ":" in part or part.endswith((".", " ")) or
                part.split(".", 1)[0].upper() in reserved for part in parts) or
            pure.is_absolute()):
        raise BuildError(f"Unsafe Git path: {path!r}")


def skill_fingerprint(files: dict[str, bytes]) -> str:
    """Match ci/run_skill_evals.py:skill_sha256 for skills/bsp."""
    digest = hashlib.sha256()
    # Sort POSIX relative names explicitly so the fingerprint is OS-independent.
    skill_paths = (
        name for name in files
        if name.startswith(SKILL_PREFIX)
        and not any(
            part == "__pycache__" or part.endswith((".pyc", ".pyo"))
            for part in PurePosixPath(name[len(SKILL_PREFIX):]).parts
        )
    )
    for path in sorted(skill_paths):
        relative = path[len(SKILL_PREFIX):]
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[path])
        digest.update(b"\0")
    return digest.hexdigest()


def read_tree(repo: Path, ref: str) -> tuple[str, dict[str, bytes], dict[str, int]]:
    treeish = ref + "^{tree}"
    tree = git(repo, "rev-parse", "--verify", "--end-of-options", treeish).decode("ascii").strip()
    records = git(repo, "ls-tree", "-rz", "--full-tree", "-r", tree)
    files: dict[str, bytes] = {}
    modes: dict[str, int] = {}
    for record in records.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode_text, object_type, object_id = metadata.decode("ascii").split(" ")
            path = raw_path.decode("utf-8", "strict")
        except (ValueError, UnicodeDecodeError) as exc:
            raise BuildError("Malformed or non-UTF-8 Git tree entry") from exc
        selected = path.startswith(SKILL_PREFIX) or path in {"install.sh", "install.ps1"}
        if not selected:
            continue
        if path.startswith(SKILL_PREFIX) and any(
            part == "__pycache__" or part.endswith((".pyc", ".pyo"))
            for part in PurePosixPath(path[len(SKILL_PREFIX):]).parts
        ):
            continue
        _safe_archive_path(path)
        mode = int(mode_text, 8)
        if object_type != "blob" or mode not in (0o100644, 0o100755):
            raise BuildError(f"Unsafe Git object mode/type for {path}: {mode_text} {object_type}")
        files[path] = git(repo, "cat-file", "blob", object_id)
        modes[path] = mode
    missing = sorted(REQUIRED_PATHS - files.keys())
    if missing:
        raise BuildError("Missing required Git paths: " + ", ".join(missing))
    # Install mode is standardized in both archives regardless of host checkout semantics.
    modes["install.sh"] = 0o100755
    return tree, files, modes


def make_zip(path: Path, files: dict[str, bytes], modes: dict[str, int]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            unix_mode = stat.S_IFREG | (modes[name] & 0o777)
            info.external_attr = unix_mode << 16
            archive.writestr(info, files[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def make_tar_gz(path: Path, files: dict[str, bytes], modes: dict[str, int]) -> None:
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for name in sorted(files):
                    info = tarfile.TarInfo(name)
                    info.size = len(files[name])
                    info.mode = modes[name] & 0o777
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = 0
                    archive.addfile(info, io.BytesIO(files[name]))


def build(ref: str, version: str, output_dir: Path, repo: Path) -> dict:
    if not VERSION_RE.fullmatch(version):
        raise BuildError("Invalid version; expected a safe v-prefixed version (for example v0.13)")
    if output_dir.exists():
        raise BuildError(f"Output directory already exists: {output_dir}")
    tree, files, modes = read_tree(repo, ref)
    output_dir.mkdir(parents=True)
    try:
        zip_path = output_dir / f"bsp-skill-{version}.zip"
        tar_path = output_dir / f"bsp-skill-{version}.tar.gz"
        make_zip(zip_path, files, modes)
        make_tar_gz(tar_path, files, modes)

        # Materialize only the bytes obtained from Git objects; no archive extraction of untrusted paths.
        for name, data in files.items():
            target = output_dir / "extracted" / Path(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(modes[name] & 0o777)

        file_records = {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "mode": f"{modes[name] & 0o777:04o}"}
            for name, data in sorted(files.items())
        }
        manifest = {
            "source_tree": tree,
            "version": version,
            "files": file_records,
            "skill_fingerprint": skill_fingerprint(files),
            "archives": {
                zip_path.name: hashlib.sha256(zip_path.read_bytes()).hexdigest(),
                tar_path.name: hashlib.sha256(tar_path.read_bytes()).hexdigest(),
            },
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="ascii"
        )
        return manifest
    except Exception:
        # Never leave a partial candidate that could be mistaken for a completed build.
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD", help="Git commit or tree (default: HEAD)")
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        result = build(args.ref, args.version, args.output_dir, args.repo.resolve())
    except (BuildError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"BSP release candidate {args.version}: {len(result['files'])} files; tree {result['source_tree'][:12]}")
    for name, digest in result["archives"].items():
        print(f"{name}: sha256 {digest}")
    print(f"Skill fingerprint: {result['skill_fingerprint']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
