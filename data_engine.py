import asyncio
import aiohttp
import feedparser
from supabase import create_client, Client
from datetime import datetime, timezone
import logic_engine
import ground_truth_engine
import json
import time
import os
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SOCKET_URL = os.environ.get("SOCKET_URL", "http://localhost:8000/broadcast")

VECTOR_CACHE = [] 
vector_model = None

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    CLOUD_ACTIVE = True
    vector_model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception as e:
    CLOUD_ACTIVE = False

SEEN_LINKS = set()

def check_swarm_logic_optimized(new_headline):
    if not vector_model or not VECTOR_CACHE: return False
    try:
        new_vec = vector_model.encode([new_headline])[0]
        cached_vecs = [v[1] for v in VECTOR_CACHE]
        similarities = cosine_similarity([new_vec], cached_vecs)[0]
        count = np.sum(similarities > 0.65)
        
        VECTOR_CACHE.append((new_headline, new_vec))
        if len(VECTOR_CACHE) > 100: VECTOR_CACHE.pop(0)
        return count >= 2 
    except: return False

async def beam_to_cloud(news_items, weather_status, push_interface):
    if not CLOUD_ACTIVE: return
    
    payload = []
    for item in news_items:
        text = item.get('full_text', item['title'])
        analysis = await logic_engine.calculate_risk(text)
        
        if analysis.get('priority') == "NOISE": continue

        if check_swarm_logic_optimized(item['title']):
            analysis['score'] = min(100, analysis['score'] + 15)
            analysis['reason'] += " [Swarm Verified]"

        signal = {
            "timestamp": item['published'],
            "source": item['source'],
            "headline": item['title'],
            "full_text": text,
            "link": item['link'],
            "risk_score": int(analysis['score']),
            "priority": analysis['priority'],
            "reason": analysis['reason'],
            "vectors": json.dumps(analysis['vectors'])
        }
        payload.append(signal)

        try:
            if isinstance(push_interface, list):
                for connection in push_interface:
                    try:
                        await connection.send_json(signal)
                    except: continue
            elif hasattr(push_interface, 'post'):
                 await push_interface.post(SOCKET_URL, json=signal)
        except: pass

    try:
        if payload:
            supabase.table('signals').upsert(payload, on_conflict='link').execute()
            for p in payload: SEEN_LINKS.add(p['link'])
    except: pass

async def fetch_rss(session, target):
    try:
        async with session.get(target['url']) as response:
            content = await response.text()
            d = feedparser.parse(content)
            batch = []
            for entry in d.entries[:3]:
                if entry.link not in SEEN_LINKS:
                    batch.append({"title": entry.title, "link": entry.link, "source": target['name'], "published": datetime.now(timezone.utc).isoformat()})
            return batch
    except: return []

async def fetch_html(session, target):
    return []

async def async_listen_loop(active_connections=None):
    if CLOUD_ACTIVE:
        try:
            res = supabase.table('signals').select("headline").order('timestamp', desc=True).limit(50).execute()
            if res.data and vector_model:
                texts = [r['headline'] for r in res.data]
                vecs = vector_model.encode(texts)
                for t, v in zip(texts, vecs): VECTOR_CACHE.append((t, v))
        except: pass

    targets = [
        {"name": "News 1st", "url": "https://www.newsfirst.lk/", "selector": "div.main-news-heading", "type": "html"},
        {"name": "Ada Derana", "url": "http://www.adaderana.lk/rss.php", "type": "rss"},
        {"name": "Daily Mirror", "url": "https://www.dailymirror.lk/rss", "type": "rss"}
    ]

    while True:
        rain_mm, weather_status = ground_truth_engine.fetch_weather_risk()
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_rss(session, t) if t['type']=='rss' else fetch_html(session, t) for t in targets]
            results = await asyncio.gather(*tasks)
            all_news = [item for batch in results for item in batch]
            
            interface = active_connections if active_connections is not None else session
            
            if all_news: 
                await beam_to_cloud(all_news, weather_status, interface)
        
        await asyncio.sleep(2)
