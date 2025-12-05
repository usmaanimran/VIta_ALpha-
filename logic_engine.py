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
        self.CRITICAL_INFRASTRUCTURE = {
            "PORT": ["colombo port", "harbour", "terminal", "customs", "container"],
            "AIRPORT": ["bia", "katunayake", "mattala", "flights", "airline", "airport"],
            "HIGHWAY": ["southern expressway", "kandy road", "galle road", "a1", "a4", "expressway", "highway"],
            "POWER": ["norochcholai", "sapugaskanda", "ceb", "grid", "breakdown", "substation", "power station"],
            "FINANCE": ["cse", "colombo stock exchange", "cbsl", "central bank", "forex", "rupee"]
        }
        self.groq_key = get_secret("GROQ_API_KEY")

    async def _neural_scan(self, text):
        if not self.groq_key: 
            return 0.0, "Neural Offline", "COLOMBO", "CLEAR", "RISK", 0.0, 0.0, True, "LOW"

        try:
            async with AsyncGroq(api_key=self.groq_key) as client:
                completion = await client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": """
                        You are a Risk Analyst for Sri Lankan Supply Chains.
                        Analyze the text and assign a 'score' (0-100) based strictly on OPERATIONAL IMPACT:

                        RUBRIC:
                        - 90-100 (CRITICAL): National shutdown, Port/Airport closure, Island-wide power failure, Curfew.
                        - 70-89 (HIGH): Supply chain disruption, Strikes at Ports/Fuel, Floods blocking major highways.
                        - 40-69 (MEDIUM): Localized unrest, High inflation announcements, Weather alerts.
                        - 10-39 (LOW): Political gossip, peaceful protests, minor delays.
                        - 0 (CLEAR): No business impact.
                        
                        If text is junk/chatter set validity=false.
                        Return JSON: {validity, score, reason, sentiment_type, logistics_status, location_name, lat, lon, severity_level}
                        severity_level should be LOW, MEDIUM, or HIGH.
                        """},
                        {"role": "user", "content": f"TEXT: {text}"}
                    ],
                    temperature=0, response_format={"type": "json_object"}
                )
                r = json.loads(completion.choices[0].message.content)
            
            if r.get('validity') is False:
                return 0, "AI_REJECT", "", "", "", 0, 0, False, "LOW"

            return (
                r.get('score', 0), 
                r.get('reason', 'AI Analysis'), 
                r.get('location_name', 'Colombo'), 
                r.get('logistics_status', "CLEAR"), 
                r.get('sentiment_type', r.get('sentiment_type', "RISK")),
                r.get('lat', 0.0),
                r.get('lon', 0.0),
                True,
                r.get('severity_level', "LOW")
            )
        except Exception as e:
            return 0.0, "Neural Error", "COLOMBO", "CLEAR", "RISK", 0.0, 0.0, True, "LOW"

    def _fallback_symbolic_scan(self, text):
        text_lower = text.lower()
        score = 0
        if "dead" in text_lower or "died" in text_lower or "killed" in text_lower or "shot" in text_lower: score += 50
        if "urgent" in text_lower: score += 20
        return min(100, score)

    async def analyze(self, text):
        ai_score, ai_reason, loc_name, logistics, sentiment_type, ai_lat, ai_lon, is_valid, severity = await self._neural_scan(text)

        math_score = self._fallback_symbolic_scan(text)

        if not is_valid:
             if math_score > 40:
                 is_valid = True
                 ai_score = math_score
                 ai_reason = "Symbolic Rescue"
             else:
                 return {"priority": "TRASH", "reason": "AI Filter"}

        final_score = ai_score
        
        if ai_reason == "Neural Error" or final_score == 0:
             final_score = max(final_score, math_score)
             if ai_reason == "Neural Error": ai_reason = "Symbolic Fallback"

        infra_impacts = []
        for sector, keywords in self.CRITICAL_INFRASTRUCTURE.items():
            if any(k in text.lower() for k in keywords):
                infra_impacts.append(sector)
        
        if infra_impacts:
            ai_reason += f" [IMPACT: {', '.join(infra_impacts)}]"
            if severity == "HIGH":
                final_score += 30
            elif severity == "MEDIUM":
                final_score += 15
            else:
                final_score += 5
                
            if logistics == "CLEAR": logistics = "POTENTIAL DELAY"

        final_score = int(min(100, final_score))
        if final_score < 15: final_score = 15

        if isinstance(ai_lat, (int, float)) and isinstance(ai_lon, (int, float)) and ai_lat != 0.0:
            geo_data = {"lat": ai_lat, "lon": ai_lon}
        else:
            geo_data = locations.get_coordinates(loc_name)
            if loc_name.upper() == "COLOMBO":
                 geo_data = locations.get_coordinates(text)

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
