#!/usr/bin/env python3
"""
Script to test translation quality across different models and prompts.

Results are merged into docs/model-prompt-comparison.json, and docs/model-prompt-comparison.md
is regenerated from all of them: only the models given with --models are (re)tested.

    python test_models_prompts.py                                   # default Ollama models
    python test_models_prompts.py --models tencent/hy-mt2-7b -u https://openrouter.ai/api/v1
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from libs.prompts import PREDEFINED_PROMPTS
from libs.translation import translate_with_chunking
from libs.languages import detect_language

# Texte de test avec des idiomes français
TEST_TEXT = """<p>Dans le clair-obscur d'un bistrot parisien, le temps semblait s'être mis en grève comme la ligne&nbsp;13 un lundi matin. Adèle, accoudée au comptoir de zinc, tournait distraitement sa cuillère dans un café crème tiède, l'œil perdu entre les volutes de fumée et <em>les souvenirs que la nostalgie elle-même aurait refusés de cautionner</em>.</p>

<p>Une voix jaillit du fond de la salle, un peu éraillée, un peu trop joyeuse pour l'heure&nbsp;:</p>

<p>&mdash;&nbsp;T'es toujours pas morte, Adèle&nbsp;?</p>

<p>Elle leva à peine un sourcil &mdash; ce fameux sourcil parisien, formé à l'école du sarcasme silencieux &mdash; et esquissa un sourire en coin, entre le mépris tendre et l'indifférence amusée.</p>

<p>&mdash;&nbsp;Salut Maurice. Eh bah non, toujours pas morte. Par contre, toi, t'es toujours aussi con, je vois.</p>

<p>Dehors, la pluie tambourinait les pavés comme une vieille rengaine de Renaud, et dans le cœur d'Adèle, c'était tout un refrain de Brassens qui revenait traîner ses godasses, clope au bec.</p>"""

RESULTS_FILE = Path("docs/model-prompt-comparison.json")
MARKDOWN_FILE = Path("docs/model-prompt-comparison.md")
SOURCE_LANGUAGE = "fr"

# Default models to test
DEFAULT_MODELS = [
    "gemma3:1b",
    "gemma3:4b",
    "gemma3:12b",
    "gemma3:27b",
    "mistral:7b",
    "mistral-small:24b",
    "dorian2b/vera",
    "nous-hermes2"
]


def translate_text(model: str, prompt: str, text: str, api_base: str, api_key: str = None) -> str:
    """Traduire un texte avec un modèle et un prompt donnés."""
    formatted_prompt = prompt.format(target_language="English")
    try:
        result, _ = translate_with_chunking(
            api_base=api_base,
            models=model,
            prompt=formatted_prompt,
            html=text,
            progress={},
            debug=False,
            api_key=api_key
        )
        return result
    except Exception as e:
        return f"❌ Error: {str(e)[:100]}..."


def escape_markdown(text: str) -> str:
    """Échapper les caractères spéciaux markdown."""
    return text.replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def cell(translation: str) -> str:
    """Table cell for a translation, flagging outputs left in the source language."""
    if not translation.startswith("❌"):
        from bs4 import BeautifulSoup
        if detect_language(BeautifulSoup(translation, 'html.parser').get_text()) == SOURCE_LANGUAGE:
            return "❌ Not translated: the output is the source text"
    return escape_markdown(translation)


def write_markdown(prompt_names: list[str], results: dict) -> None:
    lines = [
        "# Comparaison des traductions par modèle et prompt",
        "",
        "*Généré par `test_models_prompts.py`. Le texte source est fictif et volontairement riche en idiomes "
        "français pour tester la capacité de traduction des nuances linguistiques ; langue cible : anglais.*",
        "",
        "## Texte original",
        "",
        TEST_TEXT,
        "",
        "## Traductions",
        "",
        "| Modèle | " + " | ".join(prompt_names) + " |",
        "| --- | " + " | ".join(["---"] * len(prompt_names)) + " |",
    ]
    for model, by_prompt in results.items():
        lines.append("| " + " | ".join([model] + [cell(by_prompt.get(p, "")) for p in prompt_names]) + " |")
    MARKDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Compare translations across models and prompts")
    parser.add_argument('--models', help="Comma-separated models to (re)test (default: the Ollama models)")
    parser.add_argument('-u', '--url', default="http://localhost:11434", help="API base URL")
    parser.add_argument('-k', '--api-key', default=os.environ.get('LLM_API_KEY'),
                        help="Bearer token for remote LLM API (or env LLM_API_KEY)")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(',')] if args.models else DEFAULT_MODELS
    prompt_names = list(PREDEFINED_PROMPTS.keys())
    data = json.loads(RESULTS_FILE.read_text(encoding="utf-8")) if RESULTS_FILE.exists() else {"results": {}}
    results = data["results"]

    print("🚀 Test de traduction avec différents modèles et prompts")
    print(f"📝 Texte source: {len(TEST_TEXT)} caractères")
    print(f"🤖 Modèles à tester: {', '.join(models)}")
    print(f"📋 Prompts à tester: {', '.join(prompt_names)}")

    for model in models:
        print(f"🔧 Testing model: {model}")
        results[model] = {}
        for idx, prompt_name in enumerate(prompt_names):
            print(f"  {prompt_name}")
            translation = translate_text(model, PREDEFINED_PROMPTS[prompt_name], TEST_TEXT, args.url, args.api_key)
            results[model][prompt_name] = translation
            if idx == 0 and translation.startswith("❌"):
                # First prompt is the availability test: skip a model that does not answer
                print(f"  ⚠️  Modèle {model} indisponible ou défaillant, passage au suivant")
                results[model] = {p: translation for p in prompt_names}
                break
            time.sleep(2)  # Petite pause pour éviter de surcharger l'API

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps({"prompts": prompt_names, "results": results}, indent=2,
                                       ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(prompt_names, results)
    print(f"✅ Résultats dans {RESULTS_FILE} et {MARKDOWN_FILE}")


if __name__ == "__main__":
    main()
