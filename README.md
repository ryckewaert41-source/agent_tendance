# Agent tendance : tendances des marchés, mises à jour chaque jour, gratuites

Ce dossier contient tout ce qu'il faut pour que **GitHub** (gratuit) calcule chaque jour la tendance d'un panier de
cryptos, de paires forex et d'actions, puis publie une **page web** toujours à jour. Votre PC peut rester éteint.

## Ce que ça fait
- Chaque jour à 00:45 UTC (02:45 en été, 01:45 en hiver, heure belge), GitHub lance `agent_tendance.py`.
- Le script télécharge les bougies journalières complètes (Yahoo Finance), calcule trois signaux fixes
  (croisement SMA 20/50, cassure 20 jours, momentum 60 jours) et en déduit l'état : haussière, mixte ou baissière.
- Il écrit `docs/data/tendances.json`. La page `docs/index.html` le lit et se rafraîchit toute seule
  (toutes les 10 minutes, et dès que vous revenez sur l'onglet).

## Mise en route (environ 15 minutes)
1. Créez un compte gratuit sur github.com, puis un **nouveau dépôt public** (par exemple `tendances`).
   Public, parce que les pages GitHub gratuites l'exigent. Il ne contient aucune donnée personnelle ni clé.
2. Dans le dépôt : **Add file > Upload files**, puis glissez **tout le contenu de ce dossier**
   (`agent_tendance.py`, `univers.json`, `requirements.txt`, `README.md`, et les dossiers `docs` et `.github`).
   Cliquez sur **Commit changes**.
   Si le dossier `.github` n'est pas pris en compte : **Add file > Create new file**, tapez le nom
   `.github/workflows/tendances.yml` (les `/` créent les dossiers) et collez le contenu du fichier.
3. **Settings > Pages** : Source = *Deploy from a branch*, Branch = `main`, dossier = `/docs`, puis **Save**.
4. **Settings > Actions > General > Workflow permissions** : choisissez *Read and write permissions*, puis **Save**.
5. Onglet **Actions** > *Mise à jour des tendances* > **Run workflow**. Attendez 2 à 3 minutes (pastille verte).
6. Ouvrez `https://VOTRE-PSEUDO.github.io/tendances/` (comptez 1 à 2 minutes après le premier lancement).
   Tant que la bannière « Données de démonstration » est affichée, la vraie mise à jour n'a pas eu lieu.

## Modifier les actifs suivis
Éditez `univers.json` directement sur GitHub (icône crayon). Les symboles sont ceux de Yahoo Finance :
`BTC-USD` (crypto), `EURUSD=X` (forex), `AAPL`, `ASML.AS`, `KBC.BR` (actions, suffixe = place de cotation).
Chaque classe a une `note` affichée sur la page : mettez-y ce que vous avez réellement vérifié.

## Tester chez vous sans internet
```
pip install -r requirements.txt
python agent_tendance.py --demo
cd docs
python -m http.server 8000      # puis ouvrez http://localhost:8000
```

## À savoir, honnêtement
- **Je n'ai pas pu tester le téléchargement réel** : le test a été fait sur des données simulées. Yahoo Finance n'est pas une
  source officielle ; elle peut limiter ou refuser certaines requêtes. Si plus de la moitié des actifs échouent, le script
  garde l'ancien fichier et le workflow apparaît en rouge (GitHub vous envoie un e-mail). Dites-moi alors l'erreur
  affichée dans l'onglet Actions, et nous changerons de source.
- Les tâches planifiées de GitHub peuvent avoir **quelques minutes ou dizaines de minutes de retard**. Si le dépôt reste
  inactif 60 jours, GitHub peut les désactiver ; les mises à jour quotidiennes comptent normalement comme activité.
  Si cela arrive, réactivez le workflow dans l'onglet Actions.
- Les tendances sont une **information**, pas un conseil financier. Dans nos tests : un effet de protection pour les
  cryptos en version acheteuse seulement, aucun avantage net sur le forex, rien de testé sur les actions.
