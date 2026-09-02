# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SQE DailyWork Windows onedir distribution."""

from __future__ import annotations

from pathlib import Path

repo_root = Path(SPECPATH).resolve().parent
src_root = repo_root / "src"

datas = [
    (str(src_root / "ui" / "assets"), "ui/assets"),
    (str(src_root / "ncr" / "ui" / "assets"), "ncr/ui/assets"),
]
services_assets = src_root / "services" / "assets"
if services_assets.exists():
    datas.append((str(services_assets), "services/assets"))

hiddenimports = [
    "app_version",
    "app_paths",
    "build_info",
    "PySide6.QtCharts",
    "PySide6.QtSvg",
    "openpyxl",
    "reportlab",
    "PIL",
    "pptx",
    "xhtml2pdf",
    "dotenv",
    "pandas",
]

a = Analysis(
    [str(repo_root / "main.py")],
    pathex=[str(repo_root), str(src_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tests",
        "ncr.tests",
        "pytest",
        "_pytest",
        "numpy.testing",
        "pandas._testing",
        "pandas.plotting",
        "pandas.io.sql",
        "sqlalchemy",
        "psycopg2",
        "botocore",
        "matplotlib",
        "jinja2",
        "PySide6.scripts",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SQE_DailyWork",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SQE_DailyWork",
)
