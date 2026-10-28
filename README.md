# PicoHub — PicoClaw Config Community

**A bilingual (فارسی / English) community library for discovering, sharing, and downloading PicoClaw configs.**

## Live service / سرویس آنلاین

**Live URL:** _Waiting for the next externally verified tunnel URL._

**Tunnel:** _Localet primary; Cloudflare fallback only when needed._

## Features / امکانات

- **فارسی و انگلیسی** — switch languages from the header; the layout changes between RTL and LTR.
- **Instant public publishing** — submissions become visible in the library immediately, without a moderation queue.
- **No fixed app-level upload-size cap** — text configs of different sizes can be submitted. The database, HTTP request, runner memory and network may still impose practical limits; this is not mathematically unlimited storage.
- **Search, categories, tags, paging, file download and copy**.
- **Best-effort secret masking** for common token/key patterns before publishing. This is not a guarantee; never submit real credentials.
- SQLite/libSQL/Turso-backed persistent metadata and config content.

## Tunnel setup / راه‌اندازی تونل

The **PicoHub Localet tunnel** workflow tries Localet first. If the Localet server is unreachable from the GitHub-hosted runner, it falls back to a Cloudflare Quick Tunnel after verifying the public `/api/health` endpoint. The README URL is only set from a URL that passes that health check.

In **Settings → Secrets and variables → Actions**, set these repository secrets:

- `loacalet_token` — your Localet token (this exact name matches the existing repository secret).
- `TURSO_DATABASE_URL` — the Turso/libSQL database URL.
- `TURSO_AUTH_TOKEN` — the Turso auth token.
- `LOCALET_SUBDOMAIN` — optional. Put the subdomain/hostname reserved in your Localet account if your installed Localet client supports a subdomain/domain argument. If the account reserves the hostname through its dashboard/token instead, configure it there as well.

To start manually, open **Actions → PicoHub Localet tunnel → Run workflow**. A scheduled restart is configured every six hours. GitHub-hosted runners are temporary; a tunnel on Actions is not guaranteed 24/7. The fallback `trycloudflare.com` URL is temporary and changes when recreated. For a permanent Localet hostname, the subdomain must actually be reserved/active in your Localet account, and Localet must be reachable from the runner.

## Run locally / اجرای محلی

```bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Open http://127.0.0.1:8000

## Database / دیتابیس

Create a database at https://turso.tech. The app creates the `configs` table and applies simple schema migrations at startup. Configs are saved as text; non-UTF-8/binary uploads are rejected.

## Important notes / نکات مهم

- Configs are published immediately. They are public to anyone with access to the site; do not upload passwords, API keys, personal data, private configuration, or confidential material.
- Secret masking is best-effort and cannot detect every credential pattern.
- There is no hard-coded 2 MiB limit in the app anymore, but the storage provider and infrastructure still have limits. Truly unbounded files require an object-storage backend with streaming uploads and appropriate quotas.
- GitHub Actions + tunnels are best suited to demos/testing. For a stable production site, run the app on always-on hosting and use a named/persistent tunnel or a managed hostname.
- PicoHub is an independent community project and is not officially affiliated with the PicoClaw team.
