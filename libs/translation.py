import requests
from bs4 import BeautifulSoup
import logging
import json
import time
from pathlib import Path
from datetime import datetime
import re
from .epub_utils import hash_key
from .notes import convert_translator_notes_to_footnotes

logger = logging.getLogger(__name__)

# Above this body size, skip the single-request attempt: models truncate or summarise huge inputs
MAX_SINGLE_REQUEST_CHARS = 16000
# Translated text shorter than this ratio of the original text is considered truncated
MIN_TRANSLATION_RATIO = 0.5
# Ratio check only applies to originals long enough for the ratio to be meaningful
MIN_TEXT_FOR_RATIO_CHECK = 500
# Token estimates used to derive the chunk size from the model limits (conservative for HTML)
CHARS_PER_TOKEN = 3
# A translation usually needs more tokens than its source (French is ~20% longer than English)
OUTPUT_TOKEN_RATIO = 1.3
TOKEN_SAFETY_MARGIN = 0.9
# smart_html_split looks for a tag up to this many chars past its target size
SPLIT_OVERSHOOT = 1000
# Chunks are never split below this size
MIN_CHUNK_SIZE = 2000
# Attempts per chunk and model before splitting it (transient API errors are common on remote providers)
CHUNK_ATTEMPTS = 3
# Base delay in seconds between attempts, multiplied by the attempt number
CHUNK_RETRY_DELAY = 5

class TranslationError(Exception):
    pass


class EmptyOutputError(TranslationError):
    """The API answered without any content (e.g. the provider dropped an output it flagged as reasoning)."""


# Models that return an empty output when given a system prompt, detected at runtime
_NO_SYSTEM_PROMPT_MODELS = set()


def is_openai_compatible(api_base: str) -> bool:
    """OpenAI-compatible APIs (OpenRouter, vLLM, llama.cpp...) are addressed by a versioned base URL."""
    return re.search(r'/v\d+$', api_base.rstrip('/')) is not None


def get_model_limits(api_base: str, model: str, api_key: str = None) -> tuple[int | None, int | None]:
    """
    Query the OpenAI-compatible /models endpoint for the model token limits.

    Returns:
        tuple: (context_length, max_output_tokens), None for each unknown value
    """
    if not is_openai_compatible(api_base):
        return None, None
    headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
    try:
        resp = requests.get(api_base.rstrip('/') + '/models', headers=headers, timeout=30)
        resp.raise_for_status()
        models = resp.json().get('data', [])
    except (requests.RequestException, ValueError) as e:
        logger.warning("Could not fetch model limits from %s/models: %s", api_base.rstrip('/'), e)
        return None, None

    for info in models:
        if info.get('id') == model:
            # OpenRouter exposes context_length/top_provider, vLLM exposes max_model_len
            context_length = info.get('context_length') or info.get('max_model_len')
            max_output = (info.get('top_provider') or {}).get('max_completion_tokens')
            return context_length, max_output
    logger.warning("Model %s not listed by %s/models, token limits unknown", model, api_base.rstrip('/'))
    return None, None


def compute_max_chunk_chars(context_length: int | None, max_output_tokens: int | None, prompt: str) -> int | None:
    """
    Derive the largest source chunk (in chars) whose translation fits the model token limits.
    The chunk and its translation must both fit the context window, and the translation the output limit.
    """
    budgets = []
    if max_output_tokens:
        budgets.append(max_output_tokens / OUTPUT_TOKEN_RATIO)
    if context_length:
        prompt_tokens = len(prompt) / CHARS_PER_TOKEN
        budgets.append((context_length - prompt_tokens) / (1 + OUTPUT_TOKEN_RATIO))
    if not budgets:
        return None
    chunk_chars = int(min(budgets) * TOKEN_SAFETY_MARGIN * CHARS_PER_TOKEN)
    return max(MIN_CHUNK_SIZE, chunk_chars)


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


