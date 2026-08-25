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
select 5, 'recherche "guerre froide" (slugs attendus)',
       count(*) filter (where slug in ('shutter-island', 'waterloo'))::text,
       '2'
from public.rechercher_passages('guerre froide', 6)
union all
select 6, 'recherche "guerre d''Algerie" (lignes)', count(*)::text, '0'
from public.rechercher_passages('guerre d''Algerie', 6)
union all
select 7, 'questions (avant tout usage)', count(*)::text, '0'
from public.questions
order by ordre;
