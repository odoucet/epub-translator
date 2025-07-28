# EPUB Translator (Autonomous Version)

This project allows you to translate EPUB books using a local LLM like Mistral or Gemma (via Ollama) or any OpenAI-compatible API.  
It preserves HTML structure (headers, emphasis, lists), supports translator footnotes, and can output both EPUB and PDF.

---

## ✨ Features

- Translate EPUB files using chunked **HTML** input for structure preservation
- Supports multi-style prompts (literary, elegant, narrative)
- Outputs EPUB **and optional PDF** (`--pdf`)
- Resumable: tracks translation progress in a JSON workspace
- Supports local LLMs via **Ollama** and remote OpenAI-compatible APIs
- Translate the **entire book or just one chapter** with `--chapter`
- Compare model outputs on a chapter (`compare_models.py`)

---

## ⚠️ Legal Notice

> ❗ Use only with books in the **public domain** (author dead >70 years or explicitly free license).
> Do not use on copyrighted material.

---

## 🐳 Docker Setup

1. Install [Ollama](https://ollama.com/) and run:
   ```bash
   ollama pull mistral
   ollama pull gemma:2b
   ollama pull nous-hermes2
   ```

2. Build and launch translator with Docker Compose:
   ```bash
   docker-compose up -d
   ```

---

## 🚀 Translate a Book

```bash
python translate.py --file book.epub -l french --prompt-style literary --pdf
```

Options:
- `--chapter 3` → translate only chapter 3
- `--workspace` → resume from previous translation progress
- `--model mistral` → use a specific model
- `--url http://localhost:11434/v1` → custom API endpoint

---

## 🔁 Compare LLM Models

To compare model outputs on chapter 3:

```bash
python compare_models.py book.epub -l french -p literary -m mistral gemma:2b -o model_comparison.md
```

---

## 📁 Files Included

- `translate.py` → full EPUB to EPUB/PDF translation
- `compare_models.py` → compare model output for chapter 3
- `prompts.py` → predefined translation prompt styles
- `requirements.txt` → pip dependencies
- `docker-compose.yml` / `Dockerfile` → for local container use
- `download_models.sh` → fetch models via Ollama API

---

## 🧪 Requirements

Install Python dependencies:

```bash
pip install -r requirements.txt
```

You also need `pandoc` + `pdflatex` installed if using `--pdf`.

---

## ✉️ Prompt Styles (in prompts.py)

- `literary`: expressive and narrative with optional translator notes
- `elegant`: fluent and idiomatic with structure preservation
- `narrative`: free but faithful rephrasing of content with tag retention

## TODO
- [ ] improve prompts to better handle HTML structure (lots of failures)
- [ ] add openai-compatible API support
- [ ] add "literal" translation.