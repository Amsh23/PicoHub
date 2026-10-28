import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import libsql
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, Response

app = FastAPI(title="PicoHub", version="2.0.0")
BASE = Path(__file__).parent
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL", "").strip()
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()

SECRET_KEY_NAMES = (
    r"api[_-]?key|access[_-]?token|auth[_-]?token|bot[_-]?token|"
    r"client[_-]?secret|password|passwd|secret|authorization|"
    r"private[_-]?key|refresh[_-]?token|bearer"
)

CATEGORY_ALIASES = {
    "channels": ("messaging", "telegram", "discord", "whatsapp", "تلگرام و پیام‌رسان‌ها", "پیام‌رسان‌ها"),
    "providers": ("provider", "providers", "model", "models", "llm", "مدل‌ها و Providerها", "مدل‌ها و فراهم‌کننده‌ها"),
    "tools": ("tool", "mcp", "tools & mcp", "ابزارها", "ابزارها و اتصال‌ها", "ابزارها و اتصال ها"),
    "automation": ("scheduling", "scheduler", "automation & scheduling", "اتوماسیون و زمان‌بندی", "اتوماسیون و زمانبندی"),
    "workflows": ("workflow", "recipe", "recipes", "workflows", "جریان‌های کاری", "گردش‌کارها"),
    "skills": ("skill", "prompt", "prompts", "مهارت‌ها", "پرامپت‌ها"),
    "memory": ("knowledge", "rag", "حافظه و دانش", "حافظه"),
    "voice": ("audio", "speech", "realtime", "صدا و گفتار", "صوت و گفتار"),
    "android": ("termux", "mobile", "اندروید و Termux", "اندروید و ترموکس"),
    "integrations": ("api", "apis", "integration", "connections", "connectors", "سرویس‌ها و اتصال‌ها", "اتصال‌ها و APIها"),
    "security": ("privacy", "secrets", "امنیت و حریم خصوصی", "امنیت"),
    "templates": ("starter", "starter template", "starter templates", "قالب‌های شروع", "قالب شروع"),
    "productivity": ("agent", "agents", "productivity & agents", "بهره‌وری و دستیارها", "دستیارها و بهره‌وری"),
    "other": ("misc", "miscellaneous", "سایر", "سایر موارد"),
}
CATEGORY_LOOKUP = {
    alias.strip().casefold(): canonical
    for canonical, aliases in CATEGORY_ALIASES.items()
    for alias in (canonical, *aliases)
}


def canonical_category(value: str) -> str:
    key = re.sub(r"\s+", " ", str(value or "").strip()).casefold()
    return CATEGORY_LOOKUP.get(key, "other")



def db():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        raise HTTPException(503, "Database is not configured. Add TURSO_DATABASE_URL and TURSO_AUTH_TOKEN.")
    try:
        return libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    except Exception as exc:
        raise HTTPException(503, f"Database connection failed: {type(exc).__name__}") from exc


def rows_as_dicts(cursor):
    columns = [column[0] for column in (cursor.description or [])]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@app.on_event("startup")
async def startup():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        return
    client = db()
    try:
        client.execute("""CREATE TABLE IF NOT EXISTS configs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '[]',
            content TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'published',
            file_name TEXT NOT NULL DEFAULT '',
            mime_type TEXT NOT NULL DEFAULT 'text/plain'
        )""")
        columns = {
            row[1] for row in client.execute("PRAGMA table_info(configs)").fetchall()
        }
        # Safe migrations for databases created by an earlier PicoHub version.
        if "file_name" not in columns:
            client.execute("ALTER TABLE configs ADD COLUMN file_name TEXT NOT NULL DEFAULT ''")
        if "mime_type" not in columns:
            client.execute("ALTER TABLE configs ADD COLUMN mime_type TEXT NOT NULL DEFAULT 'text/plain'")
        client.commit()
    finally:
        client.close()


@app.get("/", response_class=HTMLResponse)
async def home():
    return (BASE / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
async def health():
    client = db()
    try:
        client.execute("SELECT 1").fetchone()
        return {"ok": True, "database_configured": True, "database_reachable": True}
    except Exception as exc:
        raise HTTPException(503, f"Database health check failed: {type(exc).__name__}") from exc
    finally:
        client.close()


def redact_secrets(text: str) -> str:
    """Best-effort masking for common config secret fields before instant publishing."""
    quoted_value = re.compile(
        rf'(?i)(["\']?(?:{SECRET_KEY_NAMES})["\']?\s*[:=]\s*)(["\'])(.*?)(\2)'
    )
    text = quoted_value.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]" + m.group(4), text)

    # YAML / .env / INI-style unquoted assignments.
    unquoted_value = re.compile(
        rf'(?im)^(\s*(?:{SECRET_KEY_NAMES})\s*[:=]\s*)(?!["\']?\[REDACTED)([^\s"\'#;,}}\]]+)'
    )
    text = unquoted_value.sub(lambda m: m.group(1) + "[REDACTED]", text)

    text = re.sub(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "[REDACTED_PRIVATE_KEY]",
        text,
    )
    text = re.sub(
        r"\b(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[A-Z0-9]{16}|AIza[0-9A-Za-z_-]{30,}|[0-9]{7,12}:[A-Za-z0-9_-]{25,})\b",
        "[REDACTED_SECRET]",
        text,
    )
    return text


