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

## GitHub Actions + temporary tunnel
In repository **Settings → Secrets and variables → Actions**, add:
- `TURSO_DATABASE_URL`: your Turso database URL (usually starts with `libsql://`)
- `TURSO_AUTH_TOKEN`: your Turso auth token

Then open **Actions → PicoHub temporary public tunnel → Run workflow**. The temporary Cloudflare URL is printed in the run logs. A scheduled run is configured every six hours, but GitHub may delay schedules and runners are temporary; this is not reliable production hosting and the URL changes between runs.

## Turso
Create a database at https://turso.tech. The app creates its metadata table at startup.

## Current limitations
- Text configs are limited to 2 MiB in this starter. Truly unlimited uploads are not realistic; large/binary files should go to object storage with signed uploads and quotas.
- Submissions start as `pending_review`. Only rows marked `published` appear publicly. Add a secure moderation/admin flow before production.
- Secret masking is best-effort and is not a substitute for scanning and human review.
- Do not commit tokens or place secrets in frontend code.
- A public tunnel exposes this app to the internet. Use only for testing until rate limiting, abuse protection, and moderation are added.
