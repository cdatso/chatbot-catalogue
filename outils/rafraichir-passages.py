#!/usr/bin/env python3
# rafraichir-passages.py
# BKL-FOR-005 (b) v2 -- L6, rafraichissement INCREMENTAL de la table
# passages, spec NOTE-SPEC-REFRESH-PASSAGES-2026-08-25.md (regle D-7 du
# patron serverless v1.1). Diff PAR PAGE (hash par page) contre le
# registre local et les fichiers locaux -- JAMAIS un rechargement aveugle
# de la table servie.
#
# Stdlib seul (csv, hashlib, importlib.util, json, os, re, sys, urllib,
# pathlib). Reutilise les fonctions d'extraction de outils/ingerer-
# passages.py (meme repertoire, charge dynamiquement -- nom de fichier a
# tiret, "import" direct impossible) : une page se decoupe de la MEME
# facon au premier chargement et a un rafraichissement -- deux parseurs
# maintenus separement divergeraient tot ou tard (meme risque que D-6).
#
# Cles Supabase, variables d'environnement du POSTE UNIQUEMENT (patron
# S-2) -- JAMAIS en session, JAMAIS dans ce depot, JAMAIS en argument :
#   SUPABASE_URL            URL du projet (les deux modes).
#   SUPABASE_ANON_KEY       cle PUBLIQUE, lecture seule (policy SELECT
#                            de passages) -- suffit au mode --simuler.
#   SUPABASE_SERVICE_KEY    cle SECRETE, exigee par --appliquer SEUL
#                            (delete + insert, RLS contournee par role).
#
# Bornes (spec, section "Declenchement et bornes") : lecture seule sur
# analyses-de-films (LOCAL -- outil de maintenance sur le poste, hors du
# perimetre D-7/L4 qui vise exclusivement la lecture HTTP de la
# function) ; ecriture sur la SEULE table passages ; aucun appel au
# modele ; jamais lance depuis une session mandatee avec la cle (la cle
# vit chez AH) ; declenchement MANUEL par AH apres chaque publication.
#
# Deux modes :
#   (defaut, --simuler)   affiche le diff (nouvelles / modifiees /
#                          disparues / inchangees), AUCUNE ecriture.
#   --appliquer            execute le diff : insert des nouvelles,
#                          delete+insert des modifiees (page par page,
#                          la table reste servie pendant l'operation),
#                          delete des disparues APRES confirmation par
#                          prompt (un geste humain, jamais automatique).
#                          Ne touche RIEN si le diff est vide
#                          (idempotence, patron C-3).

import hashlib
import importlib.util
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_ROOT = Path(r"C:\Users\cdats\Claude\Projects\analyses-de-films")
FILMS_DATA = SITE_ROOT / "assets" / "films-data.js"
FILMS_DIR = SITE_ROOT / "films"
INGESTEUR_PY = Path(__file__).resolve().parent / "ingerer-passages.py"
URL_PREFIX = "https://www.cdatso.be/analyses-de-films/"
DELAI_S = 20


def echec(message):
    print("ECHEC -- " + message)
    sys.exit(1)


