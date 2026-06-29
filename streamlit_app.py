"""
Aria Dashboard — Streamlit monitoring UI
Deploy to Streamlit Cloud (free tier) after pushing to GitHub.
"""

import os

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Aria Dashboard — Burger House",
    page_icon="🍔",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── DB connection ─────────────────────────────────────────────────────────────
DATABASE_URL = (
    st.secrets.get("DATABASE_URL", None)
    or os.getenv("DATABASE_URL", "sqlite:///restaurant.db")
)

@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

engine = get_engine()

def run_query(sql: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎙️ Aria Voice Agent")
    st.caption("AI Restaurant Ordering System")
    st.divider()

    st.markdown("**Stack**")
    st.caption("🎤 Deepgram Nova-2 · Diarization")
    st.caption("🤖 Gemini 1.5 Flash")
    st.caption("🔊 ElevenLabs Turbo v2.5")
    st.caption("🔗 LiveKit WebRTC")
    st.divider()

    st.markdown("**Latency Target**")
    st.success("< 3 seconds end-to-end")
    st.divider()

    st.caption("**Language Support**")
    for lang in ["🇬🇧 English", "🇵🇰 Urdu", "🇮🇳 Hindi", "🟡 Punjabi"]:
        st.caption(lang)

# ── Main tabs ─────────────────────────────────────────────────────────────────
tab_voice, tab_inv, tab_orders, tab_conv = st.tabs([
    "🎙️ Voice Assistant",
    "🍔 Inventory",
    "📋 Orders",
    "💬 Conversations",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — VOICE ASSISTANT
# ═══════════════════════════════════════════════════════════════════════════════
with tab_voice:
    st.markdown("## 🎙️ Voice Ordering Interface")

    col_left, col_right = st.columns([1.5, 1])

    with col_left:
        lk_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
        connected = st.toggle("🔴 Connect to Agent", value=False)

        if connected:
            st.success(f"✅ Agent live — {lk_url}")
        else:
            st.info("Enable the toggle once `python agent.py dev` is running locally.")

        st.divider()

        st.markdown("### Voice Pipeline")
        cols = st.columns(5)
        steps = [
            ("🎤", "Deepgram\nNova-2", "STT"),
            ("🤖", "Gemini\n1.5 Flash", "LLM"),
            ("🛠️", "11 Agent\nTools", "Tools"),
            ("🔊", "ElevenLabs\nTurbo", "TTS"),
            ("👤", "Customer", "Output"),
        ]
        for c, (icon, label, role) in zip(cols, steps):
            with c:
                st.markdown(
                    f"""<div style='text-align:center;padding:12px 8px;background:#1e293b;
                    border-radius:12px;border:1px solid #334155;'>
                    <div style='font-size:24px'>{icon}</div>
                    <div style='font-size:11px;color:#94a3b8;margin-top:4px;white-space:pre'>{label}</div>
                    <div style='font-size:10px;color:#6366f1;margin-top:2px;font-weight:700'>{role}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

        st.divider()
        st.markdown("### Latency Breakdown")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("STT",   "~0.6 s")
        c2.metric("LLM",   "~0.8 s")
        c3.metric("TTS",   "~0.4 s")
        c4.metric("Total", "~1.8 s", delta="< 3 s target", delta_color="normal")

    with col_right:
        st.markdown("### Quick Start")
        st.code(
            """# 1. Start LiveKit (Docker)
docker run --rm -p 7880:7880 \\
  livekit/livekit-server --dev

# 2. Copy & fill .env
cp .env.example .env

# 3. Start agent
python agent.py dev

# 4. Open frontend
open frontend/index.html

# 5. Or use Docker Compose
docker compose up""",
            language="bash",
        )
        st.divider()
        st.markdown("### Language Support")
        st.markdown("""
| Language | Status |
|---|---|
| English | ✅ Active |
| Urdu | ✅ Active |
| Hindi | ✅ Active |
| Punjabi | ✅ Active |
| Mixed | ✅ Auto-detect |
""")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — INVENTORY
# ═══════════════════════════════════════════════════════════════════════════════
with tab_inv:
    st.markdown("## 🍔 Menu & Inventory")

    try:
        df = run_query(
            "SELECT name, category, description, price, stock, available "
            "FROM menu ORDER BY category, name"
        )
    except Exception:
        st.warning("Database not initialised yet. Run `python agent.py dev` once to seed the menu.")
        df = pd.DataFrame()

    if not df.empty:
        total_items     = len(df)
        available_items = int(df["available"].sum()) if "available" in df.columns else total_items
        low_stock       = int((df["stock"] < 20).sum()) if "stock" in df.columns else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Items",   total_items)
        c2.metric("Available",     available_items)
        c3.metric("⚠️ Low Stock",  low_stock)

        st.divider()

        cats = ["All"] + sorted(df["category"].dropna().unique().tolist())
        sel  = st.selectbox("Category", cats)
        view = df if sel == "All" else df[df["category"] == sel]

        display = view[["name", "category", "price", "stock", "available"]].copy()
        display.columns = ["Item", "Category", "Price (Rs)", "Stock", "Available"]
        display["Price (Rs)"] = display["Price (Rs)"].apply(lambda x: f"Rs {x:,.0f}")
        display["Available"]  = display["Available"].apply(lambda x: "✅" if x else "❌")
        st.dataframe(display, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Stock Levels")
        st.bar_chart(view.set_index("name")["stock"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ORDERS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_orders:
    st.markdown("## 📋 Orders")

    try:
        orders = run_query("""
            SELECT o.id, o.customer_name, o.status, o.total, o.created_at,
                   GROUP_CONCAT(oi.item_name || ' ×' || oi.quantity, ', ') AS items
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            GROUP BY o.id ORDER BY o.created_at DESC LIMIT 100
        """)
    except Exception:
        st.warning("No orders table found yet. Run the agent to generate orders.")
        orders = pd.DataFrame()

    if not orders.empty:
        total_rev = orders["total"].sum()
        conf      = int((orders["status"] == "confirmed").sum())

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Orders", len(orders))
        c2.metric("Confirmed",    conf)
        c3.metric("Revenue",      f"Rs {total_rev:,.0f}")

        st.divider()

        display = orders.copy()
        display["total"]  = display["total"].apply(lambda x: f"Rs {x:,.0f}")
        display["status"] = display["status"].apply(
            lambda s: "✅ confirmed" if s == "confirmed"
            else ("❌ cancelled" if s == "cancelled" else f"⏳ {s}")
        )
        display.columns = ["ID", "Customer", "Status", "Total", "Created", "Items"]
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.info("No orders yet. Place an order via the voice interface.")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — CONVERSATIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_conv:
    st.markdown("## 💬 Conversation Logs")

    try:
        conv = run_query(
            "SELECT speaker, message, timestamp FROM conversation "
            "ORDER BY timestamp DESC LIMIT 200"
        )
    except Exception:
        st.warning("No conversation table found yet.")
        conv = pd.DataFrame()

    if not conv.empty:
        c1, c2 = st.columns(2)
        c1.metric("Total Messages",  len(conv))
        c2.metric("Agent Messages",  int((conv["speaker"] == "agent").sum()))

        st.divider()
        for _, row in conv.iterrows():
            is_agent = str(row.get("speaker", "")).lower() in ("agent", "aria", "tool")
            col_l, col_r = st.columns([1, 4])
            with col_l:
                st.markdown("**🤖 Aria**" if is_agent else "**👤 Customer**")
                if row.get("timestamp"):
                    st.caption(str(row["timestamp"])[:19])
            with col_r:
                st.markdown(str(row.get("message", "")))
            st.divider()
    else:
        st.info("No conversation logs yet. Start a voice session to see them here.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<hr/><center style='color:#475569;font-size:12px'>"
    "Aria Voice Agent · Burger House · "
    "LiveKit + Deepgram + Gemini 1.5 Flash + ElevenLabs Turbo"
    "</center>",
    unsafe_allow_html=True,
)
