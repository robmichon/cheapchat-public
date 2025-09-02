#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# --------- AUTO-INSTALL (Ubuntu 24.04 friendly) ----------
import sys, subprocess
REQUIRED = [
    "fastapi", "uvicorn", "openai", "python-multipart",
    "duckduckgo-search", "requests",
    "pypdf", "pdfminer.six", "pdf2image", "pillow", "pytesseract", "reportlab"
]
for pkg in REQUIRED:
    try:
        __import__(pkg.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", pkg])

# ------------------- IMPORTY -------------------
import os, sqlite3, uuid, base64, pathlib, json, tempfile, asyncio
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from duckduckgo_search import DDGS
import requests

# PDF / OCR
from pdfminer.high_level import extract_text as pdf_extract_text
import pytesseract
from pdf2image import convert_from_path
from docx import Document
from odf.opendocument import load as odf_load
from odf import text as odf_text
from PIL import Image
from reportlab.pdfgen import canvas

# ----------------- KONFIG ----------------------
API_KEY = None  # loaded dynamically
MODEL_TEXT  = "gpt-5-mini"
MODEL_STT   = "gpt-4o-mini-transcribe"
MODEL_TTS   = "gpt-4o-mini-tts"
MODEL_IMAGE = "gpt-image-1"
MODEL_CHOICES = ["gpt-4o-mini", "gpt-4o", "gpt-5-mini", "gpt-5", "gpt-5-large"]

TTS_DEFAULT = "alloy"
TTS_VOICES  = ["alloy","verse","coral","amber","breeze","cobalt","sol"]  # + 'sol'
PORT = int(os.environ.get("PORT", 8000))

BASE_DIR = pathlib.Path(__file__).parent.resolve()
DATA_DIR = pathlib.Path(os.getenv("CHEAPCHAT_DATA_DIR", pathlib.Path.home() / ".config" / "cheapchat"))
print(f"[data] dir: {DATA_DIR}")
DB_PATH = DATA_DIR / "memory.sqlite"
print(f"[db] using {DB_PATH}")
PUBLIC_DIR = BASE_DIR / "public"
TEMP_FILES = {}
TEMP_TTL = 300  # seconds

# ---- API key loader ----
def _read_first_nonempty(path):
    try:
        with open(os.path.expanduser(path), "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None

def load_api_key():
    # 1) Environment
    for env_name in ("OPENAI_API_KEY", "OPENAI_KEY", "OPENAI_API_KEY_ADMIN", "OPENAI_API_KEY_USER"):
        val = os.environ.get(env_name, "").strip()
        if val:
            print(f"[keys] using {env_name} from environment")
            return val
    # 2) Pliki (kolejno; Twój priorytet: chat-api.env)
    candidates = [
        "./chat-api.env",
        "./openai.key",
        "./.env",
        "./config.json",
        "~/.openai/api_key",
        "~/.config/private-chat/openai.key",
        "~/.config/openai.key",
    ]
    for p in candidates:
        content = _read_first_nonempty(p)
        if not content:
            continue
        # JSON?
        if p.endswith(".json"):
            try:
                cfg = json.loads(content)
                for k in ("OPENAI_API_KEY","openai_api_key","api_key","OPENAI_KEY"):
                    if isinstance(cfg, dict) and isinstance(cfg.get(k), str) and cfg[k].strip():
                        print(f"[keys] using key from {p}:{k}")
                        return cfg[k].strip()
            except Exception:
                pass
        # .env style?
        if "=" in content:
            for line in content.splitlines():
                if "=" in line:
                    k,v = line.split("=",1)
                    if k.strip() in ("OPENAI_API_KEY","OPENAI_KEY") and v.strip():
                        print(f"[keys] using {k.strip()} from {p}")
                        return v.strip()
        # Plain key
        if content.startswith("sk-") and len(content) > 20:
            print(f"[keys] using plain key from {p}")
            return content.strip()
    return None

API_KEY = load_api_key()
if not API_KEY:
    raise RuntimeError("Brak klucza OpenAI. Ustaw OPENAI_API_KEY lub zapisz klucz w ./chat-api.env, ./openai.key, .env, config.json, ~/.openai/api_key, ~/.config/private-chat/openai.key")

client = OpenAI(api_key=API_KEY)

# ----------------- APP -------------------------
app = FastAPI(title="Prywatny czat z pamięcią")
app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR)), name="public")


