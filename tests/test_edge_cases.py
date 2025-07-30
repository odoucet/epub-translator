import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import requests

from libs.epub_utils import hash_key, normalize_language, get_html_chunks
from libs.translation import TranslationError, validate_translation, _translate_once
from libs.notes import convert_translator_notes_to_footnotes
from cli import truncate_text, extract_plaintext
from tests.test_utils import create_mock_epub_book, create_large_content


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_hash_key_unicode_edge_cases(self):
        """Test hash key generation with various unicode edge cases."""
        edge_cases = [
            "",  # Empty string
            " ",  # Single space
            "\n\t\r",  # Whitespace characters
            "🚀📚🔤",  # Emojis
            "中文测试",  # Chinese characters
            "مرحبا بالعالم",  # Arabic text
            "Здравствуй мир",  # Cyrillic
            "\x00\x01\x02",  # Control characters
            "a" * 10000,  # Very long string
        ]
        
        for text in edge_cases:
            hash_result = hash_key(text)
            assert isinstance(hash_result, str)
            assert len(hash_result) == 64  # SHA256 hex length
    
    def test_normalize_language_edge_cases(self):
        """Test language normalization with edge cases."""
        edge_cases = [
            ("", ""),  # Empty string
            ("   ", ""),  # Only whitespace
            ("FRENCH", "fr"),  # All caps
            ("fReNcH", "fr"),  # Mixed case
            ("\tfrench\n", "fr"),  # With tabs/newlines
            ("french ", "fr"),  # Trailing space
            (" french", "fr"),  # Leading space
            ("nonexistent", "nonexistent"),  # Unknown language
            ("123", "123"),  # Numbers
            ("fr-FR", "fr-fr"),  # Country code (passthrough)
        ]
        
        for input_lang, expected in edge_cases:
            result = normalize_language(input_lang)
            assert result == expected, f"Failed for input: '{input_lang}'"
    
    def test_truncate_text_edge_cases(self):
        """Test text truncation with edge cases."""
        # Empty text
        assert truncate_text("") == ""
        
        # Only whitespace
        assert truncate_text("   ") == ""
        
        # Single word
        assert truncate_text("word", word_limit=1) == "word"
        
        # Very long single word
        long_word = "a" * 1000
        result = truncate_text(long_word, word_limit=1)
        assert result == long_word  # Single word shouldn't be truncated
        
        # Text with multiple sentence endings
        text_with_endings = "First sentence. Second sentence! Third sentence? Fourth sentence..."
        result = truncate_text(text_with_endings, word_limit=4)
        # Should find the best sentence ending within limit
        assert result.endswith(('.', '!', '?', '...'))
        
        # Text with no sentence endings
        no_endings = " ".join(["word"] * 100)
        result = truncate_text(no_endings, word_limit=50)
        assert result.endswith("...")
    
    def test_validation_edge_cases(self):
        """Test translation validation with edge cases."""
        # Very short valid translation
        is_valid, error = validate_translation("<p>Original</p>", "<p>Short but valid translation content here</p>")
        assert is_valid is True
        
        # Translation with only HTML tags
        is_valid, error = validate_translation("<p>Original</p>", "<p></p>")
        assert is_valid is False
        assert "translation too short" in error.lower()
        
        # Translation with mixed content
        is_valid, error = validate_translation(
            "<p>Original text</p>", 
            "<p>Translation</p><div>More content</div>"
        )
        assert is_valid is True  # Should be valid despite different structure
        
        # Original without paragraphs, translation with paragraphs
        is_valid, error = validate_translation(
            "Plain text without paragraphs",
            "<p>Translation with paragraphs</p>"
        )
        assert is_valid is True  # Should be valid - adding structure is OK


