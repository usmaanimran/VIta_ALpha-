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
            print("✅ Database Connected")
        except: pass
            
    try:
        if vector_model is None:
            vector_model = SentenceTransformer('all-MiniLM-L6-v2')
            print("🧠 AI Vector Model Loaded")
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
    
    for item in news_items:
        text = item.get('full_text', item['title'])
        is_telegram = "Telegram" in item.get('source', '')
        
        if item['link'] in SEEN_LINKS:
            continue
            
        is_duplicate, is_swarm, new_vec = check_swarm_and_dedupe(text)
        
        if is_duplicate and not is_telegram:
            SEEN_LINKS.add(item['link'])
            print(f"♻️ Skipped Duplicate: {item['title'][:30]}...")
            continue
            
        analysis = await logic_engine.calculate_risk(text)
        
        if analysis.get('priority') == "TRASH":
            if is_telegram:
                analysis['priority'] = "MEDIUM"
                analysis['score'] = max(25, analysis['score'])
                analysis['reason'] = "Manual Override"
                print(f"🛡️ Telegram Override")
            else:
                SEEN_LINKS.add(item['link'])
                print(f"🗑️ Trash Filtered: {item['title'][:30]}...")
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
                
            print(f"🚀 Uploaded {len(payload)} fresh signals from {payload[0]['source']}")
            
    except Exception as e:
        print(f"❌ Supabase Write Error: {e}")

async def fetch_html(session, target):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        async with session.get(target['url'], headers=headers, timeout=10) as response:
            if response.status != 200: 
                print(f"⚠️ Blocked/Error from {target['name']}: {response.status}")
                return []
            
            html_content = await response.text()
            soup = BeautifulSoup(html_content, 'html.parser')
            batch = []
            
            def add_item(link_tag, section_name):
                if link_tag and link_tag.get_text(strip=True):
                    title = link_tag.get_text(strip=True)
                    href = link_tag['href']
                    
                    if href.startswith('/'): 
                        base_url_parts = target['url'].split('/')
                        base_url = f"{base_url_parts[0]}//{base_url_parts[2]}"
                        href = base_url + href
                    
                    if not any(x['link'] == href for x in batch):
                        full_title = f"[{section_name}] {title}"
                        batch.append({
                            "title": full_title,
                            "link": href,
                            "source": target['name'],
                            "published": datetime.now(timezone.utc).isoformat()
                        })

            if "adaderana" in target['url']:
                lead = soup.find('div', class_='news-custom-heading') or soup.find('div', class_='lead-story')
                if lead: add_item(lead.find('a'), "LEAD")
                
                if not lead:
                    top_story = soup.find('div', class_='story-text')
                    if top_story: add_item(top_story.find('a'), "LEAD")

                hot_news = soup.find_all('div', class_='story-text', limit=6)
                for item in hot_news[1:]:
                    add_item(item.find('a'), "HOT NEWS")

            elif "dailymirror" in target['url']:
                top_header = soup.find(string=re.compile("Top Story", re.IGNORECASE))
                if top_header:
                    container = top_header.find_parent('div') or top_header.find_parent('section')
                    if container: add_item(container.find('a'), "TOP STORY")
                
                breaking_header = soup.find(string=re.compile("Breaking News", re.IGNORECASE))
                if breaking_header:
                    sidebar = breaking_header.find_parent('div') or breaking_header.find_parent('aside')
                    if sidebar:
                        for link in sidebar.find_all('a', limit=5):
                            add_item(link, "BREAKING")
                
                if not batch:
                     for item in soup.select('.col-md-8 h3 a', limit=5):
                        add_item(item, "LATEST")

            elif "newsfirst" in target['url']:
                main_block = soup.find('div', class_='main-news-block')
                if main_block:
                    for link in main_block.find_all('a', limit=3):
                        add_item(link, "TOP STORY")
                
                latest_block = soup.find('div', class_='latest-news-block') or soup.find('div', class_='sub-1')
                if latest_block:
                    for link in latest_block.find_all('a', limit=5):
                        add_item(link, "LATEST")

            elif "newswire" in target['url']:
                lead_section = soup.select_one('.td_block_wrap.td_block_big_grid_fl')
                if lead_section:
                    add_item(lead_section.find('a'), "LEAD")

                latest_section = soup.select('.td_block_inner .entry-title a')
                for link in latest_section[:5]:
                    add_item(link, "LATEST")

            return batch
            
    except Exception as e:
        print(f"⚠️ HTML Parse Error [{target['name']}]: {e}")
        return []

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
        {"name": "Ada Derana", "url": "http://www.adaderana.lk/hot-news/", "type": "html"},
        {"name": "Daily Mirror", "url": "https://www.dailymirror.lk/latest-news/108", "type": "html"},
        {"name": "News First", "url": "https://english.newsfirst.lk/", "type": "html"},
        {"name": "Newswire", "url": "https://www.newswire.lk/", "type": "html"}
    ]

    print("⚡ VIta Alpha Data Engine Started HTML MODE...")

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
            await asyncio.sleep(30)
