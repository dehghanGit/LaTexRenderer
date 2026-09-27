# LaTeXaR — Coolify deployment

FastAPI LaTeX → SVG renderer extracted from the supplied Colab notebook. It supports math/physics, chemistry (`chemfig`, `mhchem`), circuits (`circuitikz`), and TikZ/pgfplots.

## Coolify

### Build with GitHub Actions

The workflow in `.github/workflows/docker-build.yml` builds the existing Dockerfile on pull requests to `main`. Pushes to `main`, tags beginning with `v`, and manual runs also publish the image to GitHub Container Registry using the automatic `GITHUB_TOKEN`; no additional build secrets are required.

After committing and pushing the workflow, open the repository's **Actions** tab to see the build. The image for this repository is:

```text
ghcr.io/dehghangit/latexrenderer:latest
```

`latest` follows the default branch. Builds also receive branch/tag and `sha-…` tags so you can deploy a specific revision. The image targets Linux AMD64.

To deploy the prebuilt image in Coolify:

1. Create **New Resource → Application → Docker Image**.
2. Set the image to `ghcr.io/dehghangit/latexrenderer` and the tag to `latest` (or a specific version/SHA tag).
3. Set the application port to `8000` and health check path to `/health`.
4. Deploy, then redeploy when you want to pull a newly published image.

GitHub container packages initially default to private visibility. For unauthenticated pulls, change the package visibility to public in GitHub's package settings. Otherwise, configure Coolify's registry credentials with a GitHub username and a personal access token with `read:packages` access.

The workflow uses Docker's [GitHub Actions integration](https://docs.docker.com/build/ci/github-actions/push-multi-registries/) and GitHub's [container publishing authentication](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images).

### Build directly in Coolify

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
