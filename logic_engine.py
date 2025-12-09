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
        self.groq_key = get_secret("GROQ_API_KEY")
        
       
        self.SPORTS_BAN_LIST = [
            "cricket", "wicket", "t20", "odi", "ipl", "lpl", "rugby", "match", 
            "won by", "lost by", "innings", "runs", "qualifier", "tournament"
        ]

        
        self.CRITICAL_INFRASTRUCTURE = {
            "PORT": ["colombo port", "harbour", "terminal", "customs", "container", "ship"],
            "AIRPORT": ["bia", "katunayake", "mattala", "flights", "airline", "airport"],
            "HIGHWAY": ["southern expressway", "kandy road", "galle road", "a1", "a4", "expressway", "highway", "interchange"],
            "POWER": ["norochcholai", "sapugaskanda", "ceb", "grid", "breakdown", "substation", "power station", "blackout"],
            "FINANCE": ["cse", "colombo stock exchange", "cbsl", "central bank", "forex", "rupee", "imf"]
        }

    async def _neural_scan(self, text, context=""):
        if not self.groq_key:
            return 0.0, "Neural Offline", "COLOMBO", "CLEAR", "RISK", 0.0, 0.0, True

        try:
            async with AsyncGroq(api_key=self.groq_key) as client:
                completion = await client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": """
                        You are a Strategic Analyst for Sri Lanka.
                        Analyze the TEXT given the CONTEXT.

                        TASKS:
                        1. DECIDE SENTIMENT ("RISK" or "OPPORTUNITY"):
                           - RISK: Danger, Delay, Loss, Strike, Violence, Bad Weather.
                           - OPPORTUNITY: Investment, IMF Grant, Tourism Spike, Growth.

                        2. VALIDITY: 
                           - FALSE: Sports, Gossip, Ads, Greetings.
                           - TRUE: Economy, Security, Logistics, Development, Traffic.

                        3. LOGISTICS STATUS:
                           - "DISRUPTED" / "POTENTIAL DELAY" / "CLEAR" (For Risk).
                           - "BOOST" (For Opportunity).

                        4. SCORE (0-100):
                           - 80-100: Critical Impact (Disaster/Mega Deal).
                           - 50-79:  High Impact (Protest/Tourism Boom).
                           - 25-49:  Medium Impact (Traffic/Small Grant).
                           - 0-24:   Low Impact.

                        5. LOCATION: Lat/Lon.

                        Return JSON: {validity, score, reason, sentiment_type, logistics_status, lat, lon}
                        """},
                        {"role": "user", "content": f"CONTEXT: {context}\n\nTEXT: {text}"}
                    ],
                    temperature=0, response_format={"type": "json_object"}
                )
                r = json.loads(completion.choices[0].message.content)
            
            if r.get('validity') is False:
                return 0, "AI_REJECT", "", "", "", 0, 0, False

            return (
                r.get('score', 0), 
                r.get('reason', 'AI Analysis'), 
                r.get('location_name', ''), 
                r.get('logistics_status', "CLEAR"), 
                r.get('sentiment_type', r.get('sentiment_type', "RISK")),
                r.get('lat', 0.0),
                r.get('lon', 0.0),
                True
            )
        except Exception as e:
            return 0.0, "Neural Error", "COLOMBO", "CLEAR", "RISK", 0.0, 0.0, True

    def _fallback_symbolic_scan(self, text):
        text_lower = text.lower()
        score = 0
        if "dead" in text_lower or "killed" in text_lower: score += 75
        if "injured" in text_lower: score += 40
        return min(100, score)

    async def analyze(self, text, context=""):
        
        text_lower = text.lower()
        if any(ban_word in text_lower for ban_word in self.SPORTS_BAN_LIST):
            return {
                "score": 0,
                "priority": "TRASH",
                "reason": "Hardcoded Sports Filter",
                "vectors": {"lat": 0, "lon": 0, "logistics_impact": "None", "sentiment_type": "None"}
            }
      
        ai_score, ai_reason, _, logistics, sentiment_type, ai_lat, ai_lon, is_valid = await self._neural_scan(text, context)

        if not is_valid:
             math_score = self._fallback_symbolic_scan(text)
             if math_score > 40:
                 is_valid = True
                 ai_score = math_score
                 ai_reason = "Symbolic Rescue"
                 sentiment_type = "RISK"
             else:
                 return {"priority": "TRASH", "reason": "AI Filter"}

        
        if sentiment_type == "RISK":
            infra_impacts = []
            for sector, keywords in self.CRITICAL_INFRASTRUCTURE.items():
                if any(k in text.lower() for k in keywords):
                    infra_impacts.append(sector)
            
            if infra_impacts:
                ai_reason += f" [IMPACT: {', '.join(infra_impacts)}]"
                ai_score += 20
                if logistics == "CLEAR": logistics = "POTENTIAL DELAY"

        final_score = int(min(100, ai_score))
        if final_score < 15: final_score = 15
        
        if isinstance(ai_lat, (int, float)) and ai_lat != 0.0:
            geo_data = {"lat": ai_lat, "lon": ai_lon}
        else:
            geo_data = locations.get_coordinates(text)

        priority = "CRITICAL" if final_score > 80 else "HIGH" if final_score > 40 else "MEDIUM"
        
        return {
            "score": final_score,
            "priority": priority,
            "reason": ai_reason,
            "vectors": {
                "lat": geo_data['lat'], "lon": geo_data['lon'],
                "logistics_impact": logistics, 
                "sentiment_type": sentiment_type
            }
        }

brain = HybridBrain()
async def calculate_risk(text, context=""): return await brain.analyze(text, context)
