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
import streamlit as st
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

def get_secret(key):
    if key in os.environ:
        return os.environ[key]
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    return None

VECTOR_CACHE = [] 
vector_model = None
supabase: Client = None

def init_db():
    global supabase, vector_model
    if supabase is not None: return supabase

    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_KEY")
    
    if url and key:
        try:
            supabase = create_client(url, key)
            print("✅ Database Connected")
        except Exception as e:
            print(f"❌ Database Init Failed: {e}")
    else:
        print("⚠️ Missing SUPABASE_URL or SUPABASE_KEY secrets")
    
    try:
        if vector_model is None:
            vector_model = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        print(f"⚠️ AI Model Init Failed: {e}")
    
    return supabase

SEEN_LINKS = set()

def check_swarm_logic_optimized(new_headline):
    if not vector_model or not VECTOR_CACHE: return False
    try:
        new_vec = vector_model.encode([new_headline])[0]
        cached_vecs = [v[1] for v in VECTOR_CACHE]
        if not cached_vecs: return False
        
        similarities = cosine_similarity([new_vec], cached_vecs)[0]
        count = np.sum(similarities > 0.65)
        
        VECTOR_CACHE.append((new_headline, new_vec))
        if len(VECTOR_CACHE) > 100: VECTOR_CACHE.pop(0)
        return count >= 2 
    except: return False

async def beam_to_cloud(news_items, weather_status):
    
    db = init_db()
    if not db: return
    
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
        if payload:
            db.table('signals').upsert(payload, on_conflict='link').execute()
            for p in payload: SEEN_LINKS.add(p['link'])
            print(f"🚀 Uploaded {len(payload)} signals.")
    except Exception as e:
        print(f"❌ Supabase Write Error: {e}")

async def fetch_rss(session, target):
    try:
        async with session.get(target['url']) as response:
            content = await response.text()
            d = feedparser.parse(content)
            batch = []
            for entry in d.entries[:5]: 
                if entry.link not in SEEN_LINKS:
                    batch.append({
                        "title": entry.title, 
                        "link": entry.link, 
                        "source": target['name'], 
                        "published": datetime.now(timezone.utc).isoformat()
                    })
            return batch
    except: return []

async def async_listen_loop():
    db = init_db()
    
    if db and vector_model:
        try:
            res = db.table('signals').select("headline").order('timestamp', desc=True).limit(50).execute()
            if res.data:
                texts = [r['headline'] for r in res.data]
                vecs = vector_model.encode(texts)
                for t, v in zip(texts, vecs): VECTOR_CACHE.append((t, v))
        except: pass

    targets = [
        {"name": "Ada Derana", "url": "http://www.adaderana.lk/rss.php", "type": "rss"},
        {"name": "Daily Mirror", "url": "https://www.dailymirror.lk/rss", "type": "rss"},
        {"name": "Lanka C News", "url": "https://lankacnews.com/feed/", "type": "rss"}
    ]

    print("⚡ VIta Alpha Data Engine Started...")

    while True:
        rain_mm, weather_status = ground_truth_engine.fetch_weather_risk()
        
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_rss(session, t) for t in targets]
            results = await asyncio.gather(*tasks)
            all_news = [item for batch in results for item in batch]
            
            if all_news: 
                await beam_to_cloud(all_news, weather_status)
        
        await asyncio.sleep(60)
