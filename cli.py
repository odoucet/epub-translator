#!/usr/bin/env python3
import argparse
import time
import json
from pathlib import Path
import logging
from ebooklib import epub
import ebooklib
from bs4 import BeautifulSoup
from tqdm import tqdm

from libs.epub_utils import (
    normalize_language, load_progress, save_progress,
    get_html_chunks, inject_translations, hash_key,
    setup_logging
)
from libs.translation import translate_with_chunking, TranslationError
from libs.notes import convert_translator_notes_to_footnotes
from libs.prompts import PREDEFINED_PROMPTS

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


def truncate_text(text: str, word_limit: int = 500) -> str:
    words = text.strip().split()
    if len(words) <= word_limit:
        return " ".join(words)
    truncated = " ".join(words[:word_limit])
    for ending in ['.', '!', '?', '...']:
        pos = truncated.rfind(ending)
        if pos > len(truncated) * 0.5:
            return truncated[:pos+1]
    return truncated + "..."


def extract_plaintext(epub_path: Path, lang: str, chapter_only: int = None, debug: bool = False) -> str:
    book = epub.read_epub(str(epub_path))
    texts = []
    valid = []
    for idx, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        txt = soup.get_text(strip=True)
        if len(txt.split()) >= 200:
            valid.append((idx, txt))
    if chapter_only:
        if 1 <= chapter_only <= len(valid):
            return valid[chapter_only-1][1]
        return ""
    return " ".join(t for _, t in valid)


def get_chapter_info(epub_path: Path, chapter: int) -> tuple[str, int]:
    """Get chapter title and word count for logging purposes."""
    book = epub.read_epub(str(epub_path))
    valid_chapters = []
    
    for idx, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        txt = soup.get_text(strip=True)
        if len(txt.split()) >= 200:
            # Try to extract title from first heading or first line
            title = ""
            for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                heading = soup.find(tag)
                if heading:
                    title = heading.get_text(strip=True)
                    break
            
            if not title:
                # Fallback to first line/sentence
                first_line = txt.split('\n')[0].strip()
                if len(first_line) > 100:  # If first line is too long, truncate
                    first_line = first_line[:97] + "..."
                title = first_line
            
            valid_chapters.append((title, len(txt.split())))
    
    if 1 <= chapter <= len(valid_chapters):
        return valid_chapters[chapter-1]
    else:
        return f"Chapter {chapter}", 0


def run_model_translation(model_name: str, chapter: int, lang: str, epub_file: Path,
                          prompt: str, url: str, debug: bool = False) -> tuple[str, float]:
    start = time.time()
    book = epub.read_epub(str(epub_file))
    chunks = get_html_chunks(book, chapter_only=chapter)
    if not chunks:
        raise ValueError(f"Chapter {chapter} not found")
    _, raw = chunks[0]
    html = raw.decode('utf-8')
    translated_html, _ = translate_with_chunking(url, model_name, prompt, html, {}, debug=debug)
    translated_html, notes = convert_translator_notes_to_footnotes(translated_html)
    full_html = translated_html + ''.join(notes)
    plain = BeautifulSoup(full_html, 'html.parser').get_text(strip=True)
    elapsed = time.time() - start
    return plain, elapsed


