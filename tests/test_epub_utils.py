import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch
import hashlib

from libs.epub_utils import (
    normalize_language, hash_key, load_progress, save_progress,
    get_html_chunks, inject_translations, setup_logging
)


class TestNormalizeLanguage:
    """Test language normalization functionality."""
    
    def test_known_language_full_name(self):
        """Test normalization of known language full names."""
        assert normalize_language("french") == "fr"
        assert normalize_language("english") == "en"
        assert normalize_language("german") == "de"
        assert normalize_language("spanish") == "es"
        assert normalize_language("italian") == "it"
        assert normalize_language("portuguese") == "pt"
        assert normalize_language("japanese") == "ja"
        assert normalize_language("chinese") == "zh"
    
    def test_case_insensitive(self):
        """Test case insensitive language normalization."""
        assert normalize_language("FRENCH") == "fr"
        assert normalize_language("French") == "fr"
        assert normalize_language("fReNcH") == "fr"
    
    def test_whitespace_handling(self):
        """Test handling of whitespace in language input."""
        assert normalize_language("  french  ") == "fr"
        assert normalize_language("\tenglish\n") == "en"
    
    def test_unknown_language_passthrough(self):
        """Test that unknown languages are passed through unchanged."""
        assert normalize_language("xy") == "xy"
        assert normalize_language("unknown") == "unknown"
        assert normalize_language("fr") == "fr"  # Already a code


class TestHashKey:
    """Test hash key generation."""
    
    def test_consistent_hashing(self):
        """Test that same input produces same hash."""
        text = "Test text for hashing"
        hash1 = hash_key(text)
        hash2 = hash_key(text)
        assert hash1 == hash2
    
    def test_different_inputs_different_hashes(self):
        """Test that different inputs produce different hashes."""
        hash1 = hash_key("Text 1")
        hash2 = hash_key("Text 2")
        assert hash1 != hash2
    
    def test_unicode_handling(self):
        """Test hash generation with unicode characters."""
        text = "Texte français avec accents: été, cœur, naïf"
        hash_result = hash_key(text)
        expected = hashlib.sha256(text.encode('utf-8')).hexdigest()
        assert hash_result == expected
    
    def test_empty_string(self):
        """Test hash generation for empty string."""
        hash_result = hash_key("")
        expected = hashlib.sha256("".encode('utf-8')).hexdigest()
        assert hash_result == expected


class TestProgressPersistence:
    """Test progress loading and saving functionality."""
    
    def test_load_progress_existing_file(self, temp_dir, sample_progress_data):
        """Test loading progress from existing file."""
        progress_file = temp_dir / "progress.json"
        progress_file.write_text(json.dumps(sample_progress_data), encoding='utf-8')
        
        loaded = load_progress(progress_file)
        assert loaded == sample_progress_data
    
    def test_load_progress_nonexistent_file(self, temp_dir):
        """Test loading progress from non-existent file returns empty dict."""
        progress_file = temp_dir / "nonexistent.json"
        loaded = load_progress(progress_file)
        assert loaded == {}
    
    def test_save_progress(self, temp_dir, sample_progress_data):
        """Test saving progress to file."""
        progress_file = temp_dir / "progress.json"
        save_progress(progress_file, sample_progress_data)
        
        assert progress_file.exists()
        loaded = json.loads(progress_file.read_text(encoding='utf-8'))
        assert loaded == sample_progress_data
    
    def test_save_progress_atomic_write(self, temp_dir, sample_progress_data):
        """Test that save_progress uses atomic write with temp file."""
        progress_file = temp_dir / "progress.json"
        temp_file = progress_file.with_suffix('.tmp')
        
        # Ensure temp file doesn't exist initially
        assert not temp_file.exists()
        
        save_progress(progress_file, sample_progress_data)
        
        # Temp file should be gone after atomic write
        assert not temp_file.exists()
        assert progress_file.exists()


