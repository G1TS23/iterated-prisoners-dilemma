# Le dilemme du prisonnier itératif - M2 DEV

Générer, transformer et comprendre la coopération

Source : Notion (GL Conseil), copié le 2026-09-11.

## Préambule

Pour comprendre le contexte complet de ce sujet, il est conseillé de regarder cette vidéo (9min) :
https://www.youtube.com/watch?v=G9ER5bLxQEU

## Contexte

En 1981, le politologue Robert Axelrod organisa une expérience restée célèbre : un tournoi
informatique où s'affrontaient des programmes incarnant différentes stratégies de comportement
dans une situation appelée le dilemme du prisonnier itératif.

Cette situation modélise une tension universelle : faut-il coopérer avec l'autre au risque
d'être trahi, ou trahir pour éviter d'être exploité ?

L'expérience d'Axelrod révéla un résultat inattendu : la stratégie la plus simple et la plus
coopérative, Tit for Tat (donnant-donnant), surclassa toutes les autres. Elle montrait qu'à
long terme, la coopération pouvait émerger spontanément dans un environnement d'agents égoïstes.

Quarante ans plus tard, vous allez rejouer cette expérience — mais à l'ère de la donnée et de
l'intelligence artificielle.

## Sujet

Vous devez concevoir un pipeline ETL complet autour d'une simulation du dilemme du prisonnier
itératif, en y intégrant une dimension générative :

- D'abord en simulant les comportements à l'aide de stratégies codées,
- Puis en déléguant les décisions à des agents d'IA locaux (par exemple via LMStudio ou Ollama).

L'objectif est de produire un jeu de données original, propre, structuré et analysable,
retraçant l'évolution des comportements de coopération ou de trahison entre agents.

## Consignes

### 1. Génération des données (Extract / Generate)

- Simulez un tournoi entre plusieurs stratégies ou agents IA.
- Chaque partie comporte un nombre défini de tours (par exemple 200).
- Chaque tour enregistre : les choix des deux joueurs, leurs gains, et toute information
  pertinente (profil, score cumulé, justification éventuelle de l'IA).
- Vous pouvez coder vos stratégies (ex : always cooperate, always defect, tit for tat, random,
  grim trigger, etc.) puis les définir via des prompts IA (profil empathique, calculateur,
  rancunier…) et confronter les deux approches.
- Pensez à mettre en place un système d'évaluation de vos prompts !

### 2. Transformation des données (Transform)

- Nettoyez et structurez vos données.
- Calculez des indicateurs : taux de coopération, score moyen, évolution du comportement par
  tour, performance relative entre stratégies.
- Enrichissez vos données par des colonnes dérivées : mémoire des tours précédents, fréquence
  de trahison, tendance à pardonner, etc.

### 3. Chargement et restitution (Load & Analyse)

- Chargez vos données dans un dataset local (Parquet).
- Réalisez une analyse exploratoire :
  - Comparaison des stratégies ou profils d'IA ;
  - Visualisations (évolution temporelle, heatmaps, corrélations) ;
  - Mise en évidence d'un comportement émergent ou d'un équilibre de Nash.
- Quel est l'impact de l'IA sur cette expérimentation ? Que peut-on déduire par rapport à des
  stratégies codées ?

## Livrables

- Script de génération : Simulation complète ou interaction avec le modèle IA.
- Architecture de données recommandée : Architecture Bronze, Silver et Gold.
- Analyse finale : Streamlit incluant dataviz et interprétation.

## Conclusion

Ce projet vous place dans la position du chercheur : vous créez vos propres données, vous les
traitez et les interprétez pour comprendre un phénomène complexe.

Comme Axelrod en 1981, vous devrez décider : serez-vous du côté de la coopération, de la
trahison, ou de l'expérimentation ?
