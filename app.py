import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import json
from supabase import create_client
import os
import time
from datetime import datetime, timedelta


st.set_page_config(page_title="VIta Alpha", layout="wide", page_icon="❎")


st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    h1 { color: #00ff9d !important; text-shadow: 0 0 10px #00ff9d; }
    div[data-testid="stMetricValue"] { color: #00ff9d; }
    
    /* Marquee Styles */
    .marquee-container {
        width: 100%;
        overflow: hidden;
        white-space: nowrap;
        background: rgba(0, 255, 157, 0.1);
        border-radius: 5px;
        padding: 10px;
        border: 1px solid #00ff9d;
    }
    .marquee-content {
        display: inline-block;
        animation: scroll-left 20s linear infinite;
        color: #00ff9d;
        font-weight: bold;
        font-family: monospace;
        font-size: 1.2rem;
    }
    @keyframes scroll-left {
        0% { transform: translateX(100%); }
        100% { transform: translateX(-100%); }
    }
</style>
""", unsafe_allow_html=True)


def get_secret(key):
    if key in os.environ: return os.environ[key]

    try:
        if hasattr(st, "secrets") and key in st.secrets: return st.secrets[key]
    except: pass


    return None


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
            float(data.get('lat', 6.927)), 
            float(data.get('lon', 79.861)), 
            str(data.get('logistics_impact', 'CLEAR')), 
            str(data.get('sentiment_type', 'RISK'))
        ])
    except:

        return pd.Series([6.927, 79.861, "CLEAR", "RISK"])


st.title("VIta Alpha: SITUATIONAL AWARENESS")

@st.fragment(run_every=2)
def live_dashboard():
    df = pd.DataFrame()
    if supabase:
        try:
          
            res = supabase.table('signals').select("*").order('timestamp', desc=True).limit(60).execute()
            df = pd.DataFrame(res.data)
        except: 
            pass 

    if df.empty:
        st.warning("Waiting for uplink... (Check Database Connection)")
        return


    df[['lat', 'lon', 'logistics', 'sentiment']] = df.apply(parse_vectors, axis=1)


    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('Asia/Colombo').dt.tz_localize(None)

    
    display_df = df.sort_values('timestamp', ascending=False)
    latest = display_df.iloc[0]

   
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])


    with c1:
        st.caption("LATEST SIGNAL LIVE FEED")
       
        st.markdown(f"""
        <div class="marquee-container">
            <div class="marquee-content">
                🔴 {latest['headline']}  ///  SOURCE: {latest['source']}  ///  {latest['timestamp'].strftime('%H:%M:%S')}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
     
        if latest['sentiment'] == "OPPORTUNITY":
            st.metric("OPPORTUNITY SCORE", f"{latest['risk_score']}/100", delta="POSITIVE IMPACT", delta_color="normal")
        else:
          
            risk_df = df[df['sentiment'] == 'RISK']
            avg_threat = int(risk_df['risk_score'].mean()) if not risk_df.empty else 0

           
            st.metric("NATIONAL THREAT LEVEL", f"{avg_threat}/100", delta=f"Latest: {latest['risk_score']}", delta_color="inverse")
            
    with c3:
        st.metric("INFRASTRUCTURE", latest['logistics'], delta_color="off")
    with c4:
        st.metric("SYSTEM STATUS", "LIVE UPLINK", "Online")

    st.divider()


    df['Trend Value'] = df.apply(lambda x: x['risk_score'] if x['sentiment'] == 'OPPORTUNITY' else x['risk_score'] * -1, axis=1)
    chart_df = df.sort_values('timestamp')

    fig = px.area(chart_df, x='timestamp', y='Trend Value', 
                  title="Real-Time Sentiment Volatility (Above 0 = Opportunity, Below 0 = Risk)",
                  color_discrete_sequence=['#00ff9d'])

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#00ff9d'),
        yaxis=dict(gridcolor='#333', zeroline=True, zerolinecolor='white'), 
        xaxis=dict(gridcolor='#333', type="date"),




        margin=dict(l=20, r=20, t=40, b=20), height=350
    )
    st.plotly_chart(fig, use_container_width=True)

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


    st.subheader("📡 Live Feed")
    top_10_df = display_df.head(10).copy()
    

    def mask_link(link):
        if "t.me" in str(link):
            return "🔒 Encrypted Source" 
        return link

    top_10_df['Source Link'] = top_10_df['link'].apply(mask_link)
    

    st.dataframe(
        top_10_df[['timestamp', 'headline', 'sentiment', 'risk_score', 'logistics', 'Source Link']], 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Source Link": st.column_config.LinkColumn("Source", display_text="Open Link"),
            "risk_score": st.column_config.ProgressColumn("Impact", min_value=0, max_value=100, format="%d")
        }
    )

if __name__ == "__main__":
    live_dashboard()
