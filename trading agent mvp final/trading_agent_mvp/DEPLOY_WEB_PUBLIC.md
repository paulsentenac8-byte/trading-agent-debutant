# Déploiement web public — sans installation locale

## Objectif
Avoir un **vrai lien web** sans rien installer sur ton ordinateur.

## Meilleur compromis avec tes contraintes
Le compromis le plus simple est :
- **hébergement Render**
- **code déjà préparé**
- **aucun Python à lancer sur ton PC**
- tu gères surtout :
  1. un compte GitHub
  2. un compte Render
  3. les clés API si tu veux plus tard connecter des services

---

## Ce que tu ne feras pas
- pas d'installation Python locale
- pas de terminal local
- pas de lancement manuel sur ton PC

---

## Ce que tu feras
### Étape 1
Créer un compte GitHub si tu n'en as pas.

### Étape 2
Mettre ce dossier dans un dépôt GitHub.

### Étape 3
Créer un compte Render.

### Étape 4
Sur Render, importer le dépôt GitHub.

### Étape 5
Render détectera `render.yaml` et déploiera l'application.

### Étape 6
Tu obtiendras un vrai lien du type :
`https://ton-app.onrender.com`

---

## Fichiers déjà prêts pour ça
- `render.yaml`
- `.streamlit/config.toml`
- `app.py`
- `doctor.py`

---

## Après déploiement
Tu auras un vrai lien public à ouvrir dans ton navigateur.

---

## Limite importante
Même avec une vraie app web :
- un bot live broker 24/7 nécessite encore des API, un broker compatible et des tests sérieux
- je recommande de garder le mode démo tant que tout n'est pas validé

---

## Si tu veux aller au bout
La prochaine étape logique est que tu me dises :
- si tu acceptes **GitHub + Render**
- quel broker/API tu veux utiliser plus tard

Et je te préparerai le plan exact de mise en ligne.
