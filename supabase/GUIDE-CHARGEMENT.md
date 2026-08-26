# Guide de chargement — chatbot catalogue vers Supabase

Ce guide est pour toi, AH. Il liste tes gestes, dans l'ordre. Rien ici ne
se fait automatiquement : la préparation s'arrête à ce point, le
chargement dans Supabase est ton geste, sur ton compte (comme FOR-003).

## ① Créer les tables

Projet Supabase `cdatso` → **SQL Editor** → colle le contenu de
`supabase\01-table-passages.sql` → **Run**.

Ce script crée les tables `passages` (avec colonne `tsv` générée et
index GIN, RLS + une policy SELECT publique pour `anon`) et `questions`
(RLS activée, **aucune** policy — écriture réservée à la clé service),
ainsi que la fonction `rechercher_passages(q, k)` appelable en RPC par
`anon`. Le bloc pgvector en fin de fichier est entièrement commenté —
ne le décommente pas sans en avoir décidé (nécessite un fournisseur
d'embeddings tiers, Claude n'en produit pas).

## ② Importer les passages

Projet `cdatso` → **Table Editor** → table `passages` → **Insert** →
**Import data from CSV** → sélectionne :

`C:\Users\cdats\Claude\Projects\chatbot-catalogue\donnees\passages.csv`

Encodage UTF-8 sans BOM, séparateur virgule (RFC4180). Colonne `id`
absente du CSV (identité générée). Si l'importeur propose un mapping,
vérifie qu'il retient les 9 colonnes telles quelles (`slug`, `titre`,
`realisateur`, `annee`, `url`, `section`, `ordre`, `texte`,
`page_hash` — ajoutée au temps (b) v2, L6 : SHA-256 de la page source,
identique pour tous les passages d'une même page, support du
rafraîchissement incrémental).

## ③ Vérifier

Projet `cdatso` → **SQL Editor** → colle et exécute
`supabase\02-controles.sql`. Compare chaque ligne du tableau retourné
(`mesure` vs `attendu`). Le premier écart est à signaler, pas à
corriger seul(e) — les attendus de ce fichier sont figés au run
d'ingestion daté dans le fichier lui-même ; si le corpus a bougé depuis
(nouvelle analyse publiée), compare plutôt au chiffre ⑤ de la note de
remise d'exécution correspondant à TON run.

**Point d'attention** : le contrôle 3 (« sections bibliographiques
résiduelles ») utilise la syntaxe SQL standard `U&'...'` (échappement
Unicode dans un littéral chaîne) pour rester dans un fichier `.sql`
ASCII pur — cette syntaxe n'a pas pu être testée sur un moteur réel
depuis ce poste (aucune connexion à un service, borne du mandat). Si
elle échoue à l'exécution, signale-le : le repli est de retaper le
motif avec de vrais caractères accentués directement dans le SQL
Editor (le fichier versionné reste ASCII, ce repli ne modifie que ta
saisie côté Supabase).

## ④ Relever les paramètres du temps (b)

Projet `cdatso` → **Settings** → **API** → relève et garde de côté
(fichier `_scratch\FOR-005-supabase-acces.txt`, hors dépôt) :

- l'**URL du projet** (`https://<ref>.supabase.co`) ;
- la clé **`anon`** (`public`).

Ces deux valeurs, plus une clé Anthropic, sont les paramètres du
chargement en variables d'environnement Netlify (temps (b), publication
— mandat séparé).

**⚠️ Borne** : la clé **`service_role`** (nécessaire à la Netlify
Function pour écrire dans `questions`, et au testeur `tester-chatbot.py`
pour l'exécution réelle) ne sort **jamais** du dashboard vers un fichier
lu par un outil de lecture standard, un dépôt, ou le chat — elle se
saisit directement dans les variables d'environnement Netlify au moment
du déploiement, ou dans la session PowerShell d'AH pour un test local.
