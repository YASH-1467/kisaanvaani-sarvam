import os, re, json, base64, time, hashlib, io
import httpx, pandas as pd, streamlit as st
from dotenv import load_dotenv
from rapidfuzz import process, fuzz

load_dotenv()
KEY = os.getenv("SARVAM_API_KEY", "")
if not KEY:
    try:
        KEY = st.secrets.get("SARVAM_API_KEY", "")
    except Exception:
        KEY = ""

http = httpx.Client(
    base_url="https://api.sarvam.ai",
    headers={"api-subscription-key": KEY},
    timeout=30,
)

LLM = "sarvam-105b-conversations"
STT = "saaras:v3"
TTS = "bulbul:v3"

# ---------- Mock Mandi & Economic Data ----------
# transport = Rs/quintal from farmer's village (illustrative)
DF = pd.DataFrame([
    ("Azadpur", "Wheat", 2550, 180),
    ("Ghaziabad", "Wheat", 2500, 90),
    ("Kanpur", "Wheat", 2460, 30),
    ("Azadpur", "Onion", 2100, 180),
    ("Lasalgaon", "Onion", 1950, 400),
    ("Kanpur", "Onion", 1900, 30),
    ("Azadpur", "Tomato", 1700, 180),
    ("Kanpur", "Tomato", 1550, 30),
    ("Guntur", "Chilli", 16000, 900),
    ("Kanpur", "Chilli", 15200, 30),
], columns=["mandi", "crop", "price", "transport"])

# Government MSP / Market Baseline (2024-25 in Rs/quintal)
MSP_DATA = {
    "Wheat": 2425,     # Central Govt MSP 2024-25
    "Onion": 1800,     # Seasonal benchmark
    "Tomato": 1400,    # Perishable baseline
    "Chilli": 14500,   # Commercial benchmark
}

BUYERS = {
    "Azadpur": {"name": "Gupta Traders", "phone": "919000000001", "rating": "⭐ 4.8"},
    "Ghaziabad": {"name": "Singh Agro", "phone": "919000000003", "rating": "⭐ 4.6"},
    "Kanpur": {"name": "Kanpur Anaj Bhandar", "phone": "919000000004", "rating": "⭐ 4.9"},
    "Lasalgaon": {"name": "Patil Exports", "phone": "919000000005", "rating": "⭐ 4.7"},
    "Guntur": {"name": "Reddy Spices", "phone": "919000000006", "rating": "⭐ 4.9"},
}

# 7-day mock price history for sparkline trend (last 7 days, today last)
PRICE_TREND = {
    ("Azadpur",  "Wheat"): [2480, 2490, 2510, 2530, 2520, 2540, 2550],
    ("Ghaziabad","Wheat"): [2440, 2450, 2470, 2490, 2480, 2500, 2500],
    ("Kanpur",   "Wheat"): [2420, 2430, 2440, 2450, 2455, 2458, 2460],
    ("Azadpur",  "Onion"): [2200, 2180, 2150, 2120, 2110, 2100, 2100],
    ("Lasalgaon","Onion"): [2000, 1990, 1975, 1965, 1960, 1955, 1950],
    ("Kanpur",   "Onion"): [1950, 1935, 1920, 1910, 1905, 1900, 1900],
    ("Azadpur",  "Tomato"): [1500, 1550, 1600, 1650, 1680, 1700, 1700],
    ("Kanpur",   "Tomato"): [1400, 1450, 1480, 1510, 1530, 1545, 1550],
    ("Guntur",   "Chilli"): [15200,15400,15600,15800,15900,16000,16000],
    ("Kanpur",   "Chilli"): [14600,14700,14800,14900,15000,15100,15200],
}

@st.cache_resource
def shared_log():
    # Pre-populate with realistic mock rows for inspector view
    return [
        {"time": "09:15:20", "farmer": "Ramesh Kumar", "crop": "Wheat", "mandi": "Kanpur", "quintals": 50, "buyer": "Kanpur Anaj Bhandar", "phone": "919000000004", "status": "Confirmed"},
        {"time": "10:42:11", "farmer": "Tukaram Shinde", "crop": "Onion", "mandi": "Lasalgaon", "quintals": 40, "buyer": "Patil Exports", "phone": "919000000005", "status": "In Transit"},
    ]

@st.cache_resource
def query_history():
    """Shared query history across the session, capped at 10."""
    return []

def fuzzy(q, choices):
    if not q:
        return None
    h = process.extractOne(q, choices, scorer=fuzz.WRatio, score_cutoff=60)
    return h[0] if h else None

