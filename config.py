"""Application configuration."""

from __future__ import annotations

import shutil
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from LATEXAR_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="LATEXAR_", extra="ignore")

    latex_compiler: str = "pdflatex"
    svg_converter: str = "dvisvgm"
    compile_timeout: int = 30
    shell_escape: bool = False
    max_input_length: int = 10_000
    temp_dir: Path = Path(tempfile.gettempdir()) / "latexar"
    cache_enabled: bool = True
    cache_max_size: int = 1_000
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


def check_latex_installation() -> dict[str, str | bool]:
    """Return paths for render dependencies that are available on PATH."""
    binaries = ("pdflatex", "xelatex", "lualatex", "dvisvgm", "pdf2svg")
    return {binary: (shutil.which(binary) or False) for binary in binaries}


