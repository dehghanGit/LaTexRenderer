# LaTeXaR — Coolify deployment

FastAPI LaTeX → SVG renderer extracted from the supplied Colab notebook. It supports math/physics, chemistry (`chemfig`, `mhchem`), circuits (`circuitikz`), and TikZ/pgfplots.

## Coolify

1. Put this directory in a Git repository (GitHub/GitLab/Gitea etc.).
2. In Coolify, create **New Resource → Application → Public/Private Repository**.
3. Select **Dockerfile** as the build pack. Coolify should detect port `8000`.
4. Set the health check path to `/health` if Coolify asks for one.
5. Assign a domain only if the renderer needs to be public. If your main app is on the same Coolify/Docker network, prefer private access.
6. Deploy. No database or persistent volume is required.

Suggested limits: **1 CPU / 512 MB–1 GB RAM**. Complex TikZ/pgfplots renders may benefit from 1 GB.

### Environment variables

```env
LATEXAR_CACHE_MAX_SIZE=200
LATEXAR_COMPILE_TIMEOUT=30
LATEXAR_SHELL_ESCAPE=false
LATEXAR_MAX_INPUT_LENGTH=10000
```

### Endpoints

- `GET /health`
- `GET /docs`
- `GET /examples`
- `POST /render`
- `POST /render/math`
- `POST /render/chemistry`
- `POST /render/circuit`
- `POST /render/tikz`

Append `?raw=true` to a render endpoint to return `image/svg+xml` directly.

### Test

```bash
curl -X POST 'https://YOUR-DOMAIN/render/math?raw=true' \
  -H 'Content-Type: application/json' \
  -d '{"latex":"e^{i\\pi} + 1 = 0","type":"math","display_mode":true,"options":{}}'
```

## Security notes

The supplied implementation rejects several dangerous TeX primitives and invokes the compiler with shell escape disabled. The container also runs as a non-root user. If this endpoint is public, add authentication/rate limiting at your proxy/app layer and keep resource limits enabled. Arbitrary TeX should still be treated as untrusted input.
