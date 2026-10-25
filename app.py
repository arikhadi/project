"""
Jalan-Jalan Buddy - chatbot Travel Assistant berbasis LLM.
Jalankan:  python app.py   lalu buka http://localhost:5000
"""
import json
import os
import re
import threading
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

import config

try:  # opsional: baca file .env bila python-dotenv terpasang
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
MEMORY_FILE = BASE_DIR / "memory.json"
_lock = threading.Lock()

PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()   # anthropic | openai
API_KEY = os.getenv("LLM_API_KEY", "").strip()
MODEL = os.getenv("LLM_MODEL") or config.DEFAULT_MODELS.get(PROVIDER, "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")


# ======================================================================
# MEMORY (parameter kreatif: fitur memory)
# ======================================================================
def load_store() -> dict:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_store(store: dict) -> None:
    MEMORY_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def get_session(store: dict, sid: str) -> dict:
    return store.setdefault(sid, {"profile": {}, "history": []})


def update_profile(profile: dict, text: str) -> None:
    """Ekstrak fakta sederhana dari pesan pengguna (rule-based, ringan & transparan)."""
    t = text.strip()
    m = re.search(r"\b(?:nama (?:saya|aku)|namaku)\s+(?:adalah\s+)?([A-Za-z]{2,20})", t, re.I)
    if m:
        profile["nama"] = m.group(1).capitalize()
    m = re.search(r"\b(?:dari|asal(?:ku)?(?: dari)?|tinggal di)\s+([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?)", t)
    if m:
        profile["kota asal"] = m.group(1)
    m = re.search(r"budget[^\d]{0,15}(\d+(?:[.,]\d+)?)\s*(juta|jt|ribu|rb|k)?", t, re.I)
    if m:
        profile["budget"] = f"{m.group(1)} {m.group(2) or ''}".strip()
    m = re.search(r"\b(?:suka|hobi(?:ku)?|senang)\s+([a-z ,]{3,40})", t, re.I)
    if m:
        minat = m.group(1).strip(" ,.")
        old = profile.get("minat", "")
        profile["minat"] = (old + ", " + minat) if old and minat not in old else (old or minat)


# ======================================================================
# API EKSTERNAL: Open-Meteo (gratis, tanpa API key)
# ======================================================================
WMO = {0: "cerah", 1: "cerah berawan", 2: "berawan sebagian", 3: "mendung",
       45: "berkabut", 48: "berkabut", 51: "gerimis", 53: "gerimis", 55: "gerimis lebat",
       61: "hujan ringan", 63: "hujan sedang", 65: "hujan lebat", 80: "hujan lokal",
       81: "hujan lokal sedang", 82: "hujan lokal lebat", 95: "badai petir", 96: "badai petir", 99: "badai petir"}

KNOWN_PLACES = ["jakarta", "bandung", "yogyakarta", "jogja", "semarang", "surabaya", "malang", "bali",
                "denpasar", "ubud", "lombok", "labuan bajo", "medan", "danau toba", "padang", "bukittinggi",
                "palembang", "makassar", "manado", "bunaken", "raja ampat", "solo", "bogor", "banyuwangi",
                "bromo", "dieng", "karimunjawa", "belitung", "lampung", "samosir", "batam", "pontianak",
                "balikpapan", "banda aceh", "sabang", "flores", "komodo", "toraja"]


def detect_place(text: str) -> str | None:
    low = text.lower()
    for p in sorted(KNOWN_PLACES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(p)}\b", low):
            return "Yogyakarta" if p == "jogja" else p.title()
    m = re.search(r"\b(?:ke|di|sekitar|menuju)\s+([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?)", text)
    return m.group(1) if m else None


def get_weather(place: str) -> dict | None:
    try:
        g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": place, "count": 1, "language": "id", "country_code": "ID"}, timeout=6)
        res = (g.json().get("results") or [])
        if not res:
            return None
        loc = res[0]
        w = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": loc["latitude"], "longitude": loc["longitude"],
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "timezone": "auto", "forecast_days": 3}, timeout=6).json()
        cur, daily = w["current"], w["daily"]
        days = []
        for i, d in enumerate(daily["time"]):
            days.append({"tanggal": d, "kondisi": WMO.get(daily["weather_code"][i], "tidak diketahui"),
                         "min": daily["temperature_2m_min"][i], "max": daily["temperature_2m_max"][i],
                         "hujan": daily["precipitation_probability_max"][i]})
        return {"lokasi": f'{loc["name"]}, {loc.get("admin1", "")}'.strip(", "),
                "sekarang": {"suhu": cur["temperature_2m"], "kondisi": WMO.get(cur["weather_code"], "tidak diketahui"),
                             "angin": cur["wind_speed_10m"]},
                "prakiraan": days}
    except Exception:
        return None


def weather_to_text(w: dict) -> str:
    s = w["sekarang"]
    txt = f'{w["lokasi"]}: sekarang {s["suhu"]}°C, {s["kondisi"]}, angin {s["angin"]} km/j. Prakiraan: '
    txt += "; ".join(f'{d["tanggal"]} {d["kondisi"]} {d["min"]}-{d["max"]}°C, peluang hujan {d["hujan"]}%'
                     for d in w["prakiraan"])
    return txt


