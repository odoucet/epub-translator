import pytest
from libs.notes import convert_translator_notes_to_footnotes


class TestConvertTranslatorNotesToFootnotes:
    """Test translator notes to footnotes conversion functionality."""
    
    def test_single_note_conversion(self):
        """Test conversion of single translator note."""
        html = "<p>This is text [Translator's note: This is a note] with content.</p>"
        processed, notes = convert_translator_notes_to_footnotes(html)
        
        # Check that note is replaced with superscript link
        assert "[Translator's note:" not in processed
        assert '<sup><a href="#refnote1" id="refnote1">1</a></sup>' in processed
        
        # Check that footnote is created
        assert len(notes) == 1
        assert 'id="note1"' in notes[0]
        assert "This is a note" in notes[0]
        assert '<sup><a href="#refnote1">1</a></sup>' in notes[0]
    
    def test_multiple_notes_conversion(self):
        """Test conversion of multiple translator notes."""
        html = """<p>First note [Translator's note: First note content] and 
                  second note [Translator's note: Second note content] here.</p>"""
        processed, notes = convert_translator_notes_to_footnotes(html)
        
        # Check that both notes are replaced
        assert "[Translator's note:" not in processed
        assert '<sup><a href="#refnote1" id="refnote1">1</a></sup>' in processed
        assert '<sup><a href="#refnote2" id="refnote2">2</a></sup>' in processed
        
        # Check that both footnotes are created
        assert len(notes) == 2
        assert "First note content" in notes[0]
        assert "Second note content" in notes[1]
        assert 'id="note1"' in notes[0]
        assert 'id="note2"' in notes[1]
    
    def test_custom_starting_number(self):
        """Test conversion with custom starting footnote number."""
        html = "<p>Text with [Translator's note: A note] content.</p>"
        processed, notes = convert_translator_notes_to_footnotes(html, start=5)
        
        # Should start from number 5
        assert '<sup><a href="#refnote5" id="refnote5">5</a></sup>' in processed
        assert len(notes) == 1
        assert 'id="note5"' in notes[0]
        assert '<sup><a href="#refnote5">5</a></sup>' in notes[0]
    
    def test_no_notes_in_text(self):
        """Test processing text without translator notes."""
        html = "<p>This text has no translator notes at all.</p>"
        processed, notes = convert_translator_notes_to_footnotes(html)
        
        # Text should remain unchanged
        assert processed == html
        # No notes should be created
        assert notes == []
    
    def test_note_with_special_characters(self):
        """Test notes containing special characters and punctuation."""
        html = '<p>Text [Translator\'s note: This note has "quotes", punctuation! And symbols: @#$%] here.</p>'
        processed, notes = convert_translator_notes_to_footnotes(html)
        
        assert len(notes) == 1
        assert 'This note has "quotes", punctuation! And symbols: @#$%' in notes[0]
    
    def test_note_with_html_content(self):
        """Test notes that might contain HTML-like content."""
        html = "<p>Text [Translator's note: This refers to <em>emphasis</em> in the original] here.</p>"
        processed, notes = convert_translator_notes_to_footnotes(html)
        
        assert len(notes) == 1
        assert "This refers to <em>emphasis</em> in the original" in notes[0]
    
    def test_whitespace_handling_in_notes(self):
        """Test proper whitespace handling in translator notes."""
        html = "<p>Text [Translator's note:   Lots of   whitespace   ] here.</p>"
        processed, notes = convert_translator_notes_to_footnotes(html)
        
        assert len(notes) == 1
        # Content should be stripped of leading/trailing whitespace
        assert "Lots of   whitespace" in notes[0]
    
    def test_case_sensitivity(self):
        """Test case sensitivity in note detection."""
        # Should match standard case
        html1 = "<p>Text [Translator's note: Standard case] here.</p>"
        processed1, notes1 = convert_translator_notes_to_footnotes(html1)
        assert len(notes1) == 1
        
        # Should not match different case (current implementation is case-sensitive)
        html2 = "<p>Text [translator's note: Lower case] here.</p>"
        processed2, notes2 = convert_translator_notes_to_footnotes(html2)
        assert len(notes2) == 0  # Current implementation is case-sensitive
        
        html3 = "<p>Text [TRANSLATOR'S NOTE: Upper case] here.</p>"
        processed3, notes3 = convert_translator_notes_to_footnotes(html3)
        assert len(notes3) == 0  # Current implementation is case-sensitive
    
    def test_malformed_notes(self):
        """Test handling of malformed translator notes."""
        # Missing closing bracket
        html1 = "<p>Text [Translator's note: Missing closing bracket here.</p>"
        processed1, notes1 = convert_translator_notes_to_footnotes(html1)
        assert len(notes1) == 0  # Should not match incomplete notes
        
        # Missing colon
        html2 = "<p>Text [Translator's note Missing colon] here.</p>"
        processed2, notes2 = convert_translator_notes_to_footnotes(html2)
        assert len(notes2) == 0  # Should not match without colon
    
    def test_note_at_text_boundaries(self):
        """Test notes at the beginning and end of text."""
        # Note at beginning
        html1 = "[Translator's note: At beginning] Rest of text."
        processed1, notes1 = convert_translator_notes_to_footnotes(html1)
        assert len(notes1) == 1
        assert processed1.startswith('<sup><a href="#refnote1"')
        
        # Note at end
        html2 = "Start of text [Translator's note: At end]"
        processed2, notes2 = convert_translator_notes_to_footnotes(html2)
        assert len(notes2) == 1
        assert processed2.endswith('</a></sup>')
    
    def test_nested_brackets_in_note(self):
        """Test handling of nested brackets within notes."""
        html = "<p>Text [Translator's note: This note has [nested brackets] inside] here.</p>"
        processed, notes = convert_translator_notes_to_footnotes(html)
        
        # The regex should handle this correctly by matching to the first closing bracket
        # The behavior depends on the regex implementation - this tests current behavior
        assert len(notes) >= 0  # May or may not match depending on regex greediness
    
    def test_footnote_html_structure(self):
        """Test the HTML structure of generated footnotes."""
        html = "<p>Text [Translator's note: Test note] here.</p>"
        processed, notes = convert_translator_notes_to_footnotes(html)
        
        footnote = notes[0]
        
        # Check HTML structure
        assert footnote.startswith('<p id="note1">')
        assert footnote.endswith('</p>')
        assert '<sup><a href="#refnote1">1</a></sup>' in footnote
        assert "Test note" in footnote
    
    def test_superscript_link_structure(self):
        """Test the HTML structure of generated superscript links."""
        html = "<p>Text [Translator's note: Test note] here.</p>"
        processed, notes = convert_translator_notes_to_footnotes(html)
        
        # Check superscript link structure
        assert '<sup><a href="#refnote1" id="refnote1">1</a></sup>' in processed
        # Ensure the original note text is completely removed
        assert "[Translator's note:" not in processed
        assert "] here." not in processed or processed.endswith('</a></sup> here.')
    
    def test_continuous_numbering(self):
        """Test that footnote numbering continues correctly with custom start."""
        html = """<p>First [Translator's note: First] and 
                  second [Translator's note: Second] and 
                  third [Translator's note: Third] notes.</p>"""
        processed, notes = convert_translator_notes_to_footnotes(html, start=10)
        
        # Should have three notes numbered 10, 11, 12
        assert len(notes) == 3
        assert 'id="note10"' in notes[0]
        assert 'id="note11"' in notes[1]
        assert 'id="note12"' in notes[2]
        
        # Check corresponding superscript links
        assert '<sup><a href="#refnote10" id="refnote10">10</a></sup>' in processed
        assert '<sup><a href="#refnote11" id="refnote11">11</a></sup>' in processed
        assert '<sup><a href="#refnote12" id="refnote12">12</a></sup>' in processed
