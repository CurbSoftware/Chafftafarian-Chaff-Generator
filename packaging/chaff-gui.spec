# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Chaff Generator desktop app (spec section 81).
#
# Build (from the repository root, inside the project venv):
#   pyinstaller packaging/chaff-gui.spec
#
# The bundle ships the built-in ChaffBank pack, templates, and every
# renderer's dependencies; users need neither Python nor an office suite.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

project_root = Path(SPECPATH).resolve().parent

# Renderers are imported lazily via importlib from a string table, so
# static analysis cannot see them — name every module explicitly.
hiddenimports = [
    "chaff_generator.renderers." + name
    for name in (
        "base",
        "text",
        "markdown",
        "html",
        "csv",
        "json",
        "xml",
        "email",
        "docx",
        "pdf",
        "xlsx",
        "pptx",
        "calendar",
        "contact",
        "payload",
        "devfile",
        "documents",
        "textutil",
    )
]
hiddenimports += collect_submodules("chaff_generator.gui")

datas = [
    # The default ChaffBank pack: banks, templates, profiles.
    (str(project_root / "src" / "chaff_generator" / "data"), "chaff_generator"),
]
datas += collect_data_files("chaff_generator")

a = Analysis(
    [str(project_root / "packaging" / "entry_gui.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ChaffGenerator",
    debug=False,
    console=False,  # windowed application
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ChaffGenerator",
)
