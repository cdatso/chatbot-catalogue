#!/usr/bin/env python3
# ingerer-passages.py
# BKL-FOR-005 (a) -- ingestion des pages d'analyses en passages.
# Stdlib seul (re, html, csv, hashlib, pathlib, sys). Fail-closed :
# chaque controle est imprime puis le script s'arrete (exit != 0) au
# premier echec. Un chiffre imprime est toujours mesure sur ce run,
# jamais recopie d'un mandat.
#
# Fragilite declaree (audit DL) : l'extraction des champs slug / title /
# director / year depuis assets/films-data.js se fait par un parseur a
# motif sur des blocs d'objets repere's par profondeur d'accolades (pas
# un vrai parseur JS) -- fonctionne pour la forme actuelle du fichier,
# fragile a une evolution de syntaxe. Le controle immediat qui suit
# (nombre d'objets = nombre de lignes "slug:") sert de garde-fou.
#
# Portee du decoupage par <h2> -- ARBITRAGE AH (elicitation en session,
# 2026-08-25) : le preambule "Ouverture" (ordre 0) ne capte que le texte
# entre la balise <main> et le premier <h2>, PAS le header/nav/hero du
# gabarit de site (identiques sur les 46 pages). Les <h2> eux-memes sont
# en revanche recherches sur le fichier ENTIER : certaines pages portent
# leurs sections bibliographiques APRES la fermeture de </main> (cas
# mesure : the-sweet-east.html) -- il faut les trouver pour les exclure.
#
# Passage > 8000 caracteres -- ARBITRAGE AH (elicitation en session,
# 2026-08-25, cas mandat 5.8-iii, specimen mesure : voyage-en-italie /
# "Themes" = 8190 caracteres) : une section qui depasse 8000 caracteres
# APRES normalisation est re-decoupee sur ses <h3> internes quand elle
# en contient (titre du sous-passage = "<section> -- <h3>"). Une section
# qui depasserait 8000 caracteres SANS <h3> interne n'est pas couverte
# par cet arbitrage -- le script s'arrete alors fail-closed (nouveau cas
# a eliciter, non rencontre sur ce run).
#
# COLONNE page_hash (BKL-FOR-005 (b) v2, L6, spec
# NOTE-SPEC-REFRESH-PASSAGES-2026-08-25.md) : SHA-256 des octets bruts
# du fichier films/<slug>.html source, IDENTIQUE pour tous les passages
# d'une meme page -- calcule UNE fois par film, jamais recalcule a
# partir du texte deja decode (meme methode que outils/rafraichir-
# passages.py : hash_page() y lit aussi read_bytes(), jamais read_text() --
# un ecart de methode entre les deux scripts romprait la comparaison de
# hash au premier refresh).

import re
import csv
import html
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_ROOT = Path(r"C:\Users\cdats\Claude\CIN\analyses-de-films")
FILMS_DATA = SITE_ROOT / "assets" / "films-data.js"
FILMS_DIR = SITE_ROOT / "films"
OUT_PASSAGES = REPO_ROOT / "donnees" / "passages.csv"
OUT_EXCLUSIONS = REPO_ROOT / "donnees" / "exclusions.csv"

URL_PREFIX = "https://www.cdatso.be/analyses-de-films/"

MOTIF_EXCLUSION = re.compile(
    "(?i)^(sources?|bibliographie|r[\u00e9\u00e8]f[\u00e9\u00e8]rences?"
    "|registre des|colophon|journal de bord|note de remise)"
)

TAG_RE = re.compile(r"<[^>]+>")
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.I | re.S)
H3_RE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.I | re.S)
MAIN_OPEN_RE = re.compile(r"<main[^>]*>", re.I)
SEUIL_LONGUEUR = 8000
SLUG_FIELD_RE = re.compile(r"slug:\s*['\"]([^'\"]+)['\"]")
TITLE_FIELD_RE = re.compile(r"title:\s*['\"]([^'\"]+)['\"]")
DIRECTOR_FIELD_RE = re.compile(r"director:\s*['\"]([^'\"]+)['\"]")
YEAR_FIELD_RE = re.compile(r"year:\s*(\d+)")


def echec(message):
    print("ECHEC -- " + message)
    sys.exit(1)


def normaliser(segment_html):
    sans_tags = TAG_RE.sub(" ", segment_html)
    decode = html.unescape(sans_tags)
    return re.sub(r"\s+", " ", decode).strip()


