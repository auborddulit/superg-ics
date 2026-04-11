# SuperG → ICS

Génère automatiquement un fichier `.ics` depuis les réservations SuperG,
publié chaque jour via GitHub Actions + GitHub Pages.

## Setup (5 minutes)

### 1. Crée le repo GitHub
- Va sur github.com → **New repository**
- Nom : `superg-ics` (ou ce que tu veux)
- Visibilité : **Public** (nécessaire pour GitHub Pages gratuit)
- Crée le repo

### 2. Upload les fichiers
Uploade ces deux fichiers dans le repo :
- `generate.py`
- `.github/workflows/generate_ics.yml`

### 3. Ajoute tes secrets
Dans le repo GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret** :
- `SUPERG_EMAIL` → ton email SuperG
- `SUPERG_PASSWORD` → ton mot de passe SuperG

### 4. Active GitHub Pages
Dans le repo → **Settings** → **Pages** :
- Source : **Deploy from a branch**
- Branch : `main` / `/ (root)`
- Save

### 5. Lance le workflow manuellement
Dans le repo → **Actions** → **Generate SuperG ICS** → **Run workflow**

### 6. Abonne-toi dans Google Calendar
Une fois le fichier généré, ton ICS est accessible à :
```
https://TON_USERNAME.github.io/superg-ics/superg_reservations.ics
```
Dans Google Calendar → **Autres agendas** → **Via une URL** → colle cette URL.

## Mise à jour automatique
Le workflow tourne tous les jours à 5h UTC (6h/7h heure de Paris).
Google Calendar se resynchronise toutes les 24h environ.
