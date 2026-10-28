# PicoHub — PicoClaw Community

Persian-first starter for sharing PicoClaw configuration snippets.

## Run locally
```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```
Open http://127.0.0.1:8000

## GitHub Actions + Localet tunnel

**Live URL:** Not available until the Localet workflow successfully starts. The workflow updates this line automatically after detecting the public URL.

In repository **Settings → Secrets and variables → Actions**, configure these repository secrets:
- `loacalet_token`: Localet client token (the secret name is intentionally the exact spelling used in this repository)
- `TURSO_DATABASE_URL`: your Turso database URL (usually starts with `libsql://`)
- `TURSO_AUTH_TOKEN`: your Turso auth token

Open **Actions → PicoHub Localet tunnel → Run workflow** to start it manually. The workflow uses Localet on port 8080 and updates this README with the public URL once it detects it. A scheduled run is configured every six hours. GitHub-hosted runners are temporary and impose execution limits, so this is not guaranteed 24/7 hosting; the tunnel may briefly disconnect and its URL may change between runs.

## Turso
Create a database at https://turso.tech. The app creates its metadata table at startup.

## Current limitations
- Text configs are limited to 2 MiB in this starter. Truly unlimited uploads are not realistic; large/binary files should go to object storage with signed uploads and quotas.
- Submissions start as `pending_review`. Only rows marked `published` appear publicly. Add a secure moderation/admin flow before production.
- Secret masking is best-effort and is not a substitute for scanning and human review.
- Do not commit tokens or place secrets in frontend code.
- A public tunnel exposes this app to the internet. Use only for testing until rate limiting, abuse protection, and moderation are added.
