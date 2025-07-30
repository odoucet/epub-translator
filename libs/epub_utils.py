import logging
from pathlib import Path
import json
import hashlib
from ebooklib import epub
import ebooklib
from bs4 import BeautifulSoup
import logging

def setup_logging(debug: bool = False) -> None:
    """Configure the root logger."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Suppress urllib3 debug messages even in debug mode
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)



logger = logging.getLogger(__name__)

def normalize_language(lang_input: str) -> str:
    """Retourne le code ISO 2 lettres pour la langue demandée."""
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
    key = lang_input.strip().lower()
    return LANGUAGES.get(key, key)


def hash_key(text: str) -> str:
    """Generate a SHA256 hash key for a given text."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_progress(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {}


def save_progress(path: Path, progress: dict) -> None:
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(progress, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def get_html_chunks(book: epub.EpubBook, chapter_only=None, min_words: int = 200):
    """
    Extract valid document items from EPUB and return list of (item, raw_html_bytes).
    """
    valid = []
    for idx, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        text = soup.get_text(strip=True)
        if len(text.split()) >= min_words:
            valid.append((idx, item, item.get_content()))
    if chapter_only:
        if 1 <= chapter_only <= len(valid):
            idx, item, raw = valid[chapter_only-1]
            return [(item, raw)]
        return []
    return [(item, raw) for _, item, raw in valid]


def inject_translations(chunks: list[tuple], translations: dict[str, str]) -> int:
    """
    Inject translated HTML back into EPUB items. Return count injected.
    """
    count = 0
    for item, raw_html in chunks:
        text = BeautifulSoup(raw_html, 'html.parser').get_text().strip()
        key = hash_key(text)
        if key in translations:
            translated = translations[key]
            if not translated.lower().startswith('<html'):
                translated = f"<?xml version='1.0' encoding='utf-8'?><!DOCTYPE html><html><head></head><body>{translated}</body></html>"
            item.set_content(translated.encode('utf-8'))
            count += 1
    logger.info("Injected %d translations", count)
    return count