@app.get("/settings")
def get_settings_page():
    return FileResponse(PUBLIC_DIR / "settings.html")

# -------------- DB + MIGRACJE ------------------
def ensure_schema():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS threads(
            id TEXT PRIMARY KEY, created_at TEXT, title TEXT, use_memory INTEGER DEFAULT 1
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT, role TEXT, content TEXT, kind TEXT, created_at TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS anchors(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT, turn_index INTEGER, label TEXT,
            UNIQUE(thread_id, turn_index)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS global_memory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT, value TEXT, scope TEXT, is_active INTEGER DEFAULT 1,
            created_at TEXT, updated_at TEXT
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS documents(
            id TEXT PRIMARY KEY, filename TEXT, orig_name TEXT,
            mime TEXT, size INTEGER, created_at TEXT
        )""")
        # defensywne kolumny:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)").fetchall()}
        if "kind" not in cols:
            conn.execute('ALTER TABLE messages ADD COLUMN kind TEXT DEFAULT "text"')
        cols = {r[1] for r in conn.execute("PRAGMA table_info(threads)").fetchall()}
        if "use_memory" not in cols:
            conn.execute('ALTER TABLE threads ADD COLUMN use_memory INTEGER DEFAULT 1')
        cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)").fetchall()}
        if "mime" not in cols:
            conn.execute('ALTER TABLE documents ADD COLUMN mime TEXT')
        if "size" not in cols:
            conn.execute('ALTER TABLE documents ADD COLUMN size INTEGER')
ensure_schema()

def db():
    return sqlite3.connect(DB_PATH)

async def remove_temp_file(file_id: str, delay: int = TEMP_TTL):
    await asyncio.sleep(delay)
    info = TEMP_FILES.pop(file_id, None)
    if not info:
        return
    try:
        info["path"].unlink(missing_ok=True)
    except Exception:
        pass
    if info.get("doc"):
        with db() as conn:
            conn.execute("DELETE FROM documents WHERE id=?", (file_id,))


async def remove_path(path, delay: int = TEMP_TTL):
    await asyncio.sleep(delay)
    try:
        pathlib.Path(path).unlink(missing_ok=True)
    except Exception:
        pass

# -------------- MODELE -------------------------
class SendReq(BaseModel):
    thread_id: Optional[str] = None
    text: str
    web: Optional[bool] = False
    use_memory: Optional[bool] = True
    model: Optional[str] = None
    files: List[str] = []

class SendResp(BaseModel):
    thread_id: str
    reply: str
    tokens: int

class RenameReq(BaseModel):
    thread_id: str
    title: str

class ToggleMemReq(BaseModel):
    thread_id: str
    use_memory: bool

class TTSReq(BaseModel):
    text: str
    voice: Optional[str] = None

class ImageReq(BaseModel):
    thread_id: Optional[str] = None
    prompt: str
    size: Optional[str] = "1024x1024"

class AnchorReq(BaseModel):
    thread_id: str
    turn_index: int
    label: str

class AnchorDelReq(BaseModel):
    thread_id: str
    turn_index: int

class MemAddReq(BaseModel):
    key: Optional[str] = None
    value: str
    scope: Optional[str] = "other"

class MemUpdateReq(BaseModel):
    id: int
    key: Optional[str] = None
    value: Optional[str] = None
    scope: Optional[str] = None
    is_active: Optional[bool] = None

class MemToggleReq(BaseModel):
    id: int


# -------------- UTIL: THREADS ------------------
def new_thread(title: str = "", use_memory: bool = True) -> str:
    tid = str(uuid.uuid4())
    with db() as conn:
        conn.execute("INSERT INTO threads(id, created_at, title, use_memory) VALUES(?,?,?,?)",
            (tid, datetime.now(timezone.utc).isoformat(), title or "", 1 if use_memory else 0))
    return tid

def set_thread_title(thread_id: str, title: str):
    with db() as conn:
        conn.execute("UPDATE threads SET title=? WHERE id=?", (title, thread_id))

def set_thread_use_memory(thread_id: str, use_memory: bool):
    with db() as conn:
        conn.execute("UPDATE threads SET use_memory=? WHERE id=?", (1 if use_memory else 0, thread_id))

def delete_thread(thread_id: str):
    with db() as conn:
        conn.execute("DELETE FROM messages WHERE thread_id=?", (thread_id,))
        conn.execute("DELETE FROM threads WHERE id=?", (thread_id,))
        conn.execute("DELETE FROM anchors WHERE thread_id=?", (thread_id,))

def add_msg(thread_id: str, role: str, content: str, kind: str = "text"):
    with db() as conn:
        conn.execute("INSERT INTO messages(thread_id,role,content,kind,created_at) VALUES(?,?,?,?,?)",
            (thread_id, role, content, kind, datetime.now(timezone.utc).isoformat()))

def get_thread_messages(thread_id: str):
    with db() as conn:
        cur = conn.execute("SELECT id, role, content, kind, created_at FROM messages WHERE thread_id=? ORDER BY id", (thread_id,))
        return [{"id": i, "role": r, "content": c, "kind": k, "at": t} for (i,r,c,k,t) in cur.fetchall()]

def get_history_for_model(thread_id: str, limit: int = 60) -> List[dict]:
    with db() as conn:
        cur = conn.execute(
            "SELECT role, content, kind FROM messages WHERE thread_id=? ORDER BY id DESC LIMIT ?",
            (thread_id, limit)
        )
        rows = list(reversed(cur.fetchall()))
    msgs = []
    for (role, content, kind) in rows:
        if kind == "text":
            msgs.append({"role": role, "content": content})
        elif kind == "search":
            msgs.append({"role": "system", "content": content})
    return msgs

# -------------- UTIL: ANCHORS ------------------
def anchors_get(thread_id: str):
    with db() as conn:
        cur = conn.execute("SELECT turn_index, label FROM anchors WHERE thread_id=? ORDER BY turn_index", (thread_id,))
        return [{"turn_index": ti, "label": lbl} for (ti,lbl) in cur.fetchall()]

def anchors_set(thread_id: str, turn_index: int, label: str):
    with db() as conn:
        conn.execute("INSERT INTO anchors(thread_id,turn_index,label) VALUES(?,?,?) "
                     "ON CONFLICT(thread_id,turn_index) DO UPDATE SET label=excluded.label",
                     (thread_id, turn_index, label))

def anchors_delete(thread_id: str, turn_index: int):
    with db() as conn:
        conn.execute("DELETE FROM anchors WHERE thread_id=? AND turn_index=?", (thread_id, turn_index))

# -------------- UTIL: GLOBAL MEMORY 2.0 --------
def mem_add(key: Optional[str], value: str, scope: str="other"):
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        conn.execute("INSERT INTO global_memory(key,value,scope,is_active,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                     (key or "", value.strip(), scope, 1, now, now))

def mem_list(active: Optional[bool]=None):
    with db() as conn:
        if active is None:
            cur = conn.execute("SELECT id,key,value,scope,is_active,created_at,updated_at FROM global_memory ORDER BY id DESC")
        else:
            cur = conn.execute("SELECT id,key,value,scope,is_active,created_at,updated_at FROM global_memory WHERE is_active=? ORDER BY id DESC",
                               (1 if active else 0,))
        rows = cur.fetchall()
    out = []
    for (i,k,v,s,a,c,u) in rows:
        out.append({"id":i,"key":k,"value":v,"scope":s,"is_active":bool(a),"created_at":c,"updated_at":u})
    return out

def mem_update(req):
    sets, vals = [], []
    if req.key is not None: sets.append("key=?"); vals.append(req.key)
    if req.value is not None: sets.append("value=?"); vals.append(req.value)
    if req.scope is not None: sets.append("scope=?"); vals.append(req.scope)
    if req.is_active is not None: sets.append("is_active=?"); vals.append(1 if req.is_active else 0)
    sets.append("updated_at=?"); vals.append(datetime.now(timezone.utc).isoformat())
    vals.append(req.id)
    with db() as conn:
        conn.execute(f"UPDATE global_memory SET {', '.join(sets)} WHERE id=?", vals)

def mem_forget(id_: int):
    with db() as conn:
        conn.execute("UPDATE global_memory SET is_active=0, updated_at=? WHERE id=?",
                     (datetime.now(timezone.utc).isoformat(), id_))

def mem_restore(id_: int):
    with db() as conn:
        conn.execute("UPDATE global_memory SET is_active=1, updated_at=? WHERE id=?",
                     (datetime.now(timezone.utc).isoformat(), id_))

def mem_profile_snippet() -> str:
    active = mem_list(active=True)
    if not active: return ""
    parts = {"style": [], "voice": [], "facts": [], "other": []}
    for m in active:
        parts.get(m["scope"] if m["scope"] in parts else "other").append(m["value"])
    def join(key, arr):
        return f"{key}: " + "; ".join(arr) if arr else ""
    lines = [join("Preferencje stylu", parts["style"]),
             join("Preferencje głosu", parts["voice"]),
             join("Fakty", parts["facts"]),
             join("Inne", parts["other"])]
    snippet = "\n".join([l for l in lines if l])[:800]
    return snippet

def mem_forget_by_phrase(phrase: str):
    phrase = phrase.strip().lower()
    if not phrase: return []
    cands = []
    for m in mem_list(active=True):
        hay = f"{(m['key'] or '').lower()} {m['value'].lower()}"
        if phrase in hay:
            cands.append(m)
    if len(cands) == 1:
        mem_forget(cands[0]["id"])
        return [{"id": cands[0]["id"], "status": "forgotten"}]
    else:
        return [{"id": x["id"], "key": x["key"], "value": x["value"]} for x in cands]

# -------------- UTIL: SEARCH -------------------
def web_search(query: str, n: int = 5) -> List[dict]:
    out = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=n, safesearch="moderate", region="wt-wt"):
            out.append({"title": r.get("title",""), "url": r.get("href",""), "snippet": r.get("body","")})
    return out

def fetch_url_preview(url: str, timeout: float = 6.0) -> str:
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
        return r.text[:800]
    except:
        return ""

def format_sources_block(results: List[dict]) -> str:
    if not results: return "Brak wyników wyszukiwania."
    lines = ["Źródła wyszukiwania (skrót):"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']} — {r['url']}\n   {r['snippet']}")
    return "\n".join(lines)

# -------------- HANDLERY BŁĘDÓW ---------------
@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": f"{exc.__class__.__name__}: {exc}"})

# -------------- ENDPOINTY: THREADS ------------
@app.post("/api/new_thread")
def api_new_thread():
    return {"thread_id": new_thread()}

@app.post("/api/rename_thread")
def api_rename_thread(req: RenameReq):
    set_thread_title(req.thread_id, req.title.strip()[:120])
    return {"ok": True}

@app.post("/api/thread/use_memory")
def api_thread_use_memory(req: ToggleMemReq):
    set_thread_use_memory(req.thread_id, req.use_memory)
    return {"ok": True}

@app.get("/api/threads")
def list_threads():
    with db() as conn:
        cur = conn.execute("SELECT id, created_at, COALESCE(NULLIF(title,''), id), use_memory FROM threads ORDER BY created_at DESC")
        return [{"id": i, "created_at": t, "title": ttl, "use_memory": bool(um)} for (i,t,ttl,um) in cur.fetchall()]

@app.get("/api/thread/{thread_id}")
def api_thread(thread_id: str):
    return get_thread_messages(thread_id)

@app.delete("/api/thread/{thread_id}")
def api_delete_thread(thread_id: str):
    delete_thread(thread_id)
    return {"ok": True}

def create_pdf(thread_id: str) -> pathlib.Path:
    msgs = get_thread_messages(thread_id)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    fpath = pathlib.Path(tmp.name)
    c = canvas.Canvas(str(fpath))
    width, height = c._pagesize
    textobj = c.beginText(40, height - 40)
    for m in msgs:
        textobj.textLine(f"{m['role']}: ")
        for line in (m['content'] or '').splitlines():
            textobj.textLine('  ' + line)
        textobj.textLine('')
    c.drawText(textobj)
    c.save()
    return fpath

@app.get("/api/thread/{thread_id}/pdf")
def thread_pdf(thread_id: str, background: BackgroundTasks):
    fpath = create_pdf(thread_id)
    background.add_task(remove_path, fpath)
    return FileResponse(fpath, media_type="application/pdf", filename=f"{thread_id}.pdf")

# -------------- ENDPOINTY: ANCHORS ------------
@app.get("/api/anchors/{thread_id}")
def api_get_anchors(thread_id: str):
    return anchors_get(thread_id)

@app.post("/api/anchors")
def api_set_anchor(req: AnchorReq):
    anchors_set(req.thread_id, req.turn_index, req.label.strip()[:120])
    return {"ok": True}

@app.delete("/api/anchors")
def api_del_anchor(req: AnchorDelReq):
    anchors_delete(req.thread_id, req.turn_index)
    return {"ok": True}

# -------------- ENDPOINTY: MEMORY 2.0 ---------
@app.get("/api/memory/list")
def api_mem_list(active: Optional[int] = None):
    if active is None:
        return mem_list(None)
    return mem_list(bool(active))

@app.post("/api/memory/add")
def api_mem_add(req: MemAddReq):
    mem_add(req.key, req.value, req.scope or "other")
    return {"ok": True}

@app.post("/api/memory/update")
def api_mem_update(req: MemUpdateReq):
    mem_update(req); return {"ok": True}

@app.post("/api/memory/forget")
def api_mem_forget(req: MemToggleReq):
    mem_forget(req.id); return {"ok": True}

@app.post("/api/memory/restore")
def api_mem_restore(req: MemToggleReq):
    mem_restore(req.id); return {"ok": True}

# -------------- MODELS -------------------------
@app.get("/api/models")
def list_models():
    return {"default": MODEL_TEXT, "models": MODEL_CHOICES}

# -------------- SEND (komendy + web + memory) -
@app.post("/api/send", response_model=SendResp)
def send(req: SendReq):
    try:
        thread_id = req.thread_id or new_thread()
        text = (req.text or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Empty message.")

        # Komendy: zapamiętaj / zapomnij
        low = text.lower().strip()
        if low.startswith(("zapamiętaj:", "zapamietaj:", "remember:")):
            payload = text.split(":",1)[1].strip() if ":" in text else text
            mem_add(None, payload, "other")
            add_msg(thread_id, "system", f"Zapisano do pamięci: {payload}", "text")
            return {"thread_id": thread_id, "reply": "✅ Zapamiętane.", "tokens": 0}

        if low.startswith(("zapomnij:", "forget:")):
            phrase = text.split(":",1)[1].strip() if ":" in text else ""
            cands = mem_forget_by_phrase(phrase)
            if len(cands)==1 and cands[0].get("status")=="forgotten":
                add_msg(thread_id, "system", f"Zapomniano: {phrase}", "text")
                return {"thread_id": thread_id, "reply": "🧹 Zapomniane.", "tokens": 0}
            elif len(cands)==0:
                return {"thread_id": thread_id, "reply": "Nie znalazłem pasujących wpisów w pamięci.", "tokens": 0}
            else:
                lines = ["Znaleziono wiele wpisów. Wybierz ID do zapomnienia w panelu pamięci:"]
                lines += [f"- #{x['id']}: {x.get('key','')} — {x['value']}" for x in cands]
                add_msg(thread_id, "system", "\n".join(lines), "text")
                return {"thread_id": thread_id, "reply": "\n".join(lines), "tokens": 0}

        add_msg(thread_id, "user", text, "text")
        file_blocks = []
        for doc_id in req.files:
            try:
                txt = files_text(doc_id).get("text", "")
                if txt:
                    file_blocks.append(txt)
            except Exception:
                pass

        # Web search
        search_block = ""
        if req.web:
            results = web_search(text, n=5)
            if results:
                preview = fetch_url_preview(results[0]["url"])
                if preview:
                    results[0]["snippet"] += f"\n[preview]\n{preview}"
            search_block = format_sources_block(results)
            add_msg(thread_id, "system", search_block, "search")

        # Memory flag
        use_mem = bool(req.use_memory)
        with db() as conn:
            cur = conn.execute("SELECT use_memory FROM threads WHERE id=?", (thread_id,))
            row = cur.fetchone()
            if row is not None and req.thread_id:
                use_mem = bool(row[0])
            else:
                set_thread_use_memory(thread_id, use_mem)

        # Kontext
        history = get_history_for_model(thread_id)
        system_prompt = (
            "You are a helpful assistant. Reply in clean, GitHub-flavored Markdown. "
            "Use headings, bullet/numbered lists, tables, and fenced code blocks with language hints when helpful. "
        )
        if use_mem:
            prof = mem_profile_snippet()
            if prof:
                system_prompt += "\nUser profile (global memory):\n" + prof
        if req.web and search_block:
            system_prompt += "\nIf a 'Źródła wyszukiwania' block is present, ground the answer in it and cite briefly."

        context = history[:-1] if len(history) > 1 else []
        user_msg = history[-1] if history else {"role": "user", "content": text}
        messages = [{"role": "system", "content": system_prompt}] + context
        for block in file_blocks:
            messages.append({"role": "system", "content": block})
        messages.append(user_msg)

        model = req.model if req.model in MODEL_CHOICES else MODEL_TEXT
        resp = client.responses.create(model=model, input=messages)
        reply = getattr(resp, "output_text", None) or str(resp)
        tokens = 0
        usage = getattr(resp, "usage", None)
        if usage:
            tokens = getattr(usage, "total_tokens", 0)
        elif isinstance(resp, dict):
            tokens = resp.get("usage", {}).get("total_tokens", 0)
        add_msg(thread_id, "assistant", reply, "text")

        # Nadaj tytuł, jeśli pusty
        with db() as conn:
            cur = conn.execute("SELECT title FROM threads WHERE id=?", (thread_id,))
            row = cur.fetchone()
        if row and not row[0]:
            set_thread_title(thread_id, text[:60])

        return {"thread_id": thread_id, "reply": reply, "tokens": tokens}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

# -------------- AUDIO --------------------------
@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    resp = client.audio.transcriptions.create(
        model=MODEL_STT,
        file=("audio.webm", audio_bytes)
    )
    text = getattr(resp, "text", None) or (resp.get("text") if isinstance(resp, dict) else None)
    return {"text": text}

@app.get("/api/voices")
def voices():
    return {"default": TTS_DEFAULT, "voices": TTS_VOICES}

@app.post("/api/tts")
def tts(req: TTSReq):
    voice = (req.voice or TTS_DEFAULT)
    vnorm = voice.lower().strip()
    if vnorm not in [v.lower() for v in TTS_VOICES]:
        raise HTTPException(status_code=400, detail=f"Unknown voice: {voice}")
    audio = client.audio.speech.create(
        model=MODEL_TTS, voice=vnorm, input=req.text, format="mp3",
    )
    data = getattr(audio, "content", None) or (audio.read() if hasattr(audio, "read") else None)
    if data is None:
        raise HTTPException(status_code=502, detail="TTS failed.")
    return Response(content=data, media_type="audio/mpeg")

# -------------- IMAGES -------------------------
@app.post("/api/image")
def gen_image(req: ImageReq, background: BackgroundTasks):
    try:
        thread_id = req.thread_id or new_thread()
        prompt = (req.prompt or "").strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Empty image prompt.")
        img = client.images.generate(model=MODEL_IMAGE, prompt=prompt, size=req.size or "1024x1024", n=1)
        b64 = img.data[0].b64_json
        raw = base64.b64decode(b64)
        file_id = uuid.uuid4().hex
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.write(raw)
        tmp.close()
        path = pathlib.Path(tmp.name)
        TEMP_FILES[file_id] = {"path": path, "mime": "image/png"}
        background.add_task(remove_temp_file, file_id)
        url = f"/api/temp/{file_id}"
        add_msg(thread_id, "assistant", json.dumps({"prompt": prompt, "url": url}), "image")
        return {"thread_id": thread_id, "url": url, "prompt": prompt}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Image generation failed: {e}")

# -------------- FILES: upload/list/delete -------
@app.post("/api/files/upload")
async def files_upload(background: BackgroundTasks, files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        raw = await file.read()
        doc_id = uuid.uuid4().hex
        suffix = pathlib.Path(file.filename).suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(raw)
        tmp.close()
        path = pathlib.Path(tmp.name)
        with db() as conn:
            conn.execute(
                "INSERT INTO documents(id, filename, orig_name, mime, size, created_at) VALUES(?,?,?,?,?,?)",
                (doc_id, path.name, file.filename, file.content_type, len(raw), datetime.now(timezone.utc).isoformat()),
            )
        TEMP_FILES[doc_id] = {"path": path, "mime": file.content_type, "doc": True}
        background.add_task(remove_temp_file, doc_id)
        url = f"/api/temp/{doc_id}"
        results.append({"id": doc_id, "url": url, "name": file.filename, "mime": file.content_type, "size": len(raw)})
    return {"files": results}

@app.get("/api/files/list")
def files_list():
    with db() as conn:
        cur = conn.execute("SELECT id, orig_name, mime, size, created_at FROM documents ORDER BY created_at DESC")
        return [
            {
                "id": i,
                "url": f"/api/temp/{i}",
                "name": on,
                "mime": m,
                "size": s,
                "created_at": ca,
            }
            for (i, on, m, s, ca) in cur.fetchall()
            if i in TEMP_FILES
        ]

@app.delete("/api/files/{doc_id}")
def files_delete(doc_id: str):
    info = TEMP_FILES.pop(doc_id, None)
    if not info:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        info["path"].unlink(missing_ok=True)
    except Exception:
        pass
    with db() as conn:
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    return {"ok": True}

@app.get("/api/files/{doc_id}/text")
def files_text(doc_id: str):
    info = TEMP_FILES.get(doc_id)
    if not info:
        raise HTTPException(status_code=404, detail="Not found")
    fpath = info["path"]
    suffix = fpath.suffix.lower()
    try:
        if suffix == ".pdf":
            text = pdf_extract_text(str(fpath))
        elif suffix in (".docx", ".doc"):
            doc = Document(str(fpath))
            text = "\n".join(p.text for p in doc.paragraphs)
        elif suffix == ".odt":
            doc = odf_load(str(fpath))
            text = "\n".join(t.firstChild.data if t.firstChild else "" for t in doc.getElementsByType(odf_text.P))
        else:
            text = fpath.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"text extraction failed: {e}")
    return {"id": doc_id, "text": text or ""}

@app.get("/api/files/{doc_id}/ocr")
def files_ocr(doc_id: str, lang: str = "pol+eng", dpi: int = 250):
    info = TEMP_FILES.get(doc_id)
    if not info:
        raise HTTPException(status_code=404, detail="Not found")
    fpath = info["path"]
    suffix = fpath.suffix.lower()
    try:
        if suffix == ".pdf":
            images = convert_from_path(str(fpath), dpi=dpi)
            texts = [pytesseract.image_to_string(img, lang=lang) for img in images]
            full = "\n\n".join(texts)
        else:
            img = Image.open(fpath)
            full = pytesseract.image_to_string(img, lang=lang)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {e}")
    return {"id": doc_id, "lang": lang, "text": full}


@app.get("/api/temp/{file_id}")
def temp_file(file_id: str):
    info = TEMP_FILES.get(file_id)
    if not info or not info["path"].exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(info["path"], media_type=info.get("mime"))

# -------------- HEALTH -------------------------
@app.get("/-/health")
def health():
    import openai as _openai
    return {"ok": True, "openai_version": getattr(_openai, "__version__", "unknown"),
            "models": {"text": MODEL_TEXT, "stt": MODEL_STT, "tts": MODEL_TTS, "image": MODEL_IMAGE}}

# Serve public directory at root so assets can be loaded relatively
app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public_root")

# -------------- AUTOSTART ----------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=True)

