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
    .stProgress > div > div > div > div { background-color: #00ff9d; }
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

if 'last_run' not in st.session_state:
    st.session_state.last_run = time.time()

if time.time() - st.session_state.last_run > 30:
    st.session_state.last_run = time.time()
    st.rerun()

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

def prioritize_news(df):
    if df.empty: return df
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df.sort_values('timestamp', ascending=False)

def render_trend_chart(df):
    if df.empty: return
    df['Trend Value'] = df.apply(lambda x: x['risk_score'] if x['sentiment'] == 'RISK' else x['risk_score'] * -1, axis=1)
    chart_df = df.sort_values('timestamp')
    fig = px.area(chart_df, x='timestamp', y='Trend Value', 
                  title="Real-Time Sentiment Volatility",
                  labels={'Trend Value': 'Market Sentiment', 'timestamp': 'Time'},
                  color_discrete_sequence=['#00ff9d'])
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#00ff9d'),
        yaxis=dict(gridcolor='#333'), xaxis=dict(gridcolor='#333'),
        margin=dict(l=20, r=20, t=40, b=20), height=300
    )
    st.plotly_chart(fig, use_container_width=True)

def render_dashboard():
    df = pd.DataFrame()
    if supabase:
        try:
            res = supabase.table('signals').select("*").order('timestamp', desc=True).limit(60).execute()
            df = pd.DataFrame(res.data)
        except Exception as e:
            st.warning("Connecting to Cloud...")
    
    if not df.empty:
        df[['lat', 'lon', 'logistics', 'sentiment']] = df.apply(parse_vectors, axis=1)
        display_df = prioritize_news(df.copy())

        st.title("VIta Alpha: SITUATIONAL AWARENESS")
        
        c1, c2, c3, c4 = st.columns(4)
        latest = df.iloc[0]
        
        c1.metric("LATEST SIGNAL", latest['headline'][:20]+"...", delta="Just Now")
        
        if latest['sentiment'] == "OPPORTUNITY":
             c2.metric("SIGNAL TYPE", "OPPORTUNITY", delta="Positive", delta_color="normal")
        else:
             c2.metric("THREAT LEVEL", f"{latest['risk_score']}/100", delta_color="inverse")
             
        c3.metric("INFRASTRUCTURE", latest['logistics'], delta_color="off")
        c4.metric("SYSTEM STATUS", "LIVE UPLINK", "Online")
        
        st.divider()
        render_trend_chart(df)
        st.divider()

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
        
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(latitude=7.87, longitude=80.77, zoom=7.5),
            tooltip={"html": "<b>{headline}</b><br/>Score: {risk_score}", "style": {"color": "white"}}
        ))
        
        st.subheader("📡 Live Intelligence Feed")
        st.dataframe(
            display_df[['timestamp', 'headline', 'sentiment', 'risk_score', 'logistics', 'link']], 
            use_container_width=True, hide_index=True,
            column_config={"link": st.column_config.LinkColumn("Source")}
        )
    else:
        st.info("Initializing Intelligence Feed... Please wait.")
        time.sleep(5)
        st.rerun()

if __name__ == "__main__":
    render_dashboard()
