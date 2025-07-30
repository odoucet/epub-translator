import requests
from bs4 import BeautifulSoup
import logging
import json
from pathlib import Path
from datetime import datetime
from .epub_utils import hash_key
from .notes import convert_translator_notes_to_footnotes

logger = logging.getLogger(__name__)

class TranslationError(Exception):
    pass


def validate_translation(orig: str, trans: str) -> tuple[bool, str]:
    if not trans or len(trans.strip()) < 10:
        return False, "Translation too short"
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
    """
    total = len(html)
    for attempt in range(max_attempts):
        parts = 2 ** (attempt + 1)
        chunk_size = total // parts
        if chunk_size <= max_size:
            break
    parts = max(1, 2 ** (attempt + 1))
    size = total // parts
    # split approximate
    chunks = [html[i*size:(i+1)*size] for i in range(parts)]
    # last takes remainder
    if parts*size < total:
        chunks.append(html[parts*size:])
    logger.debug("Dynamic split into %d parts of ~%d chars", len(chunks), size)
    return [f'<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html><head></head><body>{c}</body></html>' for c in chunks]


def smart_html_split(html: str, target_size: int = 8000) -> list[str]:
    """
    Split HTML at natural tag boundaries to create chunks of approximately target_size.
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


def translate_with_chunking(api_base: str, models: str | list[str], prompt: str, html: str, progress: dict, debug: bool=False) -> tuple[str, str]:
    """
    Translate HTML with intelligent chunking and model fallback.
    
    Args:
        models: Single model name or list of models to try in order
        
    Returns:
        tuple[str, str]: (translated_html, successful_model_name)
    """
    # Ensure models is a list
    if isinstance(models, str):
        model_list = [models]
    else:
        model_list = models
    
    logger.debug("Starting translate_with_chunking: html length=%d chars, models=%s", len(html), model_list)
    
    # Try each model in sequence
    for model_idx, model in enumerate(model_list):
        logger.debug("Trying model %s (%d/%d)", model, model_idx + 1, len(model_list))
        
        try:
            # Try full translation first
            logger.debug("Attempting full translation with %s", model)
            result = _translate_once(api_base, model, prompt, html, debug)
            logger.debug("Full translation successful with %s", model)
            return result, model
            
        except TranslationError as e:
            logger.warning("Full translate with %s failed: %s", model, e)
            
            # Try chunking with progressively smaller sizes
            chunk_sizes = [16000, 12000, 8000, 4000]
            
            for chunk_size in chunk_sizes:
                if len(html) <= chunk_size:
                    continue  # Skip if content is already smaller than chunk size
                    
                logger.debug("Trying chunking with %s, chunk size %d", model, chunk_size)
                try:
                    chunks = smart_html_split(html, chunk_size)
                    logger.debug("Created %d chunks of target size %d with %s", len(chunks), chunk_size, model)
                    
                    translated_chunks = []
                    chunk_failed = False
                    
                    for i, chunk in enumerate(chunks):
                        logger.debug("Translating chunk %d/%d with %s (length: %d chars)", i+1, len(chunks), model, len(chunk))
                        try:
                            translated_chunk = _translate_once(api_base, model, prompt, chunk, debug)
                            translated_chunks.append(translated_chunk)
                            logger.debug("Chunk %d/%d translation successful with %s", i+1, len(chunks), model)
                        except TranslationError as chunk_error:
                            logger.warning("Chunk %d/%d translation failed with %s: %s", i+1, len(chunks), model, chunk_error)
                            # If chunk is small (< 8k) and still failing, try next model
                            if len(chunk) < 8000 and model_idx < len(model_list) - 1:
                                logger.info("Chunk < 8k chars failed with %s, will try next model", model)
                                chunk_failed = True
                                break
                            else:
                                # Try smaller chunks
                                chunk_failed = True
                                break
                    
                    if not chunk_failed:
                        # All chunks successful - merge results
                        logger.debug("All chunks translated successfully with %s, merging results", model)
                        result = ''.join(translated_chunks)
                        logger.debug("Chunked translation completed successfully with %s", model)
                        return result, model
                    elif len(chunk) < 8000:
                        # Small chunk failed, break to try next model
                        break
                        
                except Exception as e:
                    logger.error("Chunking with %s, size %d failed: %s", model, chunk_size, e)
                    continue
            
            # If we're here, this model failed entirely
            if model_idx < len(model_list) - 1:
                logger.info("Model %s failed entirely, trying next model", model)
                continue
            else:
                logger.error("All models failed")
                raise TranslationError(f"All models ({', '.join(model_list)}) failed")
    
    # Should never reach here
    raise TranslationError("All models failed")


def _translate_once(api_base: str, model: str, prompt: str, block: str, debug: bool = False) -> str:
    """
    Make a single translation request. No retries - if it fails, let the caller handle it.
    """
    url = api_base.rstrip('/') + '/api/chat'
    
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
            'block_length': len(block)
        }
        try:
            with open('debug-lastcall.json', 'w', encoding='utf-8') as f:
                json.dump(debug_data, f, indent=2, ensure_ascii=False)
        except Exception as debug_err:
            logger.warning("Failed to write debug-lastcall.json: %s", debug_err)
    
    try:
        logger.debug("Making translation request with model %s, block length: %d chars", model, len(block))
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
                logger.warning("Failed to update debug-lastcall.json with response: %s", debug_err)
        
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
                logger.debug("Validation failed: %s", err)
                logger.debug("Original has <p tags: %s, Translation has <p tags: %s", 
                           '<p' in block, '<p' in content)
                raise TranslationError(f"Translation validation failed: {err}")
            
            logger.debug("Translation successful, content length: %d chars", len(content))
            return content
            
        except (KeyError, ValueError, TypeError) as json_err:
            logger.error("JSON parsing/structure error: %s", json_err)
            raise TranslationError(f"Invalid API response: {json_err}")
            
    except Exception as e:
        logger.error("Translation request failed: %s", e)
        raise TranslationError(f"Translation failed: {e}")