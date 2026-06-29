"""
Aria — Production LiveKit Voice Agent
======================================
Stack : Deepgram Nova-2 STT  |  Gemini 1.5 Flash LLM  |  ElevenLabs Turbo TTS
Lang  : English · Urdu · Hindi · Punjabi (auto-detect)
Run   : python agent.py dev
"""

import asyncio
import logging
import os
from typing import Annotated

from dotenv import load_dotenv
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import deepgram, elevenlabs, google, silero

import tools as T
from database import init_db

# ── Bootstrap ────────────────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aria-agent")

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are Aria, the friendly voice assistant for Burger House restaurant (Pakistan).

## LANGUAGE
- Auto-detect the customer's language from their speech.
- Supported: English, Urdu, Hindi, Punjabi, or any mix.
- Always reply in the same language the customer used.
- If the customer mixes languages, mirror that naturally.

## PERSONALITY
- Warm, polite, professional.
- Short spoken responses — never more than 2 sentences unless listing the menu.
- Never use emoji. Never say "certainly!" or "absolutely!".

## RULES
1. Never hallucinate menu items. Always use tools to check the menu.
2. Always verify stock with check_inventory before adding to cart.
3. Ask follow-up questions (size, quantity, extras) before adding.
4. Never save the order without an explicit YES from the customer.
5. Keep track of the cart; confirm contents before finalising.
6. All prices are in Pakistani Rupees (PKR / Rs).

## ORDER FLOW
Greet → Take order → Verify inventory → Build cart → Confirm with customer →
Get customer name → confirm_order() → save_order() → Thank customer.

