#!/usr/bin/env python3
"""
Script to test translation quality across different models and prompts
"""

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

# Texte de test avec des idiomes français
TEST_TEXT = """<p>Dans le clair-obscur d'un bistrot parisien, le temps semblait s'être mis en grève comme la ligne&nbsp;13 un lundi matin. Adèle, accoudée au comptoir de zinc, tournait distraitement sa cuillère dans un café crème tiède, l'œil perdu entre les volutes de fumée et <em>les souvenirs que la nostalgie elle-même aurait refusés de cautionner</em>.</p>

<p>Une voix jaillit du fond de la salle, un peu éraillée, un peu trop joyeuse pour l'heure&nbsp;:</p>

<p>&mdash;&nbsp;T'es toujours pas morte, Adèle&nbsp;?</p>

<p>Elle leva à peine un sourcil &mdash; ce fameux sourcil parisien, formé à l'école du sarcasme silencieux &mdash; et esquissa un sourire en coin, entre le mépris tendre et l'indifférence amusée.</p>

<p>&mdash;&nbsp;Salut Maurice. Eh bah non, toujours pas morte. Par contre, toi, t'es toujours aussi con, je vois.</p>

<p>Dehors, la pluie tambourinait les pavés comme une vieille rengaine de Renaud, et dans le cœur d'Adèle, c'était tout un refrain de Brassens qui revenait traîner ses godasses, clope au bec.</p>"""

API_BASE = "http://localhost:11434"

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

def translate_text(model: str, prompt: str, text: str) -> str:
    """Traduire un texte avec un modèle et un prompt donnés."""
    api_base = "http://localhost:11434"  # Use native Ollama API
    
    # Format the prompt for the target language
    formatted_prompt = prompt.format(target_language="English")
    
    # Create a minimal progress dict for the translation
    progress = {}
    
    try:
        result, model_used = translate_with_chunking(
            api_base=api_base,
            models=model,
            prompt=formatted_prompt,
            html=text,
            progress=progress,
            debug=False
        )
        return result
    except Exception as e:
        return f"❌ Error: {str(e)[:100]}..."

def escape_markdown(text: str) -> str:
    """Échapper les caractères spéciaux markdown."""
    return text.replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')

def main():
    """Fonction principale."""
    print("🚀 Test de traduction avec différents modèles et prompts")
    print(f"📝 Texte source: {len(TEST_TEXT)} caractères")
    print(f"🎯 Langue cible: English")
    print()
    
    # Récupérer les modèles et prompts
    models = DEFAULT_MODELS
    prompt_names = list(PREDEFINED_PROMPTS.keys())
    
    print(f"🤖 Modèles à tester: {', '.join(models)}")
    print(f"📋 Prompts à tester: {', '.join(prompt_names)}")
    print()
    
    # Matrice des résultats
    results = {}
    
    total_tests = len(models) * len(prompt_names)
    current_test = 0
    
    for model in models:
        print(f"🔧 Testing model: {model}")
        results[model] = {}
        
        # Test first prompt to see if model is available
        first_prompt_name = prompt_names[0]
        first_prompt = PREDEFINED_PROMPTS[first_prompt_name]
        
        print(f"  [{current_test + 1}/{total_tests}] {first_prompt_name} (test de disponibilité)")
        first_translation = translate_text(model, first_prompt, TEST_TEXT)
        
        # If first translation failed, skip this model entirely
        if first_translation.startswith("❌"):
            print(f"  ⚠️  Modèle {model} indisponible ou défaillant, passage au suivant")
            # Fill all results for this model with the error
            for prompt_name in prompt_names:
                current_test += 1
                results[model][prompt_name] = first_translation
            continue
        
        # Model works, record first result and continue with remaining prompts
        results[model][first_prompt_name] = first_translation
        current_test += 1
        
        # Test remaining prompts
        for prompt_name in prompt_names[1:]:
            current_test += 1
            print(f"  [{current_test}/{total_tests}] {prompt_name}")
            
            prompt = PREDEFINED_PROMPTS[prompt_name]
            translation = translate_text(model, prompt, TEST_TEXT)
            results[model][prompt_name] = translation
            
            time.sleep(2)  # Petite pause pour éviter de surcharger l'API
    
    # Sauvegarder les résultats complets
    results_file = Path("test_results.json")
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Résultats complets sauvegardés dans {results_file}")
    
    # Générer le tableau markdown
    print("\n📊 Génération du tableau markdown...")
    
    markdown_lines = []
    markdown_lines.append("## Comparaison des traductions par modèle et prompt")
    markdown_lines.append("")
    markdown_lines.append("*Note: Le texte source est fictif et volontairement riche en idiomes français pour tester la capacité de traduction des nuances linguistiques.*")
    markdown_lines.append("")
    
    # En-tête du tableau
    header = "| Modèle | " + " | ".join(prompt_names) + " |"
    separator = "| --- | " + " | ".join(["---"] * len(prompt_names)) + " |"
    
    markdown_lines.append(header)
    markdown_lines.append(separator)
    
    # Lignes du tableau
    for model in models:
        row_parts = [model]
        for prompt_name in prompt_names:
            translation = results[model][prompt_name]
            escaped = escape_markdown(translation)
            row_parts.append(escaped)
        
        row = "| " + " | ".join(row_parts) + " |"
        markdown_lines.append(row)
    
    markdown_content = "\n".join(markdown_lines)
    
    # Ajouter au README.md
    readme_path = Path("README.md")
    if readme_path.exists():
        with open(readme_path, 'r', encoding='utf-8') as f:
            current_content = f.read()
        
        # Chercher s'il y a déjà une section de comparaison
        if "## Comparaison des traductions par modèle et prompt" in current_content:
            # Remplacer l'ancienne section
            lines = current_content.split('\n')
            new_lines = []
            skip = False
            
            for line in lines:
                if line.startswith("## Comparaison des traductions par modèle et prompt"):
                    skip = True
                elif line.startswith("## ") and skip:
                    skip = False
                    new_lines.append(line)
                elif not skip:
                    new_lines.append(line)
            
            new_content = '\n'.join(new_lines) + "\n\n" + markdown_content + "\n"
        else:
            # Ajouter à la fin
            new_content = current_content.rstrip() + "\n\n" + markdown_content + "\n"
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✅ Tableau ajouté au {readme_path}")
    else:
        # Créer un nouveau README avec juste le tableau
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content + "\n")
        print(f"✅ Nouveau {readme_path} créé avec le tableau")
    
    print("\n🎉 Test terminé !")
    print(f"📄 Consulter {readme_path} pour voir le tableau de comparaison")

if __name__ == "__main__":
    main()
