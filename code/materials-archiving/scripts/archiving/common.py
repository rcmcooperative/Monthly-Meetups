"""Shared helpers: configuration, hashing and the error type shown to the user."""
from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path

VERSION = "0.1.0"

PKG_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = PKG_ROOT / "config"


class PipelineError(Exception):
    """A problem the user has to resolve. The message is printed verbatim."""


def load_toml(path: Path) -> dict:
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        raise PipelineError(f"Config file not found: {path}")
    except tomllib.TOMLDecodeError as err:
        raise PipelineError(f"Config file {path} is not valid TOML: {err}")


def load_config(config_dir: str | Path | None = None) -> dict:
    directory = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    return {
        "redaction": load_toml(directory / "redaction.toml"),
        "zoom": load_toml(directory / "zoom_schema.toml"),
        "dir": directory,
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
