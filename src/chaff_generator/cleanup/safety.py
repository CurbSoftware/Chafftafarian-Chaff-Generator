"""Cleanup safety validation (spec sections 38-40).

Nothing is deleted until :func:`validate_run_root` is satisfied. The checks
are deliberately paranoid: a run root is only ever removed whole, only when
it provably is a chaff run, and only when it sits somewhere a chaff run may
live (never a system root or the user's home).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from chaff_generator.core.errors import CleanupSafetyError
from chaff_generator.core.paths import is_within
from chaff_generator.manifest.models import MANIFEST_FILENAME, RUN_MARKER_FILENAME

#: ``Chaff_Run_YYYYMMDD_HHMMSS_<4hex>`` (spec section 34).
RUN_ID_PATTERN = re.compile(r"^Chaff_Run_\d{8}_\d{6}_[0-9a-f]{4}$")

#: Directories cleanup must refuse no matter what they contain.
FORBIDDEN_ROOTS: tuple[Path, ...] = (
    Path("/"),
    Path("C:\\"),
    Path("C:/"),
    Path.home(),
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "Desktop",
)


def validate_run_root(run_root: Path) -> None:
    """Raise :class:`CleanupSafetyError` (listing every reason) unless
    ``run_root`` is provably a chaff run safe to remove.

    Checks: exists and is a directory; not itself a symlink; not a forbidden
    root and not containing one; basename matches the run-id pattern; marker
    present, parseable, ``chaff_run: true`` with a run_id equal to the
    directory name; manifest present with the same identity.
    """
    reasons: list[str] = []

    resolved = run_root
    try:
        resolved = run_root.resolve(strict=True)
    except OSError as exc:
        raise CleanupSafetyError(
            f"Run root does not exist: {run_root}",
            details={"reasons": [str(exc)]},
        ) from exc

    if run_root.is_symlink():
        reasons.append("run root is a symlink")
    if not resolved.is_dir():
        reasons.append("run root is not a directory")

    for forbidden in FORBIDDEN_ROOTS:
        # Windows-style roots do not exist on other platforms; a
        # nonexistent path cannot be inside the deletion target, and
        # resolving it there would produce a false positive.
        if not forbidden.exists():
            continue
        try:
            forbidden_resolved = forbidden.resolve()
        except OSError:
            continue
        # Refuse when the deletion target *is* a protected location or
        # contains one (removing it would remove the protected tree too).
        # A run merely *inside* a protected location (e.g. a run under the
        # home directory) is fine: only the run root itself is removed.
        if resolved == forbidden_resolved or is_within(forbidden_resolved, resolved):
            reasons.append(f"refusing to clean a protected location: {forbidden}")

    if not RUN_ID_PATTERN.match(resolved.name):
        reasons.append(f"directory name is not a chaff run id: {resolved.name!r}")

    reasons.extend(_marker_reasons(resolved))
    if reasons:
        listing = "; ".join(reasons)
        raise CleanupSafetyError(
            f"{run_root} is not safe to clean: {listing}",
            details={"path": str(resolved), "reasons": reasons},
        )


def _marker_reasons(resolved: Path) -> list[str]:
    marker_path = resolved / RUN_MARKER_FILENAME
    if not marker_path.is_file():
        return [f"missing run marker {RUN_MARKER_FILENAME}"]
    if marker_path.is_symlink():
        return [f"run marker {RUN_MARKER_FILENAME} is a symlink"]

    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"run marker is unreadable/corrupt: {exc}"]
    if not isinstance(marker, dict) or not marker.get("chaff_run"):
        return ["run marker lacks the chaff_run identity flag"]
    if marker.get("run_id") != resolved.name:
        return [
            f"marker run_id {marker.get('run_id')!r} does not match directory "
            f"name {resolved.name!r}"
        ]

    manifest_path = resolved / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return [f"missing manifest {MANIFEST_FILENAME}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest is unreadable/corrupt: {exc}"]
    if manifest.get("run_id") != resolved.name:
        return [
            f"manifest run_id {manifest.get('run_id')!r} does not match directory "
            f"name {resolved.name!r}"
        ]
    return []


def scan_for_symlinks(run_root: Path) -> list[Path]:
    """Symlinks inside the run root (informational; rmtree never follows them).

    Returns the offending paths so callers can warn the user — a symlink in
    the run is evidence someone tampered with the run after generation.
    """
    links: list[Path] = []
    for path in run_root.rglob("*"):
        if path.is_symlink():
            links.append(path)
    return links
