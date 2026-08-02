"""ToolHub server: static tool launcher + generic per-tool document store."""
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import uvicorn
from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
HUB_DIR = BASE_DIR / "hub"
TOOLS_DIR = BASE_DIR / "tools"
DATA_DIR = BASE_DIR / "data"

TOOLS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

NAME_RE = re.compile(r"^[\w.-]+$", re.UNICODE)
RESERVED_COLUMNS = {"id", "_created_at", "_updated_at"}
RESERVED_QUERY_PARAMS = {"sort", "dir", "search"}

app = FastAPI(title="ToolHub")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)


def validate_name(name: str, kind: str) -> None:
    if not name or not NAME_RE.match(name):
        raise HTTPException(400, f"Invalid {kind}: '{name}'")


def get_db_path(tool_id: str) -> Path:
    return DATA_DIR / f"{tool_id}.db"


def get_connection(tool_id: str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(get_db_path(tool_id)))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table(conn: sqlite3.Connection, collection: str) -> None:
    conn.execute(
        f'CREATE TABLE IF NOT EXISTS "{collection}" ('
        "id TEXT PRIMARY KEY, data TEXT NOT NULL, "
        "_created_at TEXT NOT NULL, _updated_at TEXT NOT NULL)"
    )
    conn.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_to_doc(row: sqlite3.Row) -> dict:
    doc = json.loads(row["data"])
    doc["id"] = row["id"]
    doc["_created_at"] = row["_created_at"]
    doc["_updated_at"] = row["_updated_at"]
    return doc


def strip_reserved(body: dict) -> dict:
    return {k: v for k, v in body.items() if k not in RESERVED_COLUMNS}


def build_filters(query_params: dict) -> tuple[list, list]:
    clauses, values = [], []
    for key, value in query_params.items():
        validate_name(key, "filter field")
        if key in RESERVED_COLUMNS:
            clauses.append(f'"{key}" = ?')
        else:
            clauses.append(f"json_extract(data, '$.{key}') = ?")
        values.append(value)
    return clauses, values


# ---------------------------------------------------------------------------
# Tool discovery
# ---------------------------------------------------------------------------