class TestGetHtmlChunks:
    """Test HTML chunk extraction from EPUB."""
    
    def test_get_all_chunks(self, sample_epub):
        """Test getting all valid chunks from EPUB."""
        chunks = get_html_chunks(sample_epub)
        
        # Should only get chapter 1 (chapter 2 is too short)
        assert len(chunks) == 1
        item, raw = chunks[0]
        assert item.get_name() == "chapter1.xhtml"
        assert b"Chapter 1" in raw
    
    def test_get_specific_chapter(self, sample_epub):
        """Test getting a specific chapter."""
        chunks = get_html_chunks(sample_epub, chapter_only=1)
        
        assert len(chunks) == 1
        item, raw = chunks[0]
        assert item.get_name() == "chapter1.xhtml"
    
    def test_get_nonexistent_chapter(self, sample_epub):
        """Test requesting non-existent chapter returns empty list."""
        chunks = get_html_chunks(sample_epub, chapter_only=999)
        assert chunks == []
    
    def test_custom_min_words(self, sample_epub):
        """Test custom minimum word count."""
        # With very high min_words, no chapters should qualify
        chunks = get_html_chunks(sample_epub, min_words=10000)
        assert len(chunks) == 0
        
        # With very low min_words, both chapters should qualify
        chunks = get_html_chunks(sample_epub, min_words=1)
        assert len(chunks) == 2


class TestInjectTranslations:
    """Test translation injection into EPUB chunks."""
    
    def test_inject_translations_success(self, sample_epub):
        """Test successful translation injection."""
        chunks = get_html_chunks(sample_epub)
        
        # Get the text and create a translation mapping
        item, raw = chunks[0]
        from bs4 import BeautifulSoup
        text = BeautifulSoup(raw, 'html.parser').get_text().strip()
        key = hash_key(text)
        
        translations = {
            key: "<p>Translated content</p>"
        }
        
        count = inject_translations(chunks, translations)
        assert count == 1
        
        # Verify the content was actually injected
        new_content = item.get_content().decode('utf-8')
        assert "Translated content" in new_content
    
    def test_inject_translations_no_matches(self, sample_epub):
        """Test injection with no matching translations."""
        chunks = get_html_chunks(sample_epub)
        translations = {"nonexistent_key": "<p>Translation</p>"}
        
        count = inject_translations(chunks, translations)
        assert count == 0
    
    def test_inject_translations_html_wrapping(self, sample_epub):
        """Test that translations are properly wrapped in HTML."""
        chunks = get_html_chunks(sample_epub)
        item, raw = chunks[0]
        
        from bs4 import BeautifulSoup
        text = BeautifulSoup(raw, 'html.parser').get_text().strip()
        key = hash_key(text)
        
        # Translation without HTML wrapper
        translations = {
            key: "<p>Simple translation</p>"
        }
        
        inject_translations(chunks, translations)
        
        new_content = item.get_content().decode('utf-8')
        assert "<?xml version='1.0' encoding='utf-8'?>" in new_content
        assert "<!DOCTYPE html>" in new_content
        assert "<html>" in new_content
        assert "<body>" in new_content


class TestSetupLogging:
    """Test logging setup functionality."""
    
    @patch('libs.epub_utils.logging.basicConfig')
    def test_setup_logging_debug_mode(self, mock_basic_config):
        """Test logging setup in debug mode."""
        setup_logging(debug=True)
        
        mock_basic_config.assert_called_once()
        call_args = mock_basic_config.call_args
        assert call_args[1]['level'] == 10  # logging.DEBUG
    
    @patch('libs.epub_utils.logging.basicConfig')
    def test_setup_logging_normal_mode(self, mock_basic_config):
        """Test logging setup in normal mode."""
        setup_logging(debug=False)
        
        mock_basic_config.assert_called_once()
        call_args = mock_basic_config.call_args
        assert call_args[1]['level'] == 20  # logging.INFO
    
    @patch('libs.epub_utils.logging.basicConfig')
    def test_setup_logging_default(self, mock_basic_config):
        """Test logging setup with default parameters."""
        setup_logging()
        
        mock_basic_config.assert_called_once()
        call_args = mock_basic_config.call_args
        assert call_args[1]['level'] == 20  # logging.INFO
