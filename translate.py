#!/usr/bin/env python3
import argparse
import os
import json
import shutil
import subprocess
import sys
from pathlib import Path
from ebooklib import epub
from bs4 import BeautifulSoup
from openai import OpenAI
from tqdm import tqdm
from prompts import PREDEFINED_PROMPTS
import ebooklib

LANGUAGES = {
    "french": "fr",
    "english": "en",
    "german": "de",
    "spanish": "es",
    "italian": "it",
    "portuguese": "pt",
    "japanese": "ja",
    "chinese": "zh"
}

def normalize_language(lang_input):
    key = lang_input.strip().lower()
    return LANGUAGES.get(key, key)

def load_progress(workspace):
    if workspace.exists():
        with open(workspace, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_progress(workspace, progress):
    with open(workspace, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2)

def get_html_chunks(book, chapter_only=None, min_words=200):
    chunks = []
    valid_chapters = []
    
    # First, collect all valid chapters (those with enough words)
    for idx, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        if len(soup.get_text(strip=True).split()) >= min_words:
            valid_chapters.append((idx, item, str(soup)))
    
    # If chapter_only is specified, return only that chapter (1-based indexing)
    if chapter_only is not None:
        if 1 <= chapter_only <= len(valid_chapters):
            # Convert 1-based chapter number to 0-based index
            chapter_idx = chapter_only - 1
            _, item, html = valid_chapters[chapter_idx]
            chunks.append((item, html))
        # If chapter_only is out of range, return empty list
    else:
        # Return all valid chapters
        for _, item, html in valid_chapters:
            chunks.append((item, html))
    
    return chunks

def inject_translations(chunks, translations):
    for item, _ in chunks:
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        original = soup.get_text().strip()
        if original in translations:
            item.set_content(translations[original].encode("utf-8"))

def translate_html_block(client, model, prompt, html_block, debug=False):
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": html_block}
    ]
    
    if debug:
        print(f"\n🔍 DEBUG - Sending to model '{model}':")
        print(f"Full messages: {json.dumps(messages, indent=2, ensure_ascii=False)}")
    
    response = client.chat.completions.create(model=model, messages=messages)
    
    if debug:
        print(f"\n📥 DEBUG - Received response:")
        print(f"Response object: {response}")
        print(f"Content: {response.choices[0].message.content}")
    
    return response.choices[0].message.content.strip()

import re

def convert_translator_notes_to_footnotes(html, note_counter_start=1):
    notes = []
    counter = note_counter_start

    def repl(match):
        nonlocal counter
        content = match.group(1).strip()
        ref_id = f"note{counter}"
        footnote = f'<sup><a href="#{ref_id}" id="ref{ref_id}">{counter}</a></sup>'
        note_html = f'<p id="{ref_id}"><sup><a href="#ref{ref_id}">{counter}</a></sup> {content}</p>'
        notes.append(note_html)
        counter += 1
        return footnote

    # Remplace les notes dans le texte
    processed = re.sub(r"\\[Translator’s note: (.*?)\\]", repl, html)
    return processed, notes


def generate_pdf(epub_path):
    pdf_path = epub_path.with_suffix(".pdf")
    if shutil.which("pandoc"):
        try:
            subprocess.run(["pandoc", epub_path, "-o", pdf_path], check=True)
            print(f"📄 PDF generated: {pdf_path}")
        except subprocess.CalledProcessError:
            print("⚠️ Pandoc failed to generate PDF.")
            # optionnaly show docker line :
            print("You can try running: docker run --rm -v $(pwd):/data pandoc/latex", epub_path.name, "-o", pdf_path.name)
    else:
        print("⚠️ 'pandoc' not found. Skipping PDF export.")

def main():
    parser = argparse.ArgumentParser(description="Translate EPUB using HTML chunking.")
    parser.add_argument("--file", required=True, help="Path to the .epub file")
    parser.add_argument("-l", "--lang", required=True, help="Target language (e.g., french, german)")
    parser.add_argument("-p", "--prompt-style", default="literary", help="Prompt style")
    parser.add_argument("-m", "--model", default="mistral", help="Model name")
    parser.add_argument("-u", "--url", default=os.environ.get("LLM_API_URL", "http://localhost:11434/v1"))
    parser.add_argument("-w", "--workspace", default=".translation_progress.json")
    parser.add_argument("--pdf", action="store_true", help="Export to PDF using pandoc")
    parser.add_argument("--chapter", type=int, help="Translate only chapter N (1-based)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode to show API requests and responses")
    parser.add_argument("-o", "--output-file", help="Custom output filename (if not specified, will use [original].[lang].epub)")
    args = parser.parse_args()

    client = OpenAI(base_url=args.url, api_key="ollama")
    lang_code = normalize_language(args.lang)
    book = epub.read_epub(args.file)
    
    # Create a copy of the book for translation to avoid modifying the original
    import copy
    translated_book = copy.deepcopy(book)
    
    prompt = PREDEFINED_PROMPTS[args.prompt_style].format(target_language=args.lang)
    chunks = get_html_chunks(book, chapter_only=args.chapter)
    
    if args.debug:
        if args.chapter:
            print(f"🔍 DEBUG - Translating only chapter {args.chapter}")
        else:
            print(f"🔍 DEBUG - Found {len(chunks)} chunks to translate")
    
    if len(chunks) == 0:
        if args.chapter:
            print(f"⚠️ No content found for chapter {args.chapter}. Make sure the chapter number is valid (1-based).")
        else:
            print("⚠️ No content found to translate in the EPUB file.")
        return

    progress_file = Path(args.workspace)
    progress = load_progress(progress_file)
    translated = progress.get("translated", {})

    bar = tqdm(total=len(chunks), initial=len(translated), desc="Translating")

    for item, html in chunks:
        key = BeautifulSoup(html, 'html.parser').get_text().strip()
        if key in translated:
            continue
        try:
            translated_html = translate_html_block(client, args.model, prompt, html, debug=args.debug)
            translated_html, footnotes = convert_translator_notes_to_footnotes(translated_html)
            final_translated = translated_html + "".join(footnotes)
            translated[key] = final_translated
            progress["translated"] = translated
            save_progress(progress_file, progress)
        except Exception as e:
            print(f"⚠️ Error on block: {key[:50]}... -> {e}")
            if args.debug:
                print(f"🔍 DEBUG - Exception details: {type(e).__name__}: {str(e)}")
            break
        bar.update(1)

    bar.close()
    
    # Get corresponding chunks from the translated book copy
    translated_chunks = get_html_chunks(translated_book, chapter_only=args.chapter)
    inject_translations(translated_chunks, translated)
    
    # Determine output filename
    if args.output_file:
        out_path = Path(args.output_file)
        # Ensure the output file has .epub extension
        if not out_path.suffix.lower() == '.epub':
            out_path = out_path.with_suffix('.epub')
    else:
        # Create default filename: [original_name].[lang_code].epub
        input_path = Path(args.file)
        original_stem = input_path.stem  # filename without extension
        out_path = input_path.parent / f"{original_stem}.{lang_code}.epub"
    
    epub.write_epub(str(out_path), translated_book)
    print(f"✅ Translated EPUB saved to: {out_path}")

    if args.pdf:
        generate_pdf(out_path)

if __name__ == "__main__":
    main()