def extraire_objets_films(texte):
    # Decoupe des blocs d'objets top-level du tableau FILMS par profondeur
    # d'accolades -- robuste aux champs imbriques (ex. deleuze: {...}).
    blocs = []
    depth = 0
    start = None
    for i, c in enumerate(texte):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start is not None:
                blocs.append(texte[start:i + 1])
                start = None
    films = []
    for bloc in blocs:
        m_slug = SLUG_FIELD_RE.search(bloc)
        if not m_slug:
            continue
        m_title = TITLE_FIELD_RE.search(bloc)
        m_dir = DIRECTOR_FIELD_RE.search(bloc)
        m_year = YEAR_FIELD_RE.search(bloc)
        films.append({
            "slug": m_slug.group(1),
            "title": m_title.group(1) if m_title else "",
            "director": m_dir.group(1) if m_dir else "",
            "year": m_year.group(1) if m_year else "",
        })
    return films


def decouper_page(texte):
    # Retourne (preambule_ou_None, [(titre, corps_brut_html), ...]) dans
    # l'ordre du document. preambule scope <main> -> premier <h2>
    # (arbitrage AH). corps_brut_html n'est PAS encore normalise : le
    # decoupage <h3> eventuel (cas > 8000) a besoin du HTML brut.
    h2s = list(H2_RE.finditer(texte))
    m_main = MAIN_OPEN_RE.search(texte)
    if not m_main:
        return None, None
    main_start = m_main.end()
    preambule = None
    if h2s and h2s[0].start() > main_start:
        brut = texte[main_start:h2s[0].start()]
        val = normaliser(brut)
        if val:
            preambule = val
    sections = []
    for i, m in enumerate(h2s):
        titre = normaliser(m.group(1))
        fin_titre = m.end()
        debut_suivant = h2s[i + 1].start() if i + 1 < len(h2s) else len(texte)
        corps_brut = texte[fin_titre:debut_suivant]
        sections.append((titre, corps_brut))
    return preambule, sections


def decouper_par_h3(titre_section, corps_brut_html):
    # Re-decoupe une section trop longue sur ses <h3> internes. Retourne
    # None si aucun <h3> (cas non couvert par l'arbitrage AH).
    h3s = list(H3_RE.finditer(corps_brut_html))
    if not h3s:
        return None
    tiret = chr(0x2014)
    resultat = []
    intro = normaliser(corps_brut_html[:h3s[0].start()])
    if intro:
        resultat.append((titre_section, intro))
    for i, m in enumerate(h3s):
        sous_titre = normaliser(m.group(1))
        debut = m.end()
        fin = h3s[i + 1].start() if i + 1 < len(h3s) else len(corps_brut_html)
        sous_corps = normaliser(corps_brut_html[debut:fin])
        if sous_corps:
            resultat.append((titre_section + " " + tiret + " " + sous_titre, sous_corps))
    return resultat


