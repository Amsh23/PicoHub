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

## GitHub Actions + Cloudflare Quick Tunnel

**Live URL:** [https://spending-art-packaging-temporal.trycloudflare.com](https://spending-art-packaging-temporal.trycloudflare.com)

In repository **Settings → Secrets and variables → Actions**, configure these repository secrets:
- `TURSO_DATABASE_URL`: your Turso database URL (usually starts with `libsql://`)
- `TURSO_AUTH_TOKEN`: your Turso auth token

Open **Actions → PicoHub Cloudflare Quick Tunnel → Run workflow** to start it manually. The workflow exposes port 8080 through Cloudflare Quick Tunnel and updates this README only after the public URL passes the app's `/api/health` check. A scheduled run is configured every six hours. No Localet token or Cloudflare account is required. Quick Tunnel URLs are temporary and change when a new tunnel starts; GitHub-hosted runners are temporary, so this is not guaranteed 24/7 hosting. Quick Tunnels are intended for testing/development rather than production. See the [official Cloudflare Quick Tunnel documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

## Turso
Create a database at https://turso.tech. The app creates its metadata table at startup.

## Current limitations
- Text configs are limited to 2 MiB in this starter. Truly unlimited uploads are not realistic; large/binary files should go to object storage with signed uploads and quotas.
- Submissions start as `pending_review`. Only rows marked `published` appear publicly. Add a secure moderation/admin flow before production.
- Secret masking is best-effort and is not a substitute for scanning and human review.
- Do not commit tokens or place secrets in frontend code.
- A public tunnel exposes this app to the internet. Use only for testing until rate limiting, abuse protection, and moderation are added.