def validate_translation(orig: str, trans: str) -> tuple[bool, str, str]:
    """
    Validate translation and clean up backticks if present.

    Returns:
        tuple[bool, str, str]: (is_valid, error_message_or_cleaned_content, cleaned_content)
        - If valid: (True, cleaned_content, cleaned_content)
        - If invalid: (False, error_message, original_trans)
    """
    if not trans or len(trans.strip()) < 10:
        return False, "Translation too short", trans

    # Check if input starts with HTML tag and output should too
    orig_stripped = orig.strip()
    trans_stripped = trans.strip()

    # Clean backticks from output (some models wrap content in ` or ```)
    # Check for triple backticks first, then single backticks
    if trans_stripped.startswith('```') and trans_stripped.endswith('```'):
        # Remove triple backticks and any language identifier
        trans_stripped = trans_stripped[3:]
        if trans_stripped.endswith('```'):
            trans_stripped = trans_stripped[:-3]
        # Remove potential language identifier (e.g., ```html)
        if '\n' in trans_stripped:
            lines = trans_stripped.split('\n', 1)
            if lines[0].strip() and not lines[0].strip().startswith('<'):
                trans_stripped = lines[1] if len(lines) > 1 else trans_stripped
        trans_stripped = trans_stripped.strip()
    elif trans_stripped.startswith('`') and trans_stripped.endswith('`'):
        # Remove single backticks
        trans_stripped = trans_stripped[1:-1].strip()

    if orig_stripped.startswith('<'):
        # Find the first tag in original
        first_tag_end = orig_stripped.find('>')
        if first_tag_end > 0:
            first_tag = orig_stripped[:first_tag_end + 1]

            # Translation should start with the same tag
            if not trans_stripped.startswith(first_tag):
                return False, f"Output should start with '{first_tag}' but starts with '{trans_stripped[:50]}...'", trans

    if '<p' in orig and '<p' not in trans_stripped:
        return False, "Paragraph tags missing", trans
    try:
        soup = BeautifulSoup(trans_stripped, 'html.parser')
        trans_text_len = len(soup.get_text(strip=True))
        if trans_text_len < 5:  # Reduced threshold for testing
            return False, "Too little text after parsing", trans
    except Exception as e:
        return False, f"Invalid HTML: {e}", trans

    # Detect truncated or summarised output: a real translation keeps roughly the same amount of text
    orig_text_len = len(BeautifulSoup(orig, 'html.parser').get_text(strip=True))
    if orig_text_len >= MIN_TEXT_FOR_RATIO_CHECK and trans_text_len < orig_text_len * MIN_TRANSLATION_RATIO:
        return False, (f"Translation too short compared to original ({trans_text_len} vs {orig_text_len} chars), "
                       "probably truncated or summarised"), trans

    return True, trans_stripped, trans_stripped


