FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LATEXAR_HOST=0.0.0.0 \
    LATEXAR_PORT=8000 \
    LATEXAR_CACHE_MAX_SIZE=200 \
    LATEXAR_COMPILE_TIMEOUT=30 \
    LATEXAR_SHELL_ESCAPE=false

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-science \
    texlive-pictures \
    texlive-fonts-recommended \
    dvisvgm \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 latexar
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY --chown=latexar:latexar . .
USER latexar
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
