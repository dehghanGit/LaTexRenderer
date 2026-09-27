"""Pydantic models used by the API."""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_PACKAGE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class RenderType(str, Enum):
    MATH = "math"
    CHEMISTRY = "chemistry"
    CIRCUIT = "circuit"
    TIKZ = "tikz"
    RAW = "raw"


class RenderOptions(BaseModel):
    font_size: int = Field(default=12, ge=6, le=72)
    foreground: str = Field(default="#000000")
    background: str = Field(default="transparent")
    scale: float = Field(default=1.0, gt=0, le=5.0)
    extra_packages: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("foreground")
    @classmethod
    def validate_foreground(cls, value: str) -> str:
        if not _HEX_COLOR.fullmatch(value):
            raise ValueError("foreground must be a #RRGGBB color")
        return value.upper()

    @field_validator("background")
    @classmethod
    def validate_background(cls, value: str) -> str:
        if value.lower() == "transparent":
            return "transparent"
        if not _HEX_COLOR.fullmatch(value):
            raise ValueError("background must be 'transparent' or a #RRGGBB color")
        return value.upper()

    @field_validator("extra_packages")
    @classmethod
    def validate_extra_packages(cls, packages: list[str]) -> list[str]:
        invalid = [package for package in packages if not _PACKAGE_NAME.fullmatch(package)]
        if invalid:
            raise ValueError(f"invalid LaTeX package name(s): {', '.join(invalid)}")
        # Preserve request order while avoiding duplicate \usepackage lines.
        return list(dict.fromkeys(packages))


class RenderRequest(BaseModel):
    latex: str = Field(..., min_length=1, max_length=10_000)
    type: RenderType = Field(default=RenderType.MATH)
    display_mode: bool = Field(default=True)
    options: RenderOptions = Field(default_factory=RenderOptions)


class RenderMetadata(BaseModel):
    type: RenderType
    input_hash: str
    cached: bool = False
    compile_time_ms: float
    svg_bytes: int


class RenderResponse(BaseModel):
    svg: str
    metadata: RenderMetadata


class HealthResponse(BaseModel):
    status: str = "ok"
    dependencies: dict[str, str | bool] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    latex_log: Optional[str] = None


class ExampleSnippet(BaseModel):
    title: str
    type: RenderType
    latex: str
    description: str


class ExamplesResponse(BaseModel):
    examples: list[ExampleSnippet]