def charger_ingesteur():
    spec = importlib.util.spec_from_file_location("ingerer_passages_dyn", INGESTEUR_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hash_page(chemin):
    # Meme methode qu'ingerer-passages.py : octets bruts du fichier,
    # jamais un texte deja decode -- un ecart de methode entre les deux
    # scripts romprait toute comparaison de hash.
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def lire_registre_et_hashs_locaux():
    if not FILMS_DATA.exists():
        echec("registre introuvable : " + str(FILMS_DATA))
    ingesteur = charger_ingesteur()
    contenu = FILMS_DATA.read_text(encoding="utf-8")
    films = ingesteur.extraire_objets_films(contenu)
    if not films:
        echec("aucun film extrait du registre local")
    hashs = {}
    for film in films:
        chemin = FILMS_DIR / (film["slug"] + ".html")
        if not chemin.exists():
            echec("page manquante pour le slug '" + film["slug"] + "' : " + str(chemin))
        hashs[film["slug"]] = hash_page(chemin)
    return ingesteur, films, hashs


def extraire_passages_page(ingesteur, film, page_hash):
    # Reproduit le corps de la boucle par page d'ingerer-passages.py
    # pour UN seul slug (memes fonctions, meme ordre, meme motif
    # d'exclusion) -- utilise pour NOUVELLES et MODIFIEES.
    slug = film["slug"]
    chemin = FILMS_DIR / (slug + ".html")
    texte = chemin.read_text(encoding="utf-8")
    preambule, sections = ingesteur.decouper_page(texte)
    if sections is None:
        raise RuntimeError("balise <main> introuvable : " + str(chemin))
    url_absolue = URL_PREFIX + "films/" + slug + ".html"
    lignes = []
    ordre = 0
    if preambule:
        lignes.append({
            "slug": slug, "titre": film["title"], "realisateur": film["director"],
            "annee": (int(film["year"]) if str(film["year"]).strip() else None),
            "url": url_absolue, "section": "Ouverture", "ordre": ordre,
            "texte": preambule, "page_hash": page_hash,
        })
        ordre += 1
    for titre, corps_brut in sections:
        corps = ingesteur.normaliser(corps_brut)
        if ingesteur.MOTIF_EXCLUSION.match(titre):
            continue
        if not corps:
            continue
        if len(corps) > ingesteur.SEUIL_LONGUEUR:
            sous_sections = ingesteur.decouper_par_h3(titre, corps_brut)
            if sous_sections is None:
                raise RuntimeError("section > seuil sans <h3> interne : " + slug + " / " + titre)
            for sous_titre, sous_corps in sous_sections:
                lignes.append({
                    "slug": slug, "titre": film["title"], "realisateur": film["director"],
                    "annee": (int(film["year"]) if str(film["year"]).strip() else None),
                    "url": url_absolue, "section": sous_titre, "ordre": ordre,
                    "texte": sous_corps, "page_hash": page_hash,
                })
                ordre += 1
            continue
        lignes.append({
            "slug": slug, "titre": film["title"], "realisateur": film["director"],
            "annee": (int(film["year"]) if str(film["year"]).strip() else None),
            "url": url_absolue, "section": titre, "ordre": ordre,
            "texte": corps, "page_hash": page_hash,
        })
        ordre += 1
    return lignes


def lire_table_supabase(supabase_url, cle_lecture):
    url = supabase_url.rstrip("/") + "/rest/v1/passages?select=slug,page_hash"
    req = urllib.request.Request(
        url,
        headers={"apikey": cle_lecture, "Authorization": "Bearer " + cle_lecture},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=DELAI_S) as rep:
            lignes = json.loads(rep.read().decode("utf-8"))
    except urllib.error.URLError as e:
        echec("lecture de la table passages impossible : " + str(e))
    table = {}
    for ligne in lignes:
        table[ligne["slug"]] = ligne.get("page_hash")
    return table


def calculer_diff(hashs_registre, hashs_table):
    slugs_registre = set(hashs_registre)
    slugs_table = set(hashs_table)
    nouvelles = sorted(slugs_registre - slugs_table)
    disparues = sorted(slugs_table - slugs_registre)
    communes = slugs_registre & slugs_table
    modifiees = sorted(s for s in communes if hashs_table[s] != hashs_registre[s])
    inchangees = sorted(s for s in communes if hashs_table[s] == hashs_registre[s])
    return nouvelles, modifiees, disparues, inchangees


def supprimer_slug(supabase_url, cle_service, slug):
    url = supabase_url.rstrip("/") + "/rest/v1/passages?slug=eq." + urllib.parse.quote(slug, safe="")
    req = urllib.request.Request(
        url,
        headers={
            "apikey": cle_service,
            "Authorization": "Bearer " + cle_service,
            "Prefer": "return=minimal",
        },
        method="DELETE",
    )
    with urllib.request.urlopen(req, timeout=DELAI_S) as rep:
        rep.read()


def inserer_lignes(supabase_url, cle_service, lignes):
    if not lignes:
        return
    req = urllib.request.Request(
        supabase_url.rstrip("/") + "/rest/v1/passages",
        data=json.dumps(lignes).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "apikey": cle_service,
            "Authorization": "Bearer " + cle_service,
            "Prefer": "return=minimal",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as rep:
        rep.read()


def main():
    mode_appliquer = "--appliquer" in sys.argv

    supabase_url = os.environ.get("SUPABASE_URL")
    if not supabase_url:
        echec("variable d'environnement SUPABASE_URL absente")

    if mode_appliquer:
        cle_service = os.environ.get("SUPABASE_SERVICE_KEY")
        if not cle_service:
            echec("--appliquer exige SUPABASE_SERVICE_KEY (variable d'environnement du poste, jamais en session)")
        cle_lecture = cle_service
    else:
        cle_lecture = os.environ.get("SUPABASE_ANON_KEY")
        if not cle_lecture:
            echec("variable d'environnement SUPABASE_ANON_KEY absente (lecture publique, mode --simuler)")

    ingesteur, films, hashs_registre = lire_registre_et_hashs_locaux()
    print("registre local : " + str(len(films)) + " films (" + str(FILMS_DATA) + ", lecture LOCALE)")

    hashs_table = lire_table_supabase(supabase_url, cle_lecture)
    print("table passages : " + str(len(hashs_table)) + " slugs distincts en base")

    nouvelles, modifiees, disparues, inchangees = calculer_diff(hashs_registre, hashs_table)

    print("")
    print(str(len(nouvelles)) + " nouvelle" + ("" if len(nouvelles) == 1 else "s") +
          " / " + str(len(modifiees)) + " modifiee" + ("" if len(modifiees) == 1 else "s") +
          " / " + str(len(disparues)) + " disparue" + ("" if len(disparues) == 1 else "s") +
          " / " + str(len(inchangees)) + " inchangee" + ("" if len(inchangees) == 1 else "s"))
    for s in nouvelles:
        print("  + nouvelle  : " + s)
    for s in modifiees:
        print("  ~ modifiee  : " + s)
    for s in disparues:
        print("  - disparue  : " + s)

    if not nouvelles and not modifiees and not disparues:
        print("")
        print("rien a faire (idempotence) -- table a jour")
        return

    if not mode_appliquer:
        print("")
        print("mode --simuler (par defaut) : aucune ecriture. Rejoue avec --appliquer pour executer ce diff.")
        return

    films_par_slug = {f["slug"]: f for f in films}

    for s in disparues:
        reponse = input("Supprimer definitivement les passages du slug disparu '" + s + "' ? [o/N] ")
        if reponse.strip().lower() != "o":
            print("  -> conserve (non confirme) : " + s)
            continue
        supprimer_slug(supabase_url, cle_service, s)
        print("  -> supprime : " + s)

    for s in modifiees:
        supprimer_slug(supabase_url, cle_service, s)
        lignes = extraire_passages_page(ingesteur, films_par_slug[s], hashs_registre[s])
        inserer_lignes(supabase_url, cle_service, lignes)
        print("  -> remplace (" + str(len(lignes)) + " passages) : " + s)

    for s in nouvelles:
        lignes = extraire_passages_page(ingesteur, films_par_slug[s], hashs_registre[s])
        inserer_lignes(supabase_url, cle_service, lignes)
        print("  -> insere (" + str(len(lignes)) + " passages) : " + s)

    print("")
    print("applique.")


if __name__ == "__main__":
    main()