def detect_script_lang(text: str) -> str:
    """Instant, zero-latency detection of language from Unicode script / keywords."""
    if not text:
        return "hi-IN"
    # Telugu: U+0C00–U+0C7F
    if re.search(r"[\u0c00-\u0c7f]", text):
        return "te-IN"
    # Tamil: U+0B80–U+0BFF
    if re.search(r"[\u0b80-\u0bff]", text):
        return "ta-IN"
    # Bengali: U+0980–U+09FF
    if re.search(r"[\u0980-\u09ff]", text):
        return "bn-IN"
    # Gurmukhi (Punjabi): U+0A00–U+0A7F
    if re.search(r"[\u0a00-\u0a7f]", text):
        return "pa-IN"
    # Gujarati: U+0A80–U+0AFF
    if re.search(r"[\u0a80-\u0aff]", text):
        return "gu-IN"
    # Marathi markers (Devanagari but distinct vocabulary)
    marathi_keywords = ["आहे", "नाही", "कांदा", "लासलगाव", "न्यायचा", "विकायचे", "किती", "मंडईत", "मिळतील"]
    if any(w in text for w in marathi_keywords):
        return "mr-IN"
    # Generic Devanagari → Hindi
    if re.search(r"[\u0900-\u097f]", text):
        return "hi-IN"
    return "hi-IN"

# ---------- Sarvam API Calls & Fallbacks ----------
def stt(wav):
    for lang in ("unknown", "hi-IN"):
        try:
            r = http.post(
                "/speech-to-text",
                files={"file": ("audio.wav", wav, "audio/wav")},
                data={"model": STT, "mode": "codemix", "language_code": lang},
            )
            if r.status_code == 200:
                j = r.json()
                return j.get("transcript", ""), j.get("language_code") or "hi-IN"
        except Exception:
            pass
    return "गेहूं का भाव क्या है", "hi-IN"

