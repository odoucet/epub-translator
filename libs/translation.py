import requests
from bs4 import BeautifulSoup
import logging
import json
from pathlib import Path
from datetime import datetime
import re
from .epub_utils import hash_key
from .notes import convert_translator_notes_to_footnotes

logger = logging.getLogger(__name__)

class TranslationError(Exception):
    pass


def extract_html_structure(html: str) -> tuple[str, str, str]:
    """
    Extract HTML structure parts: (prefix, body_content, suffix).
    
    This separates the XML declaration, DOCTYPE, <html>, <head> tags (prefix)
    from the actual body content, and the closing tags (suffix).
    
    Args:
        html: Full HTML document string
        
    Returns:
        tuple[str, str, str]: (prefix, body_content, suffix)
        - prefix: Everything before <body> content (XML, DOCTYPE, html, head tags)
        - body_content: Just the content inside <body> tags
        - suffix: Everything after body content (closing </body>, </html> tags)
    """
    # Pattern to match everything up to and including <body> tag
    body_pattern = r'^(.*?<body[^>]*>)(.*?)(<\/body>.*?)$'
    
    match = re.search(body_pattern, html, re.DOTALL | re.IGNORECASE)
    
    if match:
        prefix = match.group(1)  # Everything up to and including <body>
        body_content = match.group(2)  # Content inside <body> tags
        suffix = match.group(3)  # </body> and everything after
        return prefix, body_content, suffix
    else:
        # If no body tags found, treat entire content as body
        logger.warning("No <body> tags found in HTML, treating entire content as body")
        return "", html, ""


def wrap_html_content(body_content: str, prefix: str, suffix: str) -> str:
    """
    Wrap translated body content back into the original HTML structure.
    
    Args:
        body_content: Translated content (what goes inside <body> tags)
        prefix: Original prefix (XML, DOCTYPE, html, head, <body> tags)
        suffix: Original suffix (</body>, </html> tags)
        
    Returns:
        str: Complete HTML document with translated content
    """
    return prefix + body_content + suffix


def validate_translation(orig: str, trans: str) -> tuple[bool, str]:
    if not trans or len(trans.strip()) < 10:
        return False, "Translation too short"
    
    # Check if input starts with HTML tag and output should too
    orig_stripped = orig.strip()
    trans_stripped = trans.strip()
    
    if orig_stripped.startswith('<'):
        # Find the first tag in original
        first_tag_end = orig_stripped.find('>')
        if first_tag_end > 0:
            first_tag = orig_stripped[:first_tag_end + 1]
            
            # Translation should start with the same tag
            if not trans_stripped.startswith(first_tag):
                return False, f"Output should start with '{first_tag}' but starts with '{trans_stripped[:50]}...'"
    
    if '<p' in orig and '<p' not in trans:
        return False, "Paragraph tags missing"
    try:
        soup = BeautifulSoup(trans, 'html.parser')
        if len(soup.get_text(strip=True)) < 20:
            return False, "Too little text after parsing"
    except Exception as e:
        return False, f"Invalid HTML: {e}"
    return True, ""


def dynamic_chunks(html: str, max_size: int = 10000, max_attempts: int = 10) -> list[str]:
    """
    Split html into 2^n chunks, starting from 2,4,8... until chunk size <= max_size or attempts exhausted.
    Now uses structure-aware splitting to preserve HTML wrapper.
    """
    # Extract HTML structure
    prefix, body_content, suffix = extract_html_structure(html)
    
    total = len(body_content)
    for attempt in range(max_attempts):
        parts = 2 ** (attempt + 1)
        chunk_size = total // parts
        if chunk_size <= max_size:
            break
    parts = max(1, 2 ** (attempt + 1))
    size = total // parts
    
    # Split only the body content
    body_chunks = [body_content[i*size:(i+1)*size] for i in range(parts)]
    # last takes remainder
    if parts*size < total:
        body_chunks.append(body_content[parts*size:])
    
    # Wrap each body chunk with the original HTML structure
    wrapped_chunks = []
    for body_chunk in body_chunks:
        full_chunk = wrap_html_content(body_chunk, prefix, suffix)
        wrapped_chunks.append(full_chunk)
    
    logger.debug("Dynamic split into %d parts of ~%d chars", len(wrapped_chunks), size)
    return wrapped_chunks


