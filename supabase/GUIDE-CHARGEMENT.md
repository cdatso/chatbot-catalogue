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

## ⑤ Vérifier le rafraîchissement (L6, spec 25/08)

Après ① + ② + ③ + ④, la table est fraîchement chargée : elle doit être
exactement à jour avec les fichiers locaux. Vérifie-le sans écrire
(clé `anon` seule, celle relevée à l'étape ④ ci-dessus) :

```powershell
$env:SUPABASE_URL = "https://<ref>.supabase.co"          # valeur de l'etape ④
$env:SUPABASE_ANON_KEY = "<clé anon publique>"            # valeur de l'etape ④
py -3.12 outils\rafraichir-passages.py
```

(`--simuler` est le mode par défaut — pas besoin de le taper ; le
drapeau existe pour la lisibilité si tu préfères l'écrire.)

**Sortie attendue, juste après un chargement frais** : `0 nouvelle /
0 modifiee / 0 disparue / 46 inchangees`. Un écart (des « modifiées »
ou des « nouvelles ») signale que le CSV importé et les fichiers locaux
de `analyses-de-films` ne correspondent plus — signale-le avant de
poursuivre.

**Après une nouvelle analyse publiée sur le site**, c'est LA commande à
rejouer (le détecteur de dérive du contrôle ③ ligne 8 dit QUAND) ; si le
diff n'est pas vide, rejoue avec `--appliquer` pour l'exécuter (détail :
`README.md`, section « La table `passages` est une copie datée »).
