FROM python:3.10-slim

# Définir le répertoire de travail
WORKDIR /app

# Copier et installer les dépendances
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY . /app

# Ajouter PYTHONPATH pour les imports relatifs
ENV PYTHONPATH=/app

# Exposer le port Gradio par défaut
EXPOSE 7860

# Lancer le serveur Gradio
CMD ["python", "gradio_app.py"]