#!/usr/bin/env python3
import argparse
import os
import json
import shutil
import subprocess
import sys
import requests
from pathlib import Path
from ebooklib import epub
from bs4 import BeautifulSoup
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
        text_content = soup.get_text(strip=True)
        word_count = len(text_content.split())
        
        if word_count >= min_words:
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

def inject_translations(chunks, translations, debug=False):
    injected_count = 0
    
    if debug:
        print(f"🔍 DEBUG - Starting injection with {len(translations)} stored translations")
        print(f"🔍 DEBUG - Translation keys available:")
        for i, key in enumerate(list(translations.keys())[:2]):  # Show first 2 keys
            preview = key[:100].replace('\n', ' ')
            print(f"  Key {i+1}: {preview}...")
    
    for item, html in chunks:
        # Use the same HTML that was used during translation for key generation
        original = BeautifulSoup(html, 'html.parser').get_text().strip()
        
        if debug:
            preview = original[:100].replace('\n', ' ')
            print(f"🔍 DEBUG - Looking for translation of: {preview}...")
            print(f"🔍 DEBUG - Original item href: {getattr(item, 'get_name', lambda: 'unknown')()}")
        
        if original in translations:
            if debug:
                print(f"🔍 DEBUG - Found translation! Injecting...")
                print(f"🔍 DEBUG - Translation content length: {len(translations[original])}")
            
            # Ensure the translation is properly formatted HTML
            translated_content = translations[original]
            if not translated_content.startswith('<?xml'):
                # Wrap in proper HTML structure if needed
                translated_content = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head></head>
<body>{translated_content}</body>
</html>"""
            
            # Set the content
            try:
                item.set_content(translated_content.encode('utf-8'))
                if debug:
                    print(f"🔍 DEBUG - Successfully set content (UTF-8 encoded)")
            except Exception as e:
                if debug:
                    print(f"🔍 DEBUG - Failed to set content: {e}")
                continue
            
            injected_count += 1
        else:
            if debug:
                print(f"🔍 DEBUG - No translation found for this chunk")
                # Check if there's a similar key
                for key in translations.keys():
                    if key[:50] == original[:50]:
                        print(f"🔍 DEBUG - Found similar key (first 50 chars match)")
                        break
    
    if debug:
        print(f"🔍 DEBUG - Successfully injected {injected_count} translations")

def validate_translation(original_text, translated_text, debug=False):
    """
    Validate that the translation is proper HTML translation, not analysis or commentary.
    Returns (is_valid, error_message)
    """
    if not translated_text or len(translated_text.strip()) < 10:
        return False, "Translation too short"
    
    # Check if it's analysis/commentary instead of translation
    analysis_indicators = [
        "this text appears to be",
        "this is an excerpt",
        "the text describes",
        "the passage discusses",
        "this section contains",
        "the content is about",
        "analysis:",
        "summary:",
        "the story takes place",
        "the characters in the text"
    ]
    
    translated_lower = translated_text.lower()
    for indicator in analysis_indicators:
        if indicator in translated_lower and len(translated_text) < len(original_text)*0.5:
            return False, f"Translation appears to be analysis/commentary (contains: '{indicator}')"
    
    # Check if HTML structure is preserved
    if "<p" in original_text and "<p" not in translated_text:
        return False, "HTML paragraph tags missing in translation"
    
    if "<span" in original_text and "<span" not in translated_text:
        return False, "HTML span tags missing in translation"
    
    # Try to parse as HTML to check validity
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(translated_text, 'html.parser')
        # If it parses without major issues, it's likely valid
        if len(soup.get_text().strip()) < 20:
            return False, "Translated text too short after HTML parsing"
    except Exception as e:
        return False, f"Invalid HTML structure: {str(e)}"
    
    if debug:
        print(f"🔍 DEBUG - Translation validation passed")
    
    return True, "Valid translation"

def split_html_into_chunks(html_content, max_chars=8000, debug=False):
    """
    Split HTML content into smaller chunks while preserving HTML structure
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract all paragraphs and other block elements
    block_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'div'])
    
    if not block_elements:
        # If no block elements found, return the whole content as one chunk
        return [html_content]
    
    chunks = []
    current_chunk = ""
    current_length = 0
    
    # Get the HTML structure prefix (everything before body content)
    html_prefix = str(soup)[:str(soup).find('<body>') + 6] if '<body>' in str(soup) else '<!DOCTYPE html>\n<html>\n<head></head>\n<body>'
    html_suffix = '</body>\n</html>' if '<body>' in str(soup) else ''
    
    prefix_length = len(html_prefix) + len(html_suffix)
    
    if debug:
        print(f"🔍 DEBUG - Splitting HTML into chunks (max {max_chars} chars)")
        print(f"🔍 DEBUG - Found {len(block_elements)} block elements")
        print(f"🔍 DEBUG - HTML prefix/suffix overhead: {prefix_length} chars")
    
    for element in block_elements:
        element_html = str(element)
        element_length = len(element_html)
        
        # If adding this element would exceed the limit, start a new chunk
        if current_length + element_length + prefix_length > max_chars and current_chunk:
            # Complete current chunk
            complete_chunk = html_prefix + current_chunk + html_suffix
            chunks.append(complete_chunk)
            
            if debug:
                print(f"� DEBUG - Created chunk {len(chunks)} with {len(complete_chunk)} chars")
            
            # Start new chunk
            current_chunk = element_html
            current_length = element_length
        else:
            # Add element to current chunk
            current_chunk += element_html
            current_length += element_length
    
    # Add the last chunk if it has content
    if current_chunk:
        complete_chunk = html_prefix + current_chunk + html_suffix
        chunks.append(complete_chunk)
        
        if debug:
            print(f"� DEBUG - Created final chunk {len(chunks)} with {len(complete_chunk)} chars")
    
    if debug:
        print(f"� DEBUG - Split into {len(chunks)} chunks total")
    
    return chunks

