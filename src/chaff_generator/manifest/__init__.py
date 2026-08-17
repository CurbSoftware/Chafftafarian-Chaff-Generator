"""Manifest, journal, verification, and run discovery (spec sections 34-38)."""

from chaff_generator.manifest.models import (
    JOURNAL_FILENAME,
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
    RUN_MARKER_FILENAME,
    ChaffManifest,
    FileRecord,
    RunMarker,
)
from chaff_generator.manifest.reader import (
    RunInfo,
    discover_runs,
    journal_files,
    manifest_for_run,
    read_journal,
    read_manifest,
)
from chaff_generator.manifest.verifier import (
    FileVerdict,
    VerificationEngine,
    VerificationMode,
    VerificationReport,
    verify_run,
)
from chaff_generator.manifest.writer import (
    JournalWriter,
    new_manifest,
    write_manifest,
    write_run_marker,
)

__all__ = [
    "JOURNAL_FILENAME",
    "MANIFEST_FILENAME",
    "MANIFEST_SCHEMA_VERSION",
    "RUN_MARKER_FILENAME",
    "ChaffManifest",
    "FileRecord",
    "FileVerdict",
    "JournalWriter",
    "RunInfo",
    "RunMarker",
    "VerificationEngine",
    "VerificationMode",
    "VerificationReport",
    "discover_runs",
    "journal_files",
    "manifest_for_run",
    "new_manifest",
    "read_journal",
    "read_manifest",
    "verify_run",
    "write_manifest",
    "write_run_marker",
]
