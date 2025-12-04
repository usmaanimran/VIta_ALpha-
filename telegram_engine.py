import asyncio
import os
import aiohttp
from datetime import datetime, timezone
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import data_engine
import streamlit as st

def get_secret(key):
    if key in os.environ:
        return os.environ[key]
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    return None

API_ID = 36361719
API_HASH = "5e8435321c3c529ea50fa8ed3f9b2526"

client = None

async def start_telegram_listener():
    global client
    
    session_string = get_secret("TELEGRAM_SESSION")
    
    if not session_string:
        print("⚠️ No TELEGRAM_SESSION secret found. Skipping Telegram listener.")
        return

    try:
        print("🔵 Starting Telegram Client...")
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.start()

        @client.on(events.NewMessage())
        async def handler(event):
            try:
                text = event.message.message
                if not text or text.startswith('/'): return

                chat = await event.get_chat()
                source_name = getattr(chat, 'title', getattr(chat, 'username', 'Unknown'))

                signal = {
                    "title": text[:100] + "...",
                    "full_text": text,
                    "link": f"https://t.me/{source_name}/{event.id}",
                    "source": f"Telegram ({source_name})",
                    "published": datetime.now(timezone.utc).isoformat()
                }
                
                await data_engine.beam_to_cloud([signal], "CLEAR")

            except Exception as e:
                print(f"Telegram Error: {e}")
        
        print("✅ Telegram Listener Active")
        await client.run_until_disconnected()
        
    except Exception as e:
        print(f"❌ Telegram Startup Failed: {e}")
