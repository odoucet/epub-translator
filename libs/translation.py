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
    # Try full
    try:
        return _translate_once(api_base, model, prompt, html)
    except TranslationError as e:
        logger.warning("Full translate failed, attempting chunked: %s", e)
        # determine chunk_size globally
        if 'chunk_parts' in progress:
            attempts = int.bit_length(progress['chunk_parts']) - 1
            parts = progress['chunk_parts']
        else:
            attempts = 0
            parts = 2
        while attempts < 10:
            # dynamic split
            chunks = dynamic_chunks(html, max_size=10000, max_attempts=10)
            translated_chunks = []
            for chunk in chunks:
                translated_chunks.append(_translate_once(api_base, model, prompt, chunk))
            result = ''.join([BeautifulSoup(tc, 'html.parser').find('body').decode_contents() for tc in translated_chunks])
            # record new parts for progress
            progress['chunk_parts'] = len(chunks)
            return result
        raise TranslationError("Chunked translation also failed")


def _translate_once(api_base: str, model: str, prompt: str, block: str) -> str:
    url = api_base.rstrip('/') + '/api/chat'
    system = prompt
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
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            content = resp.json()['message']['content'].strip()
            valid, err = validate_translation(block, content)
            if valid:
                return content
            system += f"\nPrevious failed: {err}. Preserve HTML."
        except Exception as e:
            logger.error("Translate attempt %d failed: %s", i+1, e)
            if i == 2:
                raise TranslationError(e)
    raise TranslationError("All retries failed")