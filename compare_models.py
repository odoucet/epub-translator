#!/usr/bin/env python3
import argparse
import subprocess
import os
import tempfile
from bs4 import BeautifulSoup
from pathlib import Path

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

def extract_plaintext(epub_path, lang_code, chapter_only=None, debug=False):
    from ebooklib import epub
    import ebooklib
    from bs4 import BeautifulSoup

    book = epub.read_epub(epub_path)
    texts = []
    valid_chapters = []
    
    # First, collect all valid chapters (those with enough words) - same logic as translate.py
    for idx, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        text = soup.get_text(strip=True)
        if len(text.split()) >= 200:  # Same min_words threshold as translate.py
            valid_chapters.append((idx, text))
    
    if debug and chapter_only is not None:
        print(f"📖 DEBUG: Found {len(valid_chapters)} valid chapters in {epub_path}")
        for i, (_, text) in enumerate(valid_chapters):
            chapter_start = text[:50].replace('\n', ' ')
            print(f"  Chapter {i+1}: {chapter_start}...")
    
    # If chapter_only is specified, return only that chapter (1-based indexing)
    if chapter_only is not None:
        if 1 <= chapter_only <= len(valid_chapters):
            # Convert 1-based chapter number to 0-based index
            chapter_idx = chapter_only - 1
            _, text = valid_chapters[chapter_idx]
            
            if debug:
                preview = text[:100].replace('\n', ' ')
                print(f"📖 DEBUG: Returning chapter {chapter_only}: {preview}...")
            
            return text
        else:
            if debug:
                print(f"❌ DEBUG: Chapter {chapter_only} not found (only {len(valid_chapters)} chapters available)")
            return ""  # Chapter not found
    else:
        # Return all valid chapters
        for _, text in valid_chapters:
            texts.append(text)
        return " ".join(texts)

def truncate_text(text, word_limit=1000):
    words = text.strip().split()
    if len(words) <= word_limit:
        return " ".join(words)
    
    # Take the first word_limit words
    truncated_words = words[:word_limit]
    truncated_text = " ".join(truncated_words)
    
    # Find the last sentence-ending punctuation
    sentence_endings = ['.', '!', '?', '...']
    last_sentence_end = -1
    
    for ending in sentence_endings:
        pos = truncated_text.rfind(ending)
        if pos > last_sentence_end:
            last_sentence_end = pos
    
    # If we found a sentence ending and it's not too close to the beginning
    # (at least 50% of the target length), cut there
    if last_sentence_end > len(truncated_text) * 0.5:
        return truncated_text[:last_sentence_end + 1]
    
    # Otherwise, return the word-truncated version with ellipsis
    return truncated_text + "..."

def normalize_language(lang_input):
    key = lang_input.strip().lower()
    return LANGUAGES.get(key, key)

def run_model_translation(model_name, chapter, lang, input_file, debug=False):
    # Create a specific output filename for each model
    input_path = Path(input_file)
    lang_code = normalize_language(lang)
    output_file = input_path.parent / f"{input_path.stem}.{model_name}.{lang_code}.epub"
    
    cmd = [
        "python", "translate.py",
        "--file", input_file,
        "--lang", lang,
        "--chapter", str(chapter),
        "--model", model_name,
        "--output-file", str(output_file),
        "--workspace", f".temp_progress_{model_name}.json"
    ]
    
    if debug:
        cmd.append("--debug")
    
    # Run subprocess and capture/display output in real-time
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    if result.returncode != 0:
        print(f"❌ Translation failed for model {model_name}")
        raise subprocess.CalledProcessError(result.returncode, cmd)
    
    return output_file

def write_markdown(out_file, original_text, model_outputs):
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("# Model Comparison - Chapter Output\n\n")
        f.write("## Original (first 1000 words)\n\n```\n")
        f.write(truncate_text(original_text) + "\n```\n\n")
        for model, result in model_outputs.items():
            f.write(f"## {model}\n\n```\n")
            f.write(truncate_text(result) + "\n```\n\n")

def main():
    parser = argparse.ArgumentParser(description="Compare translation output from translate.py on a chapter")
    parser.add_argument("--file", required=True, help="EPUB file path")
    parser.add_argument("-l", "--lang", required=True, help="Target language")
    parser.add_argument("-o", "--output-file", default="model_comparison.md", help="Output markdown file")
    parser.add_argument("-m", "--models", nargs="+", default=["gemma3:4b", "vera", "nous-hermes2"])
    parser.add_argument("-c", "--chapter", type=int, default=3)
    parser.add_argument("--debug", action="store_true", help="Enable debug mode for translate.py")
    args = parser.parse_args()

    outputs = {}
    for model in args.models:
        print(f"🔄 Translating with model: {model}")
        out_epub = run_model_translation(model, args.chapter, args.lang, args.file, debug=args.debug)
        
        if args.debug:
            print(f"🔍 DEBUG - Extracting from translated file: {out_epub}")
        
        plain = extract_plaintext(out_epub, args.lang, chapter_only=args.chapter, debug=args.debug)
        
        if args.debug:
            chapter_preview = plain[:100].replace('\n', ' ') if plain else "EMPTY"
            print(f"🔍 DEBUG - Extracted chapter content: {chapter_preview}...")
        
        outputs[model] = plain

    print(f"🔍 DEBUG - Extracting original chapter {args.chapter}")
    original = extract_plaintext(args.file, args.lang, chapter_only=args.chapter, debug=args.debug)
    
    if args.debug:
        orig_preview = original[:100].replace('\n', ' ') if original else "EMPTY"
        print(f"🔍 DEBUG - Original chapter content: {orig_preview}...")
    
    write_markdown(args.output_file, original, outputs)
    print(f"✅ Markdown saved to {args.output_file}")

if __name__ == "__main__":
    main()