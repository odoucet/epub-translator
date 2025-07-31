# EPUB Translator (Autonomous Version)

This project allows you to translate EPUB books using a local LLM like Mistral or Gemma (via Ollama) or any OpenAI-compatible API.  
It preserves HTML structure (headers, emphasis, lists), supports translator footnotes, and can output both EPUB and PDF.

---

## ✨ Features

- Translate EPUB files using chunked **HTML** input for structure preservation
- Supports multi-style prompts (literary, elegant, narrative)
- Outputs EPUB **and optional PDF** (`--pdf`)
- Resumable: tracks translation progress in a JSON workspace
- Supports local LLMs via **Ollama** and remote OpenAI-compatible APIs
- Translate the **entire book or just one chapter** with `--chapter`
- Compare model outputs on a chapter (`compare_models.py`)

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
   ollama pull mistral
   ollama pull gemma:2b
   ollama pull nous-hermes2
   ```

2. Build and launch translator with Docker Compose:
   ```bash
   docker-compose up -d
   ```

---

## 🚀 Translate a Book

```bash
python cli.py --file book.epub -l french --prompt-style literary --pdf
```

Options:
- `--chapter 3` → translate only chapter 3
- `--workspace` → resume from previous translation progress
- `--model mistral` → use a specific model
- `--url http://localhost:11434` → custom API endpoint

---

## 🔁 Compare LLM Models

To compare model outputs on chapter 3:

```bash
python cli.py --file book.epub -l french -p literary --compare gemma3:1b,mistral:7b --chapter 3 -o model_comparison.md
```

Our own tests show:
* **gemma3:1b**: hard to keep HTML structure and follow prompt exactly
* **other gemma3 models**: all timeout, to be investigated
* **mistral:7b**: hard to keep HTML structure and follow prompt exactly
* **mistral-small:24b**: good (but slow)
* **dorian2b/vera**: works very well on small chunks

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
- [ ] add openai-compatible API support
- [ ] add "literal" translation style

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
