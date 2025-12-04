import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import json
from supabase import create_client
import logic_engine
import data_engine
import telegram_engine
import os
import time
import asyncio
import threading
from datetime import datetime, timedelta


st.set_page_config(page_title="VIta Alpha", layout="wide", page_icon="❎")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    h1 { color: #00ff9d !important; text-shadow: 0 0 10px #00ff9d; }
    div[data-testid="stMetricValue"] { color: #00ff9d; }
    /* Hide the default streamlit running man to make updates feel smoother */
    div[data-testid="stStatusWidget"] { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


def get_secret(key):
    if key in os.environ:
        return os.environ[key]
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    return None

@st.cache_resource
def start_background_brain():
    """Starts the background data engine only once."""
    def run_async_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
      
        if get_secret("TELEGRAM_SESSION"):
            loop.create_task(telegram_engine.start_telegram_listener())
        
        loop.run_until_complete(data_engine.async_listen_loop())
        
    t = threading.Thread(target=run_async_loop, daemon=True)
    t.start()
    return t


if "brain_started" not in st.session_state:
    try:
        start_background_brain()
        st.session_state.brain_started = True
    except Exception as e:
        st.error(f"Failed to start Brain: {e}")


supabase = None
try:
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_KEY")
    if url and key:
        supabase = create_client(url, key)
except Exception as e:
    st.error(f"Database Connection Failed: {e}")

def parse_vectors(row):
    try:
        data = json.loads(row['vectors'])
        return pd.Series([
            data.get('lat', 6.927), 
            data.get('lon', 79.861), 
            data.get('logistics_impact', 'CLEAR'), 
            data.get('sentiment_type', 'RISK') 
        ])
    except:
        return pd.Series([6.927, 79.861, "CLEAR", "RISK"])


st.title("VIta Alpha: SITUATIONAL AWARENESS")


metrics_container = st.container()
divider_1 = st.divider()
chart_container = st.empty()
divider_2 = st.divider()
map_container = st.empty()
st.subheader("📡 Live Intelligence Feed (Top 10)")
feed_container = st.empty()


def update_dashboard():
    """Fetches data and updates placeholders in place."""
    df = pd.DataFrame()
    if supabase:
        try:
        
            res = supabase.table('signals').select("*").order('timestamp', desc=True).limit(60).execute()
            df = pd.DataFrame(res.data)
        except Exception as e:
            pass 
    
    if df.empty:
        return

    
    df[['lat', 'lon', 'logistics', 'sentiment']] = df.apply(parse_vectors, axis=1)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    display_df = df.sort_values('timestamp', ascending=False)
    latest = display_df.iloc[0]

   
    with metrics_container:
      
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("LATEST SIGNAL", latest['headline'][:20]+"...", delta="Just Now")
        
        if latest['sentiment'] == "OPPORTUNITY":
             c2.metric("SIGNAL TYPE", "OPPORTUNITY", delta="Positive", delta_color="normal")
        else:
             c2.metric("THREAT LEVEL", f"{latest['risk_score']}/100", delta_color="inverse")
             
        c3.metric("INFRASTRUCTURE", latest['logistics'], delta_color="off")
        c4.metric("SYSTEM STATUS", "LIVE UPLINK", "Online")

   
    df['Trend Value'] = df.apply(lambda x: x['risk_score'] if x['sentiment'] == 'RISK' else x['risk_score'] * -1, axis=1)
    chart_df = df.sort_values('timestamp')
    
    fig = px.area(chart_df, x='timestamp', y='Trend Value', 
                  title="Real-Time Sentiment Volatility",
                  color_discrete_sequence=['#00ff9d'])
    
   
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#00ff9d'),
        yaxis=dict(gridcolor='#333'), 
        xaxis=dict(
            gridcolor='#333',
            rangeslider=dict(visible=True), 
            type="date"
        ),
        margin=dict(l=20, r=20, t=40, b=20), height=350
    )
    chart_container.plotly_chart(fig, use_container_width=True)

   
    df['color'] = df.apply(lambda x: [0, 255, 255, 200] if x['sentiment'] == 'OPPORTUNITY' else 
                                     ([255, 0, 0, 180] if x['risk_score'] > 75 else 
                                      [255, 165, 0, 180] if x['risk_score'] > 40 else 
                                      [0, 255, 100, 180]), axis=1)
    
    layer = pdk.Layer(
        "ScatterplotLayer", df,
        get_position='[lon, lat]', get_color="color", get_radius=8000,
        pickable=True, stroked=True, filled=True,
        radius_min_pixels=5, radius_max_pixels=50,
    )
    
   
    map_container.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=pdk.ViewState(latitude=7.87, longitude=80.77, zoom=7.5),
        tooltip={"html": "<b>{headline}</b><br/>Score: {risk_score}", "style": {"color": "white"}}
    ))

  
    top_10_df = display_df.head(10)[['timestamp', 'headline', 'sentiment', 'risk_score', 'logistics', 'link']]
    
    feed_container.dataframe(
        top_10_df, 
        use_container_width=True, hide_index=True,
        column_config={"link": st.column_config.LinkColumn("Source")}
    )


if __name__ == "__main__":
   
    while True:
        update_dashboard()
       
        time.sleep(2)
