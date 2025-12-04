import asyncio
import os
import aiohttp 
from datetime import datetime, timezone 
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import data_engine


API_ID = 36361719
API_HASH = "5e8435321c3c529ea50fa8ed3f9b2526"
SESSION_STRING = os.environ.get("TELEGRAM_SESSION")


client = None

async def start_telegram_listener():
    global client
    if not SESSION_STRING:
        print("⚠️ NO TELEGRAM SESSION FOUND. SKIPPING.")
        return

    print("⚡ TELEGRAM CLOUD UPLINK: STARTING...")
    
    try:
      
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.start()
        print("✅ TELEGRAM CLOUD UPLINK: CONNECTED 24/7.")

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
                
                print(f"📨 CLOUD TELEGRAM RECEIVED: {signal['title']}")
                
               
                async with aiohttp.ClientSession() as session:
                    await data_engine.beam_to_cloud([signal], "CLEAR", session)

            except Exception as e:
                print(f"⚠️ TELEGRAM ERROR: {e}")

 
        
    except Exception as e:
        print(f"❌ TELEGRAM LOGIN FAILED: {e}")