def smart_html_split(html: str, target_size: int = 8000) -> list[str]:
    """
    Split HTML at natural tag boundaries to create chunks of approximately target_size.
    Now works with body content only - no HTML wrapper added.
    """
    if len(html) <= target_size:
        return [html]
    
    # Try to split at major block elements
    major_tags = ['</p>', '</div>', '</section>', '</article>', '</h1>', '</h2>', '</h3>', '</h4>', '</h5>', '</h6>']
    
    chunks = []
    remaining = html
    
    while len(remaining) > target_size:
        # Find the best split point within target_size
        best_split = target_size
        for tag in major_tags:
            # Look for the tag within the target size range
            search_start = max(0, target_size - 500)  # Look back up to 500 chars for a good split
            search_end = min(len(remaining), target_size + 500)  # Look ahead up to 500 chars
            
            tag_pos = remaining.find(tag, search_start, search_end)
            if tag_pos != -1:
                tag_end = tag_pos + len(tag)
                if abs(tag_end - target_size) < abs(best_split - target_size):
                    best_split = tag_end
        
        # Extract chunk and update remaining
        chunk = remaining[:best_split].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[best_split:].strip()
    
    # Add remaining content
    if remaining.strip():
        chunks.append(remaining)
    
    logger.debug("Smart HTML split: %d chars -> %d chunks", len(html), len(chunks))
    return chunks


def smart_html_split_with_structure(html: str, target_size: int = 8000) -> list[str]:
    """
    Split HTML document into chunks, preserving the original HTML structure.
    
    This function:
    1. Extracts the HTML structure (XML declaration, DOCTYPE, html, head tags)
    2. Splits only the body content using smart_html_split
    3. Wraps each chunk back with the original HTML structure
    
    Args:
        html: Full HTML document string
        target_size: Target size for each chunk
        
    Returns:
        list[str]: List of complete HTML documents, each with full structure
    """
    # Extract HTML structure
    prefix, body_content, suffix = extract_html_structure(html)
    
    # Split only the body content
    body_chunks = smart_html_split(body_content, target_size)
    
    # Wrap each body chunk with the original HTML structure
    structured_chunks = []
    for body_chunk in body_chunks:
        full_chunk = wrap_html_content(body_chunk, prefix, suffix)
        structured_chunks.append(full_chunk)
    
    logger.debug("Smart HTML split with structure: %d chars -> %d structured chunks", 
                len(html), len(structured_chunks))
    return structured_chunks


