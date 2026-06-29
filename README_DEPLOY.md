# Aria — AI Voice Ordering System
### Deploy to GitHub + Streamlit Cloud

---

## What's in this repo

| File / Folder | Purpose |
|---|---|
| `agent.py` | LiveKit voice agent (Deepgram STT → Gemini LLM → ElevenLabs TTS) |
| `database.py` | SQLAlchemy models + seed data (PKR prices) |
| `tools.py` | 11 agentic tools (cart, menu, inventory, orders) |
| `streamlit_app.py` | Monitoring dashboard — deploy on Streamlit Cloud |
| `frontend/index.html` | HTML/JS voice UI using LiveKit JS SDK |
| `docker-compose.yml` | Runs LiveKit + agent + dashboard + frontend |
| `Dockerfile` | Container image for the Python services |
| `.env.example` | Copy to `.env` and fill in API keys |
| `requirements.txt` | Python dependencies |

---

## Step 1 — Get API Keys (all free tier)

| Service | URL | Key needed |
|---|---|---|
| Deepgram | https://deepgram.com | `DEEPGRAM_API_KEY` |
| ElevenLabs | https://elevenlabs.io | `ELEVENLABS_API_KEY` |
| Google Gemini | https://aistudio.google.com/app/apikey | `GEMINI_API_KEY` |
| LiveKit | Local (`devkey`/`devsecret`) or https://cloud.livekit.io | `LIVEKIT_*` |

---

## Step 2 — Push to GitHub

```bash
git init
git add .
git commit -m "Aria voice ordering system"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

Add a `.gitignore` entry for `.env` and `restaurant.db` — secrets must not be committed.

---

## Step 3 — Deploy Dashboard to Streamlit Cloud

1. Go to https://share.streamlit.io → **New app**
2. Connect your GitHub repo
3. Set **Main file path** to `streamlit_app.py`
4. Click **Advanced settings → Secrets** and paste:

```toml
DATABASE_URL = "sqlite:///restaurant.db"
```

> **Note:** Streamlit Cloud cannot run the voice agent — the dashboard only reads the database.
> For a live demo, use the SQLite file from a local or VPS run, or switch `DATABASE_URL` to a hosted PostgreSQL.

---

## Step 4 — Run Locally (Option A: Docker)

```bash
cp .env.example .env
# Fill in your API keys in .env

docker compose up --build
```

| Service | URL |
|---|---|
| Frontend (voice UI) | http://localhost:3000 |
| Streamlit dashboard | http://localhost:8501 |
| LiveKit server | ws://localhost:7880 |

---

## Step 5 — Run Locally (Option B: Manual)

```bash
# Terminal 1 — LiveKit server
docker run --rm -p 7880:7880 livekit/livekit-server --dev

# Terminal 2 — Agent
pip install -r requirements.txt
cp .env.example .env   # fill keys
python agent.py dev

# Terminal 3 — Streamlit
streamlit run streamlit_app.py

# Frontend — just open in browser
open frontend/index.html
```

---

## Voice Pipeline

```
Customer mic
    ↓  WebRTC
LiveKit Server (local / cloud)
    ↓
LiveKit Agent (agent.py)
    ↓
Deepgram Nova-2 STT  (streaming, multilingual, diarization)
    ↓
Gemini 1.5 Flash LLM + 11 tools
    ↓
SQLite DB  (menu / orders / inventory)
    ↓
ElevenLabs Turbo v2.5 TTS  (streaming)
    ↓
Customer speaker
```

Target latency: **1–3 seconds** end-to-end.

---

## Languages Supported

- English
- Urdu (اردو)
- Hindi (हिंदी)
- Punjabi (ਪੰਜਾਬੀ)
- Mixed / code-switching — auto-detected per turn

---

## Order Flow

```
Hi → Greet
 ↓
What would you like? → search_menu()
 ↓
2 Zinger Burgers → check_inventory() → add_to_cart()
 ↓
Would you like fries? → add_to_cart()
 ↓
Confirm? Your total is Rs 1,670. → calculate_total()
 ↓
Yes → confirm_order(name) → save_order() → DB ✅
```

---

## Environment Variables

```env
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=devsecret
DEEPGRAM_API_KEY=...
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
GEMINI_API_KEY=...
DATABASE_URL=sqlite:///restaurant.db
```

---

## Database Schema

| Table | Columns |
|---|---|
| `menu` | id, name, category, description, price (PKR), stock, available |
| `orders` | id, customer_name, status, total, created_at |
| `order_items` | id, order_id, item_name, quantity, price |
| `conversation` | id, speaker, message, timestamp |

---

## Streamlit Cloud Limitations

- Cannot run the LiveKit agent (needs persistent WebSocket connection)
- Can read/display data from any connected database
- For a fully hosted solution, deploy the agent on Railway / Render / VPS and point `DATABASE_URL` to PostgreSQL

---

Made with LiveKit · Deepgram · Google Gemini · ElevenLabs · Streamlit
