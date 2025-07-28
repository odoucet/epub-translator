"""
Test utilities for epub-translator project.
This module provides helper functions and utilities for testing.
"""

import tempfile
import json
from pathlib import Path
from unittest.mock import Mock
from ebooklib import epub
import ebooklib


def create_mock_epub_book(title="Test Book", chapters=None):
    """Create a mock EPUB book for testing.
    
    Args:
        title: Title of the book
        chapters: List of (title, content) tuples for chapters
    
    Returns:
        Mock EPUB book object
    """
    if chapters is None:
        chapters = [
            ("Chapter 1", "<p>This is the first chapter with sufficient content for testing purposes. " * 20 + "</p>"),
            ("Chapter 2", "<p>This is the second chapter with enough words to pass validation. " * 25 + "</p>")
        ]
    
    book = epub.EpubBook()
    book.set_identifier('test-id-123')
    book.set_title(title)
    book.set_language('en')
    book.add_author('Test Author')
    
    epub_chapters = []
    for i, (chapter_title, content) in enumerate(chapters, 1):
        chapter = epub.EpubHtml(
            title=chapter_title,
            file_name=f'chapter{i}.xhtml',
            lang='en'
        )
        chapter.content = f'''<?xml version="1.0" encoding="utf-8"?>
        <!DOCTYPE html>
        <html xmlns="http://www.w3.org/1999/xhtml">
        <body>
        <h1>{chapter_title}</h1>
        {content}
        </body>
        </html>'''
        
        book.add_item(chapter)
        epub_chapters.append(chapter)
    
    # Add navigation
    book.toc = [epub.Link(f"chapter{i}.xhtml", title, f"ch{i}") 
                for i, (title, _) in enumerate(chapters, 1)]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Add spine
    book.spine = ['nav'] + epub_chapters
    
    return book


def create_test_epub_file(temp_dir, title="Test Book", chapters=None):
    """Create a test EPUB file on disk.
    
    Args:
        temp_dir: Temporary directory to create file in
        title: Title of the book
        chapters: List of (title, content) tuples
    
    Returns:
        Path to created EPUB file
    """
    book = create_mock_epub_book(title, chapters)
    epub_path = temp_dir / f"{title.replace(' ', '_').lower()}.epub"
    epub.write_epub(str(epub_path), book)
    return epub_path


def create_mock_api_response(content="<p>Translated content</p>", success=True):
    """Create a mock API response for translation testing.
    
    Args:
        content: Translation content to return
        success: Whether the response should indicate success
    
    Returns:
        Mock response object
    """
    if success:
        return {
            "message": {
                "content": content
            }
        }
    else:
        return {
            "error": "Translation failed"
        }


def create_test_progress_file(temp_dir, translations=None, chunk_parts=2):
    """Create a test progress file with sample data.
    
    Args:
        temp_dir: Directory to create file in
        translations: Dict of translation mappings
        chunk_parts: Number of chunk parts
    
    Returns:
        Path to created progress file
    """
    if translations is None:
        translations = {
            "hash1": "<p>Translation 1</p>",
            "hash2": "<p>Translation 2</p>"
        }
    
    progress_data = {
        "translated": translations,
        "chunk_parts": chunk_parts
    }
    
    progress_file = temp_dir / "test_progress.json"
    progress_file.write_text(json.dumps(progress_data, indent=2), encoding='utf-8')
    return progress_file


def assert_html_structure(html_content, expected_tags=None):
    """Assert that HTML content has expected structure.
    
    Args:
        html_content: HTML string to validate
        expected_tags: List of tags that should be present
    """
    if expected_tags is None:
        expected_tags = ['html', 'body']
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    for tag in expected_tags:
        assert soup.find(tag) is not None, f"Expected tag '{tag}' not found in HTML"


def assert_footnote_structure(footnote_html, note_id, content_snippet):
    """Assert that footnote HTML has correct structure.
    
    Args:
        footnote_html: Footnote HTML string
        note_id: Expected note ID
        content_snippet: Expected content snippet
    """
    assert f'id="{note_id}"' in footnote_html
    assert content_snippet in footnote_html
    assert footnote_html.startswith('<p')
    assert footnote_html.endswith('</p>')


def count_html_tags(html_content, tag_name):
    """Count occurrences of specific HTML tag.
    
    Args:
        html_content: HTML string
        tag_name: Tag name to count
    
    Returns:
        Number of tag occurrences
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    return len(soup.find_all(tag_name))


def extract_text_content(html_content):
    """Extract plain text from HTML content.
    
    Args:
        html_content: HTML string
    
    Returns:
        Plain text content
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(strip=True)


def simulate_translation_delay(delay_seconds=0.1):
    """Simulate translation API delay for performance testing.
    
    Args:
        delay_seconds: Delay in seconds
    """
    import time
    time.sleep(delay_seconds)


class MockTranslationAPI:
    """Mock translation API for testing."""
    
    def __init__(self, responses=None, fail_after=None):
        """Initialize mock API.
        
        Args:
            responses: List of responses to return in order
            fail_after: Number of successful calls before failing
        """
        self.responses = responses or ["<p>Mock translation</p>"]
        self.call_count = 0
        self.fail_after = fail_after
    
    def translate(self, content):
        """Mock translation method."""
        self.call_count += 1
        
        if self.fail_after and self.call_count > self.fail_after:
            raise Exception("Mock API failure")
        
        response_index = min(self.call_count - 1, len(self.responses) - 1)
        return self.responses[response_index]


def create_large_content(word_count=1000, sentence_length=15):
    """Create large text content for testing.
    
    Args:
        word_count: Total number of words
        sentence_length: Words per sentence
    
    Returns:
        Large text string
    """
    words = ["word", "text", "content", "sentence", "paragraph", "chapter", 
             "book", "story", "narrative", "literature", "translation", "language"]
    
    content = []
    for i in range(0, word_count, sentence_length):
        sentence_words = []
        for j in range(sentence_length):
            word_index = (i + j) % len(words)
            sentence_words.append(f"{words[word_index]}{i+j}")
        
        sentence = " ".join(sentence_words) + "."
        content.append(sentence)
    
    return " ".join(content)


def validate_markdown_structure(markdown_content):
    """Validate that markdown content has expected structure.
    
    Args:
        markdown_content: Markdown string to validate
    
    Returns:
        True if structure is valid
    """
    required_sections = [
        "# Model Comparison",
        "## Original",
        "## Timing Summary",
        "| Model | Time"
    ]
    
    for section in required_sections:
        if section not in markdown_content:
            return False
    
    return True


def create_test_config(temp_dir, **config_options):
    """Create a test configuration file.
    
    Args:
        temp_dir: Directory to create config in
        **config_options: Configuration options
    
    Returns:
        Path to config file
    """
    default_config = {
        "api_base": "http://localhost:11434",
        "default_model": "test-model",
        "prompt_style": "literary",
        "max_retries": 3,
        "chunk_size": 10000
    }
    
    config = {**default_config, **config_options}
    config_file = temp_dir / "test_config.json"
    config_file.write_text(json.dumps(config, indent=2), encoding='utf-8')
    return config_file
