# 🤖 AI-Powered Automated Paper Corrector

A Streamlit app that grades student handwritten answers against a teacher's answer key using Google Gemini. It supports PDFs, images, and Word documents (DOCX) for teacher keys, performs OCR on scanned/handwritten scripts, generates per-question feedback, and saves results with a statistics dashboard.

## Features

- 🧑‍🏫 Upload teacher answer key: PDF, DOCX, or images (PNG/JPG)
- ✍️ Upload student answer script: PDF or images (PNG/JPG) with handwritten text
- 🔎 OCR powered by Gemini for typed and handwritten content
- ✅ Per-question scoring (0–10) and constructive AI feedback
- 💾 Results saved to `results/<student>_<subject>.json`
- � Statistics dashboard to review past grading sessions

## Project Structure

```
Extraction_text/
├── .streamlit/
│   └── secrets.toml      # API key (DO NOT commit to version control)
├── app.py                # Streamlit UI (grading + dashboard)
├── utils.py              # OCR, parsing, Gemini calls, persistence
├── requirements.txt      # Python dependencies
├── results/              # Saved grading JSON files (git-ignored)
└── README.md             # This file
```

## Setup

1) Create and activate a virtual environment (recommended)

2) Install dependencies
```
pip install -r requirements.txt
```

3) Configure your Gemini API key in `.streamlit/secrets.toml`
```
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"
```

Notes:
- `secrets.toml` is already listed in `.gitignore`.
- The app reads the key via `st.secrets["GEMINI_API_KEY"]`.

4) Run the app
```
streamlit run app.py
```

The app will open at http://localhost:8501 (or a nearby port if occupied).

## How it works

1) Process uploads
	- Teacher: if DOCX, text is extracted directly; if PDF/images, pages are rasterized and sent for OCR.
	- Student: PDF/images are rasterized then OCR'd (handwriting supported).
2) Parse numbered answers (Q1, Q2, …) from both texts.
3) For each question, Gemini compares answers and returns JSON with `{ score, feedback }`.
4) Save results as JSON and display a detailed breakdown and final metrics.
5) The Statistics tab aggregates saved JSONs for quick review.

## Dependencies

- streamlit, google-generativeai
- PyMuPDF (PDF rasterization), pillow
- python-docx (teacher DOCX support)
- pandas (statistics dashboard)

## Security

Never commit secrets or student data:

```
.streamlit/secrets.toml
results/*.json
```

Both paths are already in `.gitignore`.

## Troubleshooting

- If PDFs don't render, ensure PyMuPDF is installed and importable as `pymupdf`.
- If Gemini calls fail, confirm `GEMINI_API_KEY` is present in `.streamlit/secrets.toml` and valid.
- For parsing issues, the app falls back to treating the entire text as a single answer block.

## License

MIT