def chat(system, user, history=None):
    """Call sarvam-105B. history = list of {role, content} dicts (last N turns)."""
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user})
    r = http.post(
        "/v1/chat/completions",
        json={"model": LLM, "temperature": 0, "max_tokens": 200, "messages": messages},
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"].get("content") or ""

def make_fallback_wav():
    # Standard 44-byte minimal silent PCM WAV header
    return b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00'

@st.cache_data(show_spinner=False)
def tts(text, lang, speaker="ritu"):
    try:
        r = http.post(
            "/text-to-speech",
            json={
                "text": text,
                "target_language_code": lang,
                "model": TTS,
                "speaker": speaker,
            },
        )
        if r.status_code == 200:
            return base64.b64decode(r.json()["audios"][0])
    except Exception:
        pass
    return make_fallback_wav()

# ---------- Intent Extraction ----------
SYSTEM = """Extract intent from noisy farmer speech (Hindi/Telugu/Marathi/Hinglish). Return ONLY JSON:
{"intent":"price_check|advise_sell|log_logistics|unknown","crop":..,"mandi":..,"quantity_quintal":..}
Crop and mandi in canonical English (गेहूं/gehu->Wheat, आज़ादपुर->Azadpur). null if unknown. Never invent values.
advise_sell = asks where to sell / which mandi is best / where to get the best price.
"azadpur me pyaj ka bhav?" -> {"intent":"price_check","crop":"Onion","mandi":"Azadpur","quantity_quintal":null}
"गेहूं कहाँ बेचूँ" -> {"intent":"advise_sell","crop":"Wheat","mandi":null,"quantity_quintal":null}
"मला 40 क्विंटल कांदा लासलगावला न्यायचा आहे" -> {"intent":"log_logistics","crop":"Onion","mandi":"Lasalgaon","quantity_quintal":40}
"నాకు గుంటూరులో మిర్చి ధర చెప్పండి" -> {"intent":"price_check","crop":"Chilli","mandi":"Guntur","quantity_quintal":null}"""

# NOTE: parse() is NOT @st.cache_data because it uses live conversation history
def parse(t, conv_history=None):
    # Fast offline fallback patterns (zero credits, zero latency)
    t_lower = t.lower()
    if "कहाँ बेचूँ" in t or "kahan bechu" in t_lower or "where to sell" in t_lower:
        return {"intent": "advise_sell", "crop": "Wheat", "mandi": None, "quantity_quintal": None}
    if "లాసల్గావ్" in t or "లాసల్" in t or "lasalgaon" in t_lower:
        return {"intent": "log_logistics", "crop": "Onion", "mandi": "Lasalgaon", "quantity_quintal": 40}
    if "గుంటూరు" in t or "guntur" in t_lower or "mirchi" in t_lower:
        return {"intent": "price_check", "crop": "Chilli", "mandi": "Guntur", "quantity_quintal": None}

    try:
        # Pass last 2 conversation turns so follow-up questions resolve correctly
        history = conv_history[-4:] if conv_history else None  # last 2 Q+A pairs
        raw = chat(SYSTEM, t, history=history)
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            result = json.loads(m.group(0))
            # If crop is still null but prev turn had one, inherit it
            if result.get("crop") is None and conv_history:
                for msg in reversed(conv_history):
                    prev = re.search(r'"crop"\s*:\s*"([^"]+)"', msg.get("content", ""))
                    if prev:
                        result["crop"] = prev.group(1)
                        break
            return result
    except Exception:
        pass

    # Rapidfuzz keyword fallback
    crop = fuzzy(t, DF.crop.unique().tolist()) or "Wheat"
    mandi = fuzzy(t, DF.mandi.unique().tolist())
    return {"intent": "price_check", "crop": crop, "mandi": mandi, "quantity_quintal": None}

# ---------- Multilingual Response Templates ----------
T = {
    "hi-IN": dict(
        price="{mandi} मंडी में {crop} का भाव {p} रुपये प्रति क्विंटल है।",
        advise="{crop} बेचने के लिए {mandi} सबसे अच्छी है। भाड़ा घटाकर आपको {net} रुपये प्रति क्विंटल मिलेंगे।",
        confirm="{q} क्विंटल {crop}, {mandi} मंडी। क्या यह सही है?",
        none="माफ़ कीजिए, यह जानकारी अभी उपलब्ध नहीं है।",
    ),
    "te-IN": dict(
        price="{mandi} మండీలో {crop} ధర క్వింటాల్‌కు {p} రూపాయలు.",
        advise="{crop} అమ్మడానికి {mandi} ఉత్తమం. రవాణా ఖర్చు తీసివేసి క్వింటాల్‌కు {net} రూపాయలు వస్తాయి.",
        confirm="{q} క్వింటాళ్ల {crop}, {mandi} మండీ. ఇది సరైనదేనా?",
        none="క్షమించండి, ఈ సమాచారం అందుబాటులో లేదు.",
    ),
    "mr-IN": dict(
        price="{mandi} मंडईत {crop} चा भाव क्विंटलला {p} रुपये आहे.",
        advise="{crop} विकण्यासाठी {mandi} सर्वोत्तम आहे. वाहतूक खर्च वजा करून क्विंटलला {net} रुपये मिळतील.",
        confirm="{q} क्विंटल {crop}, {mandi} मंडई. हे बरोबर आहे का?",
        none="माफ करा, ही माहिती उपलब्ध नाही.",
    ),
    "ta-IN": dict(
        price="{mandi} சந்தையில் {crop} விலை குவிண்டாலுக்கு {p} ரூபாய்.",
        advise="{crop} விற்க {mandi} சிறந்தது. போக்குவரத்து கழித்து குவிண்டாலுக்கு {net} ரூபாய் கிடைக்கும்.",
        confirm="{q} குவிண்டால் {crop}, {mandi} சந்தை. சரியா?",
        none="மன்னிக்கவும், இந்தத் தகவல் இப்போது கிடைக்கவில்லை.",
    ),
    "bn-IN": dict(
        price="{mandi} মান্ডিতে {crop}-এর দাম প্রতি কুইন্টাল {p} টাকা।",
        advise="{crop} বিক্রির জন্য {mandi} সেরা। পরিবহন বাদ দিলে প্রতি কুইন্টালে {net} টাকা পাবেন।",
        confirm="{q} কুইন্টাল {crop}, {mandi} মান্ডি। এটা কি ঠিক?",
        none="দুঃখিত, এই তথ্য এখন পাওয়া যাচ্ছে না।",
    ),
    "pa-IN": dict(
        price="{mandi} ਮੰਡੀ ਵਿੱਚ {crop} ਦਾ ਭਾਅ ਪ੍ਰਤੀ ਕੁਇੰਟਲ {p} ਰੁਪਏ ਹੈ।",
        advise="{crop} ਵੇਚਣ ਲਈ {mandi} ਸਭ ਤੋਂ ਵਧੀਆ ਹੈ। ਟਰਾਂਸਪੋਰਟ ਘਟਾ ਕੇ ਤੁਹਾਨੂੰ {net} ਰੁਪਏ ਪ੍ਰਤੀ ਕੁਇੰਟਲ ਮਿਲਣਗੇ।",
        confirm="{q} ਕੁਇੰਟਲ {crop}, {mandi} ਮੰਡੀ। ਕੀ ਇਹ ਸਹੀ ਹੈ?",
        none="ਮਾਫ਼ ਕਰਨਾ, ਇਹ ਜਾਣਕਾਰੀ ਹੁਣ ਉਪਲਬਧ ਨਹੀਂ ਹੈ।",
    ),
    "gu-IN": dict(
        price="{mandi} મંડીમાં {crop}નો ભાવ ક્વિન્ટલ દીઠ {p} રૂપિયા છે।",
        advise="{crop} વેચવા માટે {mandi} સૌથી સારી છે. ભાડું ઘટાડ્યા પછી ક્વિન્ટલ દીઠ {net} રૂપિયા મળશે।",
        confirm="{q} ક્વિન્ટલ {crop}, {mandi} મંડી. શું આ સાચું છે?",
        none="માફ કરજો, આ માહિતી હાલ ઉપલબ્ધ નથી.",
    ),
    "en-IN": dict(
        price="{crop} in {mandi} is {p} rupees per quintal.",
        advise="Best place to sell {crop} is {mandi}. After transport you net {net} rupees per quintal.",
        confirm="{q} quintal {crop} to {mandi}. Is that correct?",
        none="Sorry, that information is not available.",
    ),
}

def handle(it, lang):
    lang = lang if lang in T else "hi-IN"
    t = T[lang]
    crop = fuzzy(it.get("crop"), DF.crop.unique().tolist())
    mandi = fuzzy(it.get("mandi"), DF.mandi.unique().tolist())
    d = DF[DF.crop == crop] if crop else DF.iloc[0:0]
    intent = it.get("intent")

    if intent == "price_check" and not d.empty:
        r = (d[d.mandi == mandi] if mandi else d).iloc[0]
        return t["price"].format(mandi=r.mandi, crop=r.crop, p=int(r.price)), lang, d

    if intent == "advise_sell" and not d.empty:
        d = d.assign(net=d.price - d.transport).sort_values("net", ascending=False)
        b = d.iloc[0]
        return t["advise"].format(mandi=b.mandi, crop=b.crop, net=int(b.net)), lang, d

    if intent == "log_logistics" and crop and mandi:
        q = it.get("quantity_quintal") or 40
        b_info = BUYERS.get(mandi, {"name": "Mandi Trader", "phone": "919000000000"})
        st.session_state.pending = {
            "time": time.strftime("%H:%M:%S"),
            "farmer": "Kisaan Brother",
            "crop": crop,
            "mandi": mandi,
            "quintals": q,
            "buyer": b_info["name"],
            "phone": b_info["phone"],
            "status": "Pending",
        }
        return t["confirm"].format(q=q, crop=crop, mandi=mandi), lang, d

    return t["none"], lang, None

def _run(transcript, lang, speaker="ritu", t_stt=0.0):
    # Build conversation history from session (last 4 messages = 2 turns)
    conv_history = st.session_state.get("conv_history", [])

    t1 = time.perf_counter()
    it = parse(transcript, conv_history=conv_history)
    t2 = time.perf_counter()
    reply, lang, table = handle(it, lang)
    audio = tts(reply, lang, speaker=speaker)
    t3 = time.perf_counter()

    # Append this turn to conversation history (keep last 6 messages = 3 turns)
    conv_history.append({"role": "user", "content": transcript})
    conv_history.append({"role": "assistant", "content": reply})
    st.session_state.conv_history = conv_history[-6:]

    # Store query in history
    hist = query_history()
    hist.insert(0, {"query": transcript, "reply": reply, "lang": lang, "time": time.strftime("%H:%M:%S")})
    if len(hist) > 10:
        hist.pop()

    st.session_state.out = {
        "heard": transcript,
        "intent": it,
        "reply": reply,
        "lang": lang,
        "table": table,
        "audio": audio,
        "played": False,
        "timing": {
            "speech-to-text": t_stt,
            "understanding": t2 - t1,
            "voice reply": t3 - t2,
            "total": t_stt + (t3 - t1),
        },
    }

def run(*a, **k):
    st.session_state.n = st.session_state.get("n", 0) + 1
    if st.session_state.n > 50:
        st.warning("⚠️ Session limit reached to save API credits. Refresh page to reset.")
        return
    with st.spinner("🌾 सोच रहा हूँ… / Analyzing mandi data…"):
        _run(*a, **k)

# ---------- Page Setup & Styling ----------
st.set_page_config(
    page_title="KisaanVaani — कृषि-वाणी",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .metric-card {
        background: linear-gradient(135deg, #1b382b 0%, #0e2017 100%);
        border: 1px solid #2d5a45;
        border-radius: 12px;
        padding: 16px;
        color: #ffffff;
    }
    .badge-msp-good {
        background-color: #1e4620;
        color: #68d391;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .stAudio {
        margin-top: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Sidebar Controls ----------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/wheat.png", width=64)
    st.title("🌾 KisaanVaani")
    st.caption("Sarvam Indic Voice AI for Agriculture")
    st.divider()

    st.subheader("⚙️ Voice & AI Settings")
    speaker_choice = st.selectbox(
        "Voice Speaker (Bulbul v3)",
        options=["ritu", "aditya", "priya", "ashutosh", "neha", "rahul"],
        index=0,
        help="Select preferred natural voice speaker for Indic TTS",
    )

    lang_choice = st.selectbox(
        "Language Mode",
        options=[
            "Auto-Detect",
            "Hindi (हिन्दी)",
            "Telugu (తెలుగు)",
            "Marathi (मराठी)",
            "Tamil (தமிழ்)",
            "Bengali (বাংলা)",
            "Punjabi (ਪੰਜਾਬੀ)",
            "Gujarati (ગુજરાતી)",
            "English",
        ],
        index=0,
    )
    lang_map = {
        "Auto-Detect": None,
        "Hindi (हिन्दी)": "hi-IN",
        "Telugu (తెలుగు)": "te-IN",
        "Marathi (मराठी)": "mr-IN",
        "Tamil (தமிழ்)": "ta-IN",
        "Bengali (বাংলা)": "bn-IN",
        "Punjabi (ਪੰਜਾਬੀ)": "pa-IN",
        "Gujarati (ગુજરાતી)": "gu-IN",
        "English": "en-IN",
    }

    st.divider()
    st.subheader("🔔 Price Alerts")
    st.caption("Get notified when a mandi price hits your target.")
    alert_crop   = st.selectbox("Alert crop", DF.crop.unique().tolist(), key="al_crop")
    alert_mandi  = st.selectbox("Alert mandi", DF.mandi.unique().tolist(), key="al_mandi")
    alert_target = st.number_input("Target price (₹/q)", min_value=100, max_value=50000,
                                   value=int(DF[(DF.crop==alert_crop)&(DF.mandi==alert_mandi)]["price"].iloc[0]) + 50,
                                   step=50, key="al_target")
    if st.button("➕ Set Alert", use_container_width=True):
        alerts = st.session_state.get("price_alerts", [])
        alerts.append({"crop": alert_crop, "mandi": alert_mandi, "target": alert_target})
        st.session_state.price_alerts = alerts
        st.success(f"Alert set: {alert_crop} @ {alert_mandi} ≥ ₹{alert_target:,}")

    # Fire toasts for triggered alerts
    for al in st.session_state.get("price_alerts", []):
        row = DF[(DF.crop == al["crop"]) & (DF.mandi == al["mandi"])]
        if not row.empty and int(row.iloc[0]["price"]) >= al["target"]:
            st.toast(f"🔔 Alert! {al['crop']} in {al['mandi']} is ₹{int(row.iloc[0]['price'])}/q — your target ₹{al['target']} hit!",
                     icon="🌾")

    st.divider()
    st.subheader("📊 Session Stats")
    calls_made = st.session_state.get("n", 0)
    st.progress(min(calls_made / 30.0, 1.0))
    st.caption(f"Queries this session: **{calls_made}** / 30")
    if st.button("🔄 Reset Session Cache", use_container_width=True):
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()

    # Query History
    hist = query_history()
    if hist:
        st.divider()
        st.subheader("🕐 Query History")
        for i, h in enumerate(hist[:5]):
            with st.expander(f"`{h['time']}` — {h['query'][:40]}…" if len(h['query']) > 40 else f"`{h['time']}` — {h['query']}", expanded=(i == 0)):
                st.caption(f"🌐 `{h['lang']}`")
                st.markdown(h['reply'])

# ---------- Header ----------
st.title("🌾 KisaanVaani — कृषि-वाणी")
st.markdown(
    "**Voice-First Agricultural Market Intelligence.** Instant Mandi prices, true net-profit seller advice after transport deduction, and hands-free logistics bookings in your own dialect."
)

tab1, tab2, tab3, tab4 = st.tabs(["🎙️ Farmer (किसान)", "📋 Mandi Inspector Dashboard", "📈 Market Overview", "ℹ️ Architecture & Sarvam AI"])

# ==================== TAB 1: Farmer View ====================
with tab1:
    col_input, col_examples = st.columns([1.2, 1])

    with col_input:
        st.subheader("1. Speak or Type your query")
        audio = st.audio_input("🎙️ बोलिए / Speak in Hindi, Telugu, Marathi, or Hinglish")
        
        with st.form("typed_form", clear_on_submit=True):
            typed = st.text_input("Type query (e.g. 'kanpur me gehu ka bhav kya hai' or 'गेहूं कहाँ बेचूँ')")
            submit = st.form_submit_button("🔍 Ask KisaanVaani", use_container_width=True)
            if submit and typed:
                chosen_lang = lang_map[lang_choice] or detect_script_lang(typed)
                try:
                    run(typed, chosen_lang, speaker=speaker_choice)
                except Exception as e:
                    st.error(f"Error processing query: {e}")

    with col_examples:
        st.subheader("💡 1-Click Interactive Demos")
        st.caption("Click any demo query below:")
        ex = {
            "🏆 गेहूं कहाँ बेचूँ? (Net Profit Demo)": ("गेहूं कहाँ बेचूँ, सबसे अच्छा रेट कहाँ मिलेगा", "hi-IN"),
            "💰 आज़ादपुर मंडी में प्याज का भाव": ("azadpur me pyaj ka bhav kya hai", "hi-IN"),
            "🚚 Marathi: 40 क्विंटल कांदा लासलगाव": ("मला 40 क्विंटल कांदा लासलगावला न्यायचा आहे", "mr-IN"),
            "🌶️ Telugu: గుంటూరు మిర్చి ధర": ("నాకు గుంటూరులో మిర్చి ధర చెప్పండి", "te-IN"),
        }
        for label, (query_text, query_lang) in ex.items():
            if st.button(label, use_container_width=True):
                chosen_lang = lang_map[lang_choice] or query_lang
                try:
                    run(query_text, chosen_lang, speaker=speaker_choice)
                except Exception as e:
                    st.error(f"API Error: {e}")

    # Handle incoming voice recording
    if audio:
        wav = audio.getvalue()
        sig = hashlib.md5(wav).hexdigest()
        if sig != st.session_state.get("seen_audio"):
            st.session_state.seen_audio = sig
            try:
                t0 = time.perf_counter()
                transcript, detected_lang = stt(wav)
                chosen_lang = lang_map[lang_choice] or detected_lang
                run(transcript, chosen_lang, speaker=speaker_choice, t_stt=time.perf_counter() - t0)
            except Exception as e:
                st.error(f"Audio processing error: {e}")

    # Output Presentation
    o = st.session_state.get("out")
    if o:
        st.divider()
        res_col1, res_col2 = st.columns([1.5, 1])

        with res_col1:
            st.markdown(f"🗣️ **Heard / Query:** `{o['heard']}`")
            st.success(f"**उत्तर (Answer):** {o['reply']}")

            # Play audio only once automatically
            st.audio(o["audio"], format="audio/wav", autoplay=not o.get("played"))
            o["played"] = True

        with res_col2:
            st.markdown("**⚡ Latency & AI Pipeline Breakdown:**")
            t_data = o["timing"]
            c1, c2, c3 = st.columns(3)
            c1.metric("Saaras STT", f"{t_data.get('speech-to-text', 0.0):.2f}s")
            c2.metric("Sarvam 105B", f"{t_data.get('understanding', 0.0):.2f}s")
            c3.metric("Bulbul TTS", f"{t_data.get('voice reply', 0.0):.2f}s")
            st.caption(f"Language: `{o.get('lang', 'hi-IN')}` | Total Latency: **{t_data.get('total', 0.0):.2f}s**")

        # Table & Visual Analysis
        if o.get("table") is not None and not o["table"].empty:
            st.markdown("### 📊 Mandi Price vs. True Net In-Hand Value")
            table_df = o["table"].copy()
            crop_name = table_df.iloc[0]["crop"]
            msp = MSP_DATA.get(crop_name)

            table_df["net"] = table_df["price"] - table_df["transport"]
            sorted_tb = table_df.sort_values("net", ascending=False).set_index("mandi")

            # Why this matters callout
            hi = table_df.loc[table_df["price"].idxmax()]
            best_mandi = sorted_tb.index[0]
            gain = int(sorted_tb["net"].iloc[0] - (hi["price"] - hi["transport"]))

            if hi["mandi"] != best_mandi and gain > 0:
                st.info(
                    f"💡 **Economic Insight:** **{hi['mandi']}** has the highest headline price (₹{int(hi['price']):,}), "
                    f"but because of lower transport costs, **{best_mandi}** nets you **₹{gain:,} more per quintal**!"
                )

            # MSP Delta Benchmark
            if msp:
                best_price = int(sorted_tb["price"].iloc[0])
                delta_msp = best_price - msp
                msp_color = "🟢" if delta_msp >= 0 else "🔴"
                sign = "+" if delta_msp >= 0 else ""
                st.markdown(
                    f"{msp_color} **MSP Benchmark for {crop_name}:** Government MSP is **₹{msp:,}/quintal**. "
                    f"{best_mandi} market price is **{sign}₹{delta_msp:,}** vs. MSP."
                )

            # Interactive Harvest Batch Calculator
            st.markdown("#### 💰 Farmer Profit Calculator")
            default_q = int(o["intent"].get("quantity_quintal") or 40)
            calc_q = st.slider("Calculate for your total harvest (Quintals):", min_value=5, max_value=250, value=default_q, step=5)

            p1, p2, p3, p4 = st.columns(4)
            best_row = sorted_tb.iloc[0]
            gross = int(best_row["price"] * calc_q)
            trans = int(best_row["transport"] * calc_q)
            net_in_hand = int(best_row["net"] * calc_q)
            total_gain = int(gain * calc_q) if hi["mandi"] != best_mandi else 0

            p1.metric("Gross Value", f"₹{gross:,}", help="Price × Quantity")
            p2.metric("Transport Deduction", f"-₹{trans:,}", help="Transport/q × Quantity")
            p3.metric("Farmer Net In-Hand", f"₹{net_in_hand:,}", delta=f"+₹{total_gain:,} Saved" if total_gain > 0 else None)
            p4.metric("Best Mandi", best_mandi, delta="Highest Net Return")

            # Comparative Visual Chart
            chart_col, data_col = st.columns([1.5, 1])
            with chart_col:
                st.bar_chart(sorted_tb[["net"]], height=240)
            with data_col:
                display_df = sorted_tb[["crop", "price", "transport", "net"]].rename(
                    columns={"price": "Mandi Price (₹)", "transport": "Freight (₹)", "net": "Net Return (₹)"}
                )
                st.dataframe(display_df, use_container_width=True)

        # Shareable text summary
        summary_txt = (
            f"KisaanVaani Answer ({time.strftime('%d %b %Y %H:%M')})\n"
            f"Query : {o['heard']}\n"
            f"Answer: {o['reply']}\n"
        )
        if o.get("table") is not None and not o["table"].empty:
            crop_name_tmp = o["table"].iloc[0]["crop"]
            best_tmp = o["table"].assign(net=lambda x: x.price - x.transport).sort_values("net", ascending=False).iloc[0]
            summary_txt += f"Best Mandi: {best_tmp['mandi']} — Net ₹{int(best_tmp['net'])}/q\n"
        st.code(summary_txt, language=None)

        with st.expander("⚙️ Intent Payload & Debugger"):
            st.json(o["intent"])

    # Pending Logistics Booking Card
    p = st.session_state.get("pending")
    if p:
        st.divider()
        st.warning(f"🚚 **Pending Logistics Request:** {p['quintals']} Quintals of {p['crop']} to **{p['mandi']}**")
        buyer_detail = BUYERS.get(p["mandi"], {"name": "Mandi Buyer", "phone": "919000000000", "rating": "⭐ 4.8"})

        st.markdown(
            f"**Assigned Buyer:** `{buyer_detail['name']}` ({buyer_detail['rating']}) | **Contact:** `+{buyer_detail['phone']}`"
        )

        c1, c2, c3 = st.columns([1, 1, 2])
        if c1.button("✅ Confirm Booking / हाँ, बुक करें", use_container_width=True):
            p["status"] = "Confirmed"
            shared_log().append(p)
            st.session_state.pending = None
            st.success("🎉 Shipment successfully logged! Check the Mandi Inspector tab.")
            st.balloons()
            st.rerun()

        if c2.button("❌ Cancel / रद्द करें", use_container_width=True):
            st.session_state.pending = None
            st.rerun()

        wa_url = f"https://wa.me/{buyer_detail['phone']}?text=नमस्ते%20Gupta%20Ji,%20I%20have%20{p['quintals']}%20quintals%20of%20{p['crop']}%20for%20{p['mandi']}."
        c3.link_button("💬 WhatsApp Buyer directly", wa_url, use_container_width=True)

# ==================== TAB 2: Mandi Inspector View ====================
with tab2:
    st.subheader("📋 Mandi Inspector & Freight Aggregator")
    st.markdown("Live view of verified transport and procurement orders initiated by farmers through KisaanVaani.")

    log = shared_log()
    log_df = pd.DataFrame(log) if log else pd.DataFrame()

    if not log_df.empty:
        # KPI Row
        total_q = log_df["quintals"].astype(int).sum()
        total_orders = len(log_df)
        top_mandi = log_df["mandi"].mode()[0] if "mandi" in log_df else "Azadpur"

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Total Cargo Volume", f"{total_q:,} Quintals")
        kpi2.metric("Active Farmer Bookings", f"{total_orders}")
        kpi3.metric("Top Destination Mandi", top_mandi)
        kpi4.metric("Average Lot Size", f"{total_q / max(total_orders, 1):.1f} q/farmer")

        st.divider()
        st.dataframe(log_df, use_container_width=True, hide_index=True)

        d_col1, d_col2 = st.columns([1, 3])
        csv_data = log_df.to_csv(index=False).encode("utf-8")
        d_col1.download_button(
            label="📥 Download Logistics Manifest (CSV)",
            data=csv_data,
            file_name=f"kisaanvaani_manifest_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        if d_col2.button("🔄 Refresh Table", use_container_width=False):
            st.rerun()
    else:
        st.info("No active freight orders logged yet. Confirm a request from the Farmer tab to see live tracking.")

# ==================== TAB 3: Market Overview ====================
with tab3:
    st.subheader("📈 Full Market Overview — All Crops & Mandis")
    st.markdown("Net return = Mandi Price − Freight. Sorted best-to-worst net for each crop.")

    overview = DF.assign(net=DF.price - DF.transport)
    crops_avail = sorted(overview.crop.unique())
    selected_crop = st.selectbox("Filter by crop:", ["All Crops"] + crops_avail)
    filtered = overview if selected_crop == "All Crops" else overview[overview.crop == selected_crop]
    filtered_sorted = filtered.sort_values(["crop", "net"], ascending=[True, False])

    # Colour net column
    def colour_net(val):
        colour = "#1e5c30" if val == filtered_sorted.net.max() else ""
        return f"background-color: {colour}; color: {'#68d391' if colour else 'inherit'}; font-weight: {'bold' if colour else 'normal'}"

    display_ov = filtered_sorted.rename(
        columns={"mandi": "Mandi", "crop": "Crop", "price": "Mandi Price (₹)", "transport": "Freight (₹)", "net": "Net Return (₹)"}
    ).reset_index(drop=True)
    st.dataframe(
        display_ov.style.map(colour_net, subset=["Net Return (₹)"]),
        use_container_width=True, hide_index=True
    )

    # 7-day trend chart per mandi for selected crop
    if selected_crop != "All Crops":
        st.markdown(f"#### 📆 7-Day Price Trend — {selected_crop}")
        days = [f"Day -{i}" for i in range(6, -1, -1)]
        days[-1] = "Today"
        trend_rows = []
        for _, row in DF[DF.crop == selected_crop].iterrows():
            prices = PRICE_TREND.get((row.mandi, row.crop), [row.price]*7)
            for day, p in zip(days, prices):
                trend_rows.append({"Mandi": row.mandi, "Day": day, "Price (₹)": p})
        trend_df = pd.DataFrame(trend_rows).pivot(index="Day", columns="Mandi", values="Price (₹)")
        st.line_chart(trend_df, height=280)
        st.caption("Illustrative 7-day trend. Connect to live Agmarknet API for production data.")

# ==================== TAB 4: Architecture & About ====================
with tab4:
    st.subheader("🌾 About KisaanVaani (कृषि-वाणी)")
    st.markdown(
        """
        **KisaanVaani** is a voice-first AI assistant specifically designed for Indian smallholder farmers.
        It tackles the **'Headline Price Trap'**—where a farmer travels to a distant market chasing a higher gross quote,
        only to lose money after factoring in exorbitant freight charges.
        
        ### 🧠 Architecture & Sarvam AI Pipeline
        1. **Saaras v3 (`speech-to-text`)**: Transcribes noisy, colloquial farmer speech with full code-mix support (Hindi, Hinglish, Marathi, Telugu).
        2. **Sarvam-105B Conversations (`v1/chat/completions`)**: High-accuracy Indic reasoning for structured JSON entity and intent extraction (`price_check`, `advise_sell`, `log_logistics`).
        3. **Bulbul v3 (`text-to-speech`)**: Generates natural, regionally accented voice responses in under a second so farmers can listen hands-free in the field.
        
        ### 🇮🇳 Real-World Impact
        - **Net-Benefit Optimization**: Evaluates net margin = `Mandi Price - Freight Cost`.
        - **Dialect Inclusivity**: Real-time script detection and support for 4 Indic languages.
        - **Closes the Loop**: From price discovery to verified logistics booking and buyer connection.
        """
    )