import pytest
import argparse
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import tempfile
import io
import sys

from cli import (
    truncate_text, extract_plaintext, run_model_translation,
    write_markdown, main, DEFAULT_MODELS
)


class TestTruncateText:
    """Test text truncation functionality."""
    
    def test_short_text_no_truncation(self):
        """Test that short text is not truncated."""
        text = "This is a short text with few words."
        result = truncate_text(text, word_limit=1000)
        assert result == text
    
    def test_exact_limit_no_truncation(self):
        """Test text at exact word limit is not truncated."""
        words = ["word"] * 100
        text = " ".join(words)
        result = truncate_text(text, word_limit=100)
        assert result == text
    
    def test_long_text_truncation(self):
        """Test that long text gets truncated."""
        words = ["word"] * 2000
        text = " ".join(words)
        result = truncate_text(text, word_limit=1000)
        
        # Should be truncated
        assert len(result) < len(text)
        assert result.endswith("...")
    
    def test_truncation_at_sentence_end(self):
        """Test truncation prefers sentence endings."""
        # Create text with sentence ending in first half
        words_first_half = ["word"] * 400
        sentence_first_half = " ".join(words_first_half) + "."
        
        words_second_half = ["word"] * 700
        sentence_second_half = " ".join(words_second_half)
        
        text = sentence_first_half + " " + sentence_second_half
        result = truncate_text(text, word_limit=1000)
        
        # Should truncate at the period
        assert result.endswith(".")
        assert not result.endswith("...")
    
    def test_truncation_respects_various_endings(self):
        """Test truncation works with different sentence endings."""
        endings = [".", "!", "?", "..."]
        
        for ending in endings:
            words_first = ["word"] * 400
            words_second = ["word"] * 700
            text = " ".join(words_first) + ending + " " + " ".join(words_second)
            
            result = truncate_text(text, word_limit=1000)
            assert result.endswith(ending)
    
    def test_whitespace_handling(self):
        """Test proper whitespace handling in truncation."""
        text = "  word1   word2   word3  "
        result = truncate_text(text, word_limit=2)
        # Should handle extra whitespace properly
        assert "word1 word2" in result
    
    def test_empty_text(self):
        """Test truncation of empty text."""
        result = truncate_text("", word_limit=100)
        assert result == ""
    
    def test_custom_word_limit(self):
        """Test truncation with custom word limits."""
        words = ["word"] * 50
        text = " ".join(words)
        
        result = truncate_text(text, word_limit=25)
        result_words = result.replace("...", "").strip().split()
        assert len(result_words) <= 25


class TestExtractPlaintext:
    """Test plaintext extraction from EPUB."""
    
    def test_extract_all_chapters(self, sample_epub):
        """Test extracting all chapters from EPUB."""
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            # Save sample epub to temp file
            from ebooklib import epub
            epub.write_epub(str(tmp_path), sample_epub)
            
            result = extract_plaintext(tmp_path, "en")
            
            # Should contain content from valid chapters
            assert "Chapter 1" in result
            assert "first chapter" in result
            # Should not contain short chapter content (below word limit)
        finally:
            tmp_path.unlink(missing_ok=True)
    
    def test_extract_specific_chapter(self, sample_epub):
        """Test extracting specific chapter from EPUB."""
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            from ebooklib import epub
            epub.write_epub(str(tmp_path), sample_epub)
            
            result = extract_plaintext(tmp_path, "en", chapter_only=1)
            
            # Should contain only first chapter content
            assert "Chapter 1" in result
            assert "first chapter" in result
        finally:
            tmp_path.unlink(missing_ok=True)
    
    def test_extract_nonexistent_chapter(self, sample_epub):
        """Test extracting non-existent chapter returns empty string."""
        with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as tmp:
            tmp_path = Path(tmp.name)
            
        try:
            from ebooklib import epub
            epub.write_epub(str(tmp_path), sample_epub)
            
            result = extract_plaintext(tmp_path, "en", chapter_only=999)
            assert result == ""
        finally:
            tmp_path.unlink(missing_ok=True)


