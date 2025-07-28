#!/usr/bin/env python3
import argparse
import time
import json
from pathlib import Path
import logging
from ebooklib import epub
from bs4 import BeautifulSoup
from tqdm import tqdm

from libs.epub_utils import (
    normalize_language, load_progress, save_progress,
    get_html_chunks, inject_translations, hash_key,
    setup_logging
)
from libs.translation import translate_with_chunking, TranslationError
from libs.notes import convert_translator_notes_to_footnotes

# Default model list for comparison
DEFAULT_MODELS = [
    "gemma3:1b",
    "gemma3:4b",
    "gemma3:12b",
    "gemma3:27b",
    "mistral:7b",
    "mistral-small:24b",
    "dorian2b/vera",
    "nous-hermes2"
]


def truncate_text(text: str, word_limit: int = 1000) -> str:
    words = text.strip().split()
    if len(words) <= word_limit:
        return " ".join(words)
    truncated = " ".join(words[:word_limit])
    # Try cutting at last sentence end
    for ending in ['.', '!', '?', '...']:
        pos = truncated.rfind(ending)
        if pos > len(truncated) * 0.5:
            return truncated[:pos+1]
    return truncated + "..."


def extract_plaintext(epub_path: Path, lang: str, chapter_only: int = None, debug: bool = False) -> str:
    book = epub.read_epub(str(epub_path))
    texts = []
    valid = []
    for idx, item in enumerate(book.get_items_of_type(epub.ITEM_DOCUMENT)):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        txt = soup.get_text(strip=True)
        if len(txt.split()) >= 200:
            valid.append((idx, txt))
    if chapter_only:
        if 1 <= chapter_only <= len(valid):
            return valid[chapter_only-1][1]
        return ""
    return " ".join(t for _, t in valid)


def run_model_translation(model_name: str, chapter: int, lang: str, epub_file: Path,
                          prompt: str, url: str, debug: bool = False) -> tuple[str, float]:
    """
    Translate a single chapter in-process and return (plaintext, elapsed_time).
    """
    start = time.time()
    # Read and extract HTML for chapter
    book = epub.read_epub(str(epub_file))
    chunks = get_html_chunks(book, chapter_only=chapter)
    if not chunks:
        raise ValueError(f"Chapter {chapter} not found")
    _, raw = chunks[0]
    html = raw.decode('utf-8')
    # Translate HTML
    translated_html = translate_with_chunking(url, model_name, prompt, html, {}, debug=debug)
    translated_html, notes = convert_translator_notes_to_footnotes(translated_html)
    full_html = translated_html + ''.join(notes)
    # Extract plaintext
    plain = BeautifulSoup(full_html, 'html.parser').get_text(strip=True)
    elapsed = time.time() - start
    return plain, elapsed


def write_markdown(out_file: Path, original: str, model_data: dict):
    with out_file.open('w', encoding='utf-8') as f:
        f.write("# Model Comparison - Chapter Output\n\n")
        f.write("## Original (truncated)\n\n```\n")
        f.write(truncate_text(original) + "\n```\n")
        sorted_md = sorted(model_data.items(), key=lambda x: x[1]['time'])
        for model, data in sorted_md:
            status = "✅ Success" if data['success'] else "❌ Failed"
            f.write(f"## {model} - {data['time']:.1f}s ({status})\n\n")
            if data['success']:
                f.write("```\n")
                f.write(truncate_text(data['content']) + "\n```\n")
            else:
                f.write("*Translation failed*\n\n")
        f.write("## Timing Summary\n\n")
        f.write("| Model | Time (s) | Status |\n")
        f.write("|-------|-----------|--------|\n")
        for model, data in sorted_md:
            status = "✅ Success" if data['success'] else "❌ Failed"
            f.write(f"| {model} | {data['time']:.1f} | {status} |\n")