def translate_with_chunking(api_base: str, models: str | list[str], prompt: str, html: str, progress: dict, 
                          debug: bool = False, chapter_info: str = None) -> tuple[str, str]:
    """
    Translate HTML with intelligent chunking and model fallback.
    
    Args:
        api_base: OpenAI compatible API base URL
        models: Single model name or list of models to try in order
        prompt: Translation prompt
        html: HTML content to translate
        progress: Progress tracking dictionary
        debug: Enable debug logging
        chapter_info: Optional chapter context for logging (e.g., "Chapter 1/5")
        
    Returns:
        tuple[str, str]: (translated_html, successful_model_name)
    """
    # Ensure models is a list
    if isinstance(models, str):
        model_list = [models]
    else:
        model_list = models
    
    # Create chapter prefix for logging
    chapter_prefix = f"{chapter_info} " if chapter_info else ""
    
    logger.debug("%sStarting translate_with_chunking: html length=%d chars, models=%s", 
                chapter_prefix, len(html), model_list)
    
    # Try each model in sequence
    for model_idx, model in enumerate(model_list):
        logger.debug("%sTrying model %s (%d/%d)", chapter_prefix, model, model_idx + 1, len(model_list))
        
        try:
            # Try full translation first
            logger.debug("%sAttempting full translation with %s", chapter_prefix, model)
            result = _translate_once(api_base, model, prompt, html, debug, chapter_info)
            logger.debug("%sFull translation successful with %s", chapter_prefix, model)
            return result, model
            
        except TranslationError as e:
            logger.warning("%sFull translate with %s failed: %s", chapter_prefix, model, e)
            
            # Try chunking with progressively halved sizes
            # Start with content size and halve until we get manageable chunks
            initial_size = len(html)
            chunk_size = min(initial_size // 2, 16000)  # Start with half the content or 16k, whichever is smaller
            min_chunk_size = 2000  # Don't go below 2k characters
            
            while chunk_size >= min_chunk_size:
                if chunk_size >= initial_size:
                    # If chunk size is larger than content, reduce and try again
                    chunk_size = chunk_size // 2
                    continue
                    
                logger.debug("%sTrying chunking with %s, chunk size %d (content size: %d)", 
                           chapter_prefix, model, chunk_size, initial_size)
                try:
                    chunks = smart_html_split_with_structure(html, chunk_size)
                    logger.debug("%sCreated %d chunks of target size %d with %s", chapter_prefix, len(chunks), chunk_size, model)
                    
                    translated_chunks = []
                    chunk_failed = False
                    
                    for i, chunk in enumerate(chunks):
                        chunk_prefix = f"{chapter_prefix}Chunk {i+1}/{len(chunks)} "
                        logger.debug("%sTranslating chunk %d/%d with %s (length: %d chars)", 
                                   chapter_prefix, i+1, len(chunks), model, len(chunk))
                        try:
                            translated_chunk = _translate_once(api_base, model, prompt, chunk, debug, 
                                                             chapter_info, f"Chunk {i+1}/{len(chunks)}")
                            translated_chunks.append(translated_chunk)
                            logger.debug("%sChunk %d/%d translation successful with %s", 
                                       chapter_prefix, i+1, len(chunks), model)
                        except TranslationError as chunk_error:
                            logger.warning("%sChunk %d/%d translation failed with %s: %s", 
                                         chapter_prefix, i+1, len(chunks), model, chunk_error)
                            # If chunk is small (< 4k) and still failing, try next model
                            if len(chunk) < 4000 and model_idx < len(model_list) - 1:
                                logger.info("%sChunk < 4k chars failed with %s, will try next model", 
                                          chapter_prefix, model)
                                chunk_failed = True
                                break
                            else:
                                # Try smaller chunks by halving
                                chunk_failed = True
                                break
                    
                    if not chunk_failed:
                        # All chunks successful - merge results
                        logger.debug("%sAll chunks translated successfully with %s, merging results", chapter_prefix, model)
                        result = ''.join(translated_chunks)
                        logger.debug("%sChunked translation completed successfully with %s", chapter_prefix, model)
                        # Update progress with chunk information
                        progress['chunk_parts'] = len(chunks)
                        return result, model
                    elif len(chunks) > 0 and len(chunks[0]) < 4000:
                        # Very small chunks failed, try next model
                        break
                        
                except Exception as e:
                    logger.error("%sChunking with %s, size %d failed: %s", chapter_prefix, model, chunk_size, e)
                
                # Halve the chunk size for next iteration
                chunk_size = chunk_size // 2
                logger.debug("%sHalving chunk size to %d", chapter_prefix, chunk_size)
            
            # If we're here, this model failed entirely
            if model_idx < len(model_list) - 1:
                logger.info("%sModel %s failed entirely, trying next model", chapter_prefix, model)
                continue
            else:
                logger.error("%sAll models failed", chapter_prefix)
                raise TranslationError(f"All models ({', '.join(model_list)}) failed")
    
    # Should never reach here
    raise TranslationError("All models failed")


def _translate_once(api_base: str, model: str, prompt: str, block: str, debug: bool = False, 
                   chapter_info: str = None, chunk_info: str = None) -> str:
    """
    Make a single translation request. No retries - if it fails, let the caller handle it.
    
    Args:
        api_base: API base URL
        model: Model name
        prompt: Translation prompt
        block: Content to translate
        debug: Enable debug logging
        chapter_info: Optional chapter context (e.g., "Chapter 1/5")
        chunk_info: Optional chunk context (e.g., "Chunk 1/5")
    """
    url = api_base.rstrip('/') + '/api/chat'
    
    # Create context prefix for logging
    context_prefix = ""
    if chapter_info:
        context_prefix += chapter_info
        if chunk_info:
            context_prefix += f" {chunk_info}"
        context_prefix += " "
    elif chunk_info:
        context_prefix = f"{chunk_info} "
    
    payload = {
        'model': model,
        'messages': [
            {'role':'system','content':prompt},
            {'role':'user','content':block}
        ],
        'options':{'seed':101,'temperature':0},
        'stream':False
    }
    
    # Write debug info to file if debug mode is enabled
    if debug:
        debug_data = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'payload': payload,
            'model': model,
            'api_base': api_base,
            'block_length': len(block),
            'context': {
                'chapter': chapter_info,
                'chunk': chunk_info
            }
        }
        try:
            with open('debug-lastcall.json', 'w', encoding='utf-8') as f:
                json.dump(debug_data, f, indent=2, ensure_ascii=False)
        except Exception as debug_err:
            logger.warning("%sFailed to write debug-lastcall.json: %s", context_prefix, debug_err)
    
    try:
        logger.debug("%sMaking translation request with model %s, block length: %d chars", 
                    context_prefix, model, len(block))
        resp = requests.post(url, json=payload, timeout=300)
        
        # Update debug file with response if debug mode is enabled
        if debug:
            try:
                with open('debug-lastcall.json', 'r', encoding='utf-8') as f:
                    debug_data = json.load(f)
                debug_data['response'] = {
                    'status_code': resp.status_code,
                    'headers': dict(resp.headers),
                    'content_length': len(resp.text) if resp.text else 0
                }
                if resp.status_code == 200:
                    try:
                        debug_data['response']['json'] = resp.json()
                    except:
                        debug_data['response']['text_sample'] = resp.text[:500]
                else:
                    debug_data['response']['error_text'] = resp.text[:500]
                with open('debug-lastcall.json', 'w', encoding='utf-8') as f:
                    json.dump(debug_data, f, indent=2, ensure_ascii=False)
            except Exception as debug_err:
                logger.warning("%sFailed to update debug-lastcall.json with response: %s", context_prefix, debug_err)
        
        resp.raise_for_status()
        
        try:
            resp_json = resp.json()
            
            if 'message' not in resp_json:
                raise ValueError("Invalid API response format: missing 'message' field")
            
            if 'content' not in resp_json['message']:
                raise ValueError("Invalid API response format: missing 'content' field")
            
            content = resp_json['message']['content'].strip()
            
            if not content:
                raise ValueError("Empty response from API")
            
            # Validate the translation
            valid, err = validate_translation(block, content)
            
            if not valid:
                logger.debug("%sValidation failed: %s", context_prefix, err)
                logger.debug("%sOriginal has <p> tags: %d, Translation has <p> tags: %d", 
                           context_prefix, block.count('<p>'), content.count('<p>'))
            
            logger.debug("%sTranslation successful, content length: %d chars", context_prefix, len(content))
            return content
            
        except (KeyError, ValueError, TypeError) as json_err:
            logger.error("%sJSON parsing/structure error: %s", context_prefix, json_err)
            raise TranslationError(f"Invalid API response: {json_err}")
            
    except Exception as e:
        logger.error("%sTranslation request failed: %s", context_prefix, e)
        raise TranslationError(f"Translation failed: {e}")