class TestRunModelTranslation:
    """Test model translation functionality."""
    
    @patch('cli.translate_with_chunking')
    @patch('cli.convert_translator_notes_to_footnotes')
    @patch('cli.get_html_chunks')
    @patch('cli.epub.read_epub')
    def test_successful_translation(self, mock_read_epub, mock_get_chunks, 
                                  mock_convert_notes, mock_translate):
        """Test successful model translation."""
        # Setup mocks
        mock_epub = Mock()
        mock_read_epub.return_value = mock_epub
        
        mock_get_chunks.return_value = [
            (Mock(), b'<p>Original HTML content</p>')
        ]
        
        mock_translate.return_value = '<p>Translated HTML content</p>'
        mock_convert_notes.return_value = ('<p>Translated content</p>', [])
        
        result, elapsed = run_model_translation(
            "test-model", 1, "en", Path("test.epub"), 
            "Test prompt", "http://localhost:11434"
        )
        
        assert "Translated content" in result
        assert isinstance(elapsed, float)
        assert elapsed >= 0
    
    @patch('cli.get_html_chunks')
    @patch('cli.epub.read_epub')
    def test_chapter_not_found(self, mock_read_epub, mock_get_chunks):
        """Test error when chapter is not found."""
        mock_epub = Mock()
        mock_read_epub.return_value = mock_epub
        mock_get_chunks.return_value = []  # No chunks found
        
        with pytest.raises(ValueError, match="Chapter 1 not found"):
            run_model_translation(
                "test-model", 1, "en", Path("test.epub"),
                "Test prompt", "http://localhost:11434"
            )


class TestWriteMarkdown:
    """Test markdown output writing functionality."""
    
    def test_write_comparison_markdown(self, temp_dir):
        """Test writing model comparison markdown."""
        out_file = temp_dir / "comparison.md"
        original = "This is the original text content."
        model_data = {
            "model1": {"content": "Translated by model 1", "time": 1.5, "success": True},
            "model2": {"content": "Translated by model 2", "time": 2.3, "success": True},
            "model3": {"content": "", "time": 0, "success": False}
        }
        
        write_markdown(out_file, original, model_data)
        
        assert out_file.exists()
        content = out_file.read_text(encoding='utf-8')
        
        # Check structure
        assert "# Model Comparison - Chapter Output" in content
        assert "## Original (truncated)" in content
        assert "## Timing Summary" in content
        
        # Check model sections
        assert "model1" in content
        assert "model2" in content
        assert "model3" in content
        
        # Check success/failure indicators
        assert "✅ Success" in content
        assert "❌ Failed" in content
        
        # Check that failed translation shows appropriate message
        assert "*Translation failed*" in content
    
    def test_markdown_timing_order(self, temp_dir):
        """Test that models are ordered by translation time."""
        out_file = temp_dir / "comparison.md"
        original = "Original text"
        model_data = {
            "slow_model": {"content": "Content", "time": 10.0, "success": True},
            "fast_model": {"content": "Content", "time": 1.0, "success": True},
            "medium_model": {"content": "Content", "time": 5.0, "success": True}
        }
        
        write_markdown(out_file, original, model_data)
        content = out_file.read_text(encoding='utf-8')
        
        # Fast model should appear before medium, medium before slow
        fast_pos = content.find("fast_model")
        medium_pos = content.find("medium_model")
        slow_pos = content.find("slow_model")
        
        assert fast_pos < medium_pos < slow_pos


