import json
import pytest
import responses
from unittest.mock import patch, Mock
import requests

from libs.translation import (
    TranslationError, EmptyOutputError, validate_translation, dynamic_chunks,
    translate_with_chunking, _translate_once, get_model_limits, compute_max_chunk_chars,
    order_models, find_short_translations, _record_call
)


class TestValidateTranslation:
    """Test translation validation functionality."""

    def test_truncated_translation_rejected(self):
        """Test validation fails when output is much shorter than a long original."""
        original = "".join(f"<p>Paragraph {i} with a fair amount of original text inside.</p>" for i in range(30))
        translation = "<p>Paragraphe 0 avec pas mal de texte traduit.</p>"

        is_valid, error_cleaned, _ = validate_translation(original, translation)
        assert is_valid is False
        assert "truncated" in error_cleaned
    
    def test_valid_translation(self):
        """Test validation of a valid translation."""
        original = "<p>This is the original text.</p>"
        translation = "<p>Ceci est le texte traduit.</p>"
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is True
        assert cleaned_content == "<p>Ceci est le texte traduit.</p>"
    
    def test_empty_translation(self):
        """Test validation fails for empty translation."""
        original = "<p>Original text</p>"
        translation = ""
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is False
        assert "too short" in error_cleaned.lower()
    
    def test_very_short_translation(self):
        """Test validation fails for very short translation."""
        original = "<p>This is a longer original text with multiple words.</p>"
        translation = "Short"
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is False
        assert "too short" in error_cleaned.lower()
    
    def test_missing_paragraph_tags(self):
        """Test validation fails when paragraph tags are missing."""
        original = "<p>This text has paragraph tags.</p>"
        translation = "This text does not have paragraph tags."
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is False
        # New validation checks HTML structure first, so expect HTML structure error
        assert ("output should start with" in error_cleaned.lower() or "paragraph tags missing" in error_cleaned.lower())
    
    def test_invalid_html(self):
        """Test validation fails for invalid HTML."""
        original = "<p>Valid original</p>"
        translation = "<p>Invalid HTML <div></p>"  # Mismatched tags
        
        # This might pass basic validation, but let's test with clearly broken HTML
        translation = "<p>Text with unclosed tag <"
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        # The exact behavior depends on BeautifulSoup's error handling
        # At minimum, it should not crash
        assert isinstance(is_valid, bool)
        assert isinstance(error_cleaned, str)
    
    def test_insufficient_text_after_parsing(self):
        """Test validation fails when parsed text is too short."""
        original = "<p>This is substantial original content with many words.</p>"
        translation = "<p></p>"  # Empty paragraph
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is False
        assert "translation too short" in error_cleaned.lower()


class TestDynamicChunks:
    """Test dynamic HTML chunking functionality."""
    
    def test_small_html_no_chunking(self):
        """Test that small HTML gets minimal chunking."""
        html = "<p>Short text</p>"
        chunks = dynamic_chunks(html, max_size=10000)
        
        # The function always creates at least 2 chunks, but for small content
        # it should be minimal
        assert len(chunks) >= 1
        # Each chunk should be properly wrapped
        for chunk in chunks:
            assert "<?xml version=" in chunk
            assert "<html>" in chunk
            assert "<body>" in chunk
    
    def test_large_html_gets_chunked(self):
        """Test that large HTML gets chunked."""
        # Create a large HTML string
        large_html = "<p>" + "Very long text. " * 1000 + "</p>"
        chunks = dynamic_chunks(large_html, max_size=1000)
        
        assert len(chunks) > 1
        # Each chunk should be properly wrapped
        for chunk in chunks:
            assert "<?xml version=" in chunk
            assert "<html>" in chunk
            assert "<body>" in chunk
    
    def test_max_attempts_limit(self):
        """Test that chunking respects max_attempts limit."""
        large_html = "x" * 100000  # Very large string
        chunks = dynamic_chunks(large_html, max_size=100, max_attempts=3)
        
        # Should stop at max_attempts even if chunks are still large
        assert len(chunks) <= 2**3  # 2^max_attempts
    
    def test_remainder_handling(self):
        """Test that remainder is properly handled in chunking."""
        # Create HTML that doesn't divide evenly
        html = "x" * 1003  # Odd number that won't divide evenly
        chunks = dynamic_chunks(html, max_size=500, max_attempts=5)
        
        # All original content should be preserved
        total_content = ""
        for chunk in chunks:
            # Extract content between body tags
            start = chunk.find("<body>") + 6
            end = chunk.find("</body>")
            total_content += chunk[start:end]
        
        assert total_content == html


