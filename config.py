"""
Konfigurasi kreatif chatbot "Jalan-Jalan Buddy".
Semua parameter kreatif (gaya bahasa, domain, fitur tambahan) ada di sini,
jadi mudah diubah tanpa menyentuh logika aplikasi.
"""

# ---------- Identitas & use case ----------
BOT_NAME = "Jalan-Jalan Buddy"
USE_CASE = "Travel Assistant"
DOMAIN = "Wisata domestik Indonesia (destinasi, itinerary, budget, kuliner, cuaca)"

# ---------- Gaya bahasa (parameter kreatif #1) ----------
DEFAULT_STYLE = "santai"  # "santai" atau "formal"
STYLES = {
    "santai": (
        "Gunakan bahasa Indonesia santai dan ramah seperti teman yang suka traveling "
        "(boleh pakai 'kamu', 'banget', 'yuk'). Sisipkan emoji secukupnya (maks 2-3 per jawaban)."
    ),
    "formal": (
        "Gunakan bahasa Indonesia formal, sopan, dan profesional (gunakan 'Anda'). "
        "Jangan gunakan emoji maupun bahasa gaul."
    ),
}

# ---------- Fitur tambahan (parameter kreatif #2, #3, #4) ----------
FEATURES = {
    "weather_api": True,       # integrasi API eksternal: Open-Meteo (gratis, tanpa API key)
    "memory": True,            # chatbot mengingat nama, kota asal, budget, minat
    "recommendations": True,   # chip saran pertanyaan lanjutan
}

# ---------- Parameter model ----------
MODEL_SETTINGS = {
    "temperature": 0.8,        # lebih tinggi = lebih kreatif
    "max_tokens": 700,
    "history_turns": 8,        # jumlah pesan terakhir yang dikirim ke model
}

# Model default per provider (bisa dioverride lewat .env)
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4o-mini",   # atau model lain di endpoint OpenAI-compatible (Gemini, Groq, dll.)
}


def build_system_prompt(style: str, profile: dict, weather_text: str | None) -> str:
    """Menyusun system prompt dari semua parameter kreatif di atas."""
    parts = [
        f"Kamu adalah {BOT_NAME}, sebuah {USE_CASE} berbasis AI.",
        f"Domain pengetahuanmu: {DOMAIN}.",
        STYLES.get(style, STYLES[DEFAULT_STYLE]),
        "Aturan:",
        "- Jawab ringkas, jelas, dan relevan dengan pertanyaan pengguna (maks sekitar 180 kata).",
        "- Untuk itinerary, tulis per hari dengan poin-poin singkat dan perkiraan biaya bila relevan.",
        "- Jika pertanyaan di luar topik wisata, jawab singkat lalu arahkan kembali ke topik traveling.",
        "- Jangan mengarang harga/jam buka pasti; sebut sebagai perkiraan dan sarankan cek ulang.",
    ]
    if FEATURES["memory"] and profile:
        info = "; ".join(f"{k}: {v}" for k, v in profile.items() if v)
        if info:
            parts.append(f"Yang kamu ketahui tentang pengguna (gunakan secara natural): {info}.")
    if FEATURES["weather_api"] and weather_text:
        parts.append(
            "Data cuaca real-time dari API (gunakan sebagai dasar saran, jangan diubah): "
            + weather_text
        )
    if FEATURES["recommendations"]:
        parts.append(
            "Di baris TERAKHIR jawabanmu, tulis tepat satu baris dengan format:\n"
            "SARAN: pertanyaan lanjutan 1 | pertanyaan lanjutan 2 | pertanyaan lanjutan 3\n"
            "(pertanyaan singkat yang mungkin ingin ditanyakan pengguna selanjutnya, sudut pandang pengguna)."
        )
    return "\n".join(parts)
