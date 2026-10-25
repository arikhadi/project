# Jalan-Jalan Buddy 🧭
Chatbot **Travel Assistant** berbasis AI (LLM) untuk wisata domestik Indonesia.
Dibuat untuk tugas: *chatbot AI dengan use case dan konfigurasi parameter sesuai kreativitas masing-masing.*

## Use case
Travel assistant yang membantu pengguna merencanakan perjalanan: itinerary, estimasi budget,
kuliner, tips hemat, dan saran berdasarkan cuaca tujuan.

## Parameter kreatif yang diimplementasikan
| Parameter | Implementasi |
|---|---|
| **Gaya bahasa** | Toggle *Santai / Formal* di UI; mengubah system prompt (`config.py` → `STYLES`) |
| **Domain pengetahuan** | Wisata domestik Indonesia; pertanyaan di luar topik diarahkan kembali (`config.py` → `DOMAIN`) |
| **Integrasi API eksternal** | **Open-Meteo** (gratis, tanpa API key): cuaca saat ini + prakiraan 3 hari, otomatis dipakai jika pengguna menyebut kota/destinasi |
| **Memory** | Menyimpan nama, kota asal, budget, minat per sesi di `memory.json`, tampil di panel "Memori" |
| **Rekomendasi** | Setelah tiap jawaban, model menghasilkan 3 saran pertanyaan lanjutan (chip yang bisa diklik) |

Semua fitur bisa dimatikan/dihidupkan lewat `FEATURES` di `config.py`.

## Model AI
Menggunakan LLM lewat API (NLP alami → respons relevan). Dua provider didukung:
- `anthropic` (default, model `claude-sonnet-5-5`)
- `openai` — endpoint OpenAI-compatible (OpenAI, Gemini, Groq, OpenRouter, dll.)

Tanpa API key, aplikasi berjalan di **mode demo** agar UI tetap bisa dicoba.

## Cara menjalankan
```bash
cd jalan-jalan-buddy
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # Windows: copy .env.example .env
# edit .env → isi LLM_API_KEY (dan LLM_PROVIDER bila perlu)

python app.py
```
Buka http://localhost:5000

## Struktur project
```
jalan-jalan-buddy/
├── app.py              # backend Flask: routing, memory, API cuaca, pemanggilan LLM
├── config.py           # semua parameter kreatif + penyusun system prompt
├── templates/index.html# antarmuka chat (HTML/CSS/JS tanpa framework)
├── requirements.txt
├── .env.example
└── README.md
```

## Alur kerja
1. Pengguna mengirim pesan → backend memperbarui **memory** (nama, budget, dst.).
2. Jika ada nama kota/destinasi → ambil **cuaca** dari Open-Meteo.
3. `build_system_prompt()` menggabungkan gaya bahasa + domain + memory + data cuaca.
4. Prompt + riwayat percakapan dikirim ke **LLM**.
5. Jawaban dipisah dari baris `SARAN:` → ditampilkan sebagai balasan + chip rekomendasi.

## Contoh percakapan untuk demo/laporan
1. `Namaku Rani, dari Bandung, budget 3 juta, suka pantai`
2. `Buatkan itinerary 3 hari di Lombok` → cuaca Lombok tampil, itinerary menyesuaikan budget & minat
3. Ganti ke gaya **Formal**, tanya: `Apakah besok cocok ke Bali?`
4. Klik salah satu chip rekomendasi.

## Ide pengembangan
- Simpan memory ke database (SQLite) · login pengguna · streaming jawaban
- API tambahan: kurs mata uang, peta/Google Places · deploy ke Render / Railway