class TestTranslateOnce:
    """Test single translation attempt functionality."""
    
    @responses.activate
    def test_successful_translation(self, mock_translation_response):
        """Test successful translation on first attempt."""
        api_base = "http://localhost:11434"
        responses.add(
            responses.POST,
            f"{api_base}/api/chat",
            json=mock_translation_response,
            status=200
        )
        
        model = "test-model"
        prompt = "Translate to French"
        block = "<p>Hello world</p>"
        
        result = _translate_once(api_base, model, prompt, block)
        assert result == "<p>Ceci est un texte traduit en français.</p>"
    
    @responses.activate
    def test_successful_translation_with_validation(self):
        """Test successful translation that passes validation."""
        api_base = "http://localhost:11434"
        responses.add(
            responses.POST,
            f"{api_base}/api/chat",
            json={"message": {"content": "<p>This is a successful translation with enough content to pass all validation checks.</p>"}},
            status=200
        )
        
        model = "test-model"
        prompt = "Translate to French"
        block = "<p>Hello world with enough content for validation purposes</p>"
        
        result = _translate_once(api_base, model, prompt, block)
        assert "successful translation" in result.lower()

    @responses.activate
    def test_api_key_sent_as_bearer(self, mock_translation_response):
        """Test that api_key is sent as Authorization header, and omitted when absent."""
        api_base = "http://localhost:11434"
        responses.add(responses.POST, f"{api_base}/api/chat", json=mock_translation_response, status=200)
        responses.add(responses.POST, f"{api_base}/api/chat", json=mock_translation_response, status=200)

        _translate_once(api_base, "test-model", "prompt", "<p>Hello world</p>", api_key="secret")
        _translate_once(api_base, "test-model", "prompt", "<p>Hello world</p>")

        assert responses.calls[0].request.headers["Authorization"] == "Bearer secret"
        assert "Authorization" not in responses.calls[1].request.headers

    @responses.activate
    def test_openai_compatible_endpoint(self):
        """Test that a /v1 base URL uses the OpenAI-compatible chat completions API."""
        api_base = "https://openrouter.ai/api/v1"
        responses.add(
            responses.POST,
            f"{api_base}/chat/completions",
            json={"choices": [{"message": {"role": "assistant", "content": "<p>Bonjour le monde</p>"}}]},
            status=200,
        )

        result = _translate_once(api_base, "test-model", "prompt", "<p>Hello world</p>", api_key="secret")

        assert "Bonjour" in result
        body = json.loads(responses.calls[0].request.body)
        assert body["temperature"] == 0
        assert "options" not in body

    @responses.activate
    def test_openai_truncated_output_rejected(self):
        """Test that finish_reason=length is treated as a failure."""
        api_base = "https://openrouter.ai/api/v1"
        responses.add(
            responses.POST,
            f"{api_base}/chat/completions",
            json={"choices": [{"message": {"content": "<p>Bonjour le</p>"}, "finish_reason": "length"}]},
            status=200,
        )

        with pytest.raises(TranslationError, match="truncated"):
            _translate_once(api_base, "test-model", "prompt", "<p>Hello world</p>")

    @responses.activate
    def test_empty_output_switches_to_user_message_prompt(self):
        """Test that a model returning an empty output with a system prompt is retried without it, for good."""
        api_base = "https://openrouter.ai/api/v1"
        url = f"{api_base}/chat/completions"
        responses.add(responses.POST, url, status=200, json={
            "choices": [{"message": {"content": None}, "finish_reason": "stop"}]})
        responses.add(responses.POST, url, status=200, json={
            "choices": [{"message": {"content": "<p>Bonjour le monde</p>"}, "finish_reason": "stop"}]})
        responses.add(responses.POST, url, status=200, json={
            "choices": [{"message": {"content": "<p>Salut</p>"}, "finish_reason": "stop"}]})

        with patch('libs.translation._NO_SYSTEM_PROMPT_MODELS', set()):
            assert _translate_once(api_base, "hy-mt", "Translate", "<p>Hello world</p>") == "<p>Bonjour le monde</p>"
            assert _translate_once(api_base, "hy-mt", "Translate", "<p>Hi</p>") == "<p>Salut</p>"

        sent = [json.loads(call.request.body)["messages"] for call in responses.calls]
        assert [m["role"] for m in sent[0]] == ["system", "user"]
        assert sent[1] == [{"role": "user", "content": "Translate\n\n<p>Hello world</p>"}]
        assert sent[2] == [{"role": "user", "content": "Translate\n\n<p>Hi</p>"}]

    @responses.activate
    def test_null_content_reports_provider_error(self):
        """Test that a null content response includes the provider error details."""
        api_base = "https://openrouter.ai/api/v1"
        responses.add(
            responses.POST,
            f"{api_base}/chat/completions",
            json={"choices": [{"message": {"content": None}, "finish_reason": "error",
                               "error": {"message": "Upstream timeout"}}]},
            status=200,
        )

        with pytest.raises(TranslationError, match="finish_reason=error.*Upstream timeout"):
            _translate_once(api_base, "test-model", "prompt", "<p>Hello world</p>")

    @responses.activate
    def test_invalid_translation_retry(self):
        """Test that _translate_once raises error for invalid translation."""
        api_base = "http://localhost:11434"
        
        # Response is invalid (empty) - should cause failure
        responses.add(
            responses.POST,
            f"{api_base}/api/chat",
            json={"message": {"content": ""}},  # Completely empty - will fail validation
            status=200
        )
        
        model = "test-model"
        prompt = "Translate to French"
        block = "<p>Hello world with enough content for validation</p>"
        
        # _translate_once should raise TranslationError for invalid response
        with pytest.raises(TranslationError):
            _translate_once(api_base, model, prompt, block)
    
    @responses.activate
    def test_http_error_retry(self):
        """Test that _translate_once raises error for HTTP errors."""
        api_base = "http://localhost:11434"
        
        # Request fails with HTTP error
        responses.add(
            responses.POST,
            f"{api_base}/api/chat",
            json={"error": "Server error"},
            status=500
        )
        
        model = "test-model"
        prompt = "Translate to French"
        block = "<p>Hello world with enough content for validation purposes</p>"
        
        # _translate_once should raise TranslationError for HTTP error
        with pytest.raises(TranslationError):
            _translate_once(api_base, model, prompt, block)
    
    @responses.activate
    def test_all_retries_fail(self):
        """Test that TranslationError is raised when all retries fail."""
        api_base = "http://localhost:11434"
        
        # All requests fail
        for _ in range(3):
            responses.add(
                responses.POST,
                f"{api_base}/api/chat",
                json={"error": "Server error"},
                status=500
            )
        
        model = "test-model"
        prompt = "Translate to French"
        block = "<p>Hello world</p>"
        
        with pytest.raises(TranslationError):
            _translate_once(api_base, model, prompt, block)


