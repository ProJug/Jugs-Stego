# backend/app/main.py
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from .stego import (
    build_embedded_payload,
    embed_into_png_bytes,
    extract_from_png_bytes,
    capacity_bytes_for_image_bytes,
)
from io import BytesIO
import os

app = FastAPI(title="Stego Web")

# Serve frontend
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(index_path):
        return HTMLResponse("<h1>Frontend missing</h1>", status_code=500)
    return FileResponse(index_path)

# CORS (tighten in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/capacity")
async def api_capacity(cover: UploadFile = File(...)):
    if cover.content_type not in ("image/png",):
        raise HTTPException(status_code=400, detail="Cover must be PNG")
    cover_bytes = await cover.read()
    cap = capacity_bytes_for_image_bytes(cover_bytes)
    return {"capacity_bytes": cap}

@app.post("/api/embed")
async def api_embed(
    cover: UploadFile = File(...),
    passphrase: str = Form(...),
    message: str = Form(None),
    payload: UploadFile = File(None)
):
    if cover.content_type != "image/png":
        raise HTTPException(status_code=400, detail="Cover must be PNG")
    cover_bytes = await cover.read()

    if payload is not None:
        plaintext = await payload.read()
    elif message is not None:
        plaintext = message.encode("utf-8")
    else:
        raise HTTPException(status_code=400, detail="Provide either message or payload file")

    embedded_payload = build_embedded_payload(plaintext, passphrase)
    cap = capacity_bytes_for_image_bytes(cover_bytes)
    if len(embedded_payload) > cap:
        raise HTTPException(status_code=400, detail=f"Payload too large. Capacity {cap} bytes, need {len(embedded_payload)} bytes")

    try:
        out_png = embed_into_png_bytes(cover_bytes, embedded_payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StreamingResponse(BytesIO(out_png), media_type="image/png",
                             headers={"Content-Disposition": "attachment; filename=stego.png"})

# -------- MIME sniffing helpers (no stored metadata) --------
def _sniff_mime_ext(b: bytes):
    # Images
    if b.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if b.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if b.startswith(b"GIF87a") or b.startswith(b"GIF89a"):
        return "image/gif", "gif"
    if len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp", "webp"

    # Docs / archives
    if b.startswith(b"%PDF-"):
        return "application/pdf", "pdf"
    if b.startswith(b"PK\x03\x04") or b.startswith(b"PK\x05\x06") or b.startswith(b"PK\x07\x08"):
        return "application/zip", "zip"

    # Audio
    if b.startswith(b"ID3") or (len(b) > 1 and b[0] == 0xFF and (b[1] & 0xE0) == 0xE0):
        return "audio/mpeg", "mp3"
    if len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WAVE":
        return "audio/wav", "wav"
    if b.startswith(b"OggS"):
        return "audio/ogg", "ogg"

    # Video containers
    if len(b) >= 12 and b[4:8] == b"ftyp":
        return "video/mp4", "mp4"
    if b.startswith(b"\x1A\x45\xDF\xA3"):  # Matroska
        return "video/webm", "webm"

    # Fallback
    return "application/octet-stream", "bin"

@app.post("/api/extract")
async def api_extract(
    stego: UploadFile = File(...),
    passphrase: str = Form(...)
):
    if stego.content_type != "image/png":
        raise HTTPException(status_code=400, detail="File must be PNG")
    stego_bytes = await stego.read()
    try:
        plaintext = extract_from_png_bytes(stego_bytes, passphrase)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # If it's UTF-8 text, keep returning JSON for convenience
    try:
        text = plaintext.decode("utf-8")
        return JSONResponse({"type": "text", "data": text})
    except UnicodeDecodeError:
        mime, ext = _sniff_mime_ext(plaintext)
        filename = f"extracted.{ext}"
        return StreamingResponse(BytesIO(plaintext), media_type=mime,
                                 headers={"Content-Disposition": f'attachment; filename="{filename}"'})
