<div align="center">

<a href="https://projectalpha.streamlit.app/">
  <img src="https://readme-typing-svg.herokuapp.com?font=Orbitron&weight=700&size=40&pause=1000&color=00FF9D&center=true&vCenter=true&width=800&height=80&lines=VIta+Alpha;Live+Threat+Intelligence;The+Survival+Engine" alt="VIta Alpha" />
</a>

**Autonomous Infrastructure & Supply Chain Continuity for Sri Lanka**

<br>

<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/aqua.png" width="100%">

<br>

### 🌐 Live Access & Documentation
[![Streamlit App](https://img.shields.io/badge/🔴_LIVE_ON-STREAMLIT-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://projectalpha.streamlit.app/)
[![Hugging Face](https://img.shields.io/badge/🤗_HOSTED_ON-HUGGING_FACE-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)](https://huggingface.co/spaces/usmaan-15/VIta_brain)
[![Pitch Deck](https://img.shields.io/badge/📄_PROJECT-DOCS-4285F4?style=for-the-badge&logo=googledrive&logoColor=white)](https://drive.google.com/file/d/1pIZ2IKpCV_VNOpEzQlUyNI-WzBMyGOwc/view)

</div>

---

## 🧬 The Evolution: `vita_lk` ➔ `VIta Alpha`

**VIta Alpha is the 5th major evolution of this intelligence platform.** What initially began as the `vita_lk` prototype has been entirely re-architected. 

The most critical leap in this 5th-generation engine is the **Data Ingestion Protocol**. Earlier iterations relied on standard RSS scraping, which introduced severe latency (often 15-30 minutes behind live events) and the potential of getting banned every now and then. **VIta Alpha bypassed this limitation by deploying asynchronous HTML scraping.** By reading the live DOM of news sources via `aiohttp` and `BeautifulSoup`, and combining it with live Telegram interceptors, the system now achieves sub-minute real-time access to ground-truth data.

<div align="center">
  <img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/aqua.png" width="80%">
</div>

## 🧠 Advanced Architecture & Core Tech

VIta Alpha is an asynchronous threat-intelligence pipeline built to run 24/7 without human intervention. 

### 1. The Hybrid Brain (Zero-Downtime AI)
Located in `logic_engine.py`, the system evaluates every incoming signal through a dual-layer analysis engine:
* **Neural Layer (Primary):** Powered by **Llama-3.3-70b-versatile** via `AsyncGroq`. It performs zero-shot JSON classification, strictly filtering noise (e.g., sports, celebrity gossip) and identifying valid economic, infrastructural, or security events. It calculates a 0-100 impact score and flags signals as `RISK` or `OPPORTUNITY`.
* **Symbolic Rescue (Fallback):** If the AI layer goes offline or hits rate limits, the system instantly falls back to mathematical symbolic scanning using `VADER Sentiment Analysis` and hardcoded lexical heuristic matrices to maintain 100% uptime.

### 2. High-Dimensional Vector Deduplication (Swarm Defense)
To prevent database flooding during major news events (Swarm Reporting), `data_engine.py` employs advanced semantic math:
* **Embedding Projection:** `SentenceTransformer('all-MiniLM-L6-v2')` converts incoming headlines into dense mathematical vectors.
* **Cosine Similarity Filtering:** `sklearn` calculates the geometric distance between new signals and a rolling context buffer. If the similarity score exceeds `> 0.75`, the system autonomously drops the duplicate, keeping the intelligence feed clean and database storage optimized.

### 3. Asynchronous HTML & Telegram Intercepts
* **Real-Time HTML Scraping:** Bypasses sluggish RSS feeds to scrape live target URLs. 
* **Encrypted Intercepts:** `telethon` actively listens to encrypted Telegram signals on a background thread, instantly beaming civilian ground reports to the Supabase cloud.

### 4. Geospatial & Meteorological Ground Truth
* **Lexical Grid Mapping:** `locations.py` houses an expansive array of over 80+ Sri Lankan coordinates and landmark aliases, mapping raw text (e.g., "Parliament") to exact latitude/longitude vectors.
* **Live Environmental Validation:** Connects to live weather APIs to detect high precipitation (`precip_mm > 50`) and autonomously inject `SEVERE_FLOOD` warnings into the logistics calculations.

<div align="center">
  <img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/aqua.png" width="80%">
</div>

## 📊 The War-Room UI
The Streamlit frontend (`app.py`) is styled heavily with custom CSS and features complex, dynamic visualizations:
* **Live Marquee Injector:** A CSS-animated, continuously scrolling marquee streaming the latest threat signals directly into the DOM.
* **PyDeck 3D Mapping:** A scatterplot geospatial layer mapped across Sri Lanka, dynamically color-coding threat severity (🔴 CRITICAL, 🟡 WARNING, 🟢 CLEAR, 🔵 OPPORTUNITY).
* **Plotly Volatility Tracking:** Interactive area charts that track sentiment volatility over time, flipping Y-axes for negative risks vs. positive opportunities.

## 🛠️ Tech Stack Matrix

| Module | Technology & Libraries |
| :--- | :--- |
| **Frontend UI/UX** | Streamlit, HTML/CSS Injections, Marquee Animations |
| **Data Visualization**| Plotly Express, PyDeck (3D Geo-mapping) |
| **Database & Cloud** | Supabase (PostgreSQL) |
| **AI / Vector Math** | Groq API (Llama 3), Hugging Face SentenceTransformers, scikit-learn, VADER |
| **Scraping & Async** | BeautifulSoup4, lxml, AIOHTTP, Telethon |
| **Hosting & CI/CD** | Hugging Face Spaces (Docker), Streamlit Cloud, UptimeRobot |

## ⚠️ Infrastructure Note

Because the engine is hosted on a zero-budget, free-tier architecture (Hugging Face / Streamlit / Supabase), the PostgreSQL database may occasionally hit its maximum capacity or pause due to inactivity despite UptimeRobot pings. 
* If the real-time feeds appear to halt, the Supabase instance may require a manual unpause. 
* The system is fully containerized via `Dockerfile` and ready to be ported to a dedicated AWS/GCP instance for enterprise-grade persistence.

<div align="center">
  <img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/aqua.png" width="80%">
</div>

## 💻 Local Deployment & Setup

If you want to spin up your own instance of VIta Alpha locally or on a private server, follow these steps.

### 1. Clone the Repository

![BusyWorkingGIF](https://github.com/user-attachments/assets/769f7e5e-3343-4c37-855e-ef5786676f9d)
```bash
git clone [https://github.com/yourusername/vita-alpha.git](https://github.com/yourusername/vita-alpha.git)
cd vita-alpha

2. Install Dependencies
VIta Alpha requires Python 3.9+. Install the necessary packages via the provided requirements file:

Bash
pip install -r requirements.txt

3. Configure the Engine (Secrets)
The system relies heavily on external APIs for its hybrid brain and ground-truth validation. Create a .streamlit/secrets.toml file in the root directory and inject your API keys:

Ini, TOML
# .streamlit/secrets.toml

# Database Uplink
SUPABASE_URL = "your_supabase_project_url"
SUPABASE_KEY = "your_supabase_api_key"

# Neural Engine
GROQ_API_KEY = "your_groq_llama3_key"

# Environmental Ground Truth
WEATHERAPI_KEY = "your_weatherapi_key"

# Telegram Intercepts (Optional)
TELEGRAM_SESSION = "your_telethon_string_session"

# Toggle Background Scrapers
ENABLE_WORKERS = "True"
4. Ignite the Core
Boot up the Streamlit dashboard. With ENABLE_WORKERS set to "True", the asynchronous background listeners will automatically engage to start feeding data to your database.

Bash
streamlit run app.py
(Alternatively, you can build and run the provided Dockerfile for a fully containerized deployment!)
```
<div align="center">





<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/aqua.png" width="100%">
<p><i>Engineered by Usmaan Imran. Built for scale.</i></p>
</div>
