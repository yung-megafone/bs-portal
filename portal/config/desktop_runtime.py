"""Runtime configuration helpers for the packaged Windows desktop build.

The installer stores machine-local secrets in ProgramData with Windows DPAPI
(LocalMachine scope). The desktop executable decrypts them at startup and
exports the same environment variables used by the normal Django settings.
"""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys


class RuntimeConfigurationError(RuntimeError):
    pass


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def default_data_dir() -> Path:
    configured = os.environ.get("BS_PORTAL_DATA_DIR")
    if configured:
        return Path(configured)

    program_data = os.environ.get("PROGRAMDATA")
    if not program_data:
        raise RuntimeConfigurationError("PROGRAMDATA is not available on this system.")
    return Path(program_data) / "B.S. Supply Co" / "B.S. Portal"


def runtime_config_path() -> Path:
    configured = os.environ.get("BS_PORTAL_RUNTIME_CONFIG")
    if configured:
        return Path(configured)
    return default_data_dir() / "runtime.json"


def _dpapi_unprotect(encoded: str) -> str:
    if sys.platform != "win32":
        raise RuntimeConfigurationError("DPAPI runtime configuration is Windows-only.")

    try:
        encrypted = base64.b64decode(encoded, validate=True)
    except Exception as exc:  # pragma: no cover - defensive runtime failure
        raise RuntimeConfigurationError("A DPAPI value in runtime.json is invalid.") from exc

    if not encrypted:
        return ""

    buffer = ctypes.create_string_buffer(encrypted)
    in_blob = DATA_BLOB(
        len(encrypted),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    out_blob = DATA_BLOB()

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()

    try:
        clear = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return clear.decode("utf-8")
    finally:
        kernel32.LocalFree(out_blob.pbData)


def load_runtime_config(path: Path | None = None) -> dict:
    path = path or runtime_config_path()
    if not path.exists():
        raise RuntimeConfigurationError(
            f"B.S. Portal runtime configuration is missing: {path}. "
            "Run the B.S. Portal installer/repair operation."
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise RuntimeConfigurationError(f"Could not read {path}: {exc}") from exc

    for section in ("database", "mysql", "server"):
        if not isinstance(data.get(section), dict):
            raise RuntimeConfigurationError(f"runtime.json is missing the '{section}' section.")

    return data


def configure_environment(config: dict | None = None) -> dict:
    config = config or load_runtime_config()
    database = config["database"]

    required = {
        "name": "MYSQL_DATABASE",
        "user": "MYSQL_USER",
        "host": "MYSQL_HOST",
        "port": "MYSQL_PORT",
    }
    for key, env_name in required.items():
        value = database.get(key)
        if value in (None, ""):
            raise RuntimeConfigurationError(f"runtime.json database.{key} is required.")
        os.environ[env_name] = str(value)

    encrypted_password = database.get("password_dpapi")
    encrypted_secret = config.get("django_secret_dpapi")
    if not encrypted_password or not encrypted_secret:
        raise RuntimeConfigurationError("runtime.json is missing protected application secrets.")

    os.environ["MYSQL_PASSWORD"] = _dpapi_unprotect(encrypted_password)
    os.environ["DJANGO_SECRET_KEY"] = _dpapi_unprotect(encrypted_secret)

    data_dir = default_data_dir()
    os.environ.setdefault("BS_PORTAL_DATA_DIR", str(data_dir))
    os.environ.setdefault("BAM_MEDIA_ROOT", str(data_dir / "media"))
    os.environ.setdefault("BS_PORTAL_BUILD_ID", str(config.get("build_id", "")).strip())

    return config
