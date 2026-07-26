# Rejugement à l'aveugle et ancrage instrumenté — 2026-07-27

Deux angles morts restaient après la vérification des verdicts du même jour :
la colonne assistant-amu n'avait jamais été confrontée aux **documents sources**,
et les juges d'origine **nommaient les deux systèmes** dans leurs notes. Les deux
sont traités ici, ensemble, parce que le second a besoin du premier : sans les
passages, un juge ne peut évaluer l'ancrage des deux côtés avec le même
instrument.

## Ce qui a été fait

**1. Récupération des passages (`eval/serialize_retrieved_sources.py`).**
`assistant_amu_full_answers.json` ne conservait qu'un compteur (`n_sources: 5`)
là où le côté AnythingLLM conservait le texte intégral des passages récupérés.
L'ancrage d'assistant-amu ne pouvait donc pas être vérifié — il était inféré des
marqueurs `[S1]`. Sans historique et avec `rewrite="raw"`, la requête de
recherche est la question verbatim (`rag.py:154-158`) : rejouer `store.query()`
reproduit exactement les fragments sur lesquels les réponses stockées ont été
construites. **Aucun appel de modèle, aucune réponse régénérée** — les verdicts
existants restent comparables. Contrôle : sur six questions témoins, les chaînes
distinctives des réponses stockées (« eCandidat », « attestation sur l'honneur »,
« BCC jumeaux », « sesame.univ-amu.fr ») se retrouvent toutes dans les passages
récupérés.

**2. Rejugement à l'aveugle (`eval/blind_rejudge_bundle.py`, `…_prompts.py`).**
Les seize questions répondables ont été réparties entre huit juges indépendants,
deux chacun — le dispositif du 26 juillet. Chaque juge a reçu un dossier
autonome, dans un répertoire distinct de la clé, contenant la question, les deux
réponses en « Système A » et « Système B » (affectation par tirage à graine
fixe), et **les passages fournis à chaque système**. Barème explicite en cinq
catégories, dont une catégorie `refused` distincte de `incorrect` — la confusion
même qui avait produit l'erreur sur q01.

## Résultats

| Verdict (AnythingLLM) | rapport 26/07 | vérification 27/07 | **jury aveugle** |
| :--- | :---: | :---: | :---: |
| `correct_grounded` | 0/16 | 0/16 | **0/16** |
| `partially_grounded` | 4/16 | 5/16 | **4/16** |
| non ancrée mais plausible | 9/16 | 8/16 | **9/16** |
| `incorrect` | 3/16 | 2/16 | **2/16** |
| `refused` | 0/16 | 1/16 | **1/16** |

| Verdict (assistant-amu) | rapport 26/07 | **jury aveugle** |
| :--- | :---: | :---: |
| `correct_grounded` | 14/16 | **14/16** |
| `refused` sur question répondable | 2/16 | **2/16** |

**Accord global : 12/16 pour AnythingLLM, 16/16 pour assistant-amu.**

## Ce que ça établit

**La colonne assistant-amu tient, et elle est désormais instrumentée.** Les
quatorze réponses jugées correctes le sont toujours, cette fois par des juges
disposant des passages effectivement lus par le pipeline. Le 14/16 n'est plus
inféré de la présence de marqueurs `[S1]` : il est vérifié. C'est le chiffre qui
n'avait jamais été instruit, et il ne bouge pas.

**Le biais du jury d'origine est confirmé, et borné.** Quatre verdicts diffèrent.
Trois vont dans le sens d'une sévérité excessive envers AnythingLLM — q01
(`incorrect` → `refused`), q03 (`hallucinated` → `partially_grounded`), q11
(`incorrect` → non ancrée). **Un va dans l'autre sens** : q14, que le jury
d'origine classait `partially_grounded` et que le juge aveugle classe
`incorrect`, ayant relevé que le délai de 15 jours porte sur la convocation et
non sur la publication des sujets. Le déséquilibre est donc réel (3 contre 1)
mais pas systématique.