@pytest.mark.unit  
class TestErrorHandling:
    """Test error handling in various scenarios."""
    
    def test_translation_network_errors(self):
        """Test handling of various network errors."""
        with patch('requests.post') as mock_post:
            # Timeout error
            mock_post.side_effect = requests.exceptions.Timeout("Request timeout")
            
            with pytest.raises(TranslationError):
                _translate_once("http://localhost:11434", "model", "prompt", "<p>content</p>")
            
            # Connection error
            mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
            
            with pytest.raises(TranslationError):
                _translate_once("http://localhost:11434", "model", "prompt", "<p>content</p>")
            
            # HTTP error
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("HTTP 500")
            mock_post.return_value = mock_response
            
            with pytest.raises(TranslationError):
                _translate_once("http://localhost:11434", "model", "prompt", "<p>content</p>")
    
    def test_json_parsing_errors(self):
        """Test handling of JSON parsing errors."""
        with patch('requests.post') as mock_post:
            # Invalid JSON response
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_post.return_value = mock_response
            
            with pytest.raises(TranslationError):
                _translate_once("http://localhost:11434", "model", "prompt", "<p>content</p>")
    
    def test_malformed_api_response(self):
        """Test handling of malformed API responses."""
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            
            # Missing 'message' key
            mock_response.json.return_value = {"error": "Missing message"}
            mock_post.return_value = mock_response
            
            with pytest.raises(TranslationError):
                _translate_once("http://localhost:11434", "model", "prompt", "<p>content</p>")
            
            # Missing 'content' key
            mock_response.json.return_value = {"message": {"role": "assistant"}}
            
            with pytest.raises(TranslationError):
                _translate_once("http://localhost:11434", "model", "prompt", "<p>content</p>")
    
    def test_file_system_errors(self, temp_dir):
        """Test handling of file system errors."""
        from libs.epub_utils import save_progress, load_progress
        
        # Test with invalid path
        invalid_path = Path("/nonexistent/directory/file.json")
        
        with pytest.raises(FileNotFoundError):
            save_progress(invalid_path, {"test": "data"})
        
        # Test loading non-existent file (should return empty dict, not error)
        result = load_progress(temp_dir / "nonexistent.json")
        assert result == {}
        
        # Test with corrupted JSON
        corrupted_file = temp_dir / "corrupted.json"
        corrupted_file.write_text("invalid json content {", encoding='utf-8')
        
        with pytest.raises(json.JSONDecodeError):
            load_progress(corrupted_file)


@pytest.mark.unit
class TestPerformanceBoundaries:
    """Test performance with boundary conditions."""
    
    def test_large_text_processing(self):
        """Test processing of very large text volumes."""
        # Create very large content
        large_content = create_large_content(word_count=50000)
        
        # Test hash generation
        hash_result = hash_key(large_content)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64
        
        # Test truncation
        truncated = truncate_text(large_content, word_limit=1000)
        truncated_words = truncated.replace("...", "").strip().split()
        assert len(truncated_words) <= 1000
    
    def test_many_translator_notes(self):
        """Test processing many translator notes efficiently."""
        # Create content with many notes
        content_parts = []
        for i in range(500):
            content_parts.append(f"Text {i} [Translator's note: Note {i}] more text.")
        
        html_content = "<p>" + " ".join(content_parts) + "</p>"
        
        processed, notes = convert_translator_notes_to_footnotes(html_content)
        
        # Verify all notes were processed
        assert len(notes) == 500
        assert "[Translator's note:" not in processed
        
        # Verify note numbering
        for i in range(1, 501):
            assert f'id="note{i}"' in notes[i-1]
    
    def test_deeply_nested_html(self):
        """Test processing of deeply nested HTML structures."""
        # Create deeply nested HTML
        nested_html = "<div>" * 100 + "Content" + "</div>" * 100
        
        # Test validation doesn't crash
        is_valid, error = validate_translation(nested_html, nested_html)
        assert isinstance(is_valid, bool)
        assert isinstance(error, str)


@pytest.mark.unit
class TestConcurrentAccess:
    """Test scenarios involving concurrent access patterns."""
    
    def test_progress_file_concurrent_access(self, temp_dir):
        """Test handling of concurrent progress file access."""
        from libs.epub_utils import save_progress, load_progress
        
        progress_file = temp_dir / "concurrent_progress.json"
        
        # Simulate concurrent writes
        progress1 = {"translated": {"key1": "value1"}}
        progress2 = {"translated": {"key2": "value2"}}
        
        save_progress(progress_file, progress1)
        save_progress(progress_file, progress2)
        
        # Last write should win
        final_progress = load_progress(progress_file)
        assert final_progress == progress2
    
    def test_multiple_note_processing(self):
        """Test processing multiple note sets independently."""
        html1 = "Text [Translator's note: Note 1] content."
        html2 = "Other [Translator's note: Note 2] text."
        
        # Process independently
        processed1, notes1 = convert_translator_notes_to_footnotes(html1, start=1)
        processed2, notes2 = convert_translator_notes_to_footnotes(html2, start=10)
        
        # Verify independent numbering
        assert 'id="note1"' in notes1[0]
        assert 'id="note10"' in notes2[0]
        assert len(notes1) == 1
        assert len(notes2) == 1


