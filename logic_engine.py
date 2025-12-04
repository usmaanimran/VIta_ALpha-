import json
import os
import locations
import streamlit as st
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from groq import AsyncGroq 

def get_secret(key):
    if key in os.environ: return os.environ[key]
    try:
        if hasattr(st, "secrets") and key in st.secrets: return st.secrets[key]
    except: pass
    return None

class HybridBrain:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        self.NOISE_TRIGGERS = ["cricket", "ipl", "match", "wedding", "gossip", "horoscope", "song", "movie", "deal", "offer"]
        
        self.CRITICAL_INFRASTRUCTURE = {
            "PORT": ["colombo port", "harbour", "terminal", "customs", "container"],
            "AIRPORT": ["bia", "katunayake", "mattala", "flights", "airline"],
            "HIGHWAY": ["southern expressway", "kandy road", "galle road", "a1", "a4", "expressway"],
            "POWER": ["norochcholai", "sapugaskanda", "ceb", "grid", "breakdown", "substation"],
            "FINANCE": ["cse", "colombo stock exchange", "cbsl", "central bank", "forex"]
        }

        self.vectors = {
            "political": ["election", "parliament", "president", "gazette", "minister", "cabinet"],
            "economic": ["imf", "tax", "inflation", "dollar", "debt", "stock market", "price", "economy"],
            "social": ["protest", "strike", "riot", "tear gas", "police", "blockade", "union", "curfew"],
            "environmental": ["flood", "rain", "warning", "landslide", "cyclone", "disaster", "weather", "dam"],
            "infrastructure": ["water", "nwsdb", "electricity", "fuel", "litro", "gas", "telecom", "train", "bus"],
            "power": ["power cut", "blackout", "ceb", "leco", "outage"],
            "growth": ["investment", "profit", "launch", "opening", "recovery", "boom", "grant", "tourism", "export", "deal", "agreement"],
            "general_risk": ["accident", "crash", "death", "injured", "fire", "shoot", "attack", "arrest", "court"]
        }
        
        self.groq_key = get_secret("GROQ_API_KEY")
        self.groq_client = None
        self.neural_active = False

        if self.groq_key:
            try:
                self.groq_client = AsyncGroq(api_key=self.groq_key)
                self.neural_active = True
            except: pass

    def _validate_content(self, text):
       
        text_lower = text.lower().strip()
        word_count = len(text_lower.split())

       
        if word_count < 2: return False 
        
       
        if word_count < 5:
            has_keyword = False
            for cat, keywords in self.vectors.items():
                if any(w in text_lower for w in keywords):
                    has_keyword = True
                    break
            if not has_keyword: return False 

      
        for noise in self.NOISE_TRIGGERS:
            if noise in text_lower: return False
            
        return True

    def _symbolic_scan(self, text):
        text_lower = text.lower()
        score = 0.0
        
        for cat, keywords in self.vectors.items():
            for word in keywords:
                if word in text_lower: score += 15.0
        
        if "urgent" in text_lower or "breaking" in text_lower or "alert" in text_lower: score += 20
        
       
        if len(text.split()) > 15 and score == 0:
            score = 25.0
            
        return min(100.0, score)
    
    def _check_infrastructure_impact(self, text):
        text = text.lower()
        impacts = []
        for sector, keywords in self.CRITICAL_INFRASTRUCTURE.items():
            if any(k in text for k in keywords):
                impacts.append(sector)
        return impacts

    async def _neural_scan(self, text):
        if not self.neural_active: 
            return 0.0, "Neural Offline", "COLOMBO", "CLEAR", "RISK", 0.0, 0.0
        try:
           
            completion = await self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Analyze for Sri Lankan Business. If text is junk/chatter (e.g. 'hi', 'gm'), set validity=false. Return JSON: {validity (bool), score (0-100), reason, sentiment_type ('RISK' or 'OPPORTUNITY'), logistics_status, location_name, lat, lon}"},
                    {"role": "user", "content": f"TEXT: {text}"}
                ],
                temperature=0, response_format={"type": "json_object"}
            )
            r = json.loads(completion.choices[0].message.content)
            
            if r.get('validity') is False:
                return -999, "JUNK", "", "", "", 0, 0 

            return (
                r.get('score', 0), 
                r.get('reason', 'AI Analysis'), 
                r.get('location_name', 'Colombo'), 
                r.get('logistics_status', "CLEAR"), 
                r.get('sentiment_type', "RISK"),
                r.get('lat', 0.0),
                r.get('lon', 0.0)
            )
        except:
            return 0.0, "Neural Error", "COLOMBO", "CLEAR", "RISK", 0.0, 0.0

    async def analyze(self, text):
        
        if not self._validate_content(text):
            return {"priority": "TRASH", "reason": "Content Filter"}

        
        ai_score, ai_reason, loc_name, logistics, sentiment_type, ai_lat, ai_lon = await self._neural_scan(text)

        
        if ai_score == -999:
             return {"priority": "TRASH", "reason": "AI Rejected"}

        
        math_score = self._symbolic_scan(text)

        final_score = ai_score
        if final_score == 0:
            final_score = math_score
            ai_reason = "Symbolic Estimation"
        
        if math_score > 50 and final_score < 30:
            final_score = (final_score + math_score) / 2
            ai_reason += " + Keyword Risk Detected"

        infra_hits = self._check_infrastructure_impact(text)
        if infra_hits:
            ai_reason += f" [IMPACT: {', '.join(infra_hits)}]"
            final_score += 15
            if logistics == "CLEAR": logistics = "POTENTIAL DELAY"

        final_score = int(min(100, final_score))
        if final_score < 10: final_score = 15 

        if isinstance(ai_lat, (int, float)) and isinstance(ai_lon, (int, float)) and ai_lat != 0.0 and ai_lon != 0.0:
            geo_data = {"lat": ai_lat, "lon": ai_lon}
        else:
            geo_data = locations.get_coordinates(loc_name)

        priority = "CRITICAL" if final_score > 80 else "HIGH" if final_score > 40 else "MEDIUM"
        
        return {
            "score": final_score,
            "priority": priority,
            "reason": ai_reason,
            "vectors": {
                "lat": geo_data['lat'], "lon": geo_data['lon'],
                "logistics_impact": logistics, "sentiment_type": sentiment_type
            }
        }

brain = HybridBrain()
async def calculate_risk(text): return await brain.analyze(text)
