import gradio as gr
import tempfile
import json
from pathlib import Path
from ebooklib import epub
from bs4 import BeautifulSoup

from libs.epub_utils import get_html_chunks, normalize_language
from libs.translation import translate_with_chunking
from libs.notes import convert_translator_notes_to_footnotes

# Cache preview translations en mémoire
preview_cache = {}

def list_chapters(epub_file):
    """
    Retourne une liste de tuples (numéro_chapitre, nombre_de_mots) pour chaque chapitre valable.
    """
    book = epub.read_epub(epub_file.name)
    chapters = []
    for idx, item in enumerate(book.get_items_of_type(epub.ITEM_DOCUMENT)):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        text = soup.get_text(strip=True)
        word_count = len(text.split())
        chapters.append((idx+1, word_count))
    return chapters

def preview_translation(epub_file, lang, prompt_style, model, url, chapter_number):
    """
    Renvoie deux strings HTML : le source et la traduction pour le chapitre choisi.
    """
    book = epub.read_epub(epub_file.name)
    chunks = get_html_chunks(book, chapter_only=chapter_number)
    if not chunks:
        return "<p>Aucun chapitre trouvé.</p>", "<p>—</p>"

    item, raw_html = chunks[0]
    source_html = raw_html.decode('utf-8')

    key = f"{epub_file.name}-{chapter_number}-{lang}"
    if key in preview_cache:
        translated_html = preview_cache[key]
    else:
        translated = translate_with_chunking(
            url, model, prompt_style, source_html, {}
        )
        translated, notes = convert_translator_notes_to_footnotes(translated)
        translated_html = translated + "".join(notes)
        preview_cache[key] = translated_html

    return source_html, translated_html

def main():
    with gr.Blocks() as demo:
        gr.Markdown("## Aperçu & Traduction EPUB")

        with gr.Row():
            epub_input = gr.File(label="Charger un EPUB", file_types=['.epub'])
            lang = gr.Dropdown(
                list(["french","english","german","spanish","italian","portuguese","japanese","chinese"]),
                label="Langue cible"
            )
            prompt_style = gr.Dropdown(
                list(json.loads(Path('epub_translator/prompts.json').read_text())),
                label="Style de prompt",
                value="literary"
            )
            model = gr.Textbox(value="mistral", label="Modèle LLM")
            url = gr.Textbox(value="http://localhost:11434/v1", label="URL API")

        chapter_info = gr.Dataframe(
            headers=["Chapitre","#Mots"], row_count=1, interactive=False
        )
        select_chapter = gr.Slider(minimum=1, maximum=1, step=1, label="Chapitre")
        preview_btn = gr.Button("Voir l’aperçu")

        with gr.Tabs():
            with gr.TabItem("Source HTML"):
                source_view = gr.HTML()
            with gr.TabItem("Traduction HTML"):
                trans_view = gr.HTML()

        # Met à jour la liste des chapitres et le slider
        def update_chapters(epub_file):
            chapters = list_chapters(epub_file)
            chapter_info.data = chapters
            select_chapter.maximum = len(chapters)
            return chapters

        epub_input.change(
            fn=update_chapters,
            inputs=epub_input,
            outputs=[chapter_info, select_chapter]
        )

        preview_btn.click(
            fn=preview_translation,
            inputs=[epub_input, lang, prompt_style, model, url, select_chapter],
            outputs=[source_view, trans_view]
        )

    demo.launch()

if __name__ == '__main__':
    main()
