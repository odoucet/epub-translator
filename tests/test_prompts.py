import pytest
from libs.prompts import PREDEFINED_PROMPTS


class TestPredefinedPrompts:
    """Test predefined prompt templates."""
    
    def test_all_prompt_styles_exist(self):
        """Test that all expected prompt styles are defined."""
        expected_styles = ["literary", "elegant", "narrative"]
        
        for style in expected_styles:
            assert style in PREDEFINED_PROMPTS, f"Missing prompt style: {style}"
    
    def test_prompts_contain_target_language_placeholder(self):
        """Test that all prompts contain the {target_language} placeholder."""
        for style, prompt in PREDEFINED_PROMPTS.items():
            assert "{target_language}" in prompt, f"Prompt '{style}' missing {{target_language}} placeholder"
    
    def test_prompt_formatting_with_language(self):
        """Test that prompts can be formatted with target language."""
        test_language = "French"
        
        for style, prompt in PREDEFINED_PROMPTS.items():
            formatted = prompt.format(target_language=test_language)
            
            # Should not contain the placeholder anymore
            assert "{target_language}" not in formatted
            # Should contain the target language
            assert test_language in formatted
    
    def test_literary_prompt_content(self):
        """Test specific content of literary prompt."""
        prompt = PREDEFINED_PROMPTS["literary"]
        
        # Check for key instructions
        assert "literary translator" in prompt.lower()
        assert "proper names" in prompt.lower()
        assert "html tags" in prompt.lower()
        assert "translator's note" in prompt.lower()
    
    def test_elegant_prompt_content(self):
        """Test specific content of elegant prompt."""
        prompt = PREDEFINED_PROMPTS["elegant"]
        
        # Check for key instructions
        assert "preserving its style" in prompt.lower()
        assert "character names" in prompt.lower()
        assert "html tags" in prompt.lower()
        assert "translator's note" in prompt.lower()
    
    def test_narrative_prompt_content(self):
        """Test specific content of narrative prompt."""
        prompt = PREDEFINED_PROMPTS["narrative"]
        
        # Check for key instructions
        assert "reimagine" in prompt.lower()
        assert "fluent" in prompt.lower()
        assert "html tags" in prompt.lower()
        assert "translator's note" in prompt.lower()
    
    def test_prompts_html_preservation_instructions(self):
        """Test that all prompts contain HTML preservation instructions."""
        for style, prompt in PREDEFINED_PROMPTS.items():
            # All prompts should emphasize HTML tag preservation
            assert "html tags" in prompt.lower(), f"Prompt '{style}' missing HTML tags instruction"
            assert "intact" in prompt.lower(), f"Prompt '{style}' missing intact instruction"
    
    def test_prompts_name_preservation_instructions(self):
        """Test that all prompts contain name preservation instructions."""
        for style, prompt in PREDEFINED_PROMPTS.items():
            # All prompts should mention not translating names
            prompt_lower = prompt.lower()
            assert ("proper names" in prompt_lower or 
                   "character names" in prompt_lower or 
                   "names" in prompt_lower), f"Prompt '{style}' missing name preservation instruction"
    
    def test_prompts_translator_notes_instructions(self):
        """Test that all prompts contain translator notes instructions."""
        for style, prompt in PREDEFINED_PROMPTS.items():
            assert "translator's note" in prompt.lower(), f"Prompt '{style}' missing translator notes instruction"
    
    def test_prompts_no_confirmation_instructions(self):
        """Test that all prompts instruct not to confirm understanding."""
        for style, prompt in PREDEFINED_PROMPTS.items():
            prompt_lower = prompt.lower()
            assert ("do not confirm" in prompt_lower or 
                   "don't confirm" in prompt_lower), f"Prompt '{style}' missing no-confirmation instruction"
    
    def test_prompt_formatting_with_various_languages(self):
        """Test prompt formatting with various target languages."""
        test_languages = ["French", "Spanish", "German", "Japanese", "中文"]
        
        for language in test_languages:
            for style, prompt in PREDEFINED_PROMPTS.items():
                formatted = prompt.format(target_language=language)
                
                assert language in formatted
                assert "{target_language}" not in formatted
    
    def test_prompt_structure_consistency(self):
        """Test that all prompts follow a consistent structure."""
        for style, prompt in PREDEFINED_PROMPTS.items():
            # All prompts should be multi-line strings
            assert isinstance(prompt, str)
            assert len(prompt.strip()) > 100  # Substantial content
            
            # Should contain formatting instructions
            assert "translate" in prompt.lower()
    
    def test_prompt_special_characters_handling(self):
        """Test prompt formatting with special characters in language names."""
        special_languages = ["中文 (Chinese)", "Français", "Español"]
        
        for language in special_languages:
            for style, prompt in PREDEFINED_PROMPTS.items():
                try:
                    formatted = prompt.format(target_language=language)
                    assert language in formatted
                except Exception as e:
                    pytest.fail(f"Prompt '{style}' failed with language '{language}': {e}")
    
    def test_prompts_are_strings(self):
        """Test that all prompts are string objects."""
        for style, prompt in PREDEFINED_PROMPTS.items():
            assert isinstance(prompt, str), f"Prompt '{style}' is not a string"
            assert len(prompt.strip()) > 0, f"Prompt '{style}' is empty"
    
    def test_prompt_dictionary_immutability(self):
        """Test that modifying returned prompts doesn't affect the original."""
        original_literary = PREDEFINED_PROMPTS["literary"]
        
        # Format the prompt
        formatted = original_literary.format(target_language="TestLang")
        
        # Original should be unchanged
        assert "{target_language}" in PREDEFINED_PROMPTS["literary"]
        assert "TestLang" not in PREDEFINED_PROMPTS["literary"]
    
    def test_prompt_case_sensitivity(self):
        """Test that prompt keys are case-sensitive."""
        # These should not exist (wrong case)
        assert "Literary" not in PREDEFINED_PROMPTS
        assert "ELEGANT" not in PREDEFINED_PROMPTS
        assert "Narrative" not in PREDEFINED_PROMPTS
        
        # These should exist (correct case)
        assert "literary" in PREDEFINED_PROMPTS
        assert "elegant" in PREDEFINED_PROMPTS
        assert "narrative" in PREDEFINED_PROMPTS