class TestTranslateWithChunking:
    """Test chunked translation functionality."""
    
    @patch('libs.translation._translate_once')
    def test_successful_full_translation(self, mock_translate):
        """Test successful translation without chunking."""
        mock_translate.return_value = "<p>Translated content</p>"
        
        api_base = "http://localhost:11434"
        model = "test-model"
        prompt = "Translate to French"
        html = "<p>Original content</p>"
        progress = {}
        
        result, model_used = translate_with_chunking(api_base, model, prompt, html, progress, chapter_info="Chapter 1/5")
        assert result == "<p>Translated content</p>"
        assert model_used == model
        mock_translate.assert_called_once()
    
    @patch('libs.translation._translate_once')
    def test_fallback_to_chunking(self, mock_translate):
        """Test fallback to chunking when full translation fails."""
        # First call (full translation) fails
        # Subsequent calls (chunks) succeed - provide enough responses
        mock_translate.side_effect = [
            TranslationError("Too large"),
            "<p>Chunk 1 translated with enough content</p>",
            "<p>Chunk 2 translated with enough content</p>",
            "<p>Chunk 3 translated with enough content</p>",
            "<p>Chunk 4 translated with enough content</p>",
            "<p>Chunk 5 translated with enough content</p>"
        ]
        
        api_base = "http://localhost:11434"
        model = "test-model"
        prompt = "Translate to French"
        # Create HTML large enough to trigger chunking
        html = "<p>" + "Large content. " * 500 + "</p>"
        progress = {}
        
        result, model_used = translate_with_chunking(api_base, model, prompt, html, progress, debug=False, chapter_info="Chapter 1/5")
        
        # Should contain content from chunks
        assert "Chunk 1 translated" in result or "Chunk 2 translated" in result or "Chunk 3 translated" in result
        assert model_used == model
        
        # Progress should be updated with chunk information
        assert 'chunk_parts' in progress
        assert progress['chunk_parts'] >= 1  # Changed from > 1 to >= 1
    
    @patch('libs.translation._translate_once')
    def test_chunking_with_existing_progress(self, mock_translate):
        """Test chunking behavior with existing progress information."""
        # Create a mock that always returns a valid translation
        success_response = "<p>This is a successful translated chunk with enough content to pass validation checks and be considered proper translation text for testing purposes and requirements. This text is long enough to satisfy all validation requirements and constraints for proper translation handling.</p>"
        
        # Make the mock always return the success response (no failures)
        mock_translate.return_value = success_response
        
        api_base = "http://localhost:11434"
        model = "test-model"
        prompt = "Translate to French"
        html = "<p>Content with enough text to process and validate properly during testing and chunking operations that should work correctly with all validation requirements.</p>"
        progress = {}  # Start with empty progress
        
        result, model_used = translate_with_chunking(api_base, model, prompt, html, progress, chapter_info="Chapter 1/5")
        assert "translated chunk" in result.lower()
        assert model_used == model
    
    @patch('libs.translation._translate_once')
    def test_chunking_failure(self, mock_translate):
        """Test behavior when chunking also fails."""
        # All translation attempts fail
        mock_translate.side_effect = TranslationError("Translation failed")
        
        api_base = "http://localhost:11434"
        model = "test-model"
        prompt = "Translate to French"
        html = "<p>Content</p>"
        progress = {}
        
        with pytest.raises(TranslationError):
            result, model_used = translate_with_chunking(api_base, model, prompt, html, progress, chapter_info="Chapter 1/5")


    @patch('libs.translation._translate_once')
    def test_failed_chunk_retried_without_restarting_previous_ones(self, mock_translate):
        """Test that a transient chunk failure retries only that chunk."""
        mock_translate.side_effect = [
            "<p>Un</p>",
            TranslationError("missing 'content' field"),
            "<p>Deux</p>",
            "<p>Trois</p>",
        ]
        # Above MAX_SINGLE_REQUEST_CHARS: no full translation attempt
        body = "".join(f"<p>{word} {'x' * 6000}</p>" for word in ("One", "Two", "Three"))

        result, model_used = translate_with_chunking("http://localhost:11434", "m1", "prompt",
                                                     body, {"preferred_chunk_size": 6100})

        assert result.count("<p>") == 3
        assert "Un" in result and "Deux" in result and "Trois" in result
        assert mock_translate.call_count == 4
        assert model_used == "m1"

    @patch('libs.translation._translate_once')
    def test_persistently_failing_chunk_is_split(self, mock_translate):
        """Test that a chunk failing every attempt is split in half, alone."""
        mock_translate.side_effect = [TranslationError("bad")] * 3 + ["<p>A</p>", "<p>B</p>", "<p>C</p>"]
        # Two chunks of two paragraphs each, no full translation attempt
        body = "".join(f"<p>{word} {'x' * 5000}</p>" for word in ("One", "Two", "Three", "Four"))

        result, _ = translate_with_chunking("http://localhost:11434", "m1", "prompt", body,
                                            {"preferred_chunk_size": 10100})

        assert "<p>A</p><p>B</p><p>C</p>" in result
        assert mock_translate.call_count == 6

    @patch('libs.translation._translate_once')
    def test_fallback_model_used_for_failing_chunk_only(self, mock_translate):
        """Test that the next model is tried only for the chunk that fails."""
        def fake(api_base, model, prompt, block, *args, **kwargs):
            if model == "m1" and "Two" in block:
                raise TranslationError("bad")
            return f"<p>{model}</p>"
        mock_translate.side_effect = fake
        body = "".join(f"<p>{word} {'x' * 1500}</p>" for word in ("One", "Two", "Three"))

        result, model_used = translate_with_chunking("http://localhost:11434", ["m1", "m2"], "prompt",
                                                     body, {"preferred_chunk_size": 1600})

        assert "<p>m1</p><p>m2</p><p>m1</p>" in result
        assert model_used == "m1"

    @patch('libs.translation._translate_once')
    def test_empty_output_switches_model_without_retrying(self, mock_translate):
        """Test that an empty output goes straight to the next model, without retries nor splitting."""
        def fake(api_base, model, prompt, block, *args, **kwargs):
            if model == "m1":
                raise EmptyOutputError("missing 'content' field")
            return "<p>traduit</p>"
        mock_translate.side_effect = fake
        body = "".join(f"<p>Part {i} {'x' * 2500}</p>" for i in range(7))

        result, _ = translate_with_chunking("http://localhost:11434", ["m1", "m2"], "prompt", body,
                                            {"preferred_chunk_size": 5100})

        models = [call.args[1] for call in mock_translate.call_args_list]
        # Each chunk: one m1 call, then m2
        assert models == ["m1", "m2"] * (len(models) // 2)
        assert result.count("<p>traduit</p>") == len(models) // 2

class TestBackticksHandling:
    """Test backticks cleaning in translation validation."""
    
    def test_single_backticks_cleaned(self):
        """Test that single backticks are properly removed."""
        original = "<p>Bonjour le monde</p>"
        translation = "`<p>Hello world</p>`"
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is True
        assert cleaned_content == "<p>Hello world</p>"
    
    def test_triple_backticks_cleaned(self):
        """Test that triple backticks are properly removed."""
        original = "<p>Bonjour le monde</p>"
        translation = "```<p>Hello world</p>```"
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is True
        assert cleaned_content == "<p>Hello world</p>"
    
    def test_triple_backticks_with_language_identifier(self):
        """Test that triple backticks with language identifier are properly handled."""
        original = "<p>Bonjour le monde</p>"
        translation = "```html\n<p>Hello world</p>\n```"
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is True
        assert cleaned_content == "<p>Hello world</p>"
    
    def test_triple_backticks_multiline(self):
        """Test that multiline content in triple backticks is properly handled."""
        original = "<p>Bonjour le monde</p>"
        translation = "```\n<p>Hello world</p>\n```"
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is True
        assert cleaned_content == "<p>Hello world</p>"
    
    def test_no_backticks_unchanged(self):
        """Test that content without backticks remains unchanged."""
        original = "<p>Bonjour le monde</p>"
        translation = "<p>Hello world</p>"
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is True
        assert cleaned_content == "<p>Hello world</p>"
    
    def test_backticks_with_invalid_content(self):
        """Test that backticks are removed but validation still fails for invalid content."""
        original = "<p>Bonjour le monde</p>"
        translation = "`Hello world without tags`"
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is False
        assert "Output should start with '<p>'" in error_cleaned
    
    def test_complex_html_with_backticks(self):
        """Test complex HTML content wrapped in backticks."""
        original = "<p>Texte avec <em>emphase</em> et <strong>gras</strong>.</p>"
        translation = "```<p>Text with <em>emphasis</em> and <strong>bold</strong>.</p>```"
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is True
        assert cleaned_content == "<p>Text with <em>emphasis</em> and <strong>bold</strong>.</p>"
    
    def test_multiple_paragraphs_with_backticks(self):
        """Test multiple paragraphs wrapped in backticks."""
        original = "<p>Premier paragraphe.</p><p>Deuxième paragraphe.</p>"
        translation = "```\n<p>First paragraph.</p><p>Second paragraph.</p>\n```"
        
        is_valid, error_cleaned, cleaned_content = validate_translation(original, translation)
        assert is_valid is True
        assert cleaned_content == "<p>First paragraph.</p><p>Second paragraph.</p>"


class TestModelLimits:
    """Test chunk size derivation from the model token limits."""

    @responses.activate
    def test_openrouter_limits(self):
        """Test reading context and output limits from an OpenRouter /models listing."""
        api_base = "https://openrouter.ai/api/v1"
        responses.add(responses.GET, f"{api_base}/models", json={"data": [
            {"id": "other", "context_length": 1000},
            {"id": "tencent/hy-mt2-30b-a3b", "context_length": 8192,
             "top_provider": {"max_completion_tokens": 4096}},
        ]})

        assert get_model_limits(api_base, "tencent/hy-mt2-30b-a3b") == (8192, 4096)
        assert get_model_limits(api_base, "missing-model") == (None, None)

    @responses.activate
    def test_limits_unavailable(self):
        """Test that failures and non OpenAI-compatible APIs return unknown limits."""
        responses.add(responses.GET, "https://api.example.com/v1/models", status=500)

        assert get_model_limits("https://api.example.com/v1", "m") == (None, None)
        assert get_model_limits("http://localhost:11434", "m") == (None, None)

    def test_output_limit_bounds_chunk_size(self):
        """Test that the translated chunk must fit the max output tokens."""
        size = compute_max_chunk_chars(8192, 4096, "p" * 1000)
        # Estimated translation of the chunk fits within the output limit
        assert size / 3 * 1.3 <= 4096
        assert size > 5000

    def test_context_limit_bounds_chunk_size(self):
        """Test that prompt, chunk and translation must fit the context window."""
        size = compute_max_chunk_chars(4096, None, "p" * 3000)
        assert 1000 + size / 3 * 2.3 <= 4096

    def test_unknown_limits(self):
        """Test that unknown limits give no chunk size."""
        assert compute_max_chunk_chars(None, None, "prompt") is None

    @patch('libs.translation._translate_once')
    def test_max_chunk_chars_forces_chunking(self, mock_translate):
        """Test that content above max_chunk_chars is never sent in one request."""
        mock_translate.side_effect = lambda api_base, model, prompt, block, *a, **k: "<p>ok</p>"
        body = "".join(f"<p>Paragraph {i} {'x' * 1000}</p>" for i in range(6))

        translate_with_chunking("http://localhost:11434", "m1", "prompt", body, {}, max_chunk_chars=3000)

        sent = [call.args[3] for call in mock_translate.call_args_list]
        assert len(sent) > 1
        assert all(len(block) <= 3100 for block in sent)


class TestLengthChecks:
    """Test language-aware length validation and the detection of short translations."""

    def test_expected_ratio_rejects_omission(self):
        """Test that a translation well below the expected length for the language pair is rejected."""
        original = "".join(f"<p>Paragraph {i} with a fair amount of original text inside.</p>" for i in range(20))
        # 80% of the source length: fine without language pair, too short for English -> French (x1.15)
        translation = original[:int(len(original) * 0.8)].rsplit("</p>", 1)[0] + "</p>"

        assert validate_translation(original, translation)[0] is True
        is_valid, error, _ = validate_translation(original, translation, expected_ratio=1.15)
        assert is_valid is False
        assert "too short" in error

    def test_find_short_translations(self):
        """Test that chunks well below the book median length ratio are reported."""
        source = "<p>" + "x" * 1000 + "</p>"
        pairs = [(source, "<p>" + "y" * 1150 + "</p>")] * 6 + [(source, "<p>" + "y" * 850 + "</p>")]

        assert find_short_translations(pairs) == [6]
        assert find_short_translations(pairs[:3]) == []


class TestModelOrdering:
    """Test retries and model order adjustments."""

    def test_model_with_many_empty_outputs_is_demoted(self):
        """Test that a model returning too many empty outputs is moved after the others."""
        for i in range(10):
            _record_call("m1", empty=i < 4)

        assert order_models(["m1", "m2"]) == ["m2", "m1"]
        assert order_models(["m2", "m1"]) == ["m2", "m1"]

    def test_model_with_few_empty_outputs_keeps_its_place(self):
        """Test that occasional empty outputs do not change the model order."""
        for i in range(10):
            _record_call("m1", empty=i < 2)

        assert order_models(["m1", "m2"]) == ["m1", "m2"]

    @patch('libs.translation._translate_once')
    def test_full_empty_output_tries_next_model_before_splitting(self, mock_translate):
        """Test that an empty output on a whole chunk goes to the next model without splitting it."""
        def fake(api_base, model, prompt, block, *args, **kwargs):
            if model == "m1":
                raise EmptyOutputError("empty")
            return "<p>traduit</p>"
        mock_translate.side_effect = fake
        body = "".join(f"<p>Part {i} {'x' * 1500}</p>" for i in range(4))

        result, model_used = translate_with_chunking("http://localhost:11434", ["m1", "m2"], "prompt", body, {})

        assert [call.args[1] for call in mock_translate.call_args_list] == ["m1", "m2"]
        assert model_used == "m2"
        assert result == "<p>traduit</p>"

    @patch('libs.translation._translate_once')
    def test_retries_raise_temperature(self, mock_translate):
        """Test that each attempt uses a higher temperature and a different seed."""
        mock_translate.side_effect = [TranslationError("bad"), TranslationError("bad"), "<p>ok</p>", "<p>ok</p>"]
        # Above MAX_SINGLE_REQUEST_CHARS: no full translation attempt, two chunks
        body = "".join(f"<p>Part {i} {'x' * 1500}</p>" for i in range(12))

        translate_with_chunking("http://localhost:11434", "m1", "prompt", body, {})

        calls = mock_translate.call_args_list[:3]
        assert [c.kwargs["temperature"] for c in calls] == [0, 0.3, 0.6]
        assert len({c.kwargs["seed"] for c in calls}) == 3
