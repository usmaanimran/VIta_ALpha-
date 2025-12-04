import requests
import os
import time

WEATHERAPI_KEY = os.environ.get("WEATHERAPI_KEY", "")

def fetch_weather_risk(lat=6.927, lon=79.861):
    try:
        url = f"http://api.weatherapi.com/v1/current.json?key={WEATHERAPI_KEY}&q={lat},{lon}"
        resp = requests.get(url, timeout=2)
        if resp.status_code != 200: return 0.0, "API_ERROR"
        
        data = resp.json()
        rain_mm = data.get('current', {}).get('precip_mm', 0.0)
        
        if rain_mm > 50: return rain_mm, "SEVERE_FLOOD"
        elif rain_mm > 20: return rain_mm, "MODERATE_RAIN"
        return rain_mm, "CLEAR"
    except:
        return 0.0, "ERROR"