## TOOL USAGE
- search_menu(query)          — browse menu by keyword or category
- check_inventory(item_name)  — verify an item is in stock
- get_price(item_name)        — return PKR price of an item
- add_to_cart(item, qty)      — add item to this session's cart
- remove_from_cart(item)      — remove item from cart
- update_quantity(item, qty)  — change quantity of a cart item
- get_current_order()         — show the cart summary
- calculate_total()           — compute PKR total
- confirm_order(customer_name)— mark order confirmed (ask name first)
- save_order()                — persist to database (call after confirm)
- cancel_order()              — clear cart and start over
""".strip()

GREETING = (
    "Welcome to Burger House! I'm Aria. "
    "What would you like to order today?"
)


# ── Function context ──────────────────────────────────────────────────────────
class AriaFunctions(llm.FunctionContext):

    @llm.ai_callable(description="Search the menu by keyword or category. Use empty string to show the full menu.")
    async def search_menu(
        self,
        query: Annotated[str, llm.TypeInfo(description="Search keyword, category name, or empty for full menu")],
    ) -> str:
        result = T.search_menu(query)
        T.log_message("tool", f"search_menu({query!r}) → {result[:120]}")
        return result

    @llm.ai_callable(description="Check whether a specific menu item is available and how many are in stock.")
    async def check_inventory(
        self,
        item_name: Annotated[str, llm.TypeInfo(description="Exact or partial name of the menu item")],
    ) -> str:
        result = T.check_inventory(item_name)
        T.log_message("tool", f"check_inventory({item_name!r}) → {result}")
        return result

    @llm.ai_callable(description="Get the PKR price of a menu item.")
    async def get_price(
        self,
        item_name: Annotated[str, llm.TypeInfo(description="Name of the menu item")],
    ) -> str:
        result = T.get_price(item_name)
        T.log_message("tool", f"get_price({item_name!r}) → {result}")
        return result

    @llm.ai_callable(description="Add a menu item to the customer's cart. Always check inventory first.")
    async def add_to_cart(
        self,
        item_name: Annotated[str, llm.TypeInfo(description="Name of the menu item to add")],
        quantity: Annotated[int, llm.TypeInfo(description="Number of units to add (minimum 1)")],
    ) -> str:
        result = T.add_to_cart(item_name, quantity)
        T.log_message("tool", f"add_to_cart({item_name!r}, {quantity}) → {result}")
        return result

    @llm.ai_callable(description="Remove a menu item from the cart entirely.")
    async def remove_from_cart(
        self,
        item_name: Annotated[str, llm.TypeInfo(description="Name of the item to remove")],
    ) -> str:
        result = T.remove_from_cart(item_name)
        T.log_message("tool", f"remove_from_cart({item_name!r}) → {result}")
        return result

    @llm.ai_callable(description="Change the quantity of an item already in the cart.")
    async def update_quantity(
        self,
        item_name: Annotated[str, llm.TypeInfo(description="Name of the item to update")],
        quantity: Annotated[int, llm.TypeInfo(description="New quantity (set to 0 to remove)")],
    ) -> str:
        result = T.update_quantity(item_name, quantity)
        T.log_message("tool", f"update_quantity({item_name!r}, {quantity}) → {result}")
        return result

    @llm.ai_callable(description="Show the customer's current cart with all items and subtotals.")
    async def get_current_order(self) -> str:
        result = T.get_current_order()
        T.log_message("tool", f"get_current_order() → {result[:120]}")
        return result

    @llm.ai_callable(description="Calculate and return the PKR total for the current cart.")
    async def calculate_total(self) -> str:
        result = T.calculate_total()
        T.log_message("tool", f"calculate_total() → {result}")
        return result

    @llm.ai_callable(description="Mark the order as confirmed. Call after customer says YES. Requires customer's name.")
    async def confirm_order(
        self,
        customer_name: Annotated[str, llm.TypeInfo(description="Customer's name for the order receipt")],
    ) -> str:
        result = T.confirm_order(customer_name)
        T.log_message("tool", f"confirm_order({customer_name!r}) → confirmed")
        return result

    @llm.ai_callable(description="Save the confirmed order to the database. Call immediately after confirm_order().")
    async def save_order(self) -> str:
        result = T.save_order()
        T.log_message("tool", f"save_order() → {result[:80]}")
        return result

    @llm.ai_callable(description="Cancel the entire current order and reset the cart.")
    async def cancel_order(self) -> str:
        result = T.cancel_order()
        T.log_message("tool", f"cancel_order() → {result}")
        return result


# ── Entrypoint ─────────────────────────────────────────────────────────────────
async def entrypoint(ctx: JobContext) -> None:
    logger.info("Session started — room: %s", ctx.room.name)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    fnc_ctx     = AriaFunctions()
    chat_ctx    = llm.ChatContext().append(role="system", text=SYSTEM_PROMPT)

    agent = VoicePipelineAgent(
        vad=silero.VAD.load(),
        stt=deepgram.STT(
            model="nova-2",
            language="multi",          # auto language detection
            smart_format=True,
            diarize=True,              # speaker diarization
            interim_results=True,      # stream partial results for lower latency
        ),
        llm=google.LLM(
            model="gemini-1.5-flash",
            api_key=os.getenv("GEMINI_API_KEY"),
        ),
        tts=elevenlabs.TTS(
            voice_id=os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL"),
            model="eleven_turbo_v2_5",  # lowest-latency ElevenLabs model
            language="en",
        ),
        fnc_ctx=fnc_ctx,
        chat_ctx=chat_ctx,
        # Latency / barge-in tuning — target 1-3 s end-to-end
        allow_interruptions=True,
        interrupt_speech_duration=0.5,
        interrupt_min_words=0,
        min_endpointing_delay=0.4,
        max_endpointing_delay=6.0,
    )

    # Log every agent utterance
    @agent.on("agent_speech_committed")
    def _on_agent_speech(msg: llm.ChatMessage) -> None:
        T.log_message("agent", str(msg.content))

    # Log every user utterance
    @agent.on("user_speech_committed")
    def _on_user_speech(msg: llm.ChatMessage) -> None:
        T.log_message("customer", str(msg.content))

    agent.start(ctx.room)

    await agent.say(GREETING, allow_interruptions=True)
    await asyncio.sleep(3600)   # keep alive for 1 hour per session


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
