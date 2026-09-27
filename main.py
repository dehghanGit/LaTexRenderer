"""LaTeXaR FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import check_latex_installation, get_settings
from renderer import (
    LaTeXCompilationError,
    SVGConversionError,
    clear_cache,
    render,
)
from schemas import (
    ErrorResponse,
    ExampleSnippet,
    ExamplesResponse,
    HealthResponse,
    RenderMetadata,
    RenderRequest,
    RenderResponse,
    RenderType,
)
from security import UnsafeLaTeXError

logger = logging.getLogger("latexar")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
    )
    logger.info("LaTeX dependencies: %s", check_latex_installation())
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="LaTeXaR",
    description="Render LaTeX to SVG — math, chemistry, circuits, and TikZ.",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(UnsafeLaTeXError)
async def _unsafe_handler(_req, exc: UnsafeLaTeXError):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error="Unsafe LaTeX input",
            detail=exc.reason,
        ).model_dump(),
    )


@app.exception_handler(LaTeXCompilationError)
async def _compile_handler(_req, exc: LaTeXCompilationError):
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error="LaTeX compilation failed",
            detail=str(exc),
            latex_log=exc.latex_log,
        ).model_dump(),
    )


@app.exception_handler(SVGConversionError)
async def _svg_handler(_req, exc: SVGConversionError):
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="SVG conversion failed",
            detail=str(exc),
        ).model_dump(),
    )


def _do_render(
    body: RenderRequest,
    override_type: RenderType | None = None,
):
    rtype = override_type or body.type
    settings = get_settings()

    if len(body.latex) > settings.max_input_length:
        raise HTTPException(status_code=400, detail="Input exceeds maximum length")

    result = render(
        latex=body.latex,
        render_type=rtype,
        display_mode=body.display_mode,
        options=body.options,
        settings=settings,
    )
    return result, rtype


def _resp(result, rtype: RenderType, raw: bool):
    if raw:
        return Response(content=result.svg, media_type="image/svg+xml")

    return RenderResponse(
        svg=result.svg,
        metadata=RenderMetadata(
            type=rtype,
            input_hash=result.input_hash,
            cached=result.cached,
            compile_time_ms=round(result.compile_time_ms, 2),
            svg_bytes=len(result.svg.encode("utf-8")),
        ),
    )


# These handlers are deliberately synchronous. FastAPI runs sync handlers in its
# thread pool, so pdflatex/dvisvgm subprocesses do not block the event loop.
@app.post("/render", response_model=RenderResponse, tags=["render"])
def render_auto(body: RenderRequest, raw: bool = Query(False)):
    result, rtype = _do_render(body)
    return _resp(result, rtype, raw)


@app.post("/render/math", response_model=RenderResponse, tags=["render"])
def render_math(body: RenderRequest, raw: bool = Query(False)):
    result, rtype = _do_render(body, override_type=RenderType.MATH)
    return _resp(result, rtype, raw)


@app.post("/render/chemistry", response_model=RenderResponse, tags=["render"])
def render_chemistry(body: RenderRequest, raw: bool = Query(False)):
    result, rtype = _do_render(body, override_type=RenderType.CHEMISTRY)
    return _resp(result, rtype, raw)


@app.post("/render/circuit", response_model=RenderResponse, tags=["render"])
def render_circuit(body: RenderRequest, raw: bool = Query(False)):
    result, rtype = _do_render(body, override_type=RenderType.CIRCUIT)
    return _resp(result, rtype, raw)


@app.post("/render/tikz", response_model=RenderResponse, tags=["render"])
def render_tikz(body: RenderRequest, raw: bool = Query(False)):
    result, rtype = _do_render(body, override_type=RenderType.TIKZ)
    return _resp(result, rtype, raw)


@app.get("/health", response_model=HealthResponse, tags=["utility"])
def health():
    settings = get_settings()
    deps = check_latex_installation()

    compiler_name = Path(settings.latex_compiler).name
    converter_name = Path(settings.svg_converter).name
    healthy = bool(deps.get(compiler_name)) and bool(deps.get(converter_name))

    return HealthResponse(
        status="ok" if healthy else "degraded",
        dependencies=deps,
    )


@app.post("/cache/clear", tags=["utility"])
def cache_clear():
    return {"cleared": clear_cache()}


@app.get("/examples", response_model=ExamplesResponse, tags=["utility"])
def examples():
    return ExamplesResponse(
        examples=[
            ExampleSnippet(
                title="Euler Identity",
                type=RenderType.MATH,
                latex=r"e^{i\pi} + 1 = 0",
                description="Euler's identity.",
            ),
            ExampleSnippet(
                title="Maxwell–Faraday Equation",
                type=RenderType.MATH,
                latex=r"\nabla \times \vec{E} = -\frac{\partial \vec{B}}{\partial t}",
                description="Differential form of Faraday's law.",
            ),
            ExampleSnippet(
                title="Benzene Ring",
                type=RenderType.CHEMISTRY,
                latex=r"\chemfig{*6(-=-=-=)}",
                description="Benzene ring rendered with chemfig.",
            ),
            ExampleSnippet(
                title="RC Circuit",
                type=RenderType.CIRCUIT,
                latex=(
                    r"\begin{circuitikz}[american]"
                    r"\draw (0,0) to[V, v=$V_s$] (0,3)"
                    r" to[R, l=$R_1$] (3,3)"
                    r" to[C, l=$C_1$] (3,0) -- (0,0);"
                    r"\end{circuitikz}"
                ),
                description="Series RC circuit.",
            ),
            ExampleSnippet(
                title="Sine Wave",
                type=RenderType.TIKZ,
                latex=(
                    r"\begin{tikzpicture}"
                    r"\begin{axis}[xlabel=$t$, ylabel=$\sin(t)$]"
                    r"\addplot[blue, domain=0:2*pi, samples=100]{sin(deg(x))};"
                    r"\end{axis}"
                    r"\end{tikzpicture}"
                ),
                description="Sine wave plot.",
            ),
        ]
    )