def extract_html_structure(html: str) -> tuple[str, str, str]:
    """
    Extract HTML structure parts: (prefix, body_content, suffix).
    
    This separates the XML declaration, DOCTYPE, <html>, <head> tags (prefix)
    from the actual body content, and the closing tags (suffix).
    
    Args:
        html: Full HTML document string
        
    Returns:
        tuple[str, str, str]: (prefix, body_content, suffix)
        - prefix: Everything before <body> content (XML, DOCTYPE, html, head tags)
        - body_content: Just the content inside <body> tags
        - suffix: Everything after body content (closing </body>, </html> tags)
    """
    # Pattern to match everything up to and including <body> tag
    body_start_pattern = r'^(.*?<body[^>]*>)(.*?)(<\/body>.*?)$'
    
    match = re.search(body_start_pattern, html, re.DOTALL | re.IGNORECASE)
    
    if match:
        prefix = match.group(1)  # Everything up to and including <body>
        body_content = match.group(2)  # Content inside <body> tags
        suffix = match.group(3)  # </body> and everything after
        return prefix, body_content, suffix
    else:
        # If no body tags found, treat entire content as body
        logger.warning("No <body> tags found in HTML, treating entire content as body")
        return "", html, ""


def wrap_html_content(body_content: str, prefix: str, suffix: str) -> str:
    """
    Wrap translated body content back into the original HTML structure.
    
    Args:
        body_content: Translated content (what goes inside <body> tags)
        prefix: Original prefix (XML, DOCTYPE, html, head, <body> tags)
        suffix: Original suffix (</body>, </html> tags)
        
    Returns:
        str: Complete HTML document with translated content
    """
    return prefix + body_content + suffix