import requests
from bs4 import BeautifulSoup
import logging
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


def translate_with_chunking(api_base: str, model: str, prompt: str, html: str, progress: dict, debug: bool=False) -> str:
    logger.debug("Starting translate_with_chunking: html length=%d chars", len(html))
    
    # Try full
    try:
        logger.debug("Attempting full translation")
        result = _translate_once(api_base, model, prompt, html)
        logger.debug("Full translation successful")
        return result
    except TranslationError as e:
        logger.warning("Full translate failed, attempting chunked: %s", e)
        
        # determine chunk_size globally
        if 'chunk_parts' in progress:
            attempts = int.bit_length(progress['chunk_parts']) - 1
            parts = progress['chunk_parts']
            logger.debug("Using existing chunk_parts from progress: %d", parts)
        else:
            attempts = 0
            parts = 2
            logger.debug("Starting with initial chunk_parts: %d", parts)
        
        while attempts < 10:
            logger.debug("Chunking attempt %d", attempts + 1)
            # dynamic split
            chunks = dynamic_chunks(html, max_size=10000, max_attempts=10)
            logger.debug("Created %d chunks", len(chunks))
            
            translated_chunks = []
            for i, chunk in enumerate(chunks):
                logger.debug("Translating chunk %d/%d (length: %d chars)", i+1, len(chunks), len(chunk))
                try:
                    translated_chunk = _translate_once(api_base, model, prompt, chunk)
                    translated_chunks.append(translated_chunk)
                    logger.debug("Chunk %d/%d translation successful", i+1, len(chunks))
                except TranslationError as chunk_error:
                    logger.error("Chunk %d/%d translation failed: %s", i+1, len(chunks), chunk_error)
                    raise TranslationError(f"Chunked translation failed on chunk {i+1}/{len(chunks)}: {chunk_error}")
            
            logger.debug("All chunks translated successfully, merging results")
            result_parts = []
            for tc in translated_chunks:
                try:
                    soup = BeautifulSoup(tc, 'html.parser')
                    body = soup.find('body')
                    if body:
                        result_parts.append(body.decode_contents())
                    else:
                        # Fallback: if no body tag, use the content as-is
                        logger.warning("No body tag found in translated chunk, using content as-is")
                        result_parts.append(tc)
                except Exception as e:
                    logger.error("Error parsing translated chunk: %s", e)
                    logger.debug("Problematic chunk content: %s", tc[:200])
                    # Fallback: use content as-is
                    result_parts.append(tc)
            
            result = ''.join(result_parts)
            
            # record new parts for progress
            progress['chunk_parts'] = len(chunks)
            logger.debug("Chunked translation completed successfully")
            return result
            
        raise TranslationError("Chunked translation also failed after 10 attempts")


def _translate_once(api_base: str, model: str, prompt: str, block: str) -> str:
    url = api_base.rstrip('/') + '/api/chat'
    system = prompt
    logger.debug("Starting translation with model %s, block length: %d chars", model, len(block))
    
    for i in range(3):
        payload = {
            'model': model,
            'messages': [
                {'role':'system','content':system},
                {'role':'user','content':block}
            ],
            'options':{'seed':101,'temperature':0},
            'stream':False
        }
        try:
            logger.debug("Attempt %d: Making API request to %s", i+1, url)
            resp = requests.post(url, json=payload, timeout=300)  # Increased to 5 minutes
            logger.debug("Attempt %d: Got response status %d, content-length: %s", 
                        i+1, resp.status_code, resp.headers.get('content-length', 'unknown'))
            
            resp.raise_for_status()
            
            try:
                resp_json = resp.json()
                logger.debug("Attempt %d: Response JSON keys: %s", i+1, list(resp_json.keys()))
                
                if 'message' not in resp_json:
                    logger.error("Attempt %d: No 'message' field in response: %s", i+1, resp_json)
                    raise ValueError("Invalid API response format: missing 'message' field")
                
                if 'content' not in resp_json['message']:
                    logger.error("Attempt %d: No 'content' field in message: %s", i+1, resp_json['message'])
                    raise ValueError("Invalid API response format: missing 'content' field")
                
                content = resp_json['message']['content'].strip()
                logger.debug("Attempt %d: Got content length: %d chars", i+1, len(content))
                
                if not content:
                    logger.warning("Attempt %d: Empty content received from API", i+1)
                    raise ValueError("Empty response from API")
                
                # Debug: Show sample content for HTML structure analysis
                content_sample = content[:500].replace('\n', '\\n')
                logger.debug("Attempt %d: Content sample: %s", i+1, content_sample)
                
                valid, err = validate_translation(block, content)
                logger.debug("Attempt %d: Validation result: valid=%s, error='%s'", i+1, valid, err)
                
                if not valid:
                    # Debug: Show HTML tag comparison
                    orig_has_p = '<p' in block
                    trans_has_p = '<p' in content
                    logger.debug("Attempt %d: Original has <p tags: %s, Translation has <p tags: %s", 
                               i+1, orig_has_p, trans_has_p)
                
                if valid:
                    logger.debug("Attempt %d: Translation successful", i+1)
                    return content
                    
                system += f"\nPrevious failed: {err}. Preserve HTML."
                logger.debug("Attempt %d: Validation failed, retrying with updated prompt", i+1)
                
            except (KeyError, ValueError, TypeError) as json_err:
                logger.error("Attempt %d: JSON parsing/structure error: %s", i+1, json_err)
                logger.debug("Attempt %d: Raw response text: %s", i+1, resp.text[:500])
                raise ValueError(f"Invalid API response: {json_err}")
                
        except Exception as e:
            logger.error("Translate attempt %d failed: %s", i+1, e)
            if i == 2:
                raise TranslationError(f"All retries failed. Last error: {e}")
    
    raise TranslationError("All retries failed")