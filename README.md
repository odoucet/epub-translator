# EPUB Translator (Autonomous Version)

This project allows you to translate EPUB and PDF books using a local LLM like Mistral or Gemma (via Ollama) or any OpenAI-compatible API.  
It preserves HTML structure (headers, emphasis, lists), supports translator footnotes, and can output both EPUB and PDF.

---

## ✨ Features

- Translate **EPUB and PDF** files using chunked **HTML** input for structure preservation
- Supports multi-style prompts (literary, elegant, narrative)
- Outputs EPUB **and optional PDF** (`--pdf`)
- Supports local LLMs via **Ollama** and remote **OpenAI-compatible APIs** (OpenRouter, vLLM, llama.cpp...)
- **Model fallback**: give several models, the next one is used only for the chunks the previous one fails on
- **Chunk size adapted to the model**: derived from its context window and max output tokens
- **Robust against flaky APIs**: retries, halving of failing chunks, detection of truncated or summarised output
- **Resumable**: every translated chunk is saved in a JSON workspace, re-run the same command to resume
- Translate the **entire book or just one chapter** with `--chapter`
- Compare model outputs on a chapter (`--compare`)

---

## ⚠️ Legal Notice

> ❗ Use only with books in the **public domain** (author dead >70 years or explicitly free license).
> Do not use on copyrighted material.

---

## 🔒 DRM Protection Check

The translator automatically detects and **blocks translation of DRM-protected EPUB files** to ensure compliance with digital rights.

**Supported DRM detection:**
- ✅ **Readium LCP** (license.lcpl)
- ✅ **Adobe ADEPT** (rights.xml with Adobe algorithms)
- ✅ **Barnes & Noble** (characteristic encrypted keys)
- ✅ **Apple FairPlay** (sinf.xml signatures)
- ✅ **Unknown encrypted content** (generic encryption detection)

**What happens if DRM is detected:**
```
🔒 Vérification DRM du fichier EPUB...
❌ DRM détecté: Adobe ADEPT
❌ Impossible de traduire un fichier EPUB protégé par DRM
💡 Veuillez utiliser un fichier EPUB sans DRM
```

**How to get DRM-free EPUBs:**
- **Public domain sources:**
  - 🇺🇸 **English**: [Project Gutenberg](https://www.gutenberg.org) (60,000+ free books)
  - 🇫🇷 **French**: [Ebooks Gratuits](https://www.ebooksgratuits.com) • [BnR](https://ebooks-bnr.com)
  - 🇩🇪 **German**: [Projekt Gutenberg-DE](https://www.projekt-gutenberg.org)
  - 🇪🇸 **Spanish**: [Biblioteca Digital Ciudad Seva](http://www.ciudadseva.com)
  - 🌍 **Multi-language**: [Internet Archive](https://archive.org/details/texts) • [Wikisource](https://wikisource.org)
- **Commercial DRM-free sources:**
  - [Smashwords](https://www.smashwords.com) (independent authors)
  - [Tor/Forge](https://www.tor.com) (selected sci-fi/fantasy titles)
  - [Humble Bundle](https://www.humblebundle.com/books) (periodic book bundles)
- **Your own content:**
  - Personal authored documents
  - Academic papers and theses
  - Personal document conversions to EPUB format

---

## 🐳 Docker Setup

1. Install [Ollama](https://ollama.com/) and run:
   ```bash
   ollama pull mistral-small:24b
   ollama pull dorian2b/vera
   ```
   These are the default models. To pull every model of the comparison below, run `./download_models.sh`.

2. Build and launch translator with Docker Compose:
   ```bash
   docker-compose up -d
   ```

---

## 🚀 Translate a Book

Local model with Ollama:

```bash
python cli.py --file book.epub -l french --prompt-style literary --pdf
python cli.py --file book.pdf -l french -m mistral-small:24b,dorian2b/vera
```

Remote model with OpenRouter (see [model recommendations](#-model-recommendations)):

```bash
export LLM_API_KEY=sk-or-...
python cli.py -f book.pdf -l fr -o book.fr.epub -u https://openrouter.ai/api/v1 \
  -m tencent/hy-mt2-30b-a3b,tencent/hy-mt2-7b,mistralai/mistral-small-3.2-24b-instruct
```

Options:
- `-l french` / `-l fr` → target language (name or ISO code)
- `-s english` / `-s en` → source language, detected from the text when not given (used to check translation lengths)
- `-m model1,model2,...` → models to use, in order of preference (see [fallback](#-how-a-book-is-translated))
- `-u http://localhost:11434` → API endpoint (Ollama by default); a URL ending in `/v1` (e.g. `https://openrouter.ai/api/v1`) uses the OpenAI-compatible `/chat/completions` API
- `-k <token>` → bearer token for a remote API; prefer the `LLM_API_KEY` environment variable so the key does not show up in your shell history
- `-p literary` → prompt style (see [Prompt Styles](#%EF%B8%8F-prompt-styles))
- `--chapter 3` → translate only chapter 3
- `-w .progress.json` → progress file used to resume an interrupted translation
- `--chunk-size 6000` → force the max size (chars) sent per request instead of deriving it from the model limits
- `-o book.fr.epub` → output file
- `--pdf` → also export the translated EPUB to PDF
- `--debug` → verbose logs; the last API request and response are written to `debug-lastcall.json` (the API key is not written)

PDF input: the text is extracted with PyMuPDF (`pymupdf`), which rebuilds real paragraphs and words hyphenated across lines or pages (`pypdf` is used if PyMuPDF is not installed, with lower quality). Layout, images and tables are not kept: the output is a single-chapter EPUB.

---

## ⚙️ How a Book Is Translated

1. **Chunk size**: for OpenAI-compatible APIs, the context window and max output tokens of every model are read from the `/models` endpoint. The chunk size is chosen so that the translation fits the output limit and prompt + source + translation fit the context window; with several models the smallest limit wins. Without this information (Ollama), chunks are at most 16,000 chars.
2. **Chunking**: content is split at HTML tag boundaries (never inside a word) into chunks below that size.
3. **Validation**: every answer is checked: HTML tags kept, output not truncated by the token limit (`finish_reason=length`), and not too short. Models sometimes silently drop the end of a chunk: with a known language pair (en, fr, de, es, it, pt, ja, zh), a translation below 80% of the expected length is rejected (e.g. English → French is expected around x1.15, so below x0.92 is rejected); otherwise below half the source length.
4. **Per-chunk recovery**, already translated chunks are never redone:
   - a failing chunk is retried 3 times with a rising temperature (0, 0.3, 0.6) and a new seed, since the same request at temperature 0 gives the same answer; then it is split in half, only that chunk is affected;
   - if the model keeps failing, **the next model of `-m` is used for that chunk only**, then the following chunks go back to the first model;
   - an empty answer switches to the next model right away, for the whole chunk before any splitting;
   - a model returning an empty answer for 30% or more of its calls (after 10 calls) is moved after the other models for the rest of the run;
   - a model returning empty answers when given a system prompt is automatically switched to instructions in the user message for the rest of the run.
5. **Final pass**: once every chunk is translated, chunks whose length ratio is below 85% of the book median are retranslated, starting with the next model of `-m` and a temperature of 0.3; the new version is kept only if it is longer. This catches omissions whatever the language pair.
6. **Resume**: each translated chunk is saved in the workspace (`-w`, default `.progress.json`). If every model fails on a chunk, the command stops with an error **without writing a partial EPUB**; re-run the same command to resume where it stopped. Changing the models or `--chunk-size` changes the chunks, and the translation then starts over.

---

## 🔁 Compare LLM Models

To compare model outputs on chapter 3:

```bash
python cli.py --file book.epub -l french -p literary --compare gemma3:1b,mistral:7b --chapter 3 -o model_comparison.md
```

---

## 🏆 Model Recommendations

Always give **at least two models** with `-m`: the fallback only costs something on the chunks the first model fails on.

### Remote (OpenRouter)

Recommended for English → French, tested on a full non-fiction book (~1M chars, 150 chunks):

```
-m tencent/hy-mt2-30b-a3b,tencent/hy-mt2-7b,mistralai/mistral-small-3.2-24b-instruct
```

| Model | Role | Notes |
|---|---|---|
| `tencent/hy-mt2-30b-a3b` | main | Dedicated translation model, good literary quality, very cheap ($0.074 / $0.295 per M tokens). Small limits (8,192 tokens context, 4,096 output), so chunks of ~8,500 chars. On some passages the provider returns an **empty answer** (output flagged as reasoning and dropped, still billed): retrying, changing the prompt or `/no_think` does not help, a fallback model is required. |
| `tencent/hy-mt2-7b` | 1st fallback | Same family and style, same price and limits (chunk size unchanged), fast (~8 s per chunk). Translates the passages the 30B drops. |
| `mistralai/mistral-small-3.2-24b-instruct` | 2nd fallback | Different model family in case both Hy-MT fail, large context, $0.09 / $0.25 per M tokens. |

On that book: about 1 hour, **$0.19 in total** (failed attempts and diagnostics included), no chunk lost. The 30B returned an empty answer about once every three chunks, all recovered by the 7B; the final pass found and fixed 6 chunks with omissions, one of them needing Mistral for its last part. `deepseek/deepseek-v3.2` also gives good translations but is slower (~40 s per chunk).

### Local (Ollama)

Our own tests show:
* **gemma3:1b**: hard to keep HTML structure and follow prompt exactly
* **other gemma3 models**: all timeout, to be investigated
* **mistral:7b**: hard to keep HTML structure and follow prompt exactly
* **mistral-small:24b**: good (but slow)
* **dorian2b/vera**: works very well on small chunks

Default when `-m` is not given: `mistral-small:24b,dorian2b/vera` (pull both with `ollama pull`).

---

## 🧪 Requirements

Install Python dependencies:

```bash
pip install -r requirements.txt
```

You also need `pandoc` + `pdflatex` installed if using `--pdf`.

---

## ✉️ Prompt Styles

Available prompt styles in `libs/prompts.py`:
- **`literary-v2`**: enhanced literary style with stricter translation guidelines and no summarizing
- **`literary`**: expressive and narrative with optional translator notes
- **`elegant`**: fluent and idiomatic with structure preservation  
- **`narrative`**: free but faithful rephrasing of content with tag retention

---

## 🧪 Testing

Run the test suite:

```bash
pytest
```

Test specific functionality:
```bash
pytest tests/test_epub_utils.py::TestDRMDetection -v
```

---

## TODO
- [ ] improve prompts to better handle HTML structure (lots of failures)
- [x] add openai-compatible API support
- [ ] add "literal" translation style
- [ ] PDF input: keep headings and chapters instead of a single chapter

## Comparaison des traductions par modèle et prompt

*Note: Le texte source est fictif et volontairement riche en idiomes français pour tester la capacité de traduction des nuances linguistiques.*

| Modèle | literary-v2 | literary | elegant | narrative |
| --- | --- | --- | --- | --- |
| gemma3:1b | ❌ Error: All models (gemma3:1b) failed... | ❌ Error: All models (gemma3:1b) failed... | ❌ Error: All models (gemma3:1b) failed... | ❌ Error: All models (gemma3:1b) failed... |
| gemma3:4b | <p>In the chiaroscuro of a Parisian bistro, time seemed to have gone on strike, like line 13 on a Monday morning. Adèle, leaning against the zinc counter, was idly swirling her spoon in a lukewarm coffee crème, her gaze lost amongst the smoke swirls and <em>memories that even nostalgia itself would have refused to endorse</em>.</p>  <p>A voice erupted from the depths of the room, slightly raspy, a little too cheerful for the hour: </p>  <p>&mdash; You’re still not dead, Adèle?</p>  <p>She raised barely a brow – that famous Parisian brow, trained at the school of silent sarcasm – and sketched a wry smile in the corner of her mouth, between tender disdain and amused indifference.</p>  <p>&mdash; Hello Maurice. Eh well, no, still not dead. But you, you’re still as dense as ever, I see.</p>  <p>Outside, the rain hammered the cobblestones like a Renaud old tune, and in Adèle’s heart, it was a whole refrain of Brassens dragging its worries, cigarette dangling from its mouth.</p> | <p>In the chiaroscuro of a Parisian bistro, time seemed to have gone on strike, much like line 13 on a Monday morning. Adèle, leaning against the zinc counter, idly spun her spoon in a lukewarm café crème, her gaze lost amongst the swirls of smoke and <em>memories that even nostalgia itself would have refused to endorse</em>.</p>  <p>A voice erupted from the depths of the room, slightly raspy, a touch too cheerful for the hour: </p>  <p>&mdash; You’re still not dead, Adèle?</p>  <p>She barely raised an eyebrow – that famous Parisian eyebrow, honed at the school of silent sarcasm – and offered a wry smile in the corner of her mouth, between disdainful tenderness and amused indifference.</p>  <p>&mdash; Hello Maurice. Eh, well, no, still not dead. Though you, you’re still as dense as ever, I see.</p>  <p>Outside, the rain hammered the cobblestones like a worn Renaud song, and within Adèle’s heart, it was a whole chorus of Brassens, dragging its sorrows, cigarette dangling from its lips.</p> | <p>In the chiaroscuro of a Parisian bistro, time seemed to have gone on strike, like line 13 on a Monday morning. Adèle, leaning against the zinc counter, idly spun her spoon in a lukewarm café crème, her gaze lost amongst the swirls of smoke and <em>memories that even nostalgia itself would have refused to endorse</em>.</p>  <p>A voice erupted from the depths of the room, slightly raspy, a touch too cheerful for the hour: </p>  <p>&mdash; You’re still not dead, Adèle?</p>  <p>She barely raised an eyebrow – that famous Parisian eyebrow, honed at the school of silent sarcasm – and offered a wry smile in the corner of her mouth, between disdainful tenderness and amused indifference.</p>  <p>&mdash; Hello Maurice. Eh, well, no, still not dead. Though you, you’re still as dense as ever, I see.</p>  <p>Outside, the rain hammered the cobblestones like a tired Renaud song, and within Adèle’s heart, it was a whole chorus of Brassens returning to drag its demons, cigarette dangling from its mouth.</p> | <p>Within the chiaroscuro of a Parisian bistro, time itself seemed to have gone on strike, much like line 13 on a Monday morning. Adèle, leaning against the zinc counter, idly swirled her spoon in a tepid café crème, her gaze lost amongst the swirling smoke and <em>memories that even nostalgia itself would have refused to endorse</em>.</p>  <p>A voice erupted from the depths of the room, slightly raspy, a touch too cheerful for the hour:</p>  <p>&mdash; You’re still not dead, Adèle?</p>  <p>She barely raised an eyebrow – that famed Parisian eyebrow, honed at the school of silent sarcasm – and offered a wry smile in the corner of her mouth, a blend of tender disdain and amused indifference.</p>  <p>&mdash; Hello Maurice. Well, no, not yet. Though you, my friend, remain stubbornly, delightfully, *you*.</p>  <p>Outside, the rain hammered against the cobblestones like a weary Renaud ballad, and within Adèle’s heart, a familiar refrain of Brassens echoed, dragging its sorrows, a cigarette dangling from its lips.</p> |
| gemma3:12b | <p>Dans le clair-obscur d'un bistrot parisien, le temps semblait s'être mis en grève comme la ligne&nbsp;13 un lundi matin. Adèle, accoudée au comptoir de zinc, tournait distraitement sa cuillère dans un café crème tiède, l'œil perdu entre les volutes de fumée et <em>les souvenirs que la nostalgie elle-même aurait refusés de cautionner</em>.</p>  <p>Une voix jaillit du fond de la salle, un peu éraillée, un peu trop joyeuse pour l'heure&nbsp;:</p>  <p>&mdash;&nbsp;T'es toujours pas morte, Adèle&nbsp;?</p>  <p>Elle leva à peine un sourcil &mdash; ce fameux sourcil parisien, formé à l'école du sarcasme silencieux &mdash; et esquissa un sourire en coin, entre le mépris tendre et l'indifférence amusée.</p>  <p>&mdash;&nbsp;Salut Maurice. Eh bah non, toujours pas morte. Par contre, toi, t'es toujours aussi con, je vois.</p>  <p>Dehors, la pluie tambourinait les pavés comme une vieille rengaine de Renaud, et dans le cœur d'Adèle, c'était tout un refrain de Brassens qui revenait traîner ses godasses, clope au bec.</p> | <p>In the chiaroscuro of a Parisian bistro, time seemed to have gone on strike, like the number 13 line on a Monday morning. Adèle, leaning against the zinc bar, idly stirred a lukewarm café crème, her gaze lost amongst the swirls of smoke and <em>memories that even nostalgia itself would have rejected</em>.</p>  <p>A voice erupted from the back of the room, a little raspy, a little too cheerful for the hour:</p>  <p>&mdash;&nbsp;Still not dead, Adèle?</p>  <p>She barely lifted an eyebrow – that famous Parisian eyebrow, schooled in the art of silent sarcasm – and sketched a wry smile, somewhere between tender disdain and amused indifference.</p>  <p>&mdash;&nbsp;Hello Maurice. Well no, still not dead. Though you, you’re still as dense as ever, I see.</p>  <p>Outside, the rain drummed against the cobblestones like an old Renaud refrain, and in Adèle’s heart, it was a whole Brassens chorus returning to drag its heels, cigarette dangling from its lips.</p>  [Translator's note: Renaud and Brassens were prominent French singer-songwriters known for their poetic lyrics and often melancholic themes. Their music is deeply ingrained in French popular culture.] | <p>In the chiaroscuro of a Parisian bistro, time seemed to have gone on strike, like the Line 13 on a Monday morning. Adèle, leaning against the zinc bar, idly stirred a lukewarm café crème, her gaze lost amongst the swirls of smoke and <em >memories even nostalgia itself would have disavowed</em>.</p>  <p>A voice erupted from the back of the room, a little raspy, a little too cheerful for the hour:</p>  <p>&mdash;&nbsp;Still not dead, Adèle?</p>  <p>She barely lifted an eyebrow – that famous Parisian eyebrow, schooled in the art of silent sarcasm – and sketched a wry smile, somewhere between tender disdain and amused indifference.</p>  <p>&mdash;&nbsp;Hello Maurice. Nope, still kicking. Though you, you’re still as dense as ever, I see.</p>  <p>Outside, the rain drummed against the cobblestones like an old Renaud tune, and in Adèle’s heart, it was a whole Brassens refrain shuffling its feet, cigarette dangling from its lips.</p>  [Translator's note: Renaud and Brassens were popular French singer-songwriters known for their poetic lyrics and often melancholic themes. Their music is deeply ingrained in French culture, particularly in Paris.] | <p>In the chiaroscuro of a Parisian bistro, time seemed to have gone on strike, much like the Metro Line 13 on a Monday morning. Adèle, leaning against the zinc bar, idly swirled her spoon in a lukewarm café crème, her gaze lost amongst the swirling smoke and <em>memories that even nostalgia itself would have deemed too bitter to endorse</em>.</p>  <p>A voice erupted from the back of the room, a little raspy, a little too cheerful for the hour:</p>  <p>&mdash;&nbsp;Still not dead, Adèle?</p>  <p>She barely lifted a brow – that famed Parisian brow, schooled in the art of silent sarcasm – and sketched a wry smile, a blend of tender disdain and amused indifference.</p>  <p>&mdash;&nbsp;Hello, Maurice. No, still not dead. Though you, I see, are still as charming as ever.</p>  <p>Outside, the rain drummed against the cobblestones like an old Renaud tune, and within Adèle’s heart, a refrain of Brassens returned, shuffling its feet, a cigarette dangling from its lips.</p>  [Translator's note: Renaud and Brassens were prominent French singer-songwriters known for their poetic lyrics and often melancholic themes.] |
| gemma3:27b | <p>In the chiaroscuro of a Parisian bistro, time seemed to have gone on strike, like line 13 on a Monday morning. Adèle, leaning on the zinc counter, absently stirred her lukewarm café crème, her gaze lost between the swirls of smoke and <em>memories that even nostalgia itself would have refused to endorse</em>.</p>  <p>A voice burst forth from the back of the room, a little raspy, a little too cheerful for the hour:</p>  <p>— You’re not dead yet, Adèle?</p>  <p>She barely raised an eyebrow — that famous Parisian eyebrow, trained at the school of silent sarcasm — and sketched a wry smile, somewhere between tender contempt and amused indifference.</p>  <p>— Hello Maurice. Well, no, still not dead. Though you, you’re still just as much of an idiot, I see.</p>  <p>Outside, the rain drummed on the cobblestones like an old refrain by Renaud, and in Adèle’s heart, it was a whole chorus of Brassens dragging its slippers, cigarette clamped between its teeth.</p> | <p>In the chiaroscuro of a Parisian bistro, time seemed to have gone on strike, much like the line 13 on a Monday morning. Adèle, leaning on the zinc counter, absently stirred her lukewarm *café crème*, her gaze lost between the swirling smoke and <em>memories even nostalgia itself would have disavowed</em>.</p>  <p>A voice erupted from the back of the room, a little raspy, a little too cheerful for the hour:</p>  <p>— Still not dead, Adèle?</p>  <p>She barely raised an eyebrow – that famous Parisian eyebrow, schooled in the art of silent sarcasm – and sketched a wry smile, a blend of tender contempt and amused indifference.</p>  <p>— Hello Maurice. Well, no, not yet. Though you, I see, are still just as much of a fool.</p>  <p>Outside, the rain drummed on the cobblestones like an old Renaud tune, and in Adèle’s heart, a whole chorus of Brassens was dragging its feet, cigarette dangling from its lips.</p> | <p>In the chiaroscuro of a Parisian bistro, time seemed to have walked off the job, much like the line 13 on a Monday morning. Adèle, leaning on the zinc counter, idly stirred her lukewarm café crème, her gaze lost between the rising smoke and <em>memories even nostalgia would have disavowed</em>.</p>  <p>A voice erupted from the back of the room, a little raspy, a little too cheerful for the hour:</p>  <p>— Still not dead, Adèle?</p>  <p>She barely raised an eyebrow – that famous Parisian eyebrow, schooled in the art of silent sarcasm – and sketched a wry smile, a blend of tender contempt and amused indifference.</p>  <p>— Hello Maurice. Well, no, not yet. Though you, I see, are still as much of a fool.</p>  <p>Outside, the rain drummed on the cobblestones like an old Renaud tune, and in Adèle’s heart, a whole chorus of Brassens was dragging its feet, cigarette dangling from its lips.</p>  [Translator's note: Renaud and Brassens were both iconic French singers and songwriters known for their poetic and often melancholic lyrics. Referencing their music evokes a specific Parisian atmosphere and emotional tone.] | <p>In the chiaroscuro of a Parisian bistro, time seemed to have gone on strike, much like the line 13 on a Monday morning. Adèle, leaning on the zinc counter, absently stirred her lukewarm *café crème*, her gaze lost between the swirling smoke and <em>memories even nostalgia itself would have disavowed</em>.</p>  <p>A voice erupted from the back of the room, a little raspy, a little too cheerful for the hour:</p>  <p>— Still not dead, Adèle?</p>  <p>She barely raised an eyebrow – that famous Parisian eyebrow, schooled in the art of silent sarcasm – and sketched a wry smile, a blend of tender contempt and amused indifference.</p>  <p>— Hello Maurice. Well, no, not yet. Though you, I see, are still just as much of a fool.</p>  <p>Outside, the rain drummed on the cobblestones like an old Renaud tune, and in Adèle’s heart, a whole chorus of Brassens was dragging its feet, cigarette dangling from its lips.</p> [Translator's note: Renaud and Brassens were both iconic French singers and songwriters known for their poetic and often melancholic lyrics. Referencing their music evokes a specific Parisian atmosphere and emotional tone.] |
| mistral:7b | ❌ Error: All models (mistral:7b) failed... | ❌ Error: All models (mistral:7b) failed... | ❌ Error: All models (mistral:7b) failed... | ❌ Error: All models (mistral:7b) failed... |
| mistral-small:24b | <p>In the chiaroscuro of a Parisian bistro, time seemed to have gone on strike like line 13 on a Monday morning. Adèle, leaning on the zinc counter, absently stirred her spoon in a lukewarm café crème, her gaze lost between the swirls of smoke and <em>memories that even nostalgia would refuse to endorse</em>.</p>  <p>A voice burst from the back of the room, slightly raspy, too cheerful for the hour:</p>  <p>&mdash; You're still not dead, Adèle?</p>  <p>She barely raised an eyebrow &mdash; that famous Parisian eyebrow, trained in the school of silent sarcasm &mdash; and sketched a smile at the corner of her mouth, between tender contempt and amused indifference.</p>  <p>&mdash; Hi Maurice. Well, no, still not dead. But you, you're still as much of an idiot, I see.</p>  <p>Outside, the rain drummed on the cobblestones like an old Renaud tune, and in Adèle's heart, it was a whole chorus of Brassens that came shuffling back, cigarette dangling from its lips.</p> | <p>In the soft glow of a Parisian bistro, time seemed to have gone on strike like the line 13 on a Monday morning. Adèle, elbow propped up on the zinc counter, idly stirred her spoon in a lukewarm café crème, her gaze lost between the swirls of smoke and <em>memories that even nostalgia would refuse to endorse</em>.</p>  <p>A voice burst from the back of the room, slightly raspy, too cheerful for the hour:</p>  <p>&mdash; You're still not dead, Adèle?</p>  <p>She barely raised an eyebrow &mdash; that famous Parisian eyebrow, trained in the school of silent sarcasm &mdash; and sketched a lopsided smile, somewhere between tender contempt and amused indifference.</p>  <p>&mdash; Hi Maurice. Well, no, not dead yet. But you, you're still as much of an idiot as ever, I see.</p>  <p>Outside, the rain drummed on the cobblestones like an old tune by Renaud, and in Adèle's heart, it was a whole chorus of Brassens, dragging his shoes along, cigarette dangling from his lips. | <p>In the soft glow of a Parisian bistro, time seemed to have gone on strike like the line 13 on a Monday morning. Adèle, elbow propped up on the zinc counter, idly stirred her spoon in a lukewarm café crème, her gaze lost between the swirls of smoke and <em>memories that even nostalgia would refuse to endorse</em>.</p>  <p>A voice boomed from the back of the room, slightly raspy, too cheerful for the hour:</p>  <p>&mdash; You're still not dead, Adèle?</p>  <p>She barely raised an eyebrow &mdash; that famous Parisian eyebrow, trained in the school of silent sarcasm &mdash; and sketched a lopsided smile, somewhere between tender contempt and amused indifference.</p>  <p>&mdash; Hi Maurice. Well, no, not dead yet. But you're still as much of an idiot, I see.</p>  <p>Outside, the rain drummed on the cobblestones like an old tune by Renaud, and in Adèle's heart, it was a whole chorus of Brassens, dragging his shoes along, cigarette dangling from his lips.</p> | <p>In the soft glow of a Parisian bistro, time seemed to have gone on strike like the line 13 on a Monday morning. Adèle, elbow propped up on the zinc counter, idly stirred her spoon in a lukewarm café crème, her gaze lost between the swirls of smoke and <em>memories that even nostalgia would refuse to endorse</em>.</p>  <p>A voice erupted from the back of the room, slightly raspy, too cheerful for the hour:</p>  <p>&mdash; You're still not dead, Adèle?</p>  <p>She barely raised an eyebrow &mdash; that famous Parisian eyebrow, schooled in the art of silent sarcasm &mdash; and sketched a smile that was both tenderly contemptuous and amusedly indifferent.</p>  <p>&mdash; Hello Maurice. Well, no, still not dead. But you, you're still as much of an idiot, I see.</p>  <p>Outside, the rain drummed against the cobblestones like an old tune by Renaud, and in Adèle's heart, it was a whole chorus of Brassens that came shuffling back, cigarette dangling from its lips. [Translator's note: Renaud and Georges Brassens are famous French singer-songwriters.] |
| dorian2b/vera | <p>In the half-light of a Parisian bistro, time seemed to have gone on strike like the RER Line 13 on a Monday morning. Adèle, leaning against the zinc counter, idly stirred her warm café crème with a spoon, her eyes lost between the spirals of smoke and <em>the memories that even nostalgia itself would have refused to vouch for</em>.</p>  <p>A voice erupted from the back of the room, a bit hoarse, a bit too cheery for the hour:</p>  <p>&mdash; You're still not dead, Adèle?</p>  <p>She barely raised an eyebrow &mdash; that famous Parisian eyebrow, trained in the school of silent sarcasm &mdash; and gave a sardonic smile, half-mistrustful, half-amused.</p>  <p>&mdash; Hello Maurice. No, I'm still not dead. As for you, you're still as thick as ever, I see.</p>  <p>Outside, the rain drummed on the cobblestones like an old refrain of Renaud, and in Adèle's heart, a whole verse from Brassens kept trudging along, cigarette between his teeth.</p> | <p>In the dim light of a Parisian bistro, time seemed to have gone on strike like the RER 13 on a Monday morning. Adèle, leaning against the zinc counter, idly twirled her spoon in a warm cup of café crème, her eyes lost between the wisps of steam and <em>the memories that even nostalgia itself would have rejected as too sweet</em>.</p>  <p>A voice rang out from the back of the room, a bit hoarse, a bit too cheery for the hour:</p>  <p>&mdash; You're still not dead, Adèle?</p>  <p>She barely raised an eyebrow &mdash; that famous Parisian eyebrow, trained in the art of silent sarcasm &mdash; and gave a sardonic smile, half-mocking, half-amused.</p>  <p>&mdash; Hello Maurice. No, I'm still not dead. As for you, you're still as thick as ever, I see.</p>  <p>Outside, the rain drummed on the cobblestones like an old refrain of Renaud, and in Adèle's heart, a familiar tune by Brassens kept tapping its feet, cigarette dangling from her lips.</p> | <p>In the half-light of a Parisian bistro, time seemed to have gone on strike like Line 13 on a Monday morning. Adèle, leaning against the zinc bar, idly twirled her spoon in a warm cup of café crème, her eyes lost between the spirals of smoke and <em>memories that even nostalgia itself would have rejected</em>.</p>  <p>A voice emerged from the back of the room, a bit hoarse, a bit too cheery for the hour:</p>  <p>&mdash; You're still not dead, Adèle?</p>  <p>She barely raised an eyebrow &mdash; that famous Parisian eyebrow, trained in the school of silent sarcasm &mdash; and gave a sardonic smile, a mix of tender contempt and amused indifference.</p>  <p>&mdash; Hello, Maurice. No, I'm still not dead. As for you, you're still as thick as ever, I see.</p>  <p>Outside, the rain drummed on the cobblestones like an old refrain from Renaud, and in Adèle's heart, a familiar tune by Brassens shuffled its boots, cigarette dangling from its lips.</p> | <p>In the dim light of a Parisian bistro, time seemed to have gone on strike like the RER line on a Monday morning. Adèle, leaning against the zinc counter, idly twirled her spoon in a warm cup of café crème, her eyes lost between the swirling steam and <em>memories that even nostalgia itself would have rejected</em>.</p>  <p>A voice rang out from the back of the room, a bit hoarse, a bit too cheery for the hour:</p>  <p>&mdash;You're still not dead, Adèle?</p>  <p>She barely raised an eyebrow &mdash; that famous Parisian eyebrow, trained in the art of silent sarcasm &mdash; and gave a sardonic smile, half-mocking, half-amused.</p>  <p>&mdash;Hello, Maurice. No, I'm still not dead. As for you, you're still as thick as ever, I see.</p>  <p>Outside, the rain drummed on the cobblestones like an old refrain of Renaud, and in Adèle's heart, a familiar tune by Brassens shuffled its boots, cigarette dangling from its lips.</p> |
| nous-hermes2 | ❌ Error: All models (nous-hermes2) failed... | ❌ Error: All models (nous-hermes2) failed... | ❌ Error: All models (nous-hermes2) failed... | ❌ Error: All models (nous-hermes2) failed... |
