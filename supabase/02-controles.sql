-- 02-controles.sql
-- Rejoue sur la table chargee les controles mesures par
-- outils/ingerer-passages.py. Forme consolidee (UN seul tableau,
-- union all) -- lecon FOR-003 : le SQL Editor de Supabase n'affiche
-- que le resultat de la DERNIERE requete d'un script.
--
-- Attendus figes au run d'ingestion du 2026-08-25 (voir
-- NOTE-DE-REMISE-EXECUTION) : 462 passages, 46 slugs distincts,
-- 0 section bibliographique residuelle, 0 question au demarrage.
-- Si le corpus a bouge depuis (nouvelle analyse publiee), l'attendu
-- 'passages' et 'slugs' ne tient plus tel quel -- compare au chiffre 5
-- de la note de remise correspondant a TON run d'ingestion, pas a
-- celui-ci.
--
-- ERRATUM 2026-08-26 (BKL-FOR-005 (b) v2, L2) : la ligne 5 comptait des
-- LIGNES retournees par rechercher_passages (plusieurs passages peuvent
-- venir d'un meme film) sous un libelle "slugs distincts" -- le controle
-- etait mal ecrit, pas les donnees : les 3 lignes mesurees le 26/08
-- etaient bien toutes dans les 2 slugs attendus. Corrige en
-- count(distinct slug). Attendu inchange (2).
--
-- Ligne 8 AJOUTEE (D-7, patron serverless v1.1) : detecteur de derive
-- entre la table chargee et le registre public -- dit QUAND rafraichir
-- (outils\rafraichir-passages.py, L6). Attendu '46' fige au 26/08 ; a
-- RE-MESURER sur le registre publie au moment ou tu joues ce controle
-- (https://www.cdatso.be/analyses-de-films/assets/films-data.js) --
-- un ecart n'est pas une erreur du controle, c'est le signal qu'il porte.

select 1 as ordre, 'nb_passages' as controle,
       count(*)::text as mesure, '462' as attendu
from public.passages
union all
select 2, 'slugs distincts', count(distinct slug)::text, '46'
from public.passages
union all
select 3, 'sections bibliographiques residuelles', count(*)::text, '0'
from public.passages
where section ~* (U&'^(sources?|bibliographie|r[\00e9\00e8]f[\00e9\00e8]rences?|registre des|colophon|journal de bord|note de remise)')
union all
select 4, 'recherche "guerre froide" (lignes)', count(*)::text, '>= 1'
from public.rechercher_passages('guerre froide', 6)
union all
select 5, 'recherche "guerre froide" (slugs distincts attendus)',
       count(distinct slug) filter (where slug in ('shutter-island', 'waterloo'))::text,
       '2'
from public.rechercher_passages('guerre froide', 6)
union all
select 6, 'recherche "guerre d''Algerie" (lignes)', count(*)::text, '0'
from public.rechercher_passages('guerre d''Algerie', 6)
union all
select 7, 'questions (avant tout usage)', count(*)::text, '0'
from public.questions
union all
select 8, 'slugs distincts en table = slugs du registre publie (D-7)',
       count(distinct slug)::text, '46'
from public.passages
order by ordre;
