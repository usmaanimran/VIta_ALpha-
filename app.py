import streamlit as st
import pandas as pd
import pydeck as pdk
import json
from supabase import create_client
import logic_engine
import ground_truth_engine
import streamlit.components.v1 as components
import os
from datetime import datetime, timedelta


SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://vdyeoagyxjfkytakvzpf.supabase.co")
SUPABASE_KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY", "sb_publishable_5A-PJGxJj93ocp5G9sSnWw_7jr9ivqc")
SOCKET_URL = os.environ.get("SOCKET_URL", "wss://project-vita-backend.onrender.com/ws") 

st.set_page_config(page_title="SentinLK | Real-Time", layout="wide", page_icon="⚡")


st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    h1 { color: #00ff9d !important; text-shadow: 0 0 10px #00ff9d; }
    div[data-testid="stMetricValue"] { color: #00ff9d; }
</style>
""", unsafe_allow_html=True)


components.html(
    f"""
    <script>
        var ws = new WebSocket("{SOCKET_URL}");
        ws.onmessage = function(event) {{
            console.log("⚡ NEW DATA");
            window.parent.location.reload();
        }};
    </script>
    """, 
    height=0, width=0
)

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except: pass

def parse_vectors(row):
    try:
        data = json.loads(row['vectors'])
        return pd.Series([data.get('lat', 6.927), data.get('lon', 79.861), data.get('logistics_impact', 'CLEAR'), data.get('sentiment_type', 'RISK')])
    except:
        return pd.Series([6.927, 79.861, "CLEAR", "RISK"])

def prioritize_news(df):
   
    if df.empty: return df
    
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
   
    now = datetime.now(df['timestamp'].dt.tz)
    one_hour_ago = now - timedelta(hours=1)
    
   
    fresh_news = df[df['timestamp'] >= one_hour_ago]
    old_news = df[df['timestamp'] < one_hour_ago]
    
  
    if len(fresh_news) < 10:
        needed = 10 - len(fresh_news)
        display_df = pd.concat([fresh_news, old_news.head(needed)])
    else:
     
        display_df = fresh_news
        
  
    return display_df.sort_values('timestamp', ascending=False)

def render_dashboard():
    df = pd.DataFrame()
    try:
 
        res = supabase.table('signals').select("*").order('timestamp', desc=True).limit(60).execute()
        df = pd.DataFrame(res.data)
    except: pass
    
    if not df.empty:
   
        df[['lat', 'lon', 'logistics', 'sentiment']] = df.apply(parse_vectors, axis=1)
        
   
        display_df = prioritize_news(df.copy())

        st.title("VIta_ALpha: SITUATIONAL AWARENESS")
        
       
        c1, c2, c3, c4 = st.columns(4)
        latest = df.iloc[0]
        c1.metric("LATEST SIGNAL", latest['headline'][:25]+"...", delta="Just Now")
        c2.metric("THREAT LEVEL", f"{latest['risk_score']}/100", delta_color="inverse")
        c3.metric("INFRASTRUCTURE", latest['logistics'], delta_color="off")
        c4.metric("SYSTEM STATUS", "LIVE UPLINK", "Online")
        
       
        df['color'] = df['risk_score'].apply(lambda x: [255, 0, 0, 180] if x > 75 else [255, 165, 0, 180] if x > 40 else [0, 255, 100, 180])
        
        layer = pdk.Layer(
            "ScatterplotLayer",
            df,
            get_position='[lon, lat]',
            get_color="color",
            get_radius=8000,
            pickable=True,
            stroked=True,
            filled=True,
            radius_min_pixels=5,
            radius_max_pixels=50,
        )
        
        tooltip = {
            "html": "<div style='background: #111; color: white; padding: 10px; border-radius: 5px; border: 1px solid #333;'>"
                    "<b>{headline}</b><br/>"
                    "⚠️ Risk Score: <b>{risk_score}</b><br/>"
                    "🚛 Logistics: {logistics}<br/>"
                    "📍 Location: {lat}, {lon}</div>",
            "style": {"color": "white"}
        }

        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(latitude=7.87, longitude=80.77, zoom=7.5),
            tooltip=tooltip
        ))
        
      
        st.subheader("📡 Live Intelligence Feed")
        
        st.dataframe(
            display_df[['timestamp', 'headline', 'risk_score', 'logistics', 'link']], 
            use_container_width=True,
            hide_index=True,
            column_config={
                "link": st.column_config.LinkColumn(
                    "Source",
                    display_text="Read Source" 
                ),
                "timestamp": st.column_config.DatetimeColumn(
                    "Time",
                    format="h:mm a"
                ),
                "risk_score": st.column_config.ProgressColumn(
                    "Risk",
                    format="%d",
                    min_value=0,
                    max_value=100,
                )
            }
        )

render_dashboard()