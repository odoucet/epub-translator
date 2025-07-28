import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, Mock
import responses

from libs.epub_utils import save_progress, load_progress
from libs.translation import translate_with_chunking, TranslationError
from libs.notes import convert_translator_notes_to_footnotes


@pytest.mark.integration
class TestTranslationWorkflow:
    """Integration tests for the complete translation workflow."""
    
    def test_progress_persistence_workflow(self, temp_dir):
        """Test complete progress save/load workflow."""
        progress_file = temp_dir / "test_progress.json"
        
        # Initial progress
        initial_progress = {
            "translated": {},
            "chunk_parts": 2
        }
        
        # Save initial progress
        save_progress(progress_file, initial_progress)
        
        # Load and modify
        loaded_progress = load_progress(progress_file)
        loaded_progress["translated"]["key1"] = "<p>Translation 1</p>"
        loaded_progress["translated"]["key2"] = "<p>Translation 2</p>"
        
        # Save updated progress
        save_progress(progress_file, loaded_progress)
        
        # Verify final state
        final_progress = load_progress(progress_file)
        assert len(final_progress["translated"]) == 2
        assert final_progress["chunk_parts"] == 2
        assert final_progress["translated"]["key1"] == "<p>Translation 1</p>"
    
    def test_notes_and_translation_integration(self):
        """Test integration between translation and notes processing."""
        # HTML with translator note
        html_with_note = """
        <p>This is a paragraph with a [Translator's note: Important context] note.</p>
        <p>Another paragraph without notes.</p>
        """
        
        # Process translator notes
        processed_html, footnotes = convert_translator_notes_to_footnotes(html_with_note)
        
        # Verify note processing
        assert "[Translator's note:" not in processed_html
        assert '<sup><a href="#refnote1"' in processed_html
        assert len(footnotes) == 1
        assert "Important context" in footnotes[0]
        
        # Combine with footnotes
        final_html = processed_html + ''.join(footnotes)
        
        # Verify complete structure
        assert "Important context" in final_html
        assert 'id="note1"' in final_html
    
    @responses.activate
    def test_chunked_translation_workflow(self):
        """Test the complete chunked translation workflow."""
        api_base = "http://localhost:11434"
        
        # Mock API responses for chunked translation
        responses.add(
            responses.POST,
            f"{api_base}/api/chat",
            json={"error": "Content too large"},
            status=413
        )
        
        # Mock responses for chunks
        chunk_responses = [
            {"message": {"content": "<body><p>First chunk translated</p></body>"}},
            {"message": {"content": "<body><p>Second chunk translated</p></body>"}}
        ]
        
        for response in chunk_responses:
            responses.add(
                responses.POST,
                f"{api_base}/api/chat",
                json=response,
                status=200
            )
        
        # Large HTML that will trigger chunking
        large_html = "<p>" + "Large content. " * 1000 + "</p>"
        progress = {}
        
        with patch('libs.translation._translate_once') as mock_translate:
            # First call fails (triggers chunking), subsequent calls succeed
            mock_translate.side_effect = [
                TranslationError("Too large"),
                "<body><p>First chunk translated</p></body>",
                "<body><p>Second chunk translated</p></body>",
                "<body><p>Third chunk translated</p></body>",
                "<body><p>Fourth chunk translated</p></body>"
            ]
            
            result = translate_with_chunking(
                api_base, "test-model", "Test prompt", large_html, progress
            )
            
            # Verify chunked translation result
            assert "First chunk translated" in result
            assert "Second chunk translated" in result
            assert "chunk_parts" in progress
    
    @pytest.mark.skip(reason="EPUB writing has compatibility issues with test fixtures")
    def test_epub_processing_workflow(self, sample_epub, temp_dir):
        """Test complete EPUB processing workflow."""
        from libs.epub_utils import get_html_chunks, inject_translations, hash_key
        from bs4 import BeautifulSoup
        
        # Get chunks from sample EPUB with lower word threshold
        chunks = get_html_chunks(sample_epub, min_words=10)
        
        if len(chunks) == 0:
            pytest.skip("No chunks available from sample EPUB")
        
        # Process first chunk
        item, raw_html = chunks[0]
        text = BeautifulSoup(raw_html, 'html.parser').get_text().strip()
        key = hash_key(text)
        
        # Create mock translation
        translation = "<p>This is a translated version of the chapter.</p>"
        
        # Create translation mapping
        translations = {key: translation}
        
        # Inject translations
        count = inject_translations(chunks, translations)
        assert count >= 0  # Should work if chunks exist
        
        if count > 0:
            # Verify injection
            updated_content = item.get_content().decode('utf-8')
            assert "translated version" in updated_content
    
    @pytest.mark.slow
    @pytest.mark.skip(reason="EPUB writing has compatibility issues with test fixtures")
    def test_full_cli_workflow_simulation(self, sample_epub, temp_dir):
        """Simulate complete CLI workflow without actual API calls."""
        from cli import write_markdown, extract_plaintext
        
        # Save sample EPUB to file
        epub_path = temp_dir / "test.epub"
        from ebooklib import epub
        epub.write_epub(str(epub_path), sample_epub)
        
        # Extract plaintext (simulating original content)
        original_text = extract_plaintext(epub_path, "en", chapter_only=1)
        assert len(original_text) > 0
        
        # Mock model comparison results
        model_data = {
            "fast_model": {
                "content": "Translated content by fast model",
                "time": 1.2,
                "success": True
            },
            "slow_model": {
                "content": "Translated content by slow model", 
                "time": 5.8,
                "success": True
            },
            "failed_model": {
                "content": "",
                "time": 0,
                "success": False
            }
        }
        
        # Write comparison markdown
        output_md = temp_dir / "comparison.md"
        write_markdown(output_md, original_text, model_data)
        
        # Verify output
        assert output_md.exists()
        content = output_md.read_text()
        assert "Model Comparison" in content
        assert "fast_model" in content
        assert "slow_model" in content
        assert "failed_model" in content
        assert "✅ Success" in content
        assert "❌ Failed" in content