class TestMainFunction:
    """Test main CLI function."""
    
    def test_argument_parsing_required_args(self):
        """Test that required arguments are enforced."""
        # Mock sys.argv to test argument parsing
        test_args = ["cli.py"]  # Missing required arguments
        
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit):  # argparse calls sys.exit on error
                main()
    
    @patch('cli.setup_logging')
    @patch('cli.PREDEFINED_PROMPTS', {'literary': 'Test prompt for {target_language}'})
    def test_prompt_formatting(self, mock_setup_logging):
        """Test that prompts are properly formatted with target language."""
        test_args = [
            "cli.py", "-f", "test.epub", "-l", "French",
            "--compare", "", "--chapter", "1"
        ]
        
        with patch.object(sys, 'argv', test_args):
            with patch('cli.DEFAULT_MODELS', ['test-model']):
                with patch('cli.run_model_translation') as mock_translate:
                    with patch('cli.extract_plaintext') as mock_extract:
                        with patch('cli.write_markdown') as mock_write:
                            mock_translate.return_value = ("content", 1.0)
                            mock_extract.return_value = "original"
                            
                            try:
                                main()
                            except SystemExit:
                                pass  # Expected for successful completion
                            
                            # Check that the prompt was formatted with the target language
                            if mock_translate.called:
                                call_args = mock_translate.call_args[0]
                                prompt = call_args[4]  # prompt is 5th argument
                                assert "French" in prompt
    
    def test_default_models_list(self):
        """Test that default models list is properly defined."""
        assert isinstance(DEFAULT_MODELS, list)
        assert len(DEFAULT_MODELS) > 0
        assert all(isinstance(model, str) for model in DEFAULT_MODELS)
        
        # Check some expected models
        expected_models = ["nous-hermes2", "mistral:7b"]
        for model in expected_models:
            assert model in DEFAULT_MODELS
    
    @patch('cli.setup_logging')
    def test_debug_mode_enables_logging(self, mock_setup_logging):
        """Test that debug mode properly enables debug logging."""
        test_args = [
            "cli.py", "-f", "test.epub", "-l", "en", "--debug",
            "--compare", "", "--chapter", "1"
        ]
        
        with patch.object(sys, 'argv', test_args):
            with patch('cli.run_model_translation', side_effect=SystemExit):
                with patch('cli.extract_plaintext'):
                    try:
                        main()
                    except SystemExit:
                        pass
                    
                    mock_setup_logging.assert_called_with(True)
    
    def test_compare_mode_requires_chapter(self):
        """Test that compare mode requires chapter argument."""
        test_args = [
            "cli.py", "-f", "test.epub", "-l", "en", "--compare"
            # Missing --chapter argument
        ]
        
        with patch.object(sys, 'argv', test_args):
            with patch('cli.setup_logging'):
                with pytest.raises(SystemExit):
                    main()


class TestDefaultModels:
    """Test default models configuration."""
    
    def test_models_list_structure(self):
        """Test that DEFAULT_MODELS has expected structure."""
        assert isinstance(DEFAULT_MODELS, list)
        assert len(DEFAULT_MODELS) > 0
        
        for model in DEFAULT_MODELS:
            assert isinstance(model, str)
            assert len(model.strip()) > 0
    
    def test_contains_expected_models(self):
        """Test that DEFAULT_MODELS contains expected model names."""
        # Check for some models that should be in the list
        expected_patterns = [
            "gemma",
            "mistral",
            "nous-hermes"
        ]
        
        model_string = " ".join(DEFAULT_MODELS).lower()
        for pattern in expected_patterns:
            assert pattern in model_string, f"Expected to find '{pattern}' in models list"
    
    def test_no_duplicate_models(self):
        """Test that there are no duplicate models in the list."""
        assert len(DEFAULT_MODELS) == len(set(DEFAULT_MODELS)), "Duplicate models found in DEFAULT_MODELS"
    
    def test_model_name_format(self):
        """Test that model names follow expected format patterns."""
        for model in DEFAULT_MODELS:
            # Model names should not contain spaces
            assert " " not in model, f"Model name '{model}' contains spaces"
            # Should not start or end with special characters
            assert not model.startswith("/"), f"Model name '{model}' starts with slash"
            assert not model.endswith("/"), f"Model name '{model}' ends with slash"