# ======================================================================
# LLM
# ======================================================================
def call_llm(system: str, messages: list[dict]) -> str:
    ms = config.MODEL_SETTINGS
    if PROVIDER == "anthropic":
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": MODEL, "max_tokens": ms["max_tokens"], "temperature": min(ms["temperature"], 1.0),
                  "system": system, "messages": messages},
            timeout=60)
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")
    # OpenAI-compatible (OpenAI, Gemini endpoint OpenAI-compat, Groq, OpenRouter, dll.)
    r = requests.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "content-type": "application/json"},
        json={"model": MODEL, "temperature": ms["temperature"], "max_tokens": ms["max_tokens"],
              "messages": [{"role": "system", "content": system}] + messages},
        timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def demo_reply(message: str, style: str, profile: dict, weather: dict | None) -> str:
    """Balasan sederhana bila API key belum diisi, agar UI tetap bisa dicoba."""
    santai = style == "santai"
    nama = profile.get("nama")
    sapa = (f"Halo {nama}! " if santai else f"Halo {nama}. ") if nama else ("Halo! " if santai else "Selamat datang. ")
    body = ("Ini mode demo (API key belum diisi), jadi aku belum bisa menjawab secara cerdas. "
            if santai else "Saat ini berjalan dalam mode demo karena API key belum diisi. ")
    if weather:
        s = weather["sekarang"]
        body += (f"Tapi aku sudah ambil cuaca {weather['lokasi']}: {s['suhu']}°C, {s['kondisi']}. "
                 if santai else f"Data cuaca {weather['lokasi']}: {s['suhu']}°C, {s['kondisi']}. ")
    body += "Isi LLM_API_KEY di file .env untuk mengaktifkan AI sepenuhnya."
    return (sapa + body +
            "\nSARAN: Buatkan itinerary 3 hari di Yogyakarta | Kuliner khas Bandung apa saja? | Tips wisata hemat ke Bali")


# ======================================================================
# ROUTES
# ======================================================================
SARAN_RE = re.compile(r"\n?\s*SARAN\s*:\s*(.+)\s*$", re.I)


def split_suggestions(text: str) -> tuple[str, list[str]]:
    m = SARAN_RE.search(text)
    if not m:
        return text.strip(), []
    sug = [s.strip(" -•*") for s in m.group(1).split("|") if s.strip()][:3]
    return text[:m.start()].strip(), sug


@app.get("/")
def index():
    return render_template("index.html", bot_name=config.BOT_NAME, use_case=config.USE_CASE)


@app.get("/api/config")
def api_config():
    return jsonify({"bot_name": config.BOT_NAME, "use_case": config.USE_CASE, "domain": config.DOMAIN,
                    "default_style": config.DEFAULT_STYLE, "styles": list(config.STYLES),
                    "features": config.FEATURES, "demo_mode": not API_KEY,
                    "provider": PROVIDER, "model": MODEL})


@app.post("/api/chat")
def api_chat():
    data = request.get_json(force=True)
    sid = (data.get("session_id") or "default")[:64]
    message = (data.get("message") or "").strip()
    style = data.get("style") if data.get("style") in config.STYLES else config.DEFAULT_STYLE
    if not message:
        return jsonify({"error": "Pesan kosong."}), 400

    with _lock:
        store = load_store()
        sess = get_session(store, sid)
        if config.FEATURES["memory"]:
            update_profile(sess["profile"], message)
        profile = dict(sess["profile"])
        history = sess["history"][-config.MODEL_SETTINGS["history_turns"]:]

    weather = None
    if config.FEATURES["weather_api"]:
        place = detect_place(message)
        if place and re.search(r"cuaca|hujan|panas|suhu|musim|itinerary|liburan|wisata|jalan|trip|weekend|besok|minggu", message, re.I):
            weather = get_weather(place)

    try:
        if API_KEY:
            system = config.build_system_prompt(style, profile, weather_to_text(weather) if weather else None)
            raw = call_llm(system, history + [{"role": "user", "content": message}])
        else:
            raw = demo_reply(message, style, profile, weather)
    except requests.HTTPError as e:
        return jsonify({"error": f"Gagal memanggil model ({e.response.status_code}). Periksa API key / nama model di .env."}), 502
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"Terjadi kesalahan: {e}"}), 500

    reply, suggestions = split_suggestions(raw)
    if not config.FEATURES["recommendations"]:
        suggestions = []

    with _lock:
        store = load_store()
        sess = get_session(store, sid)
        sess["profile"] = profile
        sess["history"] += [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
        sess["history"] = sess["history"][-40:]
        save_store(store)

    return jsonify({"reply": reply, "suggestions": suggestions, "weather": weather, "profile": profile})


@app.get("/api/memory")
def api_memory():
    sid = request.args.get("session_id", "default")
    return jsonify(get_session(load_store(), sid)["profile"])


@app.post("/api/reset")
def api_reset():
    sid = (request.get_json(force=True).get("session_id") or "default")
    with _lock:
        store = load_store()
        store.pop(sid, None)
        save_store(store)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