def dynamic_chunks(html: str, max_size: int = 10000, max_attempts: int = 10) -> list[str]:
    """
    Split html into 2^n chunks, starting from 2,4,8... until chunk size <= max_size or attempts exhausted.
    Now uses structure-aware splitting to preserve HTML wrapper.
    """
    # Extract HTML structure
    prefix, body_content, suffix = extract_html_structure(html)
    
    # If no structure found (simple HTML), create a basic wrapper
    if not prefix and not suffix:
        prefix = '<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html><head></head><body>'
        suffix = '</body></html>'
    
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
    Always splits at HTML tag boundaries - never cuts words or content in half.
    """
    if len(html) <= target_size:
        return [html]
    
    # Try to split at major block elements (in order of preference)
    major_tags = ['</p>', '</div>', '</section>', '</article>', '</h1>', '</h2>', '</h3>', '</h4>', '</h5>', '</h6>']
    
    chunks = []
    remaining = html
    
    while len(remaining) > target_size:
        best_split = None
        best_distance = float('inf')
        
        # First, try to find a tag close to target_size (within reasonable range)
        search_start = max(0, target_size - 1000)  # Look back up to 1000 chars
        search_end = min(len(remaining), target_size + 1000)  # Look ahead up to 1000 chars
        
        for tag in major_tags:
            tag_pos = remaining.find(tag, search_start, search_end)
            if tag_pos != -1:
                tag_end = tag_pos + len(tag)
                distance = abs(tag_end - target_size)
                if distance < best_distance:
                    best_distance = distance
                    best_split = tag_end
        
        # If no tag found in preferred range, find the first suitable tag after minimum size
        if best_split is None:
            min_chunk_size = max(1000, target_size // 4)  # Don't create chunks smaller than 1k or 1/4 target
            for tag in major_tags:
                tag_pos = remaining.find(tag, min_chunk_size, search_end)
                if tag_pos != -1:
                    best_split = tag_pos + len(tag)
                    break
        
        # If still no tag found, find ANY closing tag after minimum size
        if best_split is None:
            min_chunk_size = max(1000, target_size // 4)
            # Look for any closing tag
            import re
            tag_pattern = r'</[^>]+>'
            match = re.search(tag_pattern, remaining[min_chunk_size:search_end])
            if match:
                best_split = min_chunk_size + match.end()
            else:
                # Last resort: cut at the last whitespace before target_size, never inside a word
                space_pos = max(remaining.rfind(' ', 0, target_size), remaining.rfind('\n', 0, target_size))
                best_split = space_pos if space_pos > min_chunk_size else target_size
                logger.warning("No HTML tag found for splitting, forced to cut at position %d", best_split)
        
        # Extract chunk and update remaining
        chunk = remaining[:best_split].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[best_split:].strip()
        
        # Safety check to prevent infinite loops
        if len(remaining) == len(html):
            logger.error("Smart HTML split failed to make progress, falling back to simple split")
            break
    
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


def split_within_limit(html: str, target_size: int, limit: int) -> list[str]:
    """Split html near target_size, leaving room for smart_html_split overshoot so chunks stay under limit."""
    return smart_html_split(html, max(MIN_CHUNK_SIZE, min(target_size, limit - SPLIT_OVERSHOOT)))


def translate_with_chunking(api_base: str, models: str | list[str], prompt: str, html: str, progress: dict, 
                          debug: bool = False, chapter_info: str = None, api_key: str = None,
                          max_chunk_chars: int = None) -> tuple[str, str]:
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
        api_key: Optional bearer token for remote APIs
        max_chunk_chars: Largest body size sent in one request, derived from the model token limits
        
    Returns:
        tuple[str, str]: (translated_html, successful_model_name)
    """
    request_limit = min(MAX_SINGLE_REQUEST_CHARS, max_chunk_chars or MAX_SINGLE_REQUEST_CHARS)

    # Ensure models is a list
    if isinstance(models, str):
        model_list = [models]
    else:
        model_list = models
    
    # Create chapter prefix for logging
    chapter_prefix = f"{chapter_info} " if chapter_info else ""
    
    logger.debug("%sStarting translate_with_chunking: html length=%d chars, models=%s", 
                chapter_prefix, len(html), model_list)
    
    # Extract HTML structure to avoid sending XML/DOCTYPE/head to model
    prefix, body_content, suffix = extract_html_structure(html)
    logger.debug("%sExtracted structure: prefix=%d chars, body=%d chars, suffix=%d chars", 
                chapter_prefix, len(prefix), len(body_content), len(suffix))
    
    # Try full translation first with the primary model - only send body content
    if len(body_content) <= request_limit:
        try:
            logger.debug("%sAttempting full translation with %s", chapter_prefix, model_list[0])
            translated_body = _translate_once(api_base, model_list[0], prompt, body_content, debug, chapter_info,
                                              api_key=api_key)
            logger.debug("%sFull translation successful with %s", chapter_prefix, model_list[0])
            return wrap_html_content(translated_body, prefix, suffix), model_list[0]
        except TranslationError as e:
            logger.warning("%sFull translate with %s failed: %s", chapter_prefix, model_list[0], e)
    else:
        logger.info("%sContent too large for a single request (%d chars), using chunks",
                    chapter_prefix, len(body_content))

    # Check if we have a previously successful chunk size to start with
    initial_size = len(body_content)
    preferred_chunk_size = progress.get('preferred_chunk_size')
    if preferred_chunk_size and preferred_chunk_size < initial_size and preferred_chunk_size <= request_limit:
        logger.debug("%sUsing previously successful chunk size: %d", chapter_prefix, preferred_chunk_size)
        chunk_size = preferred_chunk_size
    else:
        # Start with half the content or the single request limit, whichever is smaller
        chunk_size = max(MIN_CHUNK_SIZE, min(initial_size // 2, request_limit))

    body_chunks = split_within_limit(body_content, chunk_size, request_limit)
    logger.debug("%sCreated %d chunks of target size %d", chapter_prefix, len(body_chunks), chunk_size)

    translated_parts = []
    models_used = []
    for i, body_chunk in enumerate(body_chunks):
        chunk_label = f"Chunk {i+1}/{len(body_chunks)}"
        translated_body, used_model = _translate_chunk_resilient(
            api_base, model_list, prompt, body_chunk, debug, chapter_info, chunk_label, api_key
        )
        translated_parts.append(translated_body)
        models_used.append(used_model)

    progress['chunk_parts'] = len(body_chunks)
    progress['preferred_chunk_size'] = chunk_size
    logger.info("%sRemembering successful chunk size: %d chars for future chapters", chapter_prefix, chunk_size)

    # Report the model that translated most of the content
    main_model = max(model_list, key=models_used.count)
    return wrap_html_content(''.join(translated_parts), prefix, suffix), main_model


def _translate_chunk_resilient(api_base: str, model_list: list[str], prompt: str, body_chunk: str,
                               debug: bool, chapter_info: str, chunk_label: str,
                               api_key: str = None) -> tuple[str, str]:
    """
    Translate one chunk, never restarting already translated chunks:
    retry the same chunk, then split only this chunk in half, then fall back to the next model.
    """
    chapter_prefix = f"{chapter_info} " if chapter_info else ""
    last_error = None

    for model_idx, model in enumerate(model_list):
        for attempt in range(1, CHUNK_ATTEMPTS + 1):
            chunk_start = time.time()
            try:
                translated_body = _translate_once(api_base, model, prompt, body_chunk, debug,
                                                  chapter_info, chunk_label, api_key=api_key)
                chunk_elapsed = time.time() - chunk_start
                chars_per_min = int((len(body_chunk) * 60) / chunk_elapsed) if chunk_elapsed > 0 else 0
                logger.info("%s%s ✅ %s - %.1fs (%d chars/min) - %d chars",
                            chapter_prefix, chunk_label, model, chunk_elapsed, chars_per_min, len(translated_body))
                return translated_body, model
            except TranslationError as e:
                last_error = e
                logger.warning("%s%s attempt %d/%d failed with %s: %s",
                               chapter_prefix, chunk_label, attempt, CHUNK_ATTEMPTS, model, e)
                if isinstance(e, EmptyOutputError) and model_idx < len(model_list) - 1:
                    # Retrying rarely helps when the provider drops the output: switch model right away
                    break
                if attempt < CHUNK_ATTEMPTS:
                    time.sleep(CHUNK_RETRY_DELAY * attempt)

        if isinstance(last_error, EmptyOutputError) and model_idx < len(model_list) - 1:
            logger.info("%s%s: empty output from %s, trying next model", chapter_prefix, chunk_label, model)
            continue

        # Retries exhausted: split only this chunk and translate its halves
        if len(body_chunk) >= 2 * MIN_CHUNK_SIZE:
            sub_chunks = smart_html_split(body_chunk, len(body_chunk) // 2)
            if len(sub_chunks) > 1:
                logger.info("%s%s: splitting into %d smaller chunks", chapter_prefix, chunk_label, len(sub_chunks))
                parts = []
                sub_models = []
                for j, sub_chunk in enumerate(sub_chunks):
                    sub_body, sub_model = _translate_chunk_resilient(
                        api_base, model_list[model_idx:], prompt, sub_chunk, debug, chapter_info,
                        f"{chunk_label}.{j+1}", api_key
                    )
                    parts.append(sub_body)
                    sub_models.append(sub_model)
                return ''.join(parts), sub_models[0]

        if model_idx < len(model_list) - 1:
            logger.info("%s%s failed with %s, trying next model", chapter_prefix, chunk_label, model)

    logger.error("%s%s: all models failed", chapter_prefix, chunk_label)
    raise TranslationError(f"All models ({', '.join(model_list)}) failed on {chunk_label}: {last_error}")


def _translate_once(api_base: str, model: str, prompt: str, block: str, debug: bool = False, 
                   chapter_info: str = None, chunk_info: str = None, api_key: str = None) -> str:
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
        api_key: Optional bearer token sent as Authorization header
    """
    base = api_base.rstrip('/')
    openai_compat = is_openai_compatible(base)
    url = base + ('/chat/completions' if openai_compat else '/api/chat')
    
    # Create context prefix for logging
    context_prefix = ""
    if chapter_info:
        context_prefix += chapter_info
        if chunk_info:
            context_prefix += f" {chunk_info}"
        context_prefix += " "
    elif chunk_info:
        context_prefix = f"{chunk_info} "
    
    if model in _NO_SYSTEM_PROMPT_MODELS:
        messages = [{'role':'user','content':prompt + "\n\n" + block}]
    else:
        messages = [
            {'role':'system','content':prompt},
            {'role':'user','content':block}
        ]
    payload = {
        'model': model,
        'messages': messages,
        'stream':False
    }
    if openai_compat:
        payload.update({'seed':101,'temperature':0})
    else:
        payload['options'] = {'seed':101,'temperature':0}
    headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
    
    # Write debug info to file if debug mode is enabled
    if debug:
        debug_data = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'payload': payload,
            'model': model,
            'api_base': api_base,
            'api_key_set': bool(api_key),
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
        resp = requests.post(url, json=payload, headers=headers, timeout=300)
        
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
            
            if openai_compat:
                if not resp_json.get('choices'):
                    raise ValueError("Invalid API response format: missing 'choices' field")
                message = resp_json['choices'][0].get('message', {})
                finish_reason = resp_json['choices'][0].get('finish_reason')
            else:
                if 'message' not in resp_json:
                    raise ValueError("Invalid API response format: missing 'message' field")
                message = resp_json['message']
                finish_reason = resp_json.get('done_reason')

            if finish_reason == 'length':
                raise TranslationError("Output truncated by the model (max output tokens reached)")
            
            if not (message.get('content') or '').strip() and model not in _NO_SYSTEM_PROMPT_MODELS:
                # Some models (e.g. Tencent Hy-MT) switch to an empty "reasoning" output when given a system
                # prompt: send the instructions in the user message for this model from now on
                logger.warning("%sEmpty output from %s with a system prompt, retrying with instructions "
                               "in the user message (kept for the rest of the run)", context_prefix, model)
                _NO_SYSTEM_PROMPT_MODELS.add(model)
                return _translate_once(api_base, model, prompt, block, debug, chapter_info, chunk_info, api_key)

            if 'content' not in message or message['content'] is None:
                # Providers (e.g. OpenRouter) report upstream failures as a null content with an error field
                details = []
                if finish_reason:
                    details.append(f"finish_reason={finish_reason}")
                provider_error = resp_json.get('error') or (resp_json.get('choices') or [{}])[0].get('error')
                if provider_error:
                    details.append(f"error={provider_error}")
                suffix_msg = f" ({', '.join(details)})" if details else ""
                raise EmptyOutputError(f"Invalid API response format: missing 'content' field{suffix_msg}")
            
            content = message['content'].strip()
            
            if not content:
                raise EmptyOutputError("Empty response from API")
            
            # Validate the translation
            valid, error_cleaned, cleaned_content = validate_translation(block, content)

            if not valid:
                logger.debug("%sValidation failed: %s", context_prefix, error_cleaned)
                logger.debug("%sOriginal has <p> tags: %d, Translation has <p> tags: %d",
                           context_prefix, block.count('<p>'), content.count('<p>'))
                raise TranslationError(f"Translation validation failed: {error_cleaned}")

            # Use the cleaned content
            content = cleaned_content
            
            logger.debug("%sTranslation successful, content length: %d chars", context_prefix, len(content))
            return content
            
        except (KeyError, ValueError, TypeError) as json_err:
            logger.error("%sJSON parsing/structure error: %s", context_prefix, json_err)
            raise TranslationError(f"Invalid API response: {json_err}")
            
    except EmptyOutputError as e:
        logger.error("%sTranslation request failed: %s", context_prefix, e)
        raise
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