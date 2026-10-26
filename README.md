# KisaanVaani — कृषि-वाणी 🌾

> **Voice-first agricultural market intelligence for 140M+ Indian smallholder farmers.**  
> Built with [Sarvam AI](https://sarvam.ai) · Indic Speech-to-Text · 105B LLM · Text-to-Speech

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://kisaanvaani-sarvam.streamlit.app)

---

## 🎯 Problem

Farmers travel to distant mandis chasing a high headline price — only to lose money after freight costs. **KisaanVaani solves this with voice-first, dialect-aware AI.**

## ✨ Features

| Feature | Detail |
|---|---|
| 🎙️ **Voice Input** | Saaras v3 STT — Hindi, Telugu, Marathi, Tamil, Bengali, Punjabi, Gujarati, English |
| 🧠 **Multi-turn AI** | Sarvam-105B with conversation memory (follow-up questions work) |
| 💰 **Net Profit Advisor** | Computes `Mandi Price − Freight` across all mandis, not just headline price |
| 📊 **7-day Price Trends** | Sparkline chart per crop/mandi |
| 🔔 **Price Alerts** | Set a target price; get toast notification when crossed |
| 🚚 **Logistics Booking** | Farmer confirms dispatch; inspector dashboard tracks it |
| 💬 **WhatsApp Buyer Link** | One-tap direct buyer contact |
| 📥 **CSV Export** | Mandi inspector downloads full freight manifest |
| 🌏 **8 Languages** | hi-IN · te-IN · mr-IN · ta-IN · bn-IN · pa-IN · gu-IN · en-IN |

## 🧠 Sarvam AI Stack

```
Farmer Voice → Saaras v3 (STT) → Sarvam-105B (Intent + NER) → Bulbul v3 (TTS) → Farmer Ears
```

## 🚀 Run Locally

```bash
git clone https://github.com/YOUR_USERNAME/kisaanvaani-sarvam.git
cd kisaanvaani-sarvam
pip install -r requirements.txt

# Add your Sarvam API key
echo "SARVAM_API_KEY=your_key_here" > .env

streamlit run main.py
```

## ☁️ Deploy on Streamlit Community Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select `main.py` as the entry point
4. Under **Advanced → Secrets**, add:
   ```toml
   SARVAM_API_KEY = "your_sarvam_api_key"
   ```
5. Click **Deploy** 🚀

## 📁 Project Structure

```
kisaanvaani-sarvam/
├── main.py          # Full Streamlit application
├── smoke.py         # API connectivity smoke tests
├── requirements.txt # Python dependencies
└── .gitignore       # Excludes .env and secrets
```

## 🌾 Impact

- **Net-benefit optimization**: Evaluates true farmer take-home across mandis
- **Dialect inclusivity**: Real-time Unicode script detection for 8 Indic languages  
- **Closes the loop**: Price discovery → logistics booking → buyer contact

---

*Built for Sarvam Campus Hackathon, IIT Kanpur · October 2026*