def translate_single_chunk(api_url, model, prompt, html_chunk, debug=False):
    """
    Translate a single HTML chunk using the Ollama API
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": html_chunk}
        ],
        "options": {
            "seed": 101,
            "temperature": 0
        },
        "stream": False
    }
    
    if debug:
        print(f"\n� DEBUG - Translating chunk ({len(html_chunk)} chars)...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=300  # 5 minute timeout
            )
            
            response.raise_for_status()
            result = response.json()
            translated_content = result['message']['content'].strip()
            
            # Validate the translation
            is_valid, error_msg = validate_translation(html_chunk, translated_content, debug=debug)
            
            if is_valid:
                if debug:
                    print(f"✅ DEBUG - Chunk translated successfully")
                return translated_content
            else:
                if debug:
                    print(f"❌ DEBUG - Chunk validation failed: {error_msg}")
                
                if attempt < max_retries - 1:
                    payload['messages'][0]['content'] += f"\n\nPREVIOUS ATTEMPT FAILED: {error_msg}. Please fix this and preserve ALL HTML structure."
                    continue
                else:
                    raise ValueError(f"Chunk translation failed: {error_msg}")
        
        except Exception as e:
            if attempt < max_retries - 1:
                if debug:
                    print(f"❌ DEBUG - Chunk attempt {attempt + 1} failed: {str(e)}")
                continue
            else:
                raise e
    
    raise ValueError(f"Chunk translation failed after {max_retries} attempts")

def merge_translated_chunks(chunks, debug=False):
    """
    Merge translated HTML chunks back into a single HTML document
    """
    from bs4 import BeautifulSoup
    
    if len(chunks) == 1:
        return chunks[0]
    
    if debug:
        print(f"🔍 DEBUG - Merging {len(chunks)} translated chunks...")
    
    # Parse first chunk to get the base structure
    soup = BeautifulSoup(chunks[0], 'html.parser')
    body = soup.find('body')
    
    if not body:
        # Fallback: just concatenate the content
        merged_content = ''.join(chunks)
        if debug:
            print(f"🔍 DEBUG - No body tag found, concatenating content")
        return merged_content
    
    # Clear the body content
    body.clear()
    
    # Extract and merge body content from all chunks
    for i, chunk in enumerate(chunks):
        chunk_soup = BeautifulSoup(chunk, 'html.parser')
        chunk_body = chunk_soup.find('body')
        
        if chunk_body:
            # Add all content from this chunk's body
            for element in chunk_body.children:
                if element.name:  # Skip text nodes
                    body.append(element)
        else:
            # If no body tag, assume the whole chunk is content
            if debug:
                print(f"🔍 DEBUG - Chunk {i+1} has no body tag, treating as raw content")
            chunk_soup = BeautifulSoup(f"<div>{chunk}</div>", 'html.parser')
            for element in chunk_soup.div.children:
                if element.name:
                    body.append(element)
    
    result = str(soup)
    
    if debug:
        print(f"🔍 DEBUG - Merged result: {len(result)} chars")
    
    return result

def translate_html_block(base_url, model, prompt, html_block, debug=False):
    """
    Translate HTML block with automatic chunking fallback if the content is too large
    """
    api_url = base_url.replace('/v1', '').rstrip('/') + '/api/chat'
    
    if debug:
        print(f"\n🔍 DEBUG - Using Ollama API:")
        print(f"URL: {api_url}")
        print(f"Model: {model}")
        print(f"Content length: {len(html_block)} chars")
    
    # First, try to translate the entire block
    try:
        if debug:
            print(f"🔍 DEBUG - Attempting full block translation...")
        
        return translate_single_chunk(api_url, model, prompt, html_block, debug=debug)
        
    except Exception as e:
        if debug:
            print(f"⚠️ DEBUG - Full block translation failed: {str(e)}")
            print(f"🔍 DEBUG - Falling back to chunked translation...")
        
        # If full translation fails, split into chunks and try again
        try:
            chunks = split_html_into_chunks(html_block, max_chars=8000, debug=debug)
            
            if len(chunks) == 1:
                # If chunking didn't help, the error is probably not size-related
                raise e
            
            # Translate each chunk
            translated_chunks = []
            for i, chunk in enumerate(chunks):
                if debug:
                    print(f"🔍 DEBUG - Translating chunk {i+1}/{len(chunks)}...")
                
                translated_chunk = translate_single_chunk(api_url, model, prompt, chunk, debug=debug)
                translated_chunks.append(translated_chunk)
            
            # Merge the translated chunks
            if debug:
                print(f"🔍 DEBUG - All chunks translated successfully, merging...")
            
            final_result = merge_translated_chunks(translated_chunks, debug=debug)
            
            if debug:
                print(f"✅ DEBUG - Chunked translation completed successfully!")
            
            return final_result
            
        except Exception as chunk_error:
            if debug:
                print(f"❌ DEBUG - Chunked translation also failed: {str(chunk_error)}")
            
            # If both methods fail, raise the original error
            raise Exception(f"Both full and chunked translation failed. Original error: {str(e)}, Chunk error: {str(chunk_error)}")

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
    processed = re.sub(r"\\[Translator's note: (.*?)\\]", repl, html)
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
    parser = argparse.ArgumentParser(description="Translate EPUB files with automatic chunking for large content.")
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

    lang_code = normalize_language(args.lang)
    book = epub.read_epub(args.file)
    
    prompt = PREDEFINED_PROMPTS[args.prompt_style].format(target_language=args.lang)
    chunks = get_html_chunks(book, chapter_only=args.chapter)
    
    if args.debug:
        if args.chapter:
            print(f"🔍 DEBUG - Translating only chapter {args.chapter}")
            print(f"🔍 DEBUG - Found {len(chunks)} chunks to translate")
            if len(chunks) > 0:
                # Show what chapter we're actually translating
                item, html = chunks[0]
                soup = BeautifulSoup(html, 'html.parser')
                chapter_preview = soup.get_text()[:100].replace('\n', ' ')
                print(f"🔍 DEBUG - Chapter content preview: {chapter_preview}...")
                
                # Debug: Show all document items
                print(f"🔍 DEBUG - All document items in book:")
                for idx, book_item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
                    item_name = getattr(book_item, 'get_name', lambda: f'item_{idx}')()
                    item_content = BeautifulSoup(book_item.get_content(), 'html.parser').get_text(strip=True)
                    word_count = len(item_content.split())
                    preview = item_content[:50].replace('\n', ' ')
                    print(f"    Item {idx}: {item_name} ({word_count} words) - {preview}...")
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
            translated_html = translate_html_block(args.url, args.model, prompt, html, debug=args.debug)
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
    
    # Apply translations directly to the chunks we just translated
    # This ensures we modify the actual book items that will be written
    inject_translations(chunks, translated, debug=args.debug)
    
    if args.debug:
        print(f"🔍 DEBUG - Injected translations for {len(chunks)} chunks")
        
        # Debug: Check book structure after injection
        print(f"🔍 DEBUG - Checking book structure after injection...")
        valid_items = []
        for idx, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text(strip=True)
            if len(text.split()) >= 200:
                valid_items.append((idx, text[:50].replace('\n', ' ')))
        
        print(f"🔍 DEBUG - Book has {len(valid_items)} valid chapters after injection:")
        for i, (idx, preview) in enumerate(valid_items[:5]):  # Show first 5
            print(f"  Chapter {i+1} (item {idx}): {preview}...")
    
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
    
    epub.write_epub(str(out_path), book)
    print(f"✅ Translated EPUB saved to: {out_path}")

    if args.pdf:
        generate_pdf(out_path)

if __name__ == "__main__":
    main()