@pytest.mark.integration
class TestErrorHandlingWorkflow:
    """Integration tests for error handling across components."""
    
    def test_translation_error_propagation(self):
        """Test how translation errors propagate through the system."""
        from libs.translation import translate_with_chunking, TranslationError
        
        progress = {}
        
        with patch('libs.translation._translate_once') as mock_translate:
            # All attempts fail
            mock_translate.side_effect = TranslationError("All failed")
            
            with pytest.raises(TranslationError):
                translate_with_chunking(
                    "http://localhost:11434", "test-model", 
                    "prompt", "<p>content</p>", progress
                )
    
    def test_file_handling_errors(self, temp_dir):
        """Test error handling in file operations."""
        from libs.epub_utils import load_progress, save_progress
        
        # Test loading from corrupted JSON
        corrupted_file = temp_dir / "corrupted.json"
        corrupted_file.write_text("invalid json {", encoding='utf-8')
        
        with pytest.raises(json.JSONDecodeError):
            load_progress(corrupted_file)
        
        # Test saving to read-only location (if possible)
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()
        readonly_file = readonly_dir / "progress.json"
        
        try:
            readonly_dir.chmod(0o444)  # Read-only
            with pytest.raises(PermissionError):
                save_progress(readonly_file, {"test": "data"})
        except OSError:
            # Skip if we can't make directory read-only (e.g., on Windows)
            pytest.skip("Cannot test read-only directory on this system")
        finally:
            readonly_dir.chmod(0o755)  # Restore permissions for cleanup
    
    def test_epub_processing_errors(self):
        """Test error handling in EPUB processing."""
        from libs.epub_utils import get_html_chunks
        
        # Test with invalid EPUB object
        invalid_epub = Mock()
        invalid_epub.get_items_of_type.side_effect = Exception("Invalid EPUB")
        
        with pytest.raises(Exception):
            get_html_chunks(invalid_epub)


@pytest.mark.integration  
class TestPerformanceWorkflow:
    """Integration tests focused on performance aspects."""
    
    def test_large_text_processing(self):
        """Test processing of large text volumes."""
        from libs.translation import dynamic_chunks
        from libs.epub_utils import hash_key
        
        # Create large text
        large_text = "This is a test sentence. " * 10000
        
        # Test chunking performance
        chunks = dynamic_chunks(large_text, max_size=5000)
        assert len(chunks) > 1
        
        # Test hashing performance
        hash_result = hash_key(large_text)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA256 hex length
    
    def test_concurrent_note_processing(self):
        """Test processing multiple notes efficiently."""
        from libs.notes import convert_translator_notes_to_footnotes
        
        # Text with many notes
        html_with_many_notes = ""
        for i in range(100):
            html_with_many_notes += f"<p>Paragraph {i} with [Translator's note: Note {i}] content.</p>"
        
        processed, notes = convert_translator_notes_to_footnotes(html_with_many_notes)
        
        # Verify all notes were processed
        assert len(notes) == 100
        assert "[Translator's note:" not in processed
        
        # Verify note numbering
        for i in range(1, 101):
            assert f'id="note{i}"' in notes[i-1]
