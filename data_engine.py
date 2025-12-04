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
    if key in os.environ: return os.environ[key]
    try:
        if hasattr(st, "secrets") and key in st.secrets: return st.secrets[key]
    except: pass
    return None


RECENT_NEWS_VECTORS = [] 
vector_model = None
supabase: Client = None
SEEN_LINKS = set()


DEMO_MODE = False 

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
            
    try:
        if vector_model is None:
            vector_model = SentenceTransformer('all-MiniLM-L6-v2')
            print("🧠 AI Vector Model Loaded")
    except Exception as e:
        print(f"⚠️ AI Model Init Failed: {e}")
    
    return supabase

def check_swarm_and_dedupe(new_text):
  
    global RECENT_NEWS_VECTORS
    if not vector_model: return False, False
    
    try:
        new_vec = vector_model.encode([new_text])[0]
        
        if not RECENT_NEWS_VECTORS:
            RECENT_NEWS_VECTORS.append((new_text, new_vec))
            return False, False
            
        cached_vecs = [v[1] for v in RECENT_NEWS_VECTORS]
        similarities = cosine_similarity([new_vec], cached_vecs)[0]
        
     
        if np.any(similarities > 0.85):
            return True, False 

      
        swarm_hits = np.sum((similarities > 0.60) & (similarities <= 0.85))
        is_swarm = swarm_hits >= 1

        
        RECENT_NEWS_VECTORS.append((new_text, new_vec))
        if len(RECENT_NEWS_VECTORS) > 100: RECENT_NEWS_VECTORS.pop(0)
            
        return False, is_swarm
        
    except Exception as e:
        print(f"Swarm Error: {e}")
        return False, False

async def beam_to_cloud(news_items, weather_status):
    db = init_db()
    if not db: return
    
    payload = []
    
    for item in news_items:
        text = item.get('full_text', item['title'])
        
       
        is_duplicate, is_swarm = check_swarm_and_dedupe(text)
        
        if is_duplicate:
            print(f"♻️ Skipped Duplicate: {item['title'][:30]}...")
            continue
            
       
        analysis = await logic_engine.calculate_risk(text)
        
        if analysis.get('priority') == "TRASH": 
            print(f"🗑️ Trash Filtered: {item['title'][:20]}...")
            continue

      
        if is_swarm:
            analysis['score'] = min(100, analysis['score'] + 15)
            analysis['reason'] += " [Swarm Verified]"
            print(f"🐝 Swarm Detected: {item['title'][:30]}")

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
            print(f"🚀 Uploaded {len(payload)} fresh signals.")
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
            print("⏳ Warming up Swarm Memory...")
            res = db.table('signals').select("headline").order('timestamp', desc=True).limit(50).execute()
            if res.data:
                texts = [r['headline'] for r in res.data]
                vecs = vector_model.encode(texts)
                for t, v in zip(texts, vecs): RECENT_NEWS_VECTORS.append((t, v))
            print("✅ Swarm Ready")
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
        
        if DEMO_MODE:
            print("🚀 DEMO MODE: Polling fast (10s)...")
            await asyncio.sleep(10)
        else:
            print("💤 STANDBY MODE: Polling normal (1m)...")
            await asyncio.sleep(60)
