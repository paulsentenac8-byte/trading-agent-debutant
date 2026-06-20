# GitHub + Render — guide clic par clic

## Objectif
Mettre l'application en ligne avec un vrai lien web, sans installer Python sur ton ordinateur.

---

## Partie 1 — GitHub

### 1. Créer un compte GitHub
Va sur :
- https://github.com/

Clique sur **Sign up**.

---

### 2. Créer un nouveau dépôt
Une fois connecté :
1. Clique sur **New**
2. Nom du dépôt : `trading-agent-debutant`
3. Laisse le dépôt en **Private** si tu veux garder ça privé
4. Clique sur **Create repository**

---

### 3. Envoyer les fichiers sur GitHub
1. Télécharge `trading_agent_mvp.zip`
2. Décompresse-le sur ton ordinateur
3. Sur la page GitHub du dépôt, clique sur **uploading an existing file**
4. Glisse tous les fichiers du dossier `trading_agent_mvp` dans la page
5. Attends la fin de l'upload
6. Clique sur **Commit changes**

---

## Partie 2 — Render

### 4. Créer un compte Render
Va sur :
- https://render.com/

Clique sur **Get Started**.

Tu peux te connecter avec GitHub.

---

### 5. Connecter GitHub à Render
Si Render le demande :
- autorise l'accès à ton compte GitHub

---

### 6. Créer le service web
1. Dans Render, clique sur **New +**
2. Clique sur **Web Service**
3. Choisis le dépôt GitHub `trading-agent-debutant`

Render devrait détecter les fichiers du projet.

---

### 7. Vérifier les réglages
Render doit utiliser le fichier :
- `render.yaml`

Si besoin, vérifie :
- Build Command : `pip install --upgrade pip && pip install -r requirements.txt`
- Start Command : `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

---

### 8. Lancer le déploiement
Clique sur **Create Web Service**.

Render va :
- installer les dépendances
- construire l'application
- la lancer

---

### 9. Ouvrir le lien
Une fois le déploiement terminé, Render te donnera une URL du type :
- `https://assistant-trading-debutant.onrender.com`

C'est ton vrai lien web.

---

## Si ça échoue
Regarde les logs Render.

Les premières choses à vérifier :
- dépôt GitHub bien complet
- `requirements.txt` présent
- `render.yaml` présent
- `app.py` présent

---

## Ce que tu me renvoies si tu veux mon aide
Envoie-moi :
1. le message d'erreur Render
2. ou une capture d'écran des logs
3. ou le lien Render si ça a marché
