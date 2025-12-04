import asyncio
import aiohttp
from telethon import TelegramClient, events
from datetime import datetime, timezone
import os
import data_engine 

API_ID = 36361719
API_HASH = "5e8435321c3c529ea50fa8ed3f9b2526"

async def main():
    client = TelegramClient('sentinlk_session', API_ID, API_HASH)
    await client.start()

    @client.on(events.NewMessage())
    async def handler(event):
        try:
            text = event.message.message
            if not text: return
            if text.startswith('/'): return

            chat = await event.get_chat()
            
            source_name = "Unknown"
            if hasattr(chat, 'title'): source_name = chat.title
            elif hasattr(chat, 'username'): source_name = chat.username

            signal = {
                "title": text[:100] + "...",
                "full_text": text,
                "link": f"https://t.me/{source_name}/{event.id}",
                "source": f"Telegram ({source_name})",
                "published": datetime.now(timezone.utc).isoformat()
            }

            async with aiohttp.ClientSession() as session:
                await data_engine.beam_to_cloud([signal], "CLEAR", session)

        except: pass

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())