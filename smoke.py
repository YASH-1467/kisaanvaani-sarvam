import os, httpx
from dotenv import load_dotenv

load_dotenv()
h = {"api-subscription-key": os.environ["SARVAM_API_KEY"]}
c = httpx.Client(base_url="https://api.sarvam.ai", headers=h, timeout=25)

r = c.post(
    "/v1/chat/completions",
    json={
        "model": "sarvam-105b-conversations",
        "messages": [{"role": "user", "content": "गेहूं को अंग्रेज़ी में क्या कहते हैं?"}],
        "max_tokens": 50,
    },
)
print("CHAT", r.status_code, r.text[:300])

r = c.post(
    "/text-to-speech",
    json={
        "text": "नमस्ते किसान भाई",
        "target_language_code": "hi-IN",
        "model": "bulbul:v3",
        "speaker": "ritu",
    },
)
print("TTS", r.status_code, list(r.json().keys()) if r.status_code == 200 else r.text[:300])
