import re

def convert_translator_notes_to_footnotes(html: str, start: int = 1) -> tuple[str, list[str]]:
    notes = []
    counter = start

    def repl(match: re.Match) -> str:
        nonlocal counter
        content = match.group(1).strip()
        ref = f"note{counter}"
        sup = f'<sup><a href="#ref{ref}" id="ref{ref}">{counter}</a></sup>'
        note_html = f'<p id="{ref}"><sup><a href="#ref{ref}">{counter}</a></sup> {content}</p>'
        notes.append(note_html)
        counter += 1
        return sup

    processed = re.sub(r"\[Translator's note:\s*(.*?)\]", repl, html)
    return processed, notes

