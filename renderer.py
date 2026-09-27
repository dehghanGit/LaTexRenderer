"""Core LaTeX-to-SVG rendering engine."""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import subprocess
import tempfile
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from config import Settings, get_settings
from schemas import RenderOptions, RenderType
from security import sanitise
from templates import build_document

logger = logging.getLogger("latexar.renderer")


@dataclass(frozen=True, slots=True)
class RenderResult:
    svg: str
    input_hash: str
    compile_time_ms: float
    cached: bool


class _SVGCache:
    """Small thread-safe LRU cache for rendered SVG strings."""

    def __init__(self, max_size: int = 1_000):
        self._max_size = max(1, max_size)
        self._data: OrderedDict[str, str] = OrderedDict()
        self._lock = RLock()

    def configure(self, max_size: int) -> None:
        with self._lock:
            self._max_size = max(1, max_size)
            while len(self._data) > self._max_size:
                self._data.popitem(last=False)

    def get(self, key: str) -> str | None:
        with self._lock:
            value = self._data.get(key)
            if value is not None:
                self._data.move_to_end(key)
            return value

    def put(self, key: str, value: str) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._max_size:
                self._data.popitem(last=False)

    def clear(self) -> int:
        with self._lock:
            count = len(self._data)
            self._data.clear()
            return count


_cache = _SVGCache()


def render(
    latex: str,
    render_type: RenderType = RenderType.MATH,
    *,
    display_mode: bool = True,
    options: RenderOptions | None = None,
    settings: Settings | None = None,
) -> RenderResult:
    settings = settings or get_settings()
    options = options or RenderOptions()

    # RAW still gets the same dangerous-primitive checks. It only bypasses the
    # automatic document wrapper, not the API's security boundary.
    sanitise(latex)

    _cache.configure(settings.cache_max_size)
    cache_key = _hash_input(latex, render_type, display_mode, options)

    if settings.cache_enabled:
        cached_svg = _cache.get(cache_key)
        if cached_svg is not None:
            return RenderResult(
                svg=cached_svg,
                input_hash=cache_key,
                compile_time_ms=0.0,
                cached=True,
            )

    document = build_document(
        latex,
        render_type,
        display_mode=display_mode,
        options=options,
    )

    started = time.perf_counter()
    svg = _compile_and_convert(document, settings)
    elapsed_ms = (time.perf_counter() - started) * 1_000

    if options.scale != 1.0:
        svg = _scale_svg_dimensions(svg, options.scale)

    if settings.cache_enabled:
        _cache.put(cache_key, svg)

    return RenderResult(
        svg=svg,
        input_hash=cache_key,
        compile_time_ms=elapsed_ms,
        cached=False,
    )


def clear_cache() -> int:
    return _cache.clear()


def _hash_input(
    latex: str,
    render_type: RenderType,
    display_mode: bool,
    options: RenderOptions,
) -> str:
    blob = (
        f"{render_type.value}|{display_mode}|"
        f"{options.model_dump_json()}|{latex}"
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _compile_and_convert(document: str, settings: Settings) -> str:
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="job-", dir=settings.temp_dir))
    tex_path = work_dir / "input.tex"
    pdf_path = work_dir / "input.pdf"
    svg_path = work_dir / "input.svg"

    try:
        tex_path.write_text(document, encoding="utf-8")

        compiler = settings.latex_compiler
        compile_cmd = [
            compiler,
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            "-output-directory",
            str(work_dir),
            "-shell-escape" if settings.shell_escape else "-no-shell-escape",
            str(tex_path),
        ]

        try:
            result = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=settings.compile_timeout,
                cwd=str(work_dir),
                check=False,
            )
        except FileNotFoundError as exc:
            raise LaTeXCompilationError(
                f"LaTeX compiler '{compiler}' was not found on PATH",
                latex_log=None,
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise LaTeXCompilationError(
                f"LaTeX compilation timed out after {settings.compile_timeout}s",
                latex_log=None,
            ) from exc

        if result.returncode != 0 or not pdf_path.exists():
            log_text = _extract_error(work_dir / "input.log")
            fallback = (result.stderr or result.stdout)[-2_000:]
            raise LaTeXCompilationError(
                f"{Path(compiler).name} exited with code {result.returncode}",
                latex_log=log_text or fallback or None,
            )

        return _pdf_to_svg(pdf_path, svg_path, settings)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _pdf_to_svg(pdf_path: Path, svg_path: Path, settings: Settings) -> str:
    converter = settings.svg_converter

    if Path(converter).name == "dvisvgm":
        cmd = [
            converter,
            "--pdf",
            "--no-fonts",
            "--exact-bbox",
            "--stdout",
            str(pdf_path),
        ]
        output_to_stdout = True
    elif Path(converter).name == "pdf2svg":
        cmd = [converter, str(pdf_path), str(svg_path)]
        output_to_stdout = False
    else:
        raise SVGConversionError(f"Unknown SVG converter: {converter}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.compile_timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SVGConversionError(
            f"SVG converter '{converter}' was not found on PATH"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SVGConversionError(
            f"SVG conversion timed out after {settings.compile_timeout}s"
        ) from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[-1_000:]
        raise SVGConversionError(
            f"{Path(converter).name} exited with code {result.returncode}: {detail}"
        )

    svg = result.stdout if output_to_stdout else svg_path.read_text(encoding="utf-8")
    if "<svg" not in svg:
        raise SVGConversionError("Converter returned no SVG document")
    return svg


def _extract_error(log_path: Path) -> str | None:
    if not log_path.exists():
        return None

    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    for index, line in enumerate(lines):
        if line.startswith("!") or ": error:" in line.lower():
            return "\n".join(lines[index : index + 16])

    return "\n".join(lines[-20:]) if lines else None


def _scale_svg_dimensions(svg: str, scale: float) -> str:
    """Scale rendered display size without changing/cropping the SVG viewBox."""
    match = re.search(r"<svg\b[^>]*>", svg, flags=re.IGNORECASE)
    if not match:
        return svg

    header = match.group(0)
    dimension_pattern = re.compile(
        r"""(\b(?:width|height)=["'])([0-9]*\.?[0-9]+)([A-Za-z%]*)(["'])""",
        flags=re.IGNORECASE,
    )

    def repl(m: re.Match[str]) -> str:
        value = float(m.group(2)) * scale
        formatted = f"{value:.6f}".rstrip("0").rstrip(".")
        return f"{m.group(1)}{formatted}{m.group(3)}{m.group(4)}"

    scaled_header = dimension_pattern.sub(repl, header)
    return svg[: match.start()] + scaled_header + svg[match.end() :]


class LaTeXCompilationError(Exception):
    def __init__(self, message: str, *, latex_log: str | None = None):
        self.latex_log = latex_log
        super().__init__(message)


class SVGConversionError(Exception):
    pass


