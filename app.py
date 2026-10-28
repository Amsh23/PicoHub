import os, json, re, secrets, hashlib
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
import libsql

app = FastAPI(title="PicoHub")
BASE = Path(__file__).parent
MAX_METADATA_BYTES = 2 * 1024 * 1024
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()


def db():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        raise HTTPException(503, "Database is not configured. Add TURSO_DATABASE_URL and TURSO_AUTH_TOKEN.")
    try:
        return libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    except Exception as exc:
        raise HTTPException(503, f"Could not connect to the database: {type(exc).__name__}") from exc


def rows_as_dicts(cursor):
    columns = [column[0] for column in (cursor.description or [])]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@app.on_event("startup")
async def startup():
    if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
        client = db()
        try:
            client.execute("""CREATE TABLE IF NOT EXISTS configs (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]',
                content TEXT NOT NULL, content_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending_review'
            )""")
            client.commit()
        finally:
            client.close()


@app.get("/", response_class=HTMLResponse)
async def home():
    return (BASE / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
async def health():
    return {"ok": True, "database_configured": bool(TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)}


def redact_secrets(s: str) -> str:
    s = re.sub(r'(?i)("(?:api[_-]?key|token|bot_token|password|secret|authorization)"\s*:\s*")[^"]*(")', r'\1[REDACTED]\2', s)
    s = re.sub(r'\b(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|[0-9]{7,12}:[A-Za-z0-9_-]{25,})\b', '[REDACTED_SECRET]', s)
    return s


@app.post("/api/configs")
async def submit_config(title: str = Form(...), category: str = Form(...),
                        description: str = Form(""), tags: str = Form(""),
                        content: str = Form(""), file: UploadFile | None = File(None)):
    if file:
        raw = await file.read()
        if len(raw) > MAX_METADATA_BYTES:
            raise HTTPException(413, "Config text is too large. Use external object storage for large files.")
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(415, "Only UTF-8 text configs are supported in this starter.")
    if not content.strip():
        raise HTTPException(400, "Upload a config or paste its contents.")
    clean = redact_secrets(content)
    if len(clean.encode("utf-8")) > MAX_METADATA_BYTES:
        raise HTTPException(413, "Config text is too large.")
    config_id = secrets.token_urlsafe(9)
    created = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(clean.encode()).hexdigest()
    client = db()
    try:
        client.execute(
            "INSERT INTO configs (id,title,category,description,tags,content,content_sha256,created_at,status) VALUES (?,?,?,?,?,?,?,?,?)",
            (config_id, title[:180], category[:100], description[:1500],
             json.dumps([x.strip() for x in tags.split(",") if x.strip()][:30]),
             clean, digest, created, "pending_review"))
        client.commit()
    finally:
        client.close()
    return {"ok": True, "id": config_id, "status": "pending_review",
            "note": "Secret masking is best-effort. Review before publishing."}


@app.get("/api/configs")
async def list_configs(limit: int = 30):
    limit = max(1, min(limit, 100))
    client = db()
    try:
        cursor = client.execute(
            "SELECT id,title,category,description,tags,content_sha256,created_at,status FROM configs WHERE status='published' ORDER BY created_at DESC LIMIT ?",
            (limit,))
        return {"items": rows_as_dicts(cursor)}
    finally:
        client.close()


@app.get("/api/configs/{config_id}")
async def get_config(config_id: str):
    client = db()
    try:
        cursor = client.execute(
            "SELECT id,title,category,description,tags,content,content_sha256,created_at,status FROM configs WHERE id=? AND status='published'",
            (config_id,))
        rows = rows_as_dicts(cursor)
        if not rows:
            raise HTTPException(404, "Config not found")
        return rows[0]
    finally:
        client.close()
