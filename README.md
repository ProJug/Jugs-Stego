# Stego Web (PNG LSB + AES-GCM)

Hide text or files inside PNGs. Extract with the same passphrase. Frontend is static HTML/JS, served by FastAPI. No bundlers. Clean.

## Local run

### Option A: Python only
```bash
# from repo root
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
# open http://localhost:8000
