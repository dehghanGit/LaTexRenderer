"""LaTeX document templates."""

from __future__ import annotations

from collections.abc import Iterable

from schemas import RenderOptions, RenderType

PackageSpec = str | tuple[str, str]


def _font_size_cmd(pt: int) -> str:
    baseline = max(pt + 2, round(pt * 1.2))
    return f"\\fontsize{{{pt}}}{{{baseline}}}\\selectfont"


def _package_lines(packages: Iterable[PackageSpec]) -> list[str]:
    lines: list[str] = []
    for package in packages:
        if isinstance(package, tuple):
            name, package_options = package
            lines.append(f"\\usepackage[{package_options}]{{{name}}}")
        else:
            lines.append(f"\\usepackage{{{package}}}")
    return lines


def _document(
    body: str,
    *,
    options: RenderOptions,
    packages: Iterable[PackageSpec],
    border_pt: int,
    preamble_lines: Iterable[str] = (),
) -> str:
    """Build a cropped standalone document around an already-prepared body."""
    foreground = options.foreground.removeprefix("#")
    lines = [
        f"\\documentclass[border={border_pt}pt]{{standalone}}",
        *_package_lines(packages),
        "\\usepackage{xcolor}",
        *_package_lines(options.extra_packages),
        *preamble_lines,
        "\\begin{document}",
        _font_size_cmd(options.font_size),
        f"\\color[HTML]{{{foreground}}}",
    ]

    if options.background != "transparent":
        background = options.background.removeprefix("#")
        lines.append(f"\\pagecolor[HTML]{{{background}}}")

    lines.extend((body, "\\end{document}"))
    return "\n".join(lines)


def build_document(
    latex: str,
    render_type: RenderType,
    *,
    display_mode: bool = True,
    options: RenderOptions | None = None,
) -> str:
    opts = options or RenderOptions()
    builders = {
        RenderType.MATH: _math_doc,
        RenderType.CHEMISTRY: _chem_doc,
        RenderType.CIRCUIT: _circuit_doc,
        RenderType.TIKZ: _tikz_doc,
        RenderType.RAW: _raw_doc,
    }
    return builders[render_type](latex, display_mode=display_mode, options=opts)


def _math_doc(latex: str, *, display_mode: bool, options: RenderOptions) -> str:
    # `standalone` typesets its content in a box, where display-math
    # environments (equation*, \[...\], etc.) are not valid. Inline math plus
    # \displaystyle preserves display-style fractions/sums without leaving the
    # horizontal box.
    style = "\\displaystyle " if display_mode else ""
    body = f"\\({style}{latex}\\)"
    return _document(
        body,
        options=options,
        packages=("amsmath", "amssymb", "mathtools", "siunitx"),
        border_pt=2,
    )


def _chem_doc(latex: str, *, display_mode: bool, options: RenderOptions) -> str:
    del display_mode
    return _document(
        latex,
        options=options,
        packages=("chemfig", ("mhchem", "version=4"), "amsmath", "amssymb"),
        border_pt=5,
    )


def _circuit_doc(latex: str, *, display_mode: bool, options: RenderOptions) -> str:
    del display_mode
    return _document(
        latex,
        options=options,
        packages=(("circuitikz", "siunitx"), "amsmath", "amssymb"),
        border_pt=5,
    )


def _tikz_doc(latex: str, *, display_mode: bool, options: RenderOptions) -> str:
    del display_mode
    return _document(
        latex,
        options=options,
        packages=("tikz", "pgfplots", "amsmath", "amssymb"),
        border_pt=5,
        preamble_lines=(
            "\\pgfplotsset{compat=1.18}",
            "\\usetikzlibrary{arrows.meta,calc,positioning,"
            "decorations.pathmorphing,shapes.geometric}",
        ),
    )


def _raw_doc(latex: str, *, display_mode: bool, options: RenderOptions) -> str:
    del display_mode, options
    return latex