def translate_with_fallback(models: list[str], prompt: str, url: str, html: str, 
                           progress: dict, debug: bool = False) -> tuple[str, str]:
    """
    Translate using multiple models with intelligent chunking and fallback.
    Returns (translated_html, successful_model_name)
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting translation with models: %s", ", ".join(models))
        translated, successful_model = translate_with_chunking(url, models, prompt, html, progress, debug=debug)
        logger.info("✅ Translation successful with model: %s", successful_model)
        return translated, successful_model
        
    except TranslationError as e:
        logger.error("❌ All models failed: %s", e)
        raise e


def write_markdown(out_file: Path, original: str, model_data: dict):
    # Calculate word count for speed metrics
    original_word_count = len(original.split())
    
    with out_file.open('w', encoding='utf-8') as f:
        f.write("# Model Comparison - Chapter Output\n\n")
        f.write("## Original (truncated)\n\n")
        f.write("```\n")
        f.write(truncate_text(original) + "\n")
        f.write("```\n\n")

        sorted_md = sorted(model_data.items(), key=lambda x: x[1]['time'])
        for model, data in sorted_md:
            status = "✅ Success" if data['success'] else "❌ Failed"
            if data['success'] and data['time'] > 0:
                words_per_min = (original_word_count * 60) / data['time']
                f.write(f"## {model} - {data['time']:.1f}s ({words_per_min:.0f} words/min) ({status})\n\n")
            else:
                f.write(f"## {model} - {data['time']:.1f}s ({status})\n\n")
            
            if data['success']:
                f.write("```\n")
                f.write(truncate_text(data['content']) + "\n")
                f.write("```\n\n")
            else:
                f.write("*Translation failed*\n\n")

        f.write("## Timing Summary\n\n")
        f.write("| Model | Time (s) | Words/min | Status |\n")
        f.write("|-------|-----------|-----------|--------|\n")
        for model, data in sorted_md:
            status = "✅ Success" if data['success'] else "❌ Failed"
            if data['success'] and data['time'] > 0:
                words_per_min = (original_word_count * 60) / data['time']
                f.write(f"| {model} | {data['time']:.1f} | {words_per_min:.0f} | {status} |\n")
            else:
                f.write(f"| {model} | {data['time']:.1f} | N/A | {status} |\n")


def main():
    parser = argparse.ArgumentParser(description="Translate EPUB or compare models on a chapter.")
    parser.add_argument('-f', '--file', required=True, help="Path to EPUB file")
    parser.add_argument('-l', '--lang', required=True, help="Target language")
    parser.add_argument('-m', '--model', default='mistral:7b,nous-hermes2', 
                       help="Model name(s) for translation - comma-separated list, will fallback in order (e.g., 'dorian2b/vera,mistral-small:24b')")
    parser.add_argument('-p', '--prompt-style', default='literary', help="Prompt style")
    parser.add_argument('-u', '--url', default='http://localhost:11434', help="API base URL")
    parser.add_argument('-w', '--workspace', default='.progress.json', help="Progress file")
    parser.add_argument('--chapter', type=int, help="Chapter number for translation or comparison")
    parser.add_argument('--pdf', action='store_true', help="Export to PDF")
    parser.add_argument('--debug', action='store_true', help="Enable debug mode")
    parser.add_argument('-o', '--output-file', help="Output EPUB or markdown file")
    parser.add_argument('--compare', nargs='?', const='', help="Comma-separated models to compare (default all)")
    args = parser.parse_args()

    # Parse comma-separated model names
    if isinstance(args.model, str):
        model_list = [m.strip() for m in args.model.split(',') if m.strip()]
    else:
        model_list = args.model
    
    setup_logging(args.debug)
    logger = logging.getLogger(__name__)

    prompt = PREDEFINED_PROMPTS[args.prompt_style].format(target_language=args.lang)

    if args.compare is not None:
        if args.compare == '':
            models = DEFAULT_MODELS
        else:
            models = [m.strip() for m in args.compare.split(',') if m.strip()]
        if not args.chapter:
            parser.error("--chapter is required for model comparison.")
        
        # Get chapter info for better logging
        chapter_title, word_count = get_chapter_info(Path(args.file), args.chapter)
        
        outputs = {}
        for model in models:
            logger.info("Translating chapter %d ('%s', %d words) with model %s", 
                       args.chapter, chapter_title, word_count, model)
            try:
                content, elapsed = run_model_translation(
                    model, args.chapter, args.lang, Path(args.file), prompt, args.url, debug=args.debug
                )
                outputs[model] = {'content': content, 'time': elapsed, 'success': True}
                logger.info("%s done in %.1fs", model, elapsed)
            except Exception as e:
                outputs[model] = {'content': '', 'time': 0, 'success': False}
                logger.error("Model %s failed: %s", model, e)
        original = extract_plaintext(Path(args.file), args.lang, chapter_only=args.chapter, debug=args.debug)
        out_md = Path(args.output_file or 'model_comparison.md')
        write_markdown(out_md, original, outputs)
        print(f"✅ Comparison saved to {out_md}")
        return

    lang_code = normalize_language(args.lang)
    book = epub.read_epub(args.file)
    chunks = get_html_chunks(book, args.chapter)
    if not chunks:
        logger.error("No content to translate")
        return
    workspace = Path(args.workspace)
    prog = load_progress(workspace)
    trans_map = prog.get('translated', {})

    debug_data = {}
    debug_path = Path('.debug.translate.json')
    if args.debug and debug_path.exists():
        debug_data = json.loads(debug_path.read_text(encoding='utf-8'))

    bar = tqdm(total=len(chunks), desc="Translating")
    for item, raw in chunks:
        text = BeautifulSoup(raw, 'html.parser').get_text().strip()
        key = hash_key(text)
        if key in trans_map:
            bar.update()
            continue
        try:
            # Use fallback system with multiple models
            translated, successful_model = translate_with_fallback(
                model_list, prompt, args.url, raw.decode('utf-8'), prog, debug=args.debug
            )
            logger.info("✅ Chunk translated successfully with model: %s", successful_model)
            
            if args.debug:
                debug_data[text] = translated
                debug_path.write_text(json.dumps(debug_data, indent=2, ensure_ascii=False), encoding='utf-8')
        except TranslationError as e:
            logger.error("Translation error with all models: %s", e)
            break
        trans_html, notes = convert_translator_notes_to_footnotes(translated)
        trans_map[key] = trans_html + ''.join(notes)
        prog['translated'] = trans_map
        save_progress(workspace, prog)
        bar.update()
    bar.close()

    injected = inject_translations(chunks, trans_map)
    out_epub = Path(args.output_file or f"{Path(args.file).stem}.{lang_code}.epub")
    epub.write_epub(str(out_epub), book)
    logger.info("Saved translated EPUB: %s", out_epub)
    if args.pdf:
        from .epub_utils import generate_pdf
        generate_pdf(out_epub)

if __name__ == '__main__':
    main()