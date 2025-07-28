import pytest
import tempfile
import json
from pathlib import Path
from ebooklib import epub
import ebooklib


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_progress_data():
    """Sample progress data for testing."""
    return {
        "translated": {
            "abc123": "<p>This is a translated text</p>",
            "def456": "<p>Another translated text</p>"
        },
        "chunk_parts": 4
    }


@pytest.fixture
def sample_epub():
    """Create a minimal EPUB for testing."""
    book = epub.EpubBook()
    book.set_identifier('test123')
    book.set_title('Test Book')
    book.set_language('en')
    book.add_author('Test Author')
    
    # Create a chapter with sufficient content
    chapter1 = epub.EpubHtml(
        title='Chapter 1',
        file_name='chapter1.xhtml',
        lang='en'
    )
    chapter1.content = '''<?xml version="1.0" encoding="utf-8"?>
    <!DOCTYPE html>
    <html xmlns="http://www.w3.org/1999/xhtml">
    <body>
    <h1>Chapter 1</h1>
    <p>This is the first chapter of our test book. It contains enough text to meet the minimum word requirement for processing. The content includes multiple sentences and paragraphs to simulate a real book chapter. This paragraph continues with more text to ensure we have sufficient content for testing purposes. The story begins with our protagonist walking through a mysterious forest, encountering strange creatures and magical elements along the way. As the journey progresses, more characters are introduced and the plot becomes increasingly complex. The chapter concludes with a dramatic cliffhanger that leaves readers eager for more.</p>
    <p>This is another paragraph with substantial content to ensure the chapter meets the minimum word count requirements. The narrative continues to develop with rich descriptions and engaging dialogue between characters. Multiple plot threads are woven together to create a compelling story that captures the reader's attention and maintains their interest throughout the chapter.</p>
    </body>
    </html>'''
    
    # Create a short chapter that won't meet word requirements
    chapter2 = epub.EpubHtml(
        title='Short Chapter',
        file_name='chapter2.xhtml',
        lang='en'
    )
    chapter2.content = '''<?xml version="1.0" encoding="utf-8"?>
    <!DOCTYPE html>
    <html xmlns="http://www.w3.org/1999/xhtml">
    <body>
    <h1>Short Chapter</h1>
    <p>Too short.</p>
    </body>
    </html>'''
    
    book.add_item(chapter1)
    book.add_item(chapter2)
    
    # Add navigation
    book.toc = (
        epub.Link("chapter1.xhtml", "Chapter 1", "ch1"),
        epub.Link("chapter2.xhtml", "Short Chapter", "ch2")
    )
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Add spine
    book.spine = ['nav', chapter1, chapter2]
    
    return book


@pytest.fixture
def mock_translation_response():
    """Mock translation API response."""
    return {
        "message": {
            "content": "<p>Ceci est un texte traduit en français.</p>"
        }
    }
