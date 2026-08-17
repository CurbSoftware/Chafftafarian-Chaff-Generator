# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Chaff Generator CLI (spec section 81).
#
# Build (from the repository root, inside the project venv):
#   pyinstaller packaging/chaff-cli.spec
#
# Console build: no Qt — the GUI-free core plus the Typer CLI.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

project_root = Path(SPECPATH).resolve().parent

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

datas = [
    (str(project_root / "src" / "chaff_generator" / "data"), "chaff_generator"),
]
datas += collect_data_files("chaff_generator")

a = Analysis(
    [str(project_root / "packaging" / "entry_cli.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["PySide6", "tkinter"],  # the CLI never touches Qt
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="chaff",
    debug=False,
    console=True,
)
