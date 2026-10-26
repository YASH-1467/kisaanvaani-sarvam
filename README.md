# KisaanVaani — कृषि-वाणी 🌾

> **Voice-first agricultural market intelligence for 140M+ Indian smallholder farmers.**  
> Built with [Sarvam AI](https://sarvam.ai) · Indic Speech-to-Text · 105B LLM · Text-to-Speech

[![Live Demo](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://kisaanvaani-sarvam-wq5nva7d7irqhtjxmrkh4.streamlit.app)
[![Tests Passing](https://img.shields.io/badge/Tests-8%2F8%20Passed%20%E2%9C%85-green)](test_app.py)

**Live Web App:** [https://kisaanvaani-sarvam-wq5nva7d7irqhtjxmrkh4.streamlit.app](https://kisaanvaani-sarvam-wq5nva7d7irqhtjxmrkh4.streamlit.app)  
**GitHub Repository:** [https://github.com/YASH-1467/kisaanvaani-sarvam](https://github.com/YASH-1467/kisaanvaani-sarvam)

---

## 🎯 The Problem: The "Headline Price Trap"

Smallholder farmers often travel to distant terminal mandis chasing higher gross price quotes — only to lose money once freight and distance deductions are calculated. **KisaanVaani solves this by calculating the true net in-hand profit (`Price − Transport`) across all regional mandis via conversational voice in regional Indic languages.**

---

## ✨ Key Features & Innovations

| Feature | Description |
|---|---|
| 🎙️ **Voice-First Input** | Saaras v3 STT supporting Hindi, Telugu, Marathi, Punjabi, Tamil, Bengali, Gujarati & English |
| 🧠 **Multi-turn Indic AI** | Sarvam-105B Conversations with context memory for seamless follow-up questions |
| 💰 **Net Profit Optimization** | Ranks mandis by actual take-home profit rather than deceptive headline rates |
| 🚜 **Dynamic Freight Simulation** | Adjust for diesel cost spikes or farmgate distance factors (0.8x to 1.5x) |
| 📲 **WhatsApp Advisory Share** | 1-click shareable formatted advisory for village farmer groups |
| 📄 **Advisory Slip Download** | Download printable mandi receipt and advisory slip (`.txt`) |
| 📊 **7-Day Price Trends** | Interactive sparkline trends per crop and mandi |
| 🔔 **Custom Price Alerts** | Set price thresholds; receive real-time toast alerts when crossed |
| 🚚 **Hands-Free Logistics** | One-tap logistics booking with assigned buyer name and verified WhatsApp chat |
| 📋 **Mandi Inspector Portal** | Freight aggregator dashboard with KPIs and downloadable CSV manifest |
| ⚡ **Resilient Zero-Latency Fallback** | Instant script detection and fuzzy regex fallbacks ensure 100% uptime with zero credit waste |

---

## 🧠 Sarvam AI Pipeline Architecture

```
[Farmer Speaks] 
       │
       ▼
[Saaras v3 (STT)] ──> Multi-dialect audio transcription with code-mix support
       │
       ▼
[Sarvam-105B LLM] ──> Structured Intent Parsing & Canonical NER (JSON extraction)
       │
       ▼
[Net Profit Engine] ─> Price vs. Freight calculation, MSP benchmark & Buyer assignment
       │
       ▼
[Bulbul v3 (TTS)] ──> Natural regional voice audio response delivered in real-time
       │
       ▼
[Farmer Ears & WhatsApp]
```

---

## 🧪 Automated Testing

Run the full end-to-end test suite:

```bash
python3 -m unittest test_app.py
```

All 8 core integration and business logic tests pass:
- ✅ Net Profit calculation (Kanpur nets ₹60/q more than Azadpur)
- ✅ Intent extraction across noisy farmer queries
- ✅ Instant Unicode script auto-detection
- ✅ All 8 Indic translation template validations
- ✅ Live & fallback TTS audio generation

---

## 🚀 Run Locally

```bash
git clone https://github.com/YASH-1467/kisaanvaani-sarvam.git
cd kisaanvaani-sarvam
pip install -r requirements.txt

# Add your Sarvam API key
echo "SARVAM_API_KEY=your_key_here" > .env

streamlit run main.py
```

---

## ☁️ Deploy on Streamlit Community Cloud

1. Fork or push this repository to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select `YASH-1467/kisaanvaani-sarvam` and file `main.py`
4. Under **Settings → Secrets**, add:
   ```toml
   SARVAM_API_KEY = "your_actual_sarvam_key"
   ```
5. Click **Save & Deploy** 🚀

---

*Built for Sarvam Campus Hackathon, IIT Kanpur · October 2026*
