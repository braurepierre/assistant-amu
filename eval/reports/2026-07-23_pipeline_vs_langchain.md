# Rapport — pipeline manuel vs port LangChain — 2026-07-23

- Backend LLM (les deux pipelines) : `mistral/mistral-small-latest` (température 0.2) | Embeddeur : `intfloat/multilingual-e5-small` | k = 5
- Même collection ChromaDB, même prompt système → la comparaison isole *le câblage*.
- 20 questions. **Parité de refus** : 19/20. **Parité de citations [S…]** : 15/20. **Recouvrement lexical moyen** : 0.75.

## Synthèse

- La chaîne LCEL renvoie une **chaîne de caractères** ; le pipeline manuel renvoie un `RagResult` structuré (`answer` + `sources` + `model` + `retrieved_chunks`).
- Détection de refus, mise à zéro des sources sur refus, mapping erreur backend → 503 : **hors** de la chaîne — c'est du code produit que LangChain n'abstrait pas.
- Un recouvrement < 1.0 est attendu : même contexte et même prompt, mais deux formulations d'un modèle non déterministe. Le signal fiable d'équivalence est la **parité de refus** et la **parité de citations**, pas l'égalité mot-à-mot.

## Détail par question

| id | ans. | refus main/lc | cites main/lc | recouvr. | réponse manuelle | réponse LangChain |
|---|---|---|---|---|---|---|
| q01 | o | non/non ✅ | 3/3 | 0.64 | Pour demander une césure à AMU, suivez ces étapes selon votre profil :  1. **Vérifiez vot… | Pour demander une césure à AMU, suivez ces étapes :  1. **Vérifiez votre éligibilité** : … |
| q02 | o | oui/oui ✅ | 0/0 | 1.00 | Je ne trouve pas cette information dans les documents disponibles. | Je ne trouve pas cette information dans les documents disponibles. |
| q03 | o | non/non ✅ | 3/1 | 0.64 | Les aménagements pour un étudiant salarié ou sportif de haut niveau à Aix-Marseille Unive… | Les aménagements pour un étudiant salarié ou sportif de haut niveau à Aix-Marseille Unive… |
| q04 | o | non/non ✅ | 1/1 | 0.67 | Vous pouvez vous loger dans les résidences des Crous, prioritairement attribuées aux étud… | Vous pouvez vous loger dans les résidences des Crous, prioritairement attribuées aux étud… |
| q05 | o | non/non ✅ | 1/2 | 0.46 | Les aménagements pour un étudiant en situation de handicap à Aix-Marseille Université inc… | Les aménagements pour un étudiant en situation de handicap incluent : - Prise de note et … |
| q06 | o | non/non ✅ | 1/1 | 0.83 | Les établissements étudiants proposent souvent des emplois étudiants compatibles avec les… | Les établissements étudiants proposent souvent des emplois étudiants compatibles avec les… |
| q07 | o | non/non ✅ | 0/0 | 0.78 | Pour obtenir un duplicata de votre diplôme à l'IUT, vous devez fournir : - un document pr… | Pour obtenir un duplicata de votre diplôme à l'IUT, vous devez fournir : - un document pr… |
| q08 | o | non/non ✅ | 3/3 | 0.80 | Le Régime Spécial d’Études (RSE) permet aux étudiants ayant des besoins spécifiques de co… | Le Régime Spécial d’Études (RSE) permet aux étudiants ayant des besoins spécifiques de co… |
| q09 | o | non/non ✅ | 2/2 | 0.85 | La CVEC (Contribution de Vie Étudiante et de Campus) est une taxe affectée destinée à fin… | La CVEC (Contribution de Vie Étudiante et de Campus) est une taxe affectée destinée à fin… |
| q10 | o | non/non ✅ | 0/2 | 0.69 | Les modalités de contrôle des connaissances (M3C) en ALLSH s’organisent selon trois nivea… | Les modalités de contrôle des connaissances (M3C) en ALLSH s’organisent selon trois nivea… |
| q11 | o | non/non ✅ | 1/1 | 0.70 | La compensation des notes en licence fonctionne comme suit :  - Les UE se compensent entr… | La compensation des notes en licence fonctionne comme suit :  - **Au sein d'une année** :… |
| q12 | o | non/non ✅ | 1/1 | 1.00 | Le sigle BCC signifie **Bloc de Connaissances et Compétences** [S2]. | Le sigle **BCC** signifie **Bloc de Connaissances et Compétences** [S2]. |
| q13 | o | non/non ✅ | 2/2 | 0.61 | Pour une première inscription administrative en ligne (IA web) :  1. **Connexion** :    -… | Pour une première inscription administrative en ligne (IA web) : - Utilisez comme identif… |
| q14 | o | non/non ✅ | 1/2 | 0.65 | La charte des examens d'Aix-Marseille Université : - Réglemente les délais de convocation… | La charte des examens d'Aix-Marseille Université régit les droits et obligations des étud… |
| q15 | o | non/non ✅ | 3/3 | 0.66 | Les droits et devoirs figurant dans la charte des étudiants d'AMU sont les suivants :  **… | Les droits et devoirs figurant dans la charte des étudiants d'AMU sont les suivants :  **… |
| q16 | o | non/oui ⚠️ | 1/0 | 0.04 | Pour consulter le calendrier universitaire de la faculté des sciences, vous pouvez vous r… | Je ne trouve pas cette information dans les documents disponibles. |
| q17 | n | oui/oui ✅ | 0/0 | 1.00 | Je ne trouve pas cette information dans les documents disponibles. | Je ne trouve pas cette information dans les documents disponibles. |
| q18 | n | oui/oui ✅ | 0/0 | 1.00 | Je ne trouve pas cette information dans les documents disponibles. | Je ne trouve pas cette information dans les documents disponibles. |
| q19 | n | oui/oui ✅ | 0/0 | 1.00 | Je ne trouve pas cette information dans les documents disponibles. | Je ne trouve pas cette information dans les documents disponibles. |
| q20 | n | oui/oui ✅ | 0/0 | 1.00 | Je ne trouve pas cette information dans les documents disponibles. | Je ne trouve pas cette information dans les documents disponibles. |

## Divergences de refus (à regarder)

| id | question | main | lc |
|---|---|---|---|
| q16 | Où consulter le calendrier universitaire de la fa… | répond | refus |

