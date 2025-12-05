import asyncio
import aiohttp
import feedparser
from bs4 import BeautifulSoup 
import re
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
        except: pass
            
    try:
        if vector_model is None:
            vector_model = SentenceTransformer('all-MiniLM-L6-v2')
    except: pass
    
    return supabase

def check_swarm_and_dedupe(new_text):
    global RECENT_NEWS_VECTORS
    if not vector_model: return False, False, None
    
    try:
        new_vec = vector_model.encode([new_text])[0]
        
        if not RECENT_NEWS_VECTORS:
            return False, False, new_vec
            
        cached_vecs = [v[1] for v in RECENT_NEWS_VECTORS]
        similarities = cosine_similarity([new_vec], cached_vecs)[0]
        
        if np.any(similarities > 0.85):
            return True, False, new_vec

        swarm_hits = np.sum((similarities > 0.60) & (similarities <= 0.85))
        is_swarm = swarm_hits >= 1

        return False, is_swarm, new_vec
        
    except:
        return False, False, None

async def beam_to_cloud(news_items, weather_status):
    db = init_db()
    if not db: return
    
    payload = []
    items_to_cache = [] 
    
    tasks = []
    processing_queue = []

    for item in news_items:
        text = item.get('full_text', item['title'])
        is_telegram = "Telegram" in item.get('source', '')
        
        if item['link'] in SEEN_LINKS:
            continue
            
        is_duplicate, is_swarm, new_vec = check_swarm_and_dedupe(text)
        
        if is_duplicate:
            SEEN_LINKS.add(item['link'])
            continue
            
        tasks.append(logic_engine.calculate_risk(text))
        processing_queue.append((item, text, is_telegram, is_swarm, new_vec))

    if not tasks: return

    results = await asyncio.gather(*tasks)

    for (item, text, is_telegram, is_swarm, new_vec), analysis in zip(processing_queue, results):
        if analysis.get('priority') == "TRASH":
            if is_telegram:
                analysis['priority'] = "MEDIUM"
                analysis['score'] = max(25, analysis['score'])
                analysis['reason'] = "Manual Override"
            else:
                SEEN_LINKS.add(item['link'])
                continue

        if is_swarm:
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
        
        if new_vec is not None:
            items_to_cache.append((text, new_vec))

    try:
        if payload:
            db.table('signals').upsert(payload, on_conflict='link').execute()
            for p in payload: SEEN_LINKS.add(p['link'])
            for txt, vec in items_to_cache:
                RECENT_NEWS_VECTORS.append((txt, vec))
                if len(RECENT_NEWS_VECTORS) > 100: RECENT_NEWS_VECTORS.pop(0)
    except Exception: pass

async def fetch_html(session, target):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36"
    }
    
    try:
        fresh_url = f"{target['url']}?t={int(time.time())}"
        async with session.get(fresh_url, headers=headers, timeout=15) as response:
            if response.status != 200: 
                return []
            
            html_content = await response.text()
            soup = BeautifulSoup(html_content, 'html.parser')
            batch = []
            
            selectors = [
                'h3 a', '.cat-title a', '.entry-title a', 
                '.news-custom-heading a', '.story-text a', 
                '.news-block a', '.main-news-block a',
                '.col-md-8 h3 a', 'h2 a'
            ]
            
            seen_in_batch = set()

            for selector in selectors:
                for item in soup.select(selector, limit=10):
                    if item and item.get_text(strip=True):
                        title = item.get_text(strip=True)
                        href = item['href']
                        if href.startswith('/'): 
                            base_url_parts = target['url'].split('/')
                            base_url = f"{base_url_parts[0]}//{base_url_parts[2]}"
                            href = base_url + href
                        
                        if href not in seen_in_batch:
                            seen_in_batch.add(href)
                            batch.append({
                                "title": f"[{target['name']}] {title}",
                                "link": href,
                                "source": target['name'],
                                "published": datetime.now(timezone.utc).isoformat()
                            })

            if not batch:
                for link in soup.find_all('a', href=True):
                    text = link.get_text(strip=True)
                    if 25 < len(text) < 150 and "http" in link['href']:
                        if link['href'] not in seen_in_batch:
                            seen_in_batch.add(link['href'])
                            batch.append({
                                "title": f"[{target['name']}] {text}",
                                "link": link['href'],
                                "source": target['name'],
                                "published": datetime.now(timezone.utc).isoformat()
                            })
            
            return batch[:10]
            
    except Exception:
        return []

async def async_listen_loop():
    db = init_db()
    
    if db:
        try:
            res = db.table('signals').select("link").order('timestamp', desc=True).limit(300).execute()
            if res.data:
                for r in res.data: SEEN_LINKS.add(r['link'])

            if vector_model:
                res = db.table('signals').select("headline").order('timestamp', desc=True).limit(50).execute()
                if res.data:
                    texts = [r['headline'] for r in res.data]
                    vecs = vector_model.encode(texts)
                    for t, v in zip(texts, vecs): RECENT_NEWS_VECTORS.append((t, v))
        except: pass

    targets = [
        {"name": "Ada Derana", "url": "http://www.adaderana.lk/hot-news/", "type": "html"},
        {"name": "Daily Mirror", "url": "https://www.dailymirror.lk/latest-news/108", "type": "html"},
        {"name": "News First", "url": "https://english.newsfirst.lk/latest-news", "type": "html"},
        {"name": "Newswire", "url": "https://www.newswire.lk/", "type": "html"}
    ]

    while True:
        rain_mm, weather_status = ground_truth_engine.fetch_weather_risk()
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for t in targets:
                tasks.append(fetch_html(session, t))
            
            results = await asyncio.gather(*tasks)
            all_news = [item for batch in results for item in batch]
            
            if all_news: 
                await beam_to_cloud(all_news, weather_status)
        
        if DEMO_MODE:
            await asyncio.sleep(10)
        else:
            await asyncio.sleep(60)
