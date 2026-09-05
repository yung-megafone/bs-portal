# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parents[1]
portal = root / "portal"
sys.path.insert(0, str(portal))
staticfiles = root / ".desktop_staticfiles"

hiddenimports = [
    "pystray._win32",
]
for package in (
    "apps.identity.migrations",
    "apps.departments.migrations",
    "apps.bam.migrations",
    "apps.shit.migrations",
    "apps.timeclock.migrations",
):
    hiddenimports += collect_submodules(package)

datas = [
    (str(portal / "templates"), "templates"),
    (str(portal / "static"), "static"),
    (str(staticfiles), "staticfiles"),
]
for package in (
    "apps.core",
    "apps.identity",
    "apps.departments",
    "apps.bam",
    "apps.shit",
    "apps.timeclock",
):
    datas += collect_data_files(package, includes=["templates/**/*"])

datas += collect_data_files("django.contrib.admin", includes=["templates/**/*"])
datas += collect_data_files("django.contrib.auth", includes=["templates/**/*"])

a = Analysis(
    [str(portal / "desktop.py")],
    pathex=[str(portal)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="BS-Portal",
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