def main():
    if not FILMS_DATA.exists():
        echec("registre introuvable : " + str(FILMS_DATA))
    contenu_registre = FILMS_DATA.read_text(encoding="utf-8")
    nb_lignes_slug = len(re.findall(r"slug:", contenu_registre))
    films = extraire_objets_films(contenu_registre)
    print("registre : lignes 'slug:' mesurees = " + str(nb_lignes_slug))
    print("registre : objets extraits = " + str(len(films)))
    if len(films) != nb_lignes_slug:
        echec("nombre d'objets extraits (" + str(len(films)) +
              ") != nombre de lignes slug: (" + str(nb_lignes_slug) + ")")

    lignes_passages = []
    lignes_exclusions = []
    pages_zero_exclusion = []
    sections_scindees = []
    total_h2_par_page = {}

    for film in films:
        slug = film["slug"]
        chemin = FILMS_DIR / (slug + ".html")
        if not chemin.exists():
            echec("page manquante pour le slug '" + slug + "' : " + str(chemin))
        page_hash = hashlib.sha256(chemin.read_bytes()).hexdigest()
        texte = chemin.read_text(encoding="utf-8")
        preambule, sections = decouper_page(texte)
        if sections is None:
            echec("balise <main> introuvable dans " + str(chemin))

        url_absolue = URL_PREFIX + "films/" + slug + ".html"
        ordre = 0
        nb_exclusions_page = 0

        if preambule:
            lignes_passages.append([
                slug, film["title"], film["director"], film["year"],
                url_absolue, "Ouverture", str(ordre), preambule, page_hash,
            ])
            ordre += 1

        for titre, corps_brut in sections:
            corps = normaliser(corps_brut)
            if MOTIF_EXCLUSION.match(titre):
                nb_exclusions_page += 1
                lignes_exclusions.append([slug, titre, str(len(corps))])
                continue
            if not corps:
                continue
            if len(corps) > SEUIL_LONGUEUR:
                sous_sections = decouper_par_h3(titre, corps_brut)
                if sous_sections is None:
                    echec("section > " + str(SEUIL_LONGUEUR) +
                          " caracteres sans <h3> interne (non couvert par "
                          "l'arbitrage AH du 2026-08-25) : " + slug + " / " + titre)
                sections_scindees.append(slug + " / " + titre + " (" + str(len(corps)) + " car.)")
                for sous_titre, sous_corps in sous_sections:
                    lignes_passages.append([
                        slug, film["title"], film["director"], film["year"],
                        url_absolue, sous_titre, str(ordre), sous_corps, page_hash,
                    ])
                    ordre += 1
                continue
            lignes_passages.append([
                slug, film["title"], film["director"], film["year"],
                url_absolue, titre, str(ordre), corps, page_hash,
            ])
            ordre += 1

        total_h2_par_page[slug] = ordre
        if nb_exclusions_page == 0:
            pages_zero_exclusion.append(slug)

    # ----- ecriture passages.csv (UTF-8 sans BOM, RFC4180, \n) -----
    OUT_PASSAGES.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PASSAGES, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writerow(["slug", "titre", "realisateur", "annee", "url", "section", "ordre", "texte", "page_hash"])
        for row in lignes_passages:
            w.writerow(row)

    with open(OUT_EXCLUSIONS, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writerow(["slug", "section", "longueur"])
        for row in lignes_exclusions:
            w.writerow(row)

    # ----- controles fail-closed (imprimes puis stop au premier echec) -----
    print("")
    print("=== controles ===")

    # 1. pages traitees = compte du registre
    print("1. pages traitees = " + str(len(films)) + " (registre = " + str(nb_lignes_slug) + ")")
    if len(films) != nb_lignes_slug:
        echec("controle 1 : pages traitees != compte du registre")

    # 2. 0 annexe
    slugs_traites = set(f["slug"] for f in films)
    annexe_presente = "the-sweet-east-annexe" in slugs_traites
    print("2. annexe traitee = " + str(int(annexe_presente)) + " (attendu 0)")
    if annexe_presente:
        echec("controle 2 : l'annexe a ete traitee")

    # 3. passages > 0 par page
    pages_sans_passage = [s for s in slugs_traites if total_h2_par_page.get(s, 0) == 0]
    print("3. pages sans passage = " + str(len(pages_sans_passage)))
    if pages_sans_passage:
        echec("controle 3 : pages sans aucun passage : " + ", ".join(pages_sans_passage))

    # 4. zero '<' dans les textes
    nb_chevrons = sum(row[7].count("<") for row in lignes_passages)
    nb_chevrons += sum(row[1].count("<") for row in lignes_exclusions)
    print("4. chevrons '<' residuels = " + str(nb_chevrons))
    if nb_chevrons != 0:
        echec("controle 4 : des chevrons '<' subsistent dans le texte extrait")

    # 5. total passages (mesure)
    print("5. total passages = " + str(len(lignes_passages)))

    # 6. longueur max d'un texte
    longueur_max = max((len(row[7]) for row in lignes_passages), default=0)
    print("6. longueur max d'un texte = " + str(longueur_max) + " caracteres")
    print("   sections scindees par <h3> (> " + str(SEUIL_LONGUEUR) + " car. avant scission) = " +
          str(len(sections_scindees)))
    for s in sections_scindees:
        print("     -> " + s)

    # 7. url sous le prefixe
    hors_prefixe = [row for row in lignes_passages if not row[4].startswith(URL_PREFIX + "films/")]
    print("7. urls hors prefixe = " + str(len(hors_prefixe)))
    if hors_prefixe:
        echec("controle 7 : url(s) hors prefixe attendu")

    # 8. sha-256 du csv
    sha = hashlib.sha256(OUT_PASSAGES.read_bytes()).hexdigest()
    print("8. sha-256 passages.csv = " + sha)

    print("")
    print("exclusions totales = " + str(len(lignes_exclusions)))
    print("pages a 0 exclusion (signale, non bloquant) = " + str(len(pages_zero_exclusion)))
    if pages_zero_exclusion:
        print("  -> " + ", ".join(pages_zero_exclusion))

    print("")
    print("passages.csv : " + str(OUT_PASSAGES))
    print("exclusions.csv : " + str(OUT_EXCLUSIONS))


if __name__ == "__main__":
    main()