def safe_file_name(name: str) -> str:
    name = (name or "config.txt").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._() -]", "_", name).strip(" .")
    return (name or "config.txt")[:180]


@app.post("/api/configs")
async def submit_config(
    title: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    tags: str = Form(""),
    content: str = Form(""),
    file: UploadFile | None = File(None),
):
    file_name = ""
    mime_type = "text/plain; charset=utf-8"

    if file is not None and file.filename:
        file_name = safe_file_name(file.filename)
        mime_type = (file.content_type or "text/plain").split(";")[0][:120]
        raw = await file.read()
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                415,
                "This library stores text-based configs. Convert binary files to a text config or archive before uploading.",
            ) from exc
    else:
        file_name = safe_file_name((title.strip() or "config") + ".txt")

    if not content.strip():
        raise HTTPException(400, "Choose a file or paste the configuration content.")
    if not title.strip():
        raise HTTPException(400, "A title is required.")
    if not category.strip():
        raise HTTPException(400, "A category is required.")

    clean = redact_secrets(content)
    config_id = secrets.token_urlsafe(9)
    created = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()
    client = db()
    try:
        client.execute(
            """INSERT INTO configs
               (id,title,category,description,tags,content,content_sha256,created_at,status,file_name,mime_type)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                config_id,
                title.strip()[:180],
                canonical_category(category),
                description.strip()[:1500],
                json.dumps([x.strip() for x in tags.split(",") if x.strip()][:30], ensure_ascii=False),
                clean,
                digest,
                created,
                "published",
                file_name,
                mime_type,
            ),
        )
        client.commit()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            503,
            f"Could not save this config to the database: {type(exc).__name__}. The storage provider may impose a request or row-size limit.",
        ) from exc
    finally:
        client.close()

    return {
        "ok": True,
        "id": config_id,
        "status": "published",
        "file_name": file_name,
        "content_sha256": digest,
        "note": "Published immediately. Common secret patterns were masked automatically, but secret detection is not guaranteed.",
    }


@app.get("/api/configs")
async def list_configs(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str = Query("", max_length=200),
    category: str = Query("", max_length=100),
    sort: str = Query("newest", max_length=20),
):
    if sort not in {"newest", "oldest", "title"}:
        raise HTTPException(400, "Unsupported sort order.")
    terms = ["status='published'"]
    params: list[object] = []
    if q.strip():
        terms.append("(title LIKE ? OR description LIKE ? OR tags LIKE ? OR content LIKE ?)")
        pattern = f"%{q.strip()}%"
        params.extend([pattern, pattern, pattern, pattern])
    if category.strip():
        normalized = canonical_category(category)
        aliases = [alias.casefold() for alias in (normalized, *CATEGORY_ALIASES[normalized])]
        placeholders = ",".join("?" for _ in aliases)
        terms.append(f"(lower(category) IN ({placeholders}))")
        params.extend(aliases)

    where = " AND ".join(terms)
    order_by = {
        "newest": "created_at DESC",
        "oldest": "created_at ASC",
        "title": "title COLLATE NOCASE ASC",
    }[sort]
    client = db()
    try:
        cursor = client.execute(
            f"""SELECT id,title,category,description,tags,content_sha256,created_at,status,file_name,mime_type
                FROM configs WHERE {where}
                ORDER BY {order_by} LIMIT ? OFFSET ?""",
            tuple(params + [limit + 1, offset]),
        )
        items = rows_as_dicts(cursor)
        has_more = len(items) > limit
        items = items[:limit]
        for item in items:
            try:
                item["tags"] = json.loads(item.get("tags") or "[]")
            except (TypeError, json.JSONDecodeError):
                item["tags"] = []
            item["category"] = canonical_category(item.get("category"))
        return {"items": items, "limit": limit, "offset": offset, "has_more": has_more, "sort": sort}
    finally:
        client.close()


@app.get("/api/configs/{config_id}/download")
async def download_config(config_id: str):
    client = db()
    try:
        cursor = client.execute(
            "SELECT content,file_name,mime_type FROM configs WHERE id=? AND status='published'",
            (config_id,),
        )
        rows = rows_as_dicts(cursor)
        if not rows:
            raise HTTPException(404, "Config not found")
        item = rows[0]
        filename = safe_file_name(item.get("file_name") or "config.txt")
        return Response(
            content=item["content"],
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
        )
    finally:
        client.close()


@app.get("/api/configs/{config_id}")
async def get_config(config_id: str):
    client = db()
    try:
        cursor = client.execute(
            """SELECT id,title,category,description,tags,content,content_sha256,created_at,status,file_name,mime_type
               FROM configs WHERE id=? AND status='published'""",
            (config_id,),
        )
        rows = rows_as_dicts(cursor)
        if not rows:
            raise HTTPException(404, "Config not found")
        try:
            rows[0]["tags"] = json.loads(rows[0].get("tags") or "[]")
        except (TypeError, json.JSONDecodeError):
            rows[0]["tags"] = []
        rows[0]["category"] = canonical_category(rows[0].get("category"))
        return rows[0]
    finally:
        client.close()
