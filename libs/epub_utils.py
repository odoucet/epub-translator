import logging
from pathlib import Path
import json
import hashlib
import zipfile
import xml.etree.ElementTree as ET
import re
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


# DRM Detection Constants
DRM_NONE = "Aucun DRM détecté"
DRM_UNKNOWN = "Ressources chiffrées (type indéterminé)"
DRM_LCP = "Readium LCP"
DRM_ADOBE = "Adobe ADEPT"
DRM_BN = "Barnes & Noble"
DRM_FAIRPLAY = "Apple FairPlay"


def detect_drm(epub_path: str) -> str:
    """Retourne une chaîne décrivant le DRM détecté (ou DRM_NONE)."""
    with zipfile.ZipFile(epub_path) as z:
        names = set(z.namelist())

        # 1. LCP
        if "license.lcpl" in names or "META-INF/license.lcpl" in names:
            return DRM_LCP

        # 2. Adobe / B&N / FairPlay via rights.xml + encryption.xml
        if "META-INF/rights.xml" in names:
            rights = z.read("META-INF/rights.xml")
            # Heuristique B&N : clé chiffrée de 78 octets
            if re.search(rb"<encryptedKey>.{78}</encryptedKey>", rights, re.S):
                return DRM_BN
            # Heuristique Adobe : clé de 186 octets
            if re.search(rb"<encryptedKey>.{186}</encryptedKey>", rights, re.S):
                return DRM_ADOBE

        if "META-INF/encryption.xml" in names:
            enc_root = ET.fromstring(z.read("META-INF/encryption.xml"))
            algos = [m.get("Algorithm", "") for m in enc_root.iter("{http://www.w3.org/2001/04/xmlenc#}EncryptionMethod")]
            algo_str = "|".join(algos).lower()
            if "adept" in algo_str or "adobe" in algo_str:
                return DRM_ADOBE
            if "fairplay" in algo_str:
                return DRM_FAIRPLAY
            # Chiffrement sans droits.xml : peut être un DRM exotique ou de simples polices
            return DRM_UNKNOWN

        # 3. Apple FairPlay repéré par sinf.xml même sans encryption.xml
        if any(name.endswith(".sinf") or "sinf.xml" in name for name in names):
            return DRM_FAIRPLAY

    return DRM_NONE



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
            # Check if translation already contains complete HTML structure
            if not (translated.lower().startswith('<?xml') or translated.lower().startswith('<html')):
                translated = f"<?xml version='1.0' encoding='utf-8'?><!DOCTYPE html><html><head></head><body>{translated}</body></html>"
            item.set_content(translated.encode('utf-8'))
            count += 1
    logger.info("Injected %d translations", count)
    return count