**La correction sur q01 est confirmée par une voie indépendante.** Le juge
aveugle classe la réponse `refused` et ajoute, sans connaître le dossier, que le
refus était *correctement motivé* : ses passages ne contenaient effectivement
rien sur la césure. C'est plus favorable encore que ma propre correction.

**Le refus q02 d'assistant-amu est aggravé.** Le juge relève que ses propres
passages répondaient explicitement (« souhaitez suspendre vos études pour un ou
deux semestres… La césure est faite pour vous ! »). Ce n'est pas un refus par
prudence sur une question limite : c'est un refus sur une question à laquelle le
contexte fourni répondait.

## Ce que ça réfute — y compris dans la vérification du matin

Deux conclusions de `2026-07-27_anythingllm_verdicts_verification.md` ne
survivent pas au rejugement.

1. **q15 était bien `ungrounded`.** J'avais proposé de la reclasser en
   `partially_grounded` au motif qu'AnythingLLM citait la charte des étudiants et
   en reprenait de la matière réelle. Le juge aveugle, qui a lu les **passages**
   et non les titres, constate qu'ils portent sur le déroulement des examens, la
   charte du doctorat et le plagiat — et qu'aucun ne soutient la section
   « Droits » de la réponse. Le verdict d'origine était juste, ma correction
   était fausse.

2. **q11 ne démontre pas un troisième mode d'échec.** J'avais écrit que le bon
   PDF avait été récupéré et que la réponse le contredisait, concluant que les
   deux causes structurelles du rapport ne couvraient pas tout. Le juge aveugle
   montre que les passages effectivement remontés de ce PDF ne contenaient que la
   structure (BCC, UE, ECTS) et une mention de bonus — **pas la règle de
   compensation**. Le bon document, mais pas le bon fragment : c'est un défaut de
   recherche, pas le mode d'échec inédit que j'annonçais. La réponse reste
   factuellement fausse sur la règle réelle d'AMU ; ce qu'elle ne prouve pas,
   c'est ma conclusion sur les causes.

**Les deux erreurs ont la même origine.** J'ai jugé la qualité de la recherche
d'AnythingLLM sur les **titres** des documents remontés, sans ouvrir le texte des
passages, alors que ce texte était disponible dans le fichier. C'est exactement
le raccourci que je reprochais au rapport du 26 juillet, qui inférait l'ancrage
d'assistant-amu de ses marqueurs `[S1]` sans ouvrir les fragments. Même erreur, un
étage plus haut.

## Un défaut de l'anonymisation, à connaître avant de lire q16

Pour empêcher l'identification des systèmes, les **titres et URL de source ont
été retirés** des passages : les deux systèmes nomment leurs documents
différemment (intitulés propres d'un côté, noms de fichiers téléversés de
l'autre), ce qui aurait trahi l'identité.

Or le pipeline d'assistant-amu **fournit ces titres au modèle** en production
(`rag.py:83-87`, attributs `titre=` et `page=` des balises `<source>`). Les juges
ont donc évalué assistant-amu sur moins de matière qu'il n'en avait réellement.
L'effet est nul pour les questions de contenu, mais réel pour q16 (« où consulter
le calendrier ? ») : le juge conclut `answer_was_available: false` parce que les
passages anonymisés ne portaient plus d'adresse, alors que le système, lui, avait
le titre « Sciences — Calendriers universitaires de la Faculté ». **Le refus q16
reste un vrai refus à tort** — la page attendue était bien dans le top-5, ce que
la récupération des passages établit — mais le `answer_was_available: false` de
ce verdict n'est pas fiable.

## Ce que ça ne couvre toujours pas

- Les réponses restent **verbatim**, donc distinguables l'une de l'autre par leur
  mise en forme (marqueurs `[S1]` d'un côté, titres markdown et note de source
  finale de l'autre). Un juge ignorant ce dépôt ne peut rattacher aucun de ces
  styles à un produit donné, mais l'anonymat n'est pas parfait pour autant.
- Chaque question reste jugée **une seule fois** : aucun accord inter-juges n'est
  mesurable, ni sur cette série ni sur la précédente.
- La performance d'AnythingLLM **correctement configuré** demeure le principal
  angle mort, inchangé.