@app.get("/api/tools")
def list_tools():
    tools = []
    for entry in sorted(TOOLS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        manifest_path = entry / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        tools.append(
            {
                "id": entry.name,
                "name": manifest.get("name", entry.name),
                "icon": manifest.get("icon", "\U0001f527"),
                "color": manifest.get("color", "#4a9eff"),
                "description": manifest.get("description", ""),
            }
        )
    return tools


# ---------------------------------------------------------------------------
# Backup endpoints (must be registered before the generic collection routes
# so that literal suffixes like "_export" are not swallowed by {collection})
# ---------------------------------------------------------------------------


@app.get("/api/store/{tool_id}/_export/json")
def export_json(tool_id: str):
    validate_name(tool_id, "tool_id")
    conn = get_connection(tool_id)
    try:
        tables = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        collections = {}
        for table in tables:
            rows = conn.execute(
                f'SELECT id, data, _created_at, _updated_at FROM "{table}"'
            ).fetchall()
            collections[table] = [row_to_doc(r) for r in rows]
        return {
            "tool_id": tool_id,
            "exported_at": now_iso(),
            "collections": collections,
        }
    finally:
        conn.close()


@app.get("/api/store/{tool_id}/_export")
def export_db(tool_id: str):
    validate_name(tool_id, "tool_id")
    path = get_db_path(tool_id)
    if not path.exists():
        get_connection(tool_id).close()
    return FileResponse(
        path, media_type="application/octet-stream", filename=f"{tool_id}.db"
    )


@app.post("/api/store/{tool_id}/_import/json")
def import_json(tool_id: str, body: dict = Body(...)):
    validate_name(tool_id, "tool_id")
    collections = body.get("collections", {})
    conn = get_connection(tool_id)
    try:
        imported, skipped = 0, 0
        for collection, docs in collections.items():
            validate_name(collection, "collection")
            ensure_table(conn, collection)
            for doc in docs:
                doc = dict(doc)
                doc_id = doc.pop("id", None) or str(uuid4())
                exists = conn.execute(
                    f'SELECT 1 FROM "{collection}" WHERE id = ?', (doc_id,)
                ).fetchone()
                if exists:
                    skipped += 1
                    continue
                created = doc.pop("_created_at", None) or now_iso()
                updated = doc.pop("_updated_at", None) or created
                conn.execute(
                    f'INSERT INTO "{collection}" (id, data, _created_at, _updated_at) '
                    "VALUES (?, ?, ?, ?)",
                    (doc_id, json.dumps(doc), created, updated),
                )
                imported += 1
        conn.commit()
        return {"success": True, "imported": imported, "skipped": skipped}
    finally:
        conn.close()


@app.post("/api/store/{tool_id}/_import")
async def import_db(tool_id: str, file: UploadFile = File(...)):
    validate_name(tool_id, "tool_id")
    contents = await file.read()
    if not contents.startswith(b"SQLite format 3\x00"):
        raise HTTPException(400, "Uploaded file is not a valid SQLite database")
    get_db_path(tool_id).write_bytes(contents)
    return {"success": True, "tool_id": tool_id}


@app.delete("/api/store/{tool_id}/_reset")
def reset_db(tool_id: str, confirm: bool = False):
    validate_name(tool_id, "tool_id")
    if not confirm:
        raise HTTPException(400, "Reset requires ?confirm=true")
    path = get_db_path(tool_id)
    if path.exists():
        path.unlink()
    return {"success": True, "tool_id": tool_id, "reset": True}


# ---------------------------------------------------------------------------
# Collection-level literal routes (must precede {doc_id})
# ---------------------------------------------------------------------------


@app.get("/api/store/{tool_id}/{collection}/_count")
def count_documents(tool_id: str, collection: str, request: Request):
    validate_name(tool_id, "tool_id")
    validate_name(collection, "collection")
    conn = get_connection(tool_id)
    try:
        ensure_table(conn, collection)
        clauses, values = build_filters(dict(request.query_params))
        sql = f'SELECT COUNT(*) AS c FROM "{collection}"'
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        row = conn.execute(sql, values).fetchone()
        return {"count": row["c"]}
    finally:
        conn.close()


@app.get("/api/store/{tool_id}/{collection}/_aggregate")
def aggregate_documents(tool_id: str, collection: str, request: Request):
    validate_name(tool_id, "tool_id")
    validate_name(collection, "collection")
    conn = get_connection(tool_id)
    try:
        ensure_table(conn, collection)
        qp = dict(request.query_params)
        group_by = qp.pop("group_by", None)
        agg_specs = {}
        for func in ("sum", "avg", "min", "max"):
            if func in qp:
                field = qp.pop(func)
                validate_name(field, "aggregate field")
                agg_specs[func] = field

        clauses, values = build_filters(qp)

        select_cols = []
        if group_by:
            validate_name(group_by, "group_by field")
            select_cols.append(f"json_extract(data, '$.{group_by}') AS group_value")
        for func, field in agg_specs.items():
            select_cols.append(
                f"{func.upper()}(CAST(json_extract(data, '$.{field}') AS REAL)) "
                f'AS "{func}_{field}"'
            )
        select_cols.append("COUNT(*) AS count")

        sql = f'SELECT {", ".join(select_cols)} FROM "{collection}"'
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        if group_by:
            sql += " GROUP BY group_value"

        rows = [dict(r) for r in conn.execute(sql, values).fetchall()]
        if not group_by:
            return rows[0] if rows else {}
        return rows
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Collection-level CRUD
# ---------------------------------------------------------------------------


@app.get("/api/store/{tool_id}/{collection}")
def list_documents(tool_id: str, collection: str, request: Request):
    validate_name(tool_id, "tool_id")
    validate_name(collection, "collection")
    conn = get_connection(tool_id)
    try:
        ensure_table(conn, collection)
        qp = dict(request.query_params)
        sort = qp.pop("sort", None)
        direction = qp.pop("dir", "asc")
        search = qp.pop("search", None)

        clauses, values = build_filters(qp)
        if search:
            clauses.append("data LIKE ?")
            values.append(f"%{search}%")

        sql = f'SELECT id, data, _created_at, _updated_at FROM "{collection}"'
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        if sort:
            validate_name(sort, "sort field")
            direction_sql = "DESC" if direction.lower() == "desc" else "ASC"
            if sort in RESERVED_COLUMNS:
                sql += f' ORDER BY "{sort}" {direction_sql}'
            else:
                sql += f" ORDER BY json_extract(data, '$.{sort}') {direction_sql}"

        rows = conn.execute(sql, values).fetchall()
        return [row_to_doc(r) for r in rows]
    finally:
        conn.close()


@app.post("/api/store/{tool_id}/{collection}", status_code=201)
def create_document(tool_id: str, collection: str, body: dict = Body(...)):
    validate_name(tool_id, "tool_id")
    validate_name(collection, "collection")
    conn = get_connection(tool_id)
    try:
        ensure_table(conn, collection)
        doc_id = str(body.get("id") or uuid4())
        data = strip_reserved(body)
        data.pop("id", None)
        timestamp = now_iso()
        try:
            conn.execute(
                f'INSERT INTO "{collection}" (id, data, _created_at, _updated_at) '
                "VALUES (?, ?, ?, ?)",
                (doc_id, json.dumps(data), timestamp, timestamp),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                409, f"Document with id '{doc_id}' already exists"
            ) from exc
        row = conn.execute(
            f'SELECT id, data, _created_at, _updated_at FROM "{collection}" WHERE id = ?',
            (doc_id,),
        ).fetchone()
        return row_to_doc(row)
    finally:
        conn.close()


@app.get("/api/store/{tool_id}/{collection}/{doc_id}")
def get_document(tool_id: str, collection: str, doc_id: str):
    validate_name(tool_id, "tool_id")
    validate_name(collection, "collection")
    conn = get_connection(tool_id)
    try:
        ensure_table(conn, collection)
        row = conn.execute(
            f'SELECT id, data, _created_at, _updated_at FROM "{collection}" WHERE id = ?',
            (doc_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"Document '{doc_id}' not found")
        return row_to_doc(row)
    finally:
        conn.close()


@app.put("/api/store/{tool_id}/{collection}/{doc_id}")
def replace_document(
    tool_id: str, collection: str, doc_id: str, body: dict = Body(...)
):
    validate_name(tool_id, "tool_id")
    validate_name(collection, "collection")
    conn = get_connection(tool_id)
    try:
        ensure_table(conn, collection)
        row = conn.execute(
            f'SELECT id FROM "{collection}" WHERE id = ?', (doc_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"Document '{doc_id}' not found")
        data = strip_reserved(body)
        data.pop("id", None)
        timestamp = now_iso()
        conn.execute(
            f'UPDATE "{collection}" SET data = ?, _updated_at = ? WHERE id = ?',
            (json.dumps(data), timestamp, doc_id),
        )
        conn.commit()
        updated = conn.execute(
            f'SELECT id, data, _created_at, _updated_at FROM "{collection}" WHERE id = ?',
            (doc_id,),
        ).fetchone()
        return row_to_doc(updated)
    finally:
        conn.close()


@app.patch("/api/store/{tool_id}/{collection}/{doc_id}")
def patch_document(
    tool_id: str, collection: str, doc_id: str, body: dict = Body(...)
):
    validate_name(tool_id, "tool_id")
    validate_name(collection, "collection")
    conn = get_connection(tool_id)
    try:
        ensure_table(conn, collection)
        row = conn.execute(
            f'SELECT data FROM "{collection}" WHERE id = ?', (doc_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, f"Document '{doc_id}' not found")
        existing = json.loads(row["data"])
        existing.update(strip_reserved(body))
        existing.pop("id", None)
        timestamp = now_iso()
        conn.execute(
            f'UPDATE "{collection}" SET data = ?, _updated_at = ? WHERE id = ?',
            (json.dumps(existing), timestamp, doc_id),
        )
        conn.commit()
        updated = conn.execute(
            f'SELECT id, data, _created_at, _updated_at FROM "{collection}" WHERE id = ?',
            (doc_id,),
        ).fetchone()
        return row_to_doc(updated)
    finally:
        conn.close()


@app.delete("/api/store/{tool_id}/{collection}/{doc_id}")
def delete_document(tool_id: str, collection: str, doc_id: str):
    validate_name(tool_id, "tool_id")
    validate_name(collection, "collection")
    conn = get_connection(tool_id)
    try:
        ensure_table(conn, collection)
        cursor = conn.execute(
            f'DELETE FROM "{collection}" WHERE id = ?', (doc_id,)
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(404, f"Document '{doc_id}' not found")
        return {"success": True, "id": doc_id}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Static files (mounted last so /api routes always take precedence)
# ---------------------------------------------------------------------------

app.mount("/tools", StaticFiles(directory=str(TOOLS_DIR)), name="tools")
app.mount("/", StaticFiles(directory=str(HUB_DIR), html=True), name="hub")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8800)
