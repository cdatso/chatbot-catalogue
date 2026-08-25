# Chatbot catalogue — Analyses de films

Prototype d'apprentissage BKL-FOR-005 (a) : un chatbot documentaire sur
les analyses publiées du site [Analyses de films](https://www.cdatso.be/analyses-de-films/)
(www.cdatso.be). Il répond en citant la page source ET en fournissant un
extrait verbatim court ou un résumé d'une à deux lignes — jamais un fait
sans passage source.

Ce dépôt est la **préparation** (temps (a)) : ingestion, schéma
Supabase, function, page, testeur. Le **chargement** et le
**déploiement** sont les gestes d'AH (temps (b), mandat séparé).

## Chaîne

```
films-data.js + films/*.html          (site "Analyses de films", lecture seule)
        |
        v  outils/ingerer-passages.py
donnees/passages.csv                  (462 passages, 46 pages, 47 sections exclues)
        |
        v  chargement Supabase (guide, geste AH)
table passages (tsvector, recherche plein texte)
        |
        v  netlify/functions/repondre.mjs
        |     recherche (rechercher_passages) -> prompt borne -> Claude
        v
index.html (page de chat minimale)
```

## Fichiers

- `outils/ingerer-passages.py` — ingestion stdlib, fail-closed (8 contrôles).
- `outils/tester-chatbot.py` — testeur miroir exact de la function ; mode
  `--simuler` (aucun réseau, aucune clé) ou exécution réelle (clés en
  variables d'environnement de la session PowerShell d'AH, jamais en
  argument ni en fichier).
- `donnees/passages.csv`, `donnees/exclusions.csv` — sortie d'ingestion.
- `supabase/01-table-passages.sql`, `02-controles.sql`,
  `GUIDE-CHARGEMENT.md` — schéma et gestes de chargement.
- `netlify/functions/repondre.mjs` — la function (Node 18+, zéro
  dépendance, prompt borné verbatim).
- `index.html`, `assets/style.css`, `config.js` — page de chat minimale.
- `recette/QUESTIONS-RECETTE.md` — jeu de recette (5 questions).

## Variables d'environnement (Netlify, temps (b))

| Variable | Rôle |
|---|---|
| `SUPABASE_URL` | URL du projet Supabase `cdatso` |
| `SUPABASE_ANON_KEY` | clé publique, lecture des passages + RPC recherche |
| `SUPABASE_SERVICE_KEY` | écriture du journal `questions` (jamais côté client) |
| `ANTHROPIC_API_KEY` | appel du modèle Claude |
| `CLAUDE_MODEL` | optionnel, défaut `claude-haiku-4-5-20251001` |
| `ALLOWED_ORIGIN` | optionnel, défaut `https://www.cdatso.be` |

**Zéro secret dans ce dépôt** : aucune clé n'existe sur le poste qui l'a
préparé. `.gitignore` exclut `.env` et tout fichier `*.acces*`.

## Licence

Les extraits et résumés produits par le chatbot portent sur des
analyses publiées sous licence **CC BY-NC-SA 4.0** — la mention
figure en pied de page et dans chaque réponse générée.

## Gestes d'AH, dans l'ordre

1. Chargement Supabase (`supabase\GUIDE-CHARGEMENT.md`).
2. Relevé des accès (URL projet, clé anon, clé service) hors dépôt.
3. Exécution réelle du testeur avec sa clé (`outils\tester-chatbot.py`
   sans `--simuler`, variables d'environnement posées dans sa session
   PowerShell).
4. Déploiement Netlify + remplissage de `config.js` (temps (b), mandat
   séparé).