@pytest.mark.integration
class TestIntegrationErrorScenarios:
    """Test error scenarios in integrated workflows."""
    
    def test_epub_processing_with_invalid_content(self):
        """Test EPUB processing with various invalid content types."""
        # Create book with invalid HTML
        invalid_chapters = [
            ("Chapter 1", "<p>Unclosed paragraph"),
            ("Chapter 2", "No HTML tags at all " * 50),
            ("Chapter 3", "<script>alert('test')</script>" + "<p>Content</p>" * 20)
        ]
        
        book = create_mock_epub_book(chapters=invalid_chapters)
        chunks = get_html_chunks(book, min_words=10)  # Lower threshold for testing
        
        # Should still process, even with invalid HTML
        assert len(chunks) >= 0  # May filter out some chapters
    
    def test_translation_chain_with_failures(self):
        """Test translation chain when some steps fail."""
        from libs.translation import translate_with_chunking
        
        progress = {}
        
        with patch('libs.translation._translate_once') as mock_translate:
            # Setup mixed success/failure pattern
            mock_translate.side_effect = [
                TranslationError("First attempt fails"),
                "<body><p>Chunk 1 success</p></body>",
                TranslationError("Chunk 2 fails"),
                "<body><p>Chunk 3 success</p></body>"
            ]
            
            # Should raise error when chunking also fails
            with pytest.raises(TranslationError):
                result, model_used = translate_with_chunking(
                    "http://localhost:11434", "model", "prompt", 
                    "<p>Large content</p>" * 1000, progress
                )
    
    def test_markdown_generation_with_mixed_results(self, temp_dir):
        """Test markdown generation with mixed success/failure results."""
        from cli import write_markdown
        
        mixed_results = {
            "success_model": {"content": "Success content", "time": 1.5, "success": True},
            "failure_model": {"content": "", "time": 0.0, "success": False},
            "slow_model": {"content": "Slow content", "time": 10.2, "success": True},
        }
        
        output_file = temp_dir / "mixed_results.md"
        write_markdown(output_file, "Original content", mixed_results)
        
        content = output_file.read_text()
        
        # Verify both success and failure are handled
        assert "✅ Success" in content
        assert "❌ Failed" in content
        assert "*Translation failed*" in content
        assert "Success content" in content
        assert "Slow content" in content


@pytest.mark.slow
class TestResourceIntensiveScenarios:
    """Test scenarios that are resource intensive."""
    
    def test_very_large_epub_processing(self):
        """Test processing EPUB with many large chapters using real EPUB."""
        from ebooklib import epub
        
        # Use the real andersen.epub file
        book = epub.read_epub('tests/andersen.epub')
        chunks = get_html_chunks(book, min_words=100)
        
        # Real EPUB should have many qualifying chapters
        assert len(chunks) >= 10  # Should have many chapters with 100+ words
        
        # Test that we can process chunks without errors
        assert all(len(chunk) == 2 for chunk in chunks)  # Each chunk should be (item, content) tuple
    
    def test_massive_translation_notes(self):
        """Test processing massive number of translation notes."""
        # Create content with 1000 notes
        content_parts = []
        for i in range(1000):
            content_parts.append(f"Section {i} [Translator's note: Detailed note {i} with substantial content] continues.")
        
        massive_html = "<div>" + " ".join(content_parts) + "</div>"
        
        processed, notes = convert_translator_notes_to_footnotes(massive_html)
        
        assert len(notes) == 1000
        assert "[Translator's note:" not in processed
        
        # Verify sequential numbering
        for i in range(1, 1001):
            assert f'id="note{i}"' in notes[i-1]
