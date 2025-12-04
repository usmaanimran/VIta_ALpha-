import json
import os
import locations
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from groq import AsyncGroq 

GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 

class HybridBrain:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        self.NOISE_TRIGGERS = ["cricket", "ipl", "match", "wedding", "gossip", "horoscope"]
        
        self.CRITICAL_INFRASTRUCTURE = {
            "PORT": ["colombo port", "harbour", "terminal", "customs", "container"],
            "AIRPORT": ["bia", "katunayake", "mattala", "flights", "airline"],
            "HIGHWAY": ["southern expressway", "kandy road", "galle road", "a1", "a4", "expressway", "interchange"],
            "POWER": ["norochcholai", "sapugaskanda", "ceb", "grid", "breakdown", "substation"],
            "FINANCE": ["cse", "colombo stock exchange", "cbsl", "central bank", "forex"]
        }

        self.vectors = {
            "political": ["election", "parliament", "president", "gazette"],
            "economic": ["imf", "tax", "inflation", "dollar", "debt", "stock market"],
            "social": ["protest", "strike", "riot", "tear gas", "police", "blockade"],
            "environmental": ["flood", "rain", "warning", "landslide", "cyclone", "disaster"],
            "infrastructure": ["water", "nwsdb", "electricity", "fuel", "litro", "gas", "telecom", "supply", "grid"],
            "power": ["power cut", "blackout", "ceb", "leco", "outage"]
        }
        
        if GROQ_API_KEY:
            try:
                self.groq_client = AsyncGroq(api_key=GROQ_API_KEY)
                self.neural_active = True
            except:
                self.neural_active = False
        else:
            self.neural_active = False

    def _symbolic_scan(self, text):
        text_lower = text.lower()
        for noise in self.NOISE_TRIGGERS:
            if noise in text_lower: return -1.0 

        score = 0.0
        for cat, keywords in self.vectors.items():
            for word in keywords:
                if word in text_lower: score += 15.0
        
        if "urgent" in text_lower or "breaking" in text_lower: score += 20
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
            return 0.0, "Neural Offline", "COLOMBO", "CLEAR", "RISK"
        try:
            completion = await self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Analyze for Sri Lankan Business. Return JSON: {score, reason, sentiment_type, logistics_status, location_name}"},
                    {"role": "user", "content": f"TEXT: {text}"}
                ],
                temperature=0, response_format={"type": "json_object"}
            )
            r = json.loads(completion.choices[0].message.content)
            return r.get('score', 0), r.get('reason', 'AI'), r.get('location_name', 'Colombo'), r.get('logistics_status', "CLEAR"), r.get('sentiment_type', "RISK")
        except:
            return 0.0, "Neural Error", "COLOMBO", "CLEAR", "RISK"

    async def analyze(self, text):
        math_score = self._symbolic_scan(text)
        if math_score == -1.0: return {"priority": "NOISE"}

        ai_score, ai_reason, loc_name, logistics, sentiment_type = await self._neural_scan(text)

        final_score = ai_score
        if final_score == 0:
            final_score = math_score
            ai_reason = "Symbolic Fallback"
        
        infra_hits = self._check_infrastructure_impact(text)
        if infra_hits:
            ai_reason += f" [IMPACT: {', '.join(infra_hits)}]"
            final_score += 15
            if logistics == "CLEAR": logistics = "POTENTIAL DELAY"

        final_score = int(max(math_score, final_score))
        final_score = min(100, final_score)

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