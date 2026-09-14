"""
合成语料的**内容**部分：课程文档、格式样例与测试 fixture 的全部文本。

与 `make_synthetic_corpus.py` 的分工：这里只有"写什么"，那边只有"怎么渲染与校验"。
分文件是因为语料有十几万字，混在一起会让生成逻辑淹没在文本里。

所有内容均为虚构：虚构校名（Université de démonstration）、虚构教师、虚构邮箱与日期。
技术主题只使用公开事实（图灵 1950 年的论文、1956 年 Dartmouth 会议、SAT/CNF、交叉验证等）——
事实、算法与术语本身不受著作权保护，受保护的是表达。

⚠️ **但不要把这些文本当成原创作品**：它们由语言模型生成，**未经原创性核查**。像「一条启发式是
   可采纳的，当它从不估计过高剩余代价」这类定义句属于领域内的惯常表述，抽查已确认它与多份
   公开课程材料措辞相近。作为 demo 与评测语料使用没有问题，**不要把它当作原创教材，也不要直接
   对外发布为课程材料**。

⚠️ 文本会经 PyMuPDF 内置字体（Base14 / WinAnsi）渲染，只支持 ASCII、法语重音、«» 和 °。
   `œ`、`’`、`—`、`–`、`•`、`€` 会被静默替换成 `·`，生成脚本会在渲染前直接报错拦住。
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Document:
    """一份合成讲义：一个产物文件。

    `pages` 的顺序就是 PDF 的页码顺序，golden set 里的 `expected_sources.pages` 依赖它 ——
    插入或移动任何一页都会让 golden set 的页码失效。
    """

    filename: str
    title: str
    subject: str
    pages: tuple[tuple[str, tuple[str, ...]], ...] = field(default_factory=tuple)


DOC_00_INTRODUCTION = Document(
    filename="00-introduction-ia.pdf",
    title="INF-204 - Intelligence artificielle : fondations",
    subject="corpus synthétique - module 0, introduction",
    pages=(
        (
            "Université de démonstration - Intelligence artificielle : fondations",
            (
                "Cet ensemble de documents constitue le support écrit du module INF-204, "
                "intelligence artificielle : fondations. Il est distribué aux étudiants inscrits "
                "et sert de référence unique pour l'ensemble du semestre.",
                "Le cours est découpé en six fascicules indépendants : celui-ci présente la "
                "discipline dans son ensemble, et les cinq suivants approfondissent chacun un "
                "domaine particulier.",
                "Enseignante : Dre Camille Rousseau - Département d'informatique - semestre de "
                "printemps 2026.",
            ),
        ),
        (
            "Objectifs et modalités d'évaluation",
            (
                "Objectifs pédagogiques. À la fin du module, l'étudiant doit savoir définir "
                "l'intelligence artificielle, distinguer l'IA faible de l'IA forte, décrire les "
                "trois paradigmes d'apprentissage automatique, formaliser un problème de recherche "
                "et choisir une méthode d'évaluation adaptée à un jeu de données donné.",
                "L'évaluation repose sur deux notes. Le contrôle continu compte pour quarante pour "
                "cent de la note finale et se compose de deux travaux pratiques notés, réalisés en "
                "binôme.",
                "L'examen final écrit compte pour soixante pour cent de la note finale. Il dure "
                "deux heures et porte sur l'ensemble du programme, y compris la recherche dans un "
                "espace d'états et la logique propositionnelle.",
                "La présence en cours n'est pas notée. Les séances de travaux pratiques ont lieu "
                "aux dates fixées au calendrier du semestre et ne sont pas déplacées.",
            ),
        ),
        (
            "Les six fascicules du module",
            (
                "Fascicule 0, celui-ci : présentation de la discipline, vocabulaire, repères "
                "historiques et applications.",
                "Fascicule 1, recherche et planification : formulation d'un problème sous forme "
                "d'espace d'états, algorithmes non informés, algorithmes heuristiques, complexité.",
                "Fascicule 2, logique et satisfaisabilité : logique propositionnelle, forme "
                "normale conjonctive, procédures de décision, problèmes de satisfaction de "
                "contraintes.",
                "Fascicule 3, apprentissage supervisé : modèles de classification et de "
                "régression, arbres de décision, forêts aléatoires, machines à vecteurs de support.",
                "Fascicule 4, évaluation et métriques : découpage des données, validation "
                "croisée, sur-apprentissage, mesures de performance et comparaison de modèles.",
                "Fascicule 5, réseaux de neurones : du perceptron aux architectures profondes, "
                "rétropropagation, convolution, récurrence et mécanismes d'attention.",
            ),
        ),
        (
            "Bibliographie et ressources",
            (
                "Russell, S. et Norvig, P. - Artificial Intelligence: A Modern Approach, Pearson, "
                "quatrième édition, 2020.",
                "Mitchell, T. - Machine Learning, McGraw-Hill, 1997.",
                "Turing, A. M. - Computing Machinery and Intelligence, Mind, volume 59, 1950.",
                "Les diapositives utilisées en cours, les énoncés de travaux pratiques et les "
                "corrigés sont disponibles sur la plateforme de l'université. Seuls ces documents "
                "font foi pour l'évaluation finale.",
            ),
        ),
        (
            "Qu'est-ce que l'intelligence artificielle ?",
            (
                "L'intelligence artificielle désigne l'ensemble des techniques informatiques qui "
                "permettent à une machine de réaliser des tâches qui, accomplies par un humain, "
                "seraient considérées comme requérant de l'intelligence.",
                "On regroupe traditionnellement ces techniques autour de quatre capacités : "
                "percevoir un environnement, raisonner sur des connaissances, apprendre à partir "
                "d'exemples et agir sur le monde.",
                "Cette définition est volontairement large. Elle inclut aussi bien un programme "
                "qui joue aux échecs qu'un système de traduction automatique ou un planificateur "
                "industriel.",
                "Une définition par les capacités plutôt que par les mécanismes évite les débats "
                "sur la nature exacte de l'intelligence : on demande à un système de réussir une "
                "tâche mesurable, pas de ressembler à un humain.",
            ),
        ),
        (
            "Les sous-domaines de la discipline",
            (
                "Recherche et planification. Trouver une suite d'actions qui mène d'une situation "
                "initiale à une situation désirée, dans un espace d'états souvent trop grand pour "
                "être parcouru entièrement.",
                "Représentation des connaissances et logique. Décrire des faits et des règles dans "
                "un langage formel, puis en déduire de nouveaux faits par des procédures "
                "automatiques.",
                "Apprentissage automatique. Extraire des régularités à partir d'exemples plutôt "
                "que de les écrire à la main, puis les appliquer à de nouveaux cas.",
                "Perception et langage. Extraire de l'information d'images, de sons ou de textes : "
                "vision par ordinateur, reconnaissance de la parole, traitement automatique du "
                "langage naturel.",
                "Dans ce module, nous insistons sur la recherche, la logique et l'apprentissage, "
                "qui fournissent les fondements des autres sous-domaines.",
            ),
        ),
        (
            "IA faible et IA forte",
            (
                "L'IA faible, aussi appelée IA étroite, désigne un système conçu pour une tâche "
                "précise : jouer aux échecs, reconnaitre des visages, traduire un texte ou classer "
                "des courriels. Le système n'a aucune compréhension générale et ne fonctionne pas "
                "en dehors du domaine pour lequel il a été construit.",
                "L'IA forte, aussi appelée IA générale, désigne un système hypothétique capable de "
                "comprendre, d'apprendre et de résoudre n'importe quelle tâche intellectuelle qu'un "
                "être humain peut résoudre. Une IA forte aurait des capacités comparables à celles "
                "de l'intelligence humaine dans tous les domaines.",
                "Aucun système connu ne constitue une IA forte. Tous les programmes déployés "
                "aujourd'hui relèvent de l'IA faible, même lorsque leurs performances dépassent "
                "les performances humaines sur une tâche donnée.",
                "La distinction entre IA faible et IA forte sert d'abord d'instrument d'analyse : "
                "elle sépare les questions techniques, que l'on peut mesurer, des questions "
                "philosophiques, qui portent sur la nature de la compréhension.",
            ),
        ),
        (
            "Le débat sur la compréhension",
            (
                "Le test de Turing, proposé en 1950, offre un critère opérationnel : si les "
                "réponses d'une machine sont indiscernables de celles d'un humain lors d'une "
                "conversation, on peut la déclarer intelligente. Ce critère est behavioriste, car "
                "il ne regarde que le comportement observable.",
                "John Searle a proposé en 1980 l'expérience de pensée de la chambre chinoise. Une "
                "personne enfermée qui manipule des symboles chinois selon un manuel peut produire "
                "des réponses correctes sans comprendre un mot de chinois.",
                "L'expérience vise à montrer que la manipulation correcte de symboles ne suffit "
                "pas à établir la compréhension. Elle alimente le débat entre les partisans du "
                "fonctionnalisme, pour qui l'organisation du traitement importe seule, et ceux qui "
                "exigent des états internes dotés d'un contenu.",
                "Nous ne tranchons pas ce débat dans le module. Nous retenons que la question de "
                "la compréhension n'est pas réductible à une mesure de performance, alors que les "
                "questions techniques de ce cours le sont.",
            ),
        ),
        (
            "Repères historiques : Turing et le programme initial",
            (
                "En 1950, Alan Turing publie Computing Machinery and Intelligence dans la revue "
                "Mind. L'article pose une question simple : une machine peut-elle penser ? Faute "
                "de pouvoir définir la pensée, Turing propose un critère de remplacement.",
                "Il décrit le jeu de l'imitation, que l'on appelle aujourd'hui test de Turing. Un "
                "interrogateur dialogue à distance avec un humain et avec une machine. Si, après "
                "un temps raisonnable, il ne peut pas distinguer la machine de l'humain, la "
                "machine a réussi le test.",
                "L'article discute aussi les objections classiques : l'objection mathématique, "
                "l'objection de la conscience et l'objection de l'infini. Ces objections restent "
                "discutées aujourd'hui.",
                "Turing estime qu'à la fin du vingtième siècle, une machine disposant d'une "
                "mémoire suffisante pourra tromper un interrogateur moyen pendant cinq minutes.",
            ),
        ),
        (
            "Repères historiques : la conférence de Dartmouth",
            (
                "En 1956, la conférence du Dartmouth Summer Research Project on Artificial "
                "Intelligence réunit une dizaine de chercheurs pendant plusieurs semaines. C'est "
                "à cette occasion que l'expression intelligence artificielle est proposée par "
                "John McCarthy et adoptée par la communauté.",
                "Les participants fondateurs viennent d'horizons variés : mathématiques, logique, "
                "psychologie, économie. Cette diversité explique la variété des approches qui "
                "coexistent encore aujourd'hui dans la discipline.",
                "La conférence parie sur une progression rapide. Les participants estiment qu'une "
                "génération suffira pour résoudre les principaux problèmes. Ce pari sera démenti "
                "par les décennies suivantes.",
                "L'optimisme de Dartmouth reste un motif récurrent de la discipline : chaque "
                "avancée technique s'accompagne d'annonces de généralisation prochaine.",
            ),
        ),
        (
            "Repères historiques : les hivers et les reprises",
            (
                "Après un premier élan, la discipline connait une première période de "
                "désaffection entre 1974 et 1980. Les promesses de traduction automatique et de "
                "résolution générale de problèmes ne sont pas tenues, et les financements sont "
                "interrompus.",
                "Une seconde période de désaffection suit entre 1987 et 1993, liée à "
                "l'effondrement du marché des machines spécialisées en logique. Les chercheurs "
                "parlent alors de premier et de second hiver de l'intelligence artificielle.",
                "Les succès des années suivantes sont plus discrets mais plus solides : victoire "
                "de Deep Blue contre le champion du monde en 1997, percée des réseaux de neurones "
                "profonds sur la reconnaissance d'images en 2012.",
                "À partir de 2017, les architectures fondées sur l'attention transforment le "
                "traitement du langage. Cette vague s'accompagne d'une croissance forte des "
                "ressources de calcul consacrées à l'entrainement des modèles.",
            ),
        ),
        (
            "Les tendances des années 2020",
            (
                "Trois évolutions structurent la période récente. La première est la mise à "
                "l'échelle : les modèles les plus performants croissent en taille et en volume de "
                "données, et leurs performances s'améliorent de façon prévisible.",
                "La deuxième est la généralisation d'usage : un même système pré-entrainé sur des "
                "textes variés est ensuite adapté à des tâches très différentes, souvent avec peu "
                "d'exemples spécifiques.",
                "La troisième est la dépendance aux ressources : l'entrainement de ces modèles "
                "mobilise des moyens de calcul considérables, ce qui concentre la recherche dans "
                "un petit nombre d'organisations.",
                "Ces évolutions ne changent pas les fondements enseignés dans ce module. Elles en "
                "augmentent l'importance pratique : les notions d'évaluation, de biais et de coût "
                "des erreurs deviennent des questions industrielles.",
            ),
        ),
        (
            "Apprentissage automatique : définition",
            (
                "On dit qu'un programme apprend à partir de l'expérience E pour une tâche T et une "
                "mesure de performance P si sa performance sur T, mesurée par P, s'améliore avec "
                "l'expérience E. Cette formulation, proposée par Mitchell, fixe le vocabulaire du "
                "module.",
                "La différence avec la programmation classique tient au mode d'obtention des "
                "règles. Un programme classique applique des règles écrites explicitement par un "
                "développeur. Un programme qui apprend extrait ces règles à partir d'exemples.",
                "Apprendre n'est pas mémoriser. Un modèle qui restitue les exemples vus ne sert à "
                "rien. Ce que l'on attend d'un modèle, c'est la capacité de traiter correctement "
                "des cas nouveaux : la capacité de généralisation.",
                "La qualité de la généralisation dépend de trois facteurs : la quantité et la "
                "qualité des données, l'adéquation du modèle à la tâche, et la rigueur du "
                "protocole d'évaluation.",
            ),
        ),
        (
            "Les trois paradigmes de l'apprentissage",
            (
                "L'apprentissage supervisé dispose de couples entrée-sortie. Chaque exemple est "
                "étiqueté, car on connait la réponse attendue. Le modèle apprend une fonction qui "
                "associe une entrée à une sortie, puis l'applique à de nouvelles entrées.",
                "L'apprentissage non supervisé ne dispose que des entrées, sans étiquette. Le "
                "modèle cherche une structure dans les données : groupes d'individus similaires, "
                "axes de variation, observations atypiques.",
                "L'apprentissage par renforcement ne dispose ni d'étiquettes ni de couples tout "
                "faits. Un agent agit dans un environnement, reçoit une récompense et cherche à "
                "maximiser la récompense cumulée. Le modèle apprend donc une politique d'action.",
                "Le choix du paradigme dépend de la forme des données disponibles, et non des "
                "préférences de l'équipe. Lorsque les données étiquetées sont rares, "
                "l'apprentissage non supervisé est souvent la seule option.",
            ),
        ),
        (
            "Où l'apprentissage automatique est utilisé",
            (
                "Vision par ordinateur. Détection d'objets, segmentation d'images médicales, "
                "contrôle qualité en production industrielle.",
                "Traitement du langage. Traduction automatique, résumé de documents, recherche "
                "d'information, analyse de sentiment.",
                "Prédiction tabulaire. Évaluation du risque de crédit, prévision de la demande, "
                "maintenance prédictive sur des séries de mesures.",
                "Recommandation et décision séquentielle. Sélection de contenus, affectation de "
                "ressources, ordonnancement de tâches.",
                "Dans tous ces domaines, la même démarche revient : formuler la question, "
                "rassembler des données représentatives, entrainer, évaluer, surveiller.",
            ),
        ),
        (
            "Les données au centre du problème",
            (
                "Un modèle n'est jamais meilleur que les données qui l'ont produit. Les "
                "statistiques descriptives du jeu d'entrainement déterminent ce que le modèle peut "
                "apprendre, et ce qu'il ne peut pas apprendre.",
                "Trois défauts reviennent constamment : la couverture insuffisante de certains cas "
                "d'usage, l'étiquetage incohérent entre annotateurs, et la fuite d'information "
                "entre les données d'entrainement et celles d'évaluation.",
                "Un jeu de données qui ne représente pas la population cible produit un modèle qui "
                "échoue précisément sur les cas minoritaires. C'est la principale source d'écart "
                "entre les performances annoncées et les performances observées en production.",
                "Le travail sur les données occupe souvent plus de la moitié du temps d'un projet. "
                "Cette proportion n'est pas un signe de mauvaise organisation, mais la réalité du "
                "métier.",
            ),
        ),
        (
            "Limites, risques et responsabilités",
            (
                "Un système d'intelligence artificielle produit des sorties plausibles, pas des "
                "vérités. Un modèle peut inventer une information précise et fausse, en particulier "
                "lorsqu'il généralise à partir d'un contexte absent de ses données.",
                "L'automatisation d'une décision déplace la responsabilité sans la supprimer. "
                "Lorsqu'un système classe, trie ou refuse, il faut pouvoir expliquer la décision, "
                "la contester et la corriger.",
                "Les biais présents dans les données se reproduisent dans les décisions. Mesurer "
                "la performance globale ne suffit pas : il faut la mesurer par sous-population "
                "lorsque la décision a des conséquences sur des personnes.",
                "Enfin, tout système déployé doit être surveillé. La distribution des données "
                "d'entrée change avec le temps, et un modèle qui n'est pas réévalué devient "
                "progressivement faux sans que rien ne signale l'erreur.",
            ),
        ),
        (
            "Petit lexique français-anglais",
            (
                "apprentissage supervisé, supervised learning. Apprentissage à partir d'exemples "
                "étiquetés.",
                "sur-apprentissage, overfitting. Ajustement excessif aux données d'entrainement, "
                "au détriment de la généralisation.",
                "validation croisée, cross-validation. Procédure d'évaluation qui découpe les "
                "données en parties et moyenne les scores obtenus.",
                "espace d'états, state space. Ensemble des situations atteignables depuis une "
                "situation initiale par une suite d'actions.",
                "forme normale conjonctive, conjunctive normal form. Écriture d'une formule "
                "logique comme conjonction de clauses.",
            ),
        ),
        (
            "Comment travailler ce module",
            (
                "Lire le fascicule avant la séance correspondante, puis refaire les exemples du "
                "cours sur papier. Les notions de ce module s'acquièrent par la pratique du calcul "
                "plus que par la lecture.",
                "Faire les travaux pratiques en binôme, mais écrire soi-même le compte rendu. "
                "L'écart entre ce que l'on croit avoir compris et ce que l'on sait expliquer est "
                "souvent important.",
                "Utiliser le forum du module pour les questions techniques. Une question posée "
                "publiquement profite à tout le groupe, et les réponses y restent consultables "
                "pendant toute la durée du semestre.",
                "Ne pas confondre familiarité et maitrise : reconnaitre une notion dans un "
                "document n'est pas la même chose que savoir quand l'appliquer et quand l'éviter.",
            ),
        ),
        (
            "Malentendus fréquents",
            (
                "Un réseau de neurones n'est pas plus intelligent qu'un arbre de décision : il "
                "est plus souple, ce qui aide sur certains problèmes et nuit sur d'autres. Le bon "
                "modèle dépend des données disponibles.",
                "Un score élevé ne prouve rien si le jeu d'évaluation est mal construit. Neuf "
                "pour cent d'erreur sur un jeu biaisé reste neuf pour cent d'erreur sur ce jeu, "
                "et rien de plus.",
                "Une heuristique n'est pas une approximation approximative : c'est une estimation "
                "du cout restant, qui doit satisfaire des propriétés précises pour garantir "
                "l'optimalité d'un algorithme de recherche.",
                "Enfin, l'intelligence artificielle n'est pas une discipline récente née avec les "
                "modèles de langue : ses questions fondatrices datent des années 1950 et n'ont pas "
                "toutes été résolues.",
            ),
        ),
        (
            "Informations pratiques",
            (
                "L'examen final écrit se déroule pendant la session d'examens de juin 2026. Sa "
                "durée est de deux heures et aucun document n'est autorisé, à l'exception d'une "
                "feuille de notes manuscrite recto-verso.",
                "Les deux travaux pratiques notés portent sur les jeux de données et l'évaluation, "
                "puis sur la recherche dans un espace d'états. Les énoncés sont distribués une "
                "semaine avant la séance concernée.",
                "Enseignante : Dre Camille Rousseau - camille.rousseau@universite-demonstration.fr - permanence "
                "le mardi de quatorze heures à seize heures, sur rendez-vous pris par courriel.",
            ),
        ),
    ),
)


DOC_01_RECHERCHE = Document(
    filename="01-recherche-et-planification.pdf",
    title="INF-204, fascicule 1 - recherche et planification",
    subject="corpus synthétique - module 1, recherche dans un espace d'états",
    pages=(
        (
            "Recherche et planification : présentation du fascicule",
            (
                "Ce fascicule traite d'une famille de problèmes que l'on rencontre bien avant "
                "l'apprentissage automatique : trouver une suite d'actions qui mène d'une "
                "situation de départ à une situation désirée.",
                "Deux questions le structurent. Comment décrire un problème sous une forme que "
                "l'on puisse traiter automatiquement ? Et comment explorer l'ensemble des "
                "solutions possibles sans en parcourir la totalité ?",
                "Les algorithmes présentés ici ne font appel à aucune donnée statistique. Ils "
                "sont déterministes et fournissent des garanties précises sur leur résultat, à "
                "condition que le problème soit correctement modélisé.",
                "Ce fascicule suit le fascicule 0 dans l'ordre de lecture, mais il peut être "
                "étudié avant le fascicule 2, qui formalise les mêmes questions en logique.",
            ),
        ),
        (
            "Qu'est-ce qu'un problème de recherche ?",
            (
                "Un problème de recherche est décrit par cinq éléments : un état initial, un "
                "ensemble d'actions applicables, un modèle de transition, un test de but et une "
                "fonction de cout.",
                "Résoudre le problème consiste à trouver une suite d'actions qui transforme "
                "l'état initial en un état satisfaisant le test de but, en minimisant si possible "
                "le cout total.",
                "Le mot état désigne ici une situation complète du problème, et non une étape "
                "d'un calcul. Cette distinction est importante : un état contient toute "
                "l'information nécessaire pour décider de la suite.",
                "La difficulté vient de la taille de l'ensemble des états. Même pour des "
                "problèmes modestes, cet ensemble dépasse largement ce que l'on peut énumérer en "
                "pratique.",
            ),
        ),
        (
            "Formaliser un problème : les cinq composantes",
            (
                "L'état initial. La situation de départ, décrite de façon complète. Pour un "
                "problème de navigation, la ville de départ suffit ; pour un jeu, il faut la "
                "position de toutes les pièces.",
                "Les actions. L'ensemble des transformations applicables à un état donné. Chaque "
                "action possède une précondition, éventuellement vide, qui détermine les états "
                "où elle s'applique.",
                "Le modèle de transition. La description précise de l'état obtenu après "
                "application d'une action. Ce modèle doit être déterministe dans le cadre de ce "
                "fascicule : une action donnée sur un état donné produit toujours le même "
                "résultat.",
                "Le test de but. Une condition qui caractérise les états acceptables. Elle peut "
                "définir un état unique ou un ensemble d'états, ce qui change la difficulté du "
                "problème.",
                "La fonction de cout. Le cout d'un chemin est la somme des couts de ses actions. "
                "Lorsque tous les couts valent un, la recherche du cout minimal revient à la "
                "recherche du chemin le plus court en nombre d'actions.",
            ),
        ),
        (
            "Espace d'états et arbre de recherche",
            (
                "L'espace d'états est l'ensemble de tous les états atteignables depuis l'état "
                "initial. Il forme un graphe orienté dont les noeuds sont les états et les arcs "
                "les actions.",
                "L'arbre de recherche est une autre structure : c'est l'arbre déplié par un "
                "algorithme au fil de son exploration. Un même état peut y apparaitre plusieurs "
                "fois, atteint par des chemins différents.",
                "Confondre les deux conduit à deux erreurs classiques : croire qu'un algorithme "
                "explore tout l'espace d'états alors qu'il n'en voit qu'une partie, et oublier de "
                "détecter les chemins qui reviennent sur un état déjà visité.",
                "La taille de l'arbre de recherche dépend du facteur de branchement, noté b, "
                "c'est-à-dire du nombre moyen d'actions applicables, et de la profondeur "
                "atteinte, notée d.",
            ),
        ),
        (
            "Exemple : navigation sur une grille",
            (
                "Une grille rectangulaire comporte des cases libres et des obstacles. L'état "
                "initial est la case de départ, l'état but la case d'arrivée. Les actions sont "
                "les quatre déplacements vers une case voisine libre.",
                "Le cout de chaque action vaut un, sauf si l'on souhaite favoriser certains "
                "déplacements. Le test de but compare la position courante à la position "
                "d'arrivée.",
                "Ce problème est le plus simple que l'on puisse formuler, et il sert de banc "
                "d'essai : on peut y dessiner l'arbre de recherche et compter les états "
                "développés par chaque algorithme.",
                "Sa simplicité est trompeuse. Dès que la grille grandit, le nombre de chemins "
                "possibles croit de façon exponentielle, et les différences entre algorithmes "
                "deviennent spectaculaires.",
            ),
        ),
        (
            "Exemple : le taquin",
            (
                "Le taquin est une grille de neuf cases dont huit portent un numéro et une est "
                "vide. Une action consiste à glisser dans la case vide une tuile adjacente.",
                "Un état est une permutation des huit tuiles, soit plus de trois cent mille "
                "configurations. Seule la moitié de ces configurations sont atteignables depuis "
                "une configuration donnée.",
                "Le test de but impose un ordre précis des tuiles. Trouver une solution proche de "
                "l'optimum demande un algorithme informé : les méthodes non informées y "
                "développent des centaines de milliers d'états.",
                "Le taquin est l'exemple historique des recherches sur les heuristiques. La "
                "distance de Manhattan, qui additionne les distances de chaque tuile à sa "
                "position finale, en est l'heuristique classique.",
            ),
        ),
        (
            "Exemple : planification de tournée",
            (
                "Un technicien doit visiter plusieurs sites dans la journée. Chaque site a une "
                "durée d'intervention et une plage horaire. L'état décrit les sites déjà visités "
                "et l'heure courante.",
                "Contrairement aux exemples précédents, le cout des actions varie et les "
                "contraintes temporelles rendent certains enchainements impossibles. Le test de "
                "but exige que tous les sites soient visités.",
                "Ce problème appartient à la famille des problèmes d'ordonnancement. Sa "
                "résolution exacte devient rapidement impossible, et l'on se contente souvent "
                "d'une solution bonne sans être optimale.",
                "La modélisation reste la même : états, actions, transitions, but, cout. Ce qui "
                "change est la taille de l'espace d'états et la nécessité d'accepter une "
                "solution approchée.",
            ),
        ),
        (
            "Comment évaluer un algorithme de recherche",
            (
                "Complétude. L'algorithme trouve-t-il une solution lorsqu'il en existe une ? Un "
                "algorithme incomplet peut échouer sur des problèmes qui ont une solution.",
                "Optimalité. La solution trouvée est-elle de cout minimal parmi toutes les "
                "solutions ? Cette propriété est plus forte que la complétude et ne l'implique "
                "pas.",
                "Complexité en temps. Combien d'états l'algorithme développe-t-il avant de "
                "trouver la solution ? On l'exprime en fonction du facteur de branchement et de "
                "la profondeur.",
                "Complexité en espace. Combien d'états l'algorithme doit-il garder en mémoire ? "
                "Cette mesure est déterminante en pratique : c'est presque toujours la mémoire, "
                "et non le temps, qui limite la taille des problèmes traitables.",
            ),
        ),
        (
            "Mesurer la difficulté : b, d et m",
            (
                "Trois quantités suffisent à décrire la difficulté d'un problème de recherche. "
                "Le facteur de branchement b est le nombre maximal d'actions applicables dans un "
                "état.",
                "La profondeur de la solution la plus proche, notée d, mesure la longueur du "
                "chemin que l'algorithme doit trouver. La profondeur maximale de l'espace, notée "
                "m, borne la longueur des chemins explorés.",
                "Lorsque toutes les actions ont le même cout, le nombre d'états à la profondeur d "
                "vaut environ b puissance d. Pour b égal à dix et d égal à dix, cela représente "
                "dix milliards de noeuds.",
                "Cette croissance explique pourquoi les algorithmes non informés ne suffisent "
                "pas, et pourquoi l'on cherche à utiliser une connaissance du domaine pour "
                "diriger l'exploration.",
            ),
        ),
        (
            "Recherche en largeur",
            (
                "La recherche en largeur développe d'abord tous les états à une profondeur "
                "donnée, puis passe à la profondeur suivante. Elle utilise une file d'attente "
                "dans laquelle les états sont ajoutés à la fin et retirés au début.",
                "Elle est complète dès que le facteur de branchement est fini : si une solution "
                "existe, elle sera atteinte. Elle est optimale lorsque toutes les actions ont le "
                "même cout.",
                "Sa complexité en temps est de l'ordre de b puissance d. Sa complexité en espace "
                "est du même ordre, car il faut conserver tous les états du niveau courant et "
                "ceux du niveau suivant.",
                "C'est là sa faiblesse : la mémoire nécessaire devient prohibitive bien avant le "
                "temps de calcul. Pour un facteur de branchement de dix et une profondeur de "
                "dix, elle doit stocker des milliards de noeuds.",
            ),
        ),
        (
            "Recherche en profondeur",
            (
                "La recherche en profondeur suit une branche jusqu'à son extrémité avant de "
                "revenir en arrière. Elle utilise une pile : les états sont ajoutés et retirés au "
                "même bout.",
                "Sa consommation mémoire est bien meilleure que celle de la recherche en "
                "largeur : elle ne stocke que les états du chemin courant et leurs frères non "
                "explorés, soit de l'ordre de b multiplié par m.",
                "En revanche, elle n'est ni complète ni optimale. Elle peut s'engager dans une "
                "branche infinie et ne jamais revenir, et la première solution trouvée n'est pas "
                "nécessairement la plus courte.",
                "La recherche en profondeur reste utile lorsque l'on sait que les solutions sont "
                "nombreuses et que l'on se contente d'en trouver une, quelle qu'elle soit.",
            ),
        ),
        (
            "Profondeur limitée et approfondissement itératif",
            (
                "La recherche à profondeur limitée fixe une profondeur maximale l et traite les "
                "états à cette profondeur comme des culs-de-sac. Elle rend la recherche en "
                "profondeur complète à condition de choisir l supérieur ou égal à d.",
                "Le choix de l est délicat : trop petit, on manque la solution ; trop grand, on "
                "perd l'avantage mémoire de la recherche en profondeur.",
                "L'approfondissement itératif supprime le problème du choix. On lance la "
                "recherche à profondeur limitée avec l égal à un, puis deux, puis trois, jusqu'à "
                "trouver une solution.",
                "Cette répétition semble couteuse, mais elle ne l'est pas : la majorité des "
                "noeuds se trouvent aux profondeurs basses, et le travail répété représente une "
                "fraction constante du travail total. L'algorithme est complet et optimal pour "
                "des couts uniformes, avec une consommation mémoire linéaire.",
            ),
        ),
        (
            "Recherche de cout uniforme",
            (
                "Lorsque les actions ont des couts différents, explorer par niveaux n'a plus de "
                "sens : une action peut couter un comme cent. La recherche de cout uniforme "
                "développe toujours l'état dont le cout accumulé depuis le départ est le plus "
                "faible.",
                "Cet algorithme est complet et optimal dès que les couts sont positifs. Il se "
                "ramène à la recherche en largeur lorsque tous les couts valent un.",
                "Il souffre du même défaut que la recherche en largeur : il conserve tous les "
                "états générés, et sa complexité en espace reste exponentielle dans le pire cas.",
                "Sa structure est celle d'une file de priorité ordonnée par cout accumulé. "
                "L'algorithme A étoile, présenté plus loin, ajoute à ce critère une estimation du "
                "cout restant.",
            ),
        ),
        (
            "Recherche bidirectionnelle",
            (
                "Principe. On explore simultanément depuis l'état initial et depuis l'état but, "
                "et l'on s'arrête lorsque les deux explorations se rencontrent.",
                "L'intérêt est arithmétique : si deux recherches atteignent chacune la profondeur "
                "d sur deux, leur réunion couvre la profondeur d avec un travail très inférieur à "
                "celui d'une exploration complète depuis le départ.",
                "La difficulté est pratique. Il faut savoir énumérer les prédécesseurs d'un état, "
                "ce qui n'est pas toujours naturel, et décider quand les deux fronts se sont "
                "effectivement rejoints.",
                "La méthode s'applique bien aux problèmes où l'action est réversible, comme la "
                "navigation, moins bien à ceux où le but est défini par une condition abstraite.",
            ),
        ),
        (
            "Recherche informée : l'idée d'heuristique",
            (
                "Une fonction heuristique associe à chaque état une estimation du cout restant "
                "jusqu'au but. Elle ne dit rien sur le chemin, seulement sur le cout à venir.",
                "Une heuristique s'obtient de plusieurs façons : en résolvant une version "
                "simplifiée du problème, en utilisant une distance géométrique, ou en combinant "
                "plusieurs estimations.",
                "Une bonne heuristique n'est pas nécessairement exacte. Elle doit être "
                "informative, c'est-à-dire distinguer les états proches du but de ceux qui en "
                "sont loin, tout en restant prudente sur le cout.",
                "La qualité de l'heuristique détermine directement le nombre d'états que "
                "l'algorithme doit développer. C'est le principal levier d'amélioration des "
                "algorithmes de recherche.",
            ),
        ),
        (
            "Recherche gloutonne",
            (
                "La recherche gloutonne développe toujours l'état dont l'estimation du cout "
                "restant est la plus faible. Elle ignore complètement le cout déjà payé pour "
                "l'atteindre.",
                "Elle est rapide et peu gourmande en mémoire, mais ni complète ni optimale. "
                "Comme la recherche en profondeur, elle peut s'enfermer dans une branche sans "
                "issue.",
                "Sa faiblesse est facile à illustrer : entre un état proche du but atteint au "
                "prix d'un long détour et un état plus éloigné mais atteint directement, elle "
                "choisit le premier.",
                "L'heuristique doit donc être conçue pour ce critère. Une heuristique très "
                "informative mais mal calibrée peut conduire la recherche gloutonne vers un "
                "chemin absurde.",
            ),
        ),
        (
            "L'algorithme A étoile",
            (
                "A étoile classe les états par la somme de deux termes : le cout déjà payé pour "
                "atteindre l'état depuis le départ, et l'estimation du cout restant jusqu'au but.",
                "Cette somme est une estimation du cout total du meilleur chemin passant par "
                "l'état considéré. L'algorithme développe toujours l'état dont cette estimation "
                "est la plus faible.",
                "A étoile combine les avantages des deux approches précédentes : il tient compte "
                "du cout réel comme la recherche de cout uniforme, et il est dirigé vers le but "
                "comme la recherche gloutonne.",
                "Sous une condition précise sur l'heuristique, A étoile est à la fois complet et "
                "optimal. C'est cette condition qui fait de lui l'algorithme de référence pour la "
                "recherche de chemin.",
            ),
        ),
        (
            "Heuristique admissible et optimalité de A étoile",
            (
                "Une heuristique est dite admissible si elle ne surestime jamais le cout réel "
                "restant jusqu'au but. Elle peut sous-estimer autant qu'elle veut, tant qu'elle "
                "reste positive.",
                "Si l'heuristique est admissible, A étoile est optimal. L'argument est simple : "
                "une solution sous-optimale aurait un cout total supérieur à celui de la solution "
                "optimale, et l'estimation d'un état situé sur le chemin optimal reste toujours "
                "en dessous.",
                "Une seconde condition, plus forte, est la consistance : l'estimation d'un état "
                "ne doit pas dépasser le cout d'une action plus l'estimation de l'état suivant. "
                "Une heuristique consistante est admissible, et elle garantit qu'aucun état n'est "
                "développé deux fois.",
                "En pratique, la distance de Manhattan pour le taquin et la distance à vol "
                "d'oiseau pour la navigation sont admissibles. Multiplier une heuristique "
                "admissible par un facteur supérieur à un détruit cette propriété.",
            ),
        ),
        (
            "Construire une heuristique",
            (
                "Méthode des problèmes relaxés. On supprime une contrainte du problème : le cout "
                "de la solution du problème simplifié est une estimation optimiste du cout réel. "
                "C'est la méthode la plus systématique.",
                "Pour le taquin, autoriser une tuile à se déplacer vers n'importe quelle case "
                "donne la distance de Manhattan. Autoriser une tuile à se déplacer vers une case "
                "voisine occupée donne une autre estimation, plus faible.",
                "Combiner des heuristiques. Le maximum de plusieurs heuristiques admissibles "
                "reste admissible, et il est souvent plus informatif que chacune prise "
                "séparément.",
                "Bases de données de motifs. On précalcule le cout exact de sous-problèmes "
                "récurrents, puis on utilise ces valeurs comme estimation. Cette technique a "
                "permis de résoudre le taquin à quinze cases de façon optimale.",
            ),
        ),
        (
            "Mesurer la qualité d'une heuristique",
            (
                "Le facteur de branchement effectif mesure le nombre de successeurs réellement "
                "développés par A étoile, comparé à ce qu'il faudrait pour atteindre la même "
                "profondeur avec une heuristique parfaite.",
                "Si une heuristique réduit le facteur de branchement effectif de dix à trois, le "
                "gain est considérable : à profondeur dix, le nombre d'états passe de milliards à "
                "quelques dizaines de milliers.",
                "Deux heuristiques peuvent être comparées en comparant leur facteur de "
                "branchement effectif sur la même famille de problèmes. C'est une mesure "
                "empirique, mais elle guide efficacement le travail de conception.",
                "Attention toutefois à ne pas comparer des heuristiques sur des instances "
                "différentes : la conclusion serait aussi peu fiable que celle d'un benchmark mal "
                "construit.",
            ),
        ),
        (
            "Recherche locale : la montée de colline",
            (
                "La recherche locale abandonne l'idée de chemin. Elle maintient un état courant "
                "et passe à un voisin meilleur tant qu'il en existe un.",
                "La montée de colline est immédiate à implémenter et consomme très peu de "
                "mémoire, puisqu'elle ne conserve qu'un état. Elle est utilisée pour les "
                "problèmes où seule importe la solution finale, pas le chemin.",
                "Elle souffre de trois blocages classiques : les maxima locaux, les plateaux où "
                "tous les voisins ont la même valeur, et les crêtes étroites que l'on ne peut "
                "suivre qu'en dégradant temporairement la solution.",
                "Ces blocages ne sont pas des cas pathologiques rares : sur de nombreux problèmes "
                "combinatoires, ils constituent la difficulté principale.",
            ),
        ),
        (
            "Recherche locale : recuit simulé et faisceaux",
            (
                "Le recuit simulé accepte parfois une dégradation, avec une probabilité qui "
                "diminue au fil du temps. Cette tolérance temporaire permet de sortir des maxima "
                "locaux.",
                "Le nom vient de la métallurgie, où l'on chauffe puis refroidit lentement un "
                "métal pour lui faire atteindre une structure de faible énergie. Le parallèle est "
                "formel : la température contrôle la probabilité d'accepter une dégradation.",
                "La recherche en faisceaux conserve au contraire un petit nombre d'états courants "
                "à chaque étape, les meilleurs. Elle explore donc plusieurs pistes en parallèle, "
                "au prix d'une mémoire plus grande.",
                "Ces méthodes ne fournissent aucune garantie d'optimalité. Leur intérêt est de "
                "produire rapidement une bonne solution sur des problèmes où la résolution exacte "
                "est hors de portée.",
            ),
        ),
        (
            "Vers la planification automatique",
            (
                "La planification automatique applique la recherche à des problèmes décrits dans "
                "un langage formel. On ne décrit plus les états un par un, mais les prédicats qui "
                "les caractérisent et les actions qui les transforment.",
                "Une action est décrite par ses préconditions et ses effets : ce qui doit être "
                "vrai pour l'appliquer, et ce qui devient vrai ou faux après. Ce formalisme "
                "permet de décrire des domaines entiers sans énumérer les états.",
                "La difficulté principale est que l'espace d'états est décrit de façon implicite. "
                "Les algorithmes doivent le parcourir sans le construire entièrement, ce qui "
                "exige des techniques d'exploration dirigée.",
                "Le fascicule 2 présente l'autre voie de formalisation : décrire le problème par "
                "des formules logiques et chercher une affectation qui les satisfait.",
            ),
        ),
        (
            "Ce qu'il faut retenir de ce fascicule",
            (
                "Un problème de recherche se décrit toujours par les cinq mêmes composantes : "
                "état initial, actions, transition, test de but et cout. La qualité de la "
                "modélisation détermine la difficulté réelle du problème.",
                "Les algorithmes non informés sont complets ou optimaux, mais leur complexité "
                "exponentielle limite leur usage aux problèmes de petite taille. C'est la mémoire "
                "qui est le plus souvent contraignante.",
                "L'algorithme A étoile est optimal dès que l'heuristique est admissible, ce qui "
                "donne un critère vérifiable pour la concevoir. La méthode des problèmes relaxés "
                "fournit une façon systématique d'en construire.",
                "Enfin, lorsque seule la solution compte, la recherche locale offre un compromis "
                "intéressant : aucune garantie, mais des solutions exploitables à très grande "
                "échelle.",
            ),
        ),
        (
            "Exercices du fascicule 1",
            (
                "Exercice 1. Modéliser le problème du loup, de la chèvre et du chou sous forme "
                "d'espace d'états. Donner l'état initial, les actions, le test de but, puis "
                "dessiner le graphe complet des états atteignables.",
                "Exercice 2. Comparer la recherche en largeur, la recherche en profondeur et "
                "l'approfondissement itératif sur le taquin à huit cases, en comptant les états "
                "développés pour trois configurations initiales.",
                "Exercice 3. Montrer que la distance de Manhattan est admissible pour le taquin, "
                "puis comparer le facteur de branchement effectif de cette heuristique avec celui "
                "obtenu par le nombre de tuiles mal placées.",
                "Exercice 4. Proposer une heuristique admissible pour le problème de tournée de "
                "la page précédente, puis indiquer dans quel cas elle est la plus informative.",
            ),
        ),
    ),
)


DOC_02_LOGIQUE = Document(
    filename="02-logique-et-satisfaisabilite.pdf",
    title="INF-204, fascicule 2 - logique et satisfaisabilité",
    subject="corpus synthétique - module 2, logique propositionnelle et contraintes",
    pages=(
        (
            "Logique et satisfaisabilité : présentation du fascicule",
            (
                "Le fascicule précédent décrivait un problème par une liste d'états et "
                "d'actions. Celui-ci adopte l'approche inverse : on décrit ce qui doit être vrai, "
                "et l'on demande à une procédure automatique de trouver une situation qui "
                "respecte cette description.",
                "Cette façon de procéder a deux avantages. Elle sépare la description du problème "
                "de sa résolution, et elle permet de décrire des problèmes dont on ne sait pas "
                "énumérer les états à l'avance.",
                "Le prix à payer est une difficulté théorique : décider si une formule logique "
                "admet une solution est un problème complet pour la classe NP. Aucun algorithme "
                "connu ne le résout en temps polynomial dans le pire cas.",
                "En pratique, cela n'empêche pas de traiter des instances de plusieurs millions "
                "de variables. La différence entre la théorie du pire cas et la pratique "
                "industrielle est l'un des enseignements de ce fascicule.",
            ),
        ),
        (
            "Pourquoi formaliser en logique",
            (
                "Un langage formel élimine l'ambiguïté. Une phrase en langue naturelle peut "
                "recevoir plusieurs interprétations ; une formule logique en reçoit une seule, "
                "fixée par les règles du langage.",
                "Un langage formel permet le raisonnement automatique. Une fois le problème "
                "traduit, une procédure générale peut chercher une solution sans connaître la "
                "signification des symboles.",
                "Un langage formel rend les contraintes vérifiables. On peut demander pourquoi "
                "une solution est refusée, en exhibant la contrainte violée ou la clause "
                "insatisfaite.",
                "Ces trois propriétés expliquent l'usage de la logique dans la vérification de "
                "programmes, la configuration de systèmes et la planification.",
            ),
        ),
        (
            "Syntaxe de la logique propositionnelle",
            (
                "Le vocabulaire de base est constitué de variables propositionnelles, notées "
                "habituellement p, q, r. Chacune représente une affirmation qui peut être vraie "
                "ou fausse.",
                "Les connecteurs sont la négation, la conjonction, la disjonction, l'implication "
                "et l'équivalence. Ils permettent de construire des formules à partir des "
                "variables.",
                "Une formule bien formée est définie récursivement : une variable est une "
                "formule, et l'application d'un connecteur à des formules produit une formule.",
                "Les parenthèses lèvent l'ambiguïté de lecture. Par convention, la négation lie "
                "plus fort que la conjonction, qui lie plus fort que la disjonction.",
            ),
        ),
        (
            "Sémantique et tables de vérité",
            (
                "Une affectation associe à chaque variable une valeur de vérité. Une formule est "
                "évaluée sous une affectation donnée en appliquant les règles de chaque "
                "connecteur.",
                "La table de vérité énumère les valeurs de la formule pour toutes les "
                "affectations possibles. Avec n variables, elle comporte deux puissance n lignes, "
                "ce qui interdit son usage au-delà de quelques dizaines de variables.",
                "Une formule est satisfaisable s'il existe au moins une affectation qui la rend "
                "vraie. Elle est valide si toutes les affectations la rendent vraie, et "
                "insatisfaisable dans le cas contraire.",
                "Une formule est insatisfaisable si et seulement si sa négation est valide. Ce "
                "lien entre les deux notions est utilisé par de nombreuses procédures de "
                "décision.",
            ),
        ),
        (
            "Équivalences utiles",
            (
                "Lois de De Morgan. La négation d'une conjonction est la disjonction des "
                "négations, et réciproquement. Ces lois permettent de faire descendre les "
                "négations jusqu'aux variables.",
                "Distributivité. La conjonction se distribue sur la disjonction, et la "
                "disjonction sur la conjonction. C'est la distributivité qui produit la forme "
                "normale conjonctive.",
                "Implication et équivalence. Une implication est équivalente à la disjonction de "
                "sa prémisse niée et de sa conclusion. Cette réécriture supprime un connecteur "
                "lors de la conversion en forme normale.",
                "Ces équivalences sont utilisées mécaniquement par les procédures de conversion. "
                "Elles ne changent pas la signification de la formule, seulement son écriture.",
            ),
        ),
        (
            "Raisonnement et règles d'inférence",
            (
                "Une règle d'inférence produit de nouvelles formules à partir de formules "
                "connues. Le modus ponens, qui déduit la conclusion d'une implication et de sa "
                "prémisse, en est l'exemple le plus connu.",
                "Le raisonnement par résolution utilise une seule règle. À partir de deux clauses "
                "contenant un littéral et son opposé, on produit la clause formée des autres "
                "littéraux.",
                "Cette règle est complète pour la réfutation : si un ensemble de clauses est "
                "insatisfaisable, la résolution peut en dériver la clause vide. Chercher une "
                "solution revient donc à tenter de dériver cette clause vide.",
                "Le raisonnement automatique se ramène ainsi à une question de recherche : "
                "quelles résolutions appliquer, dans quel ordre, pour parvenir à la clause vide "
                "sans exploser en combinatoire.",
            ),
        ),
        (
            "Un exemple complet de formalisation",
            (
                "Soit un système qui doit respecter trois contraintes : si la sauvegarde "
                "automatique est activée, les journaux sont archivés ; les journaux ne sont pas "
                "archivés si le disque est plein ; le disque est plein ou la sauvegarde "
                "automatique est activée.",
                "Ces trois contraintes s'écrivent comme trois formules. Le système est cohérent "
                "si ces formules peuvent être rendues vraies simultanément.",
                "Si l'on ajoute une quatrième contrainte affirmant que le disque n'est pas plein, "
                "la conjonction reste satisfaisable, mais elle impose la valeur des autres "
                "variables. Si l'on ajoute au contraire que les journaux ne sont pas archivés, "
                "les contraintes deviennent contradictoires.",
                "Cet exemple illustre l'usage réel de la logique propositionnelle : vérifier "
                "qu'un ensemble de règles ne se contredit pas, et déterminer quelles "
                "configurations les satisfont.",
            ),
        ),
        (
            "Le problème SAT",
            (
                "Le problème SAT prend en entrée une formule propositionnelle et demande si elle "
                "est satisfaisable. En cas de réponse positive, on demande souvent une affectation "
                "témoin.",
                "La forme la plus étudiée est SAT sous forme normale conjonctive, c'est-à-dire "
                "une conjonction de clauses. Toute formule peut y être ramenée.",
                "Les cas particuliers sont plus faciles. Si chaque clause comporte au plus un "
                "littéral, le problème est résolu par propagation. Si chaque clause en comporte au "
                "plus deux, le problème est résolu par une procédure fondée sur les composantes "
                "fortement connexes.",
                "La difficulté apparait dès que certaines clauses comportent trois littéraux. "
                "Cette variante, appelée 3-SAT, est complète pour la classe NP.",
            ),
        ),
        (
            "SAT et la classe NP",
            (
                "En 1971, Stephen Cook a démontré que SAT est complet pour la classe NP, c'est-à-"
                "dire qu'il appartient à NP et que tout problème de NP s'y ramène en temps "
                "polynomial. Leonid Levin a obtenu un résultat analogue de façon indépendante.",
                "Ce résultat a une conséquence pratique : si l'on trouvait un algorithme "
                "polynomial pour SAT, on en déduirait des algorithmes polynomiaux pour des "
                "milliers d'autres problèmes, de la planification à la vérification de circuits.",
                "Aucun algorithme de ce type n'est connu, et l'hypothèse contraire reste ouverte. "
                "En revanche, aucun résultat ne prouve non plus qu'il n'en existe pas.",
                "Le caractère NP-complet ne signifie pas que le problème est insoluble, mais que "
                "l'on ne peut pas espérer d'algorithme à la fois général et rapide dans le pire "
                "cas.",
            ),
        ),
        (
            "La forme normale conjonctive",
            (
                "Une clause est une disjonction de littéraux, un littéral étant une variable ou "
                "sa négation. Une formule est en forme normale conjonctive, abrégée CNF, lorsqu'"
                "elle est une conjonction de clauses.",
                "La forme normale conjonctive est l'entrée standard des solveurs. Elle a deux "
                "avantages : la satisfaction se vérifie clause par clause, et la plupart des "
                "techniques de propagation s'expriment directement sur les clauses.",
                "Un ensemble de clauses est satisfait si au moins un littéral est vrai dans "
                "chaque clause. La clause vide, qui ne contient aucun littéral, est donc "
                "insatisfaisable par convention.",
                "Deux ensembles de clauses équivalents ont les mêmes modèles, mais leur taille "
                "peut différer considérablement selon la méthode de conversion employée.",
            ),
        ),
        (
            "Convertir une formule en CNF",
            (
                "La méthode directe applique les équivalences : on élimine les implications et "
                "les équivalences, on fait descendre les négations, puis on distribue la "
                "disjonction sur la conjonction.",
                "Cette méthode préserve l'équivalence logique, mais peut faire croitre la taille "
                "de la formule de façon exponentielle. Une formule de la forme conjonction de "
                "disjonctions en est l'exemple classique.",
                "La transformation de Tseitin évite cette croissance en introduisant une variable "
                "auxiliaire pour chaque sous-formule. La formule obtenue n'est plus équivalente, "
                "mais elle est équisatisfaisable : elle admet un modèle si et seulement si "
                "l'originale en admet un.",
                "La taille obtenue est linéaire en la taille de la formule d'origine. Tous les "
                "solveurs pratiques utilisent cette transformation, ou une variante.",
            ),
        ),
        (
            "L'algorithme DPLL",
            (
                "L'algorithme DPLL, publié dans les années 1960 par Davis, Putnam, Logemann et "
                "Loveland, reste la base des solveurs modernes. Il combine deux idées : la "
                "propagation et le choix.",
                "La propagation unitaire traite les clauses où il ne reste qu'un littéral non "
                "assigné. Ce littéral doit être vrai, sinon la clause serait fausse. On l'assigne "
                "donc et l'on propage à nouveau.",
                "Lorsque plus aucune clause unitaire n'existe, l'algorithme choisit une variable "
                "non assignée et explore successivement ses deux valeurs. En cas d'échec, il "
                "revient sur ce choix.",
                "L'algorithme est complet : il explore systématiquement l'espace des "
                "affectations, mais la propagation élimine de larges portions de cet espace avant "
                "toute exploration.",
            ),
        ),
        (
            "Heuristiques de choix de variable",
            (
                "Le choix de la variable à assigner détermine l'efficacité pratique du solveur. "
                "Une mauvaise politique peut multiplier le nombre de noeuds explorés par plusieurs "
                "ordres de grandeur.",
                "L'heuristique la plus simple choisit la variable la plus fréquente dans les "
                "clauses courtes non satisfaites. Cette politique privilégie les variables qui "
                "contraignent le plus le problème.",
                "Depuis les années 1990, les solveurs utilisent des scores de littéraux décroissants "
                "au fil du temps. Ces scores sont réinitialisés régulièrement depuis les valeurs "
                "mesurées dans les conflits récents.",
                "Une fois la variable choisie, la valeur à essayer en premier est souvent celle "
                "qui satisfait le plus grand nombre de clauses. Ce choix ne change pas le pire "
                "cas, mais accélère la découverte d'un modèle dans les cas satisfaisables.",
            ),
        ),
        (
            "Apprentissage et retours arrière modernes",
            (
                "Le point faible de DPLL est la répétition des erreurs : lorsqu'un conflit "
                "survient, il n'en garde aucune trace et peut retomber sur la même configuration "
                "quelques branches plus loin.",
                "Les solveurs dits CDCL, pour conflit dirigé et apprentissage de clauses, "
                "analysent le conflit pour déterminer la partie de l'affectation qui l'a causé. "
                "Ils en déduisent une nouvelle clause, appelée clause apprise, ajoutée à la "
                "formule.",
                "Cette clause interdit de reproduire la même combinaison de valeurs. Elle "
                "accélère la recherche en éliminant définitivement certaines régions de l'espace "
                "de recherche.",
                "Par ailleurs, le retour arrière n'est plus chronologique mais dirigé : on remonte "
                "directement au point qui a causé le conflit, au lieu de dépiler un choix après "
                "l'autre. Ces deux techniques expliquent l'écart entre les solveurs des années "
                "1990 et ceux d'aujourd'hui.",
            ),
        ),
        (
            "Ce que les solveurs savent faire aujourd'hui",
            (
                "Les solveurs modernes traitent couramment des instances industrielles de "
                "plusieurs centaines de milliers de variables et de millions de clauses.",
                "Leur efficacité vient de la combinaison de plusieurs techniques : propagation "
                "unitaire optimisée par des structures de données adaptées, apprentissage de "
                "clauses, redémarrages périodiques et heuristiques dynamiques.",
                "Des compétitions annuelles comparent les solveurs sur des familles "
                "d'instances variées. Les résultats montrent que les progrès sont continus, "
                "d'environ un ordre de grandeur tous les cinq ans.",
                "Cette progression a des conséquences pratiques : de nombreux problèmes de "
                "configuration, d'ordonnancement ou de vérification formelle se ramènent à SAT et "
                "sont désormais résolus efficacement.",
            ),
        ),
        (
            "Problèmes de satisfaction de contraintes",
            (
                "Un problème de satisfaction de contraintes, abrégé CSP, est défini par un "
                "ensemble de variables, un domaine de valeurs pour chaque variable et un ensemble "
                "de contraintes portant sur des combinaisons de variables.",
                "Une affectation est complète si toutes les variables reçoivent une valeur. Une "
                "contrainte est satisfaite si la combinaison de valeurs qu'elle porte vérifie la "
                "relation attendue.",
                "Une solution est une affectation complète qui satisfait toutes les contraintes. "
                "Le problème peut être purement décisionnel, ou demander l'optimisation d'un "
                "critère parmi les solutions.",
                "La différence avec SAT tient à la forme du domaine : les variables d'un CSP "
                "prennent leurs valeurs dans un ensemble quelconque, pas nécessairement "
                "booléen.",
            ),
        ),
        (
            "Exemples classiques de CSP",
            (
                "Coloration de graphes. On veut assigner une couleur à chaque sommet de telle "
                "sorte que deux sommets reliés n'aient jamais la même. Le domaine est l'ensemble "
                "des couleurs disponibles.",
                "Ordonnancement de tâches. Chaque tâche a une durée, une fenêtre de temps "
                "possible et des ressources. Les contraintes expriment que certaines tâches ne "
                "peuvent se chevaucher.",
                "Puzzle logique. Le placement de nombres dans une grille de type sudoku, ou celui "
                "de dames sur un échiquier sans mises en prise, sont les exemples les plus "
                "courants.",
                "Ces trois familles partagent la même structure : un grand nombre de contraintes "
                "locales, dont la combinaison rend la recherche globale difficile.",
            ),
        ),
        (
            "Résolution par retour sur trace",
            (
                "L'algorithme de base parcourt les variables dans un ordre fixé. Il assigne une "
                "valeur à la première variable, puis passe à la suivante, en vérifiant après "
                "chaque assignation que les contraintes restent satisfaisables.",
                "Si aucune valeur ne convient, l'algorithme revient à la variable précédente et "
                "essaie une autre valeur. C'est un parcours systématique de l'arbre des "
                "affectations complètes.",
                "Sa complexité est celle du nombre d'affectations, mais une vérification "
                "anticipée des contraintes permet d'élaguer de larges sous-arbres avant de les "
                "explorer.",
                "Vérifier seulement les contraintes portant sur la nouvelle variable est plus "
                "efficace que de revérifier la totalité de l'affectation à chaque étape.",
            ),
        ),
        (
            "Propagation de contraintes",
            (
                "La propagation consiste à propager les conséquences d'une assignation : si une "
                "valeur devient impossible pour une variable, on retire cette valeur de son "
                "domaine.",
                "La vérification vers l'avant filtre les domaines des variables non assignées à "
                "chaque étape. Le filtrage est simple, mais il ne détecte pas les contradictions "
                "qui ne concernent que des variables non assignées.",
                "La cohérence d'arc, obtenue par un algorithme classique, est plus coûteuse mais "
                "beaucoup plus informative. Deux variables sont cohérentes d'arc si toute valeur "
                "du domaine de l'une possède un support dans le domaine de l'autre.",
                "Faire converger ces cohérences locales détecte l'échec bien plus tôt qu'une "
                "simple vérification vers l'avant, au prix d'un cout de calcul supérieur à chaque "
                "étape.",
            ),
        ),
        (
            "Heuristiques de choix dans un CSP",
            (
                "Choisir la prochaine variable. L'heuristique dite du minimum de valeurs "
                "restantes sélectionne la variable dont le domaine est le plus petit, car c'est "
                "la plus contrainte.",
                "En cas d'égalité, on choisit la variable impliquée dans le plus grand nombre de "
                "contraintes avec les variables non assignées. Cette seconde heuristique favorise "
                "les variables centrales du problème.",
                "Choisir la prochaine valeur. On essaie en premier la valeur qui contraint le "
                "moins les autres variables, afin de laisser le maximum de liberté à la suite de "
                "la recherche.",
                "Choisir le point de retour. Lorsqu'un échec survient, revenir sur la variable qui "
                "a causé le conflit plutôt que sur la dernière assignée évite de refaire "
                "systématiquement les mêmes explorations.",
            ),
        ),
        (
            "Recherche locale sur les CSP",
            (
                "La méthode dite des conflits minimaux commence par une affectation complète, "
                "éventuellement mauvaise, puis répare les contraintes violées.",
                "À chaque étape, elle choisit une variable impliquée dans un conflit et lui "
                "assigne la valeur qui minimise le nombre de conflits. La procédure s'arrête "
                "lorsqu'aucun conflit ne subsiste.",
                "Cet algorithme surprend par son efficacité sur de grandes instances, comme le "
                "placement de plusieurs milliers de reines sur un échiquier, alors que la "
                "recherche systématique y échoue.",
                "Il ne fournit aucune garantie : il peut s'arrêter sur un état sans conflit, ou "
                "tourner indéfiniment si l'instance est insatisfaisable. En pratique, on lui "
                "impose un budget de tentative et on le redémarre avec une affectation initiale "
                "différente.",
            ),
        ),
        (
            "SAT et CSP : deux vues du même problème",
            (
                "Les deux formalismes sont équivalents du point de vue de la difficulté. On "
                "encode un CSP en SAT en associant une variable booléenne à chaque couple "
                "variable-valeur, puis en écrivant les contraintes comme des clauses.",
                "Réciproquement, une formule SAT se voit comme un CSP dont les variables sont "
                "booléennes et dont chaque clause est une contrainte interdisant une combinaison "
                "précise.",
                "Le choix du formalisme est donc une question d'ergonomie et d'efficacité "
                "pratique. L'encodage en SAT bénéficie de solveurs très optimisés ; le modèle CSP "
                "conserve une structure plus lisible, utile pour expliquer les solutions.",
                "En pratique, de nombreux outils traduisent un CSP en SAT, résolvent la formule, "
                "puis reconvertissent le modèle obtenu en affectation des variables d'origine.",
            ),
        ),
        (
            "Limites et pièges",
            (
                "Un encodage maladroit peut rendre un problème facile artificiellement difficile. "
                "Ajouter des variables auxiliaires inutiles ou écrire une contrainte de façon "
                "redondante dégrade les performances de plusieurs ordres de grandeur.",
                "La taille de l'encodage compte autant que sa correction. Une traduction "
                "linéaire mais peu contrainte se propage mal ; une traduction très contrainte "
                "mais quadratique peut saturer la mémoire.",
                "Enfin, la symétrie est un piège classique. Un problème dont les solutions sont "
                "équivalentes par permutation oblige le solveur à explorer chacune d'elles, sauf "
                "si l'on ajoute des contraintes qui brisent ces symétries.",
                "Ces questions d'encodage constituent l'essentiel du travail sur les problèmes "
                "réels : le solveur, lui, est souvent utilisé tel quel.",
            ),
        ),
        (
            "Ce qu'il faut retenir de ce fascicule",
            (
                "La logique propositionnelle fournit un langage sans ambiguïté pour décrire des "
                "contraintes. Toute formule peut être ramenée en forme normale conjonctive, qui "
                "est l'entrée standard des solveurs.",
                "SAT est complet pour NP, mais cela ne l'empêche pas d'être résolu efficacement "
                "sur des instances industrielles. La différence tient à la propagation, à "
                "l'apprentissage de clauses et aux heuristiques dynamiques.",
                "Les problèmes de satisfaction de contraintes offrent une formulation plus "
                "naturelle lorsque les domaines ne sont pas booléens. Les techniques de "
                "propagation y jouent le même rôle que la propagation unitaire dans SAT.",
                "Enfin, la qualité de l'encodage détermine souvent plus les performances que le "
                "choix du solveur. C'est la partie du travail qui demande le plus de soin.",
            ),
        ),
        (
            "Exercices du fascicule 2",
            (
                "Exercice 1. Mettre la formule suivante en forme normale conjonctive, d'abord "
                "par équivalences, puis par la transformation de Tseitin. Comparer la taille des "
                "deux résultats.",
                "Exercice 2. Appliquer DPLL à la main sur un ensemble de cinq clauses à quatre "
                "variables. Indiquer à chaque étape les clauses devenues unitaires et les "
                "affectations propagées.",
                "Exercice 3. Encoder le problème de coloration d'un graphe à cinq sommets avec "
                "trois couleurs en SAT. Indiquer le nombre de variables et de clauses obtenues.",
                "Exercice 4. Résoudre une instance de quatre reines par la méthode des conflits "
                "minimaux, en partant d'une affectation initiale choisie arbitrairement, puis par "
                "retour sur trace avec propagation.",
            ),
        ),
    ),
)


DOC_03_APPRENTISSAGE = Document(
    filename="03-apprentissage-supervise.pdf",
    title="INF-204, fascicule 3 - apprentissage supervisé",
    subject="corpus synthétique - module 3, modèles de classification et de régression",
    pages=(
        (
            "Apprentissage supervisé : présentation du fascicule",
            (
                "Ce fascicule décrit les modèles qui apprennent à partir d'exemples étiquetés. "
                "C'est la famille de méthodes la plus utilisée en pratique, parce que les "
                "problèmes se formulent naturellement sous cette forme.",
                "L'objectif est double : comprendre comment un modèle représente une relation, et "
                "savoir choisir un modèle adapté à la taille et à la nature des données "
                "disponibles.",
                "Les questions d'évaluation sont traitées dans le fascicule 4. Ici, on suppose "
                "que le protocole expérimental est correctement construit et l'on se concentre "
                "sur les modèles eux-mêmes.",
                "Le fascicule 5 prolonge ce contenu avec les réseaux de neurones, qui sont des "
                "modèles supervisés parmi d'autres.",
            ),
        ),
        (
            "Le cadre formel",
            (
                "Un problème d'apprentissage supervisé est défini par un espace d'entrée, un "
                "espace de sortie et une distribution conjointe inconnue sur les couples "
                "entrée-sortie.",
                "L'apprenant reçoit un échantillon fini tiré selon cette distribution. Il choisit "
                "une hypothèse dans un ensemble prédéfini, appelé classe d'hypothèses, de manière "
                "à minimiser l'erreur attendue sur de nouveaux exemples.",
                "L'erreur attendue ne peut pas être calculée, puisque la distribution est "
                "inconnue. On la remplace par un estimateur calculé sur un échantillon, ce qui "
                "introduit un écart entre ce que l'on optimise et ce que l'on souhaite.",
                "Toute la théorie de l'apprentissage tourne autour de cet écart : l'erreur "
                "empirique mesure la performance sur les exemples vus, et l'erreur de "
                "généralisation mesure celle que l'on obtiendra sur des exemples nouveaux.",
            ),
        ),
        (
            "Classification et régression",
            (
                "En classification, la sortie est une étiquette discrète. Un courriel est "
                "indésirable ou non ; une image contient une des dix catégories prévues.",
                "En régression, la sortie est une valeur continue. La consommation d'énergie d'un "
                "bâtiment, le prix d'un bien, la concentration d'un polluant en sont des exemples.",
                "La distinction n'est pas seulement technique. Les mesures d'évaluation diffèrent "
                "radicalement entre les deux cas, et certaines méthodes ne s'appliquent qu'à l'un "
                "des deux.",
                "Rien n'interdit cependant d'aborder un problème de régression par "
                "discrétisation, ou un problème de classification par un score continu que l'on "
                "seuille ensuite. Ces transformations ont des conséquences sur le protocole.",
            ),
        ),
        (
            "La question de la représentation",
            (
                "Les données brutes sont rarement utilisables telles quelles. Une observation "
                "doit être décrite par un ensemble de variables numériques, appelées variables "
                "explicatives ou attributs.",
                "Le choix de cette description détermine ce que le modèle peut apprendre. Aucune "
                "méthode ne compense une représentation qui ne contient pas l'information "
                "nécessaire.",
                "Les variables catégorielles demandent un encodage explicite : indicatrice pour "
                "deux modalités, encodage binaire pour un nombre limité de modalités, ou "
                "encodage par fréquence lorsque les modalités sont nombreuses.",
                "Les variables numériques demandent de la prudence sur l'échelle. Un modèle "
                "fondé sur des distances réagira très différemment à une variable exprimée en "
                "centaines de mètres et à une variable exprimée en millièmes.",
            ),
        ),
        (
            "Fonctions de perte",
            (
                "La perte mesure l'écart entre la prédiction du modèle et la valeur observée. "
                "Le choix de la perte encode l'importance relative des erreurs.",
                "L'erreur quadratique pénalise fortement les grandes erreurs, ce qui la rend "
                "sensible aux observations aberrantes. L'erreur absolue traite toutes les erreurs "
                "proportionnellement à leur ampleur.",
                "La perte logistique, utilisée en classification, pénalise une prédiction "
                "confiante et fausse plus qu'une prédiction hésitante et fausse.",
                "Enfin, la perte peut être asymétrique, c'est-à-dire pénaliser davantage un type "
                "d'erreur que l'autre. C'est fréquent lorsque les conséquences des deux erreurs "
                "ne sont pas comparables.",
            ),
        ),
        (
            "Risque empirique, risque réel",
            (
                "Minimiser la perte sur l'échantillon d'entrainement s'appelle la minimisation du "
                "risque empirique. C'est une procédure calculable, mais ce n'est pas l'objectif "
                "réel.",
                "L'objectif réel est de minimiser l'espérance de la perte sur des exemples "
                "inédits, que l'on appelle le risque. L'écart entre les deux décroit avec la "
                "taille de l'échantillon, mais lentement.",
                "Une classe d'hypothèses très riche peut atteindre un risque empirique nul tout "
                "en ayant un risque réel élevé. C'est le sur-apprentissage, traité en détail dans "
                "le fascicule 4.",
                "L'arbitrage entre la richesse de la classe d'hypothèses et l'écart de "
                "généralisation est le problème central de l'apprentissage supervisé.",
            ),
        ),
        (
            "Régression linéaire",
            (
                "Le modèle le plus simple suppose que la sortie est une combinaison affine des "
                "variables d'entrée, affectée d'un bruit. Les coefficients sont ajustés pour "
                "minimiser la somme des carrés des écarts.",
                "La solution peut être calculée directement par une formule matricielle. Elle "
                "existe et est unique lorsque les variables ne sont pas colinéaires.",
                "L'interprétation des coefficients est un avantage important : chaque coefficient "
                "mesure l'effet d'une variation unitaire de la variable correspondante, toutes "
                "choses égales par ailleurs.",
                "Cette interprétation suppose que les variables sont indépendantes, ce qui est "
                "rarement le cas. La colinéarité rend les coefficients instables et leur lecture "
                "hasardeuse.",
            ),
        ),
        (
            "Gradient et taux d'apprentissage",
            (
                "Lorsque la solution directe n'existe pas ou n'est pas calculable, on ajuste les "
                "coefficients par descente de gradient : on avance dans la direction opposée au "
                "gradient de la perte.",
                "Le taux d'apprentissage contrôle l'amplitude du pas. Un taux trop grand fait "
                "osciller la procédure, voire diverger ; un taux trop petit la rend "
                "interminablement lente.",
                "Des variantes adaptatives ajustent ce taux automatiquement, en tenant compte de "
                "l'historique des gradients. Elles sont aujourd'hui utilisées par défaut dans la "
                "plupart des bibliothèques.",
                "Pour un modèle linéaire et une perte quadratique, la fonction de cout est "
                "convexe : la descente converge vers l'optimum global. Pour des modèles non "
                "linéaires, elle ne converge que vers un optimum local.",
            ),
        ),
        (
            "Régression logistique",
            (
                "Pour une classification binaire, la régression logistique transforme une "
                "combinaison linéaire en probabilité, à l'aide d'une fonction qui écrase la "
                "droite réelle dans l'intervalle entre zéro et un.",
                "L'ajustement se fait en maximisant la vraisemblance des étiquettes observées, ce "
                "qui revient à minimiser la perte logistique. Le problème est convexe, donc sans "
                "optimum local parasite.",
                "Le modèle produit une probabilité, pas seulement une décision. Le seuil de "
                "décision est un paramètre séparé, que l'on choisit en fonction du cout relatif "
                "des deux types d'erreur.",
                "Cette séparation est souvent négligée. Un modèle bien ajusté avec un seuil mal "
                "choisi produit de mauvaises décisions, et inversement.",
            ),
        ),
        (
            "Frontière de décision",
            (
                "La frontière de décision est l'ensemble des points où le modèle hésite entre "
                "les classes. Sa forme détermine la souplesse du modèle.",
                "Un modèle linéaire produit une frontière plane. Un modèle à base de voisinage "
                "produit une frontière compliquée, qui épouse la disposition des exemples.",
                "Une frontière très contournée s'ajuste au bruit : elle sépare parfaitement les "
                "exemples vus, mais se trompe sur les exemples nouveaux placés près d'elle.",
                "Visualiser la frontière sur deux variables est un exercice utile pour "
                "comprendre le comportement d'un modèle avant de l'utiliser sur des données de "
                "grande dimension.",
            ),
        ),
        (
            "Méthode des k plus proches voisins",
            (
                "La méthode des k plus proches voisins ne construit aucun modèle explicite. Pour "
                "prédire, elle cherche les k exemples d'entrainement les plus proches de "
                "l'observation et agrège leurs étiquettes.",
                "C'est la méthode la plus simple que l'on puisse imaginer, et elle sert de "
                "référence : un modèle sophistiqué qui ne fait pas mieux qu'elle n'apporte rien.",
                "Elle souffre de deux défauts. La prédiction coute le parcours de tout "
                "l'entrainement, et le résultat dépend fortement du choix de la distance et du "
                "nombre de voisins.",
                "Elle est aussi sensible à la dimension : dans un espace à grande dimension, "
                "toutes les distances se ressemblent, et la notion de voisinage perd son sens.",
            ),
        ),
        (
            "Classification naïve de Bayes",
            (
                "Cette méthode applique la règle de Bayes en supposant que les variables sont "
                "conditionnellement indépendantes étant donnée la classe. L'hypothèse est "
                "presque toujours fausse.",
                "Malgré cela, la méthode obtient de bons résultats sur de nombreux problèmes de "
                "classification de textes. Sa simplicité et sa rapidité d'entrainement en font "
                "un point de comparaison utile.",
                "Elle produit des probabilités mal calibrées, souvent proches de zéro ou de un. "
                "L'ordre des scores reste exploitable, mais leur valeur numérique doit être "
                "interprétée avec prudence.",
                "L'hypothèse d'indépendance explique aussi ses erreurs systématiques : deux "
                "variables fortement corrélées voient leur influence comptée deux fois.",
            ),
        ),
        (
            "Arbres de décision",
            (
                "Un arbre de décision pose une suite de questions sur les variables. Chaque "
                "noeud interne teste une variable, chaque branche correspond à une réponse et "
                "chaque feuille porte une prédiction.",
                "La construction choisit à chaque noeud la variable qui sépare le mieux les "
                "classes. Les critères les plus utilisés sont le gain d'information, fondé sur "
                "l'entropie, et l'indice de Gini.",
                "Le gain d'information mesure la réduction d'incertitude produite par le test. "
                "L'indice de Gini mesure la probabilité de mal classer un exemple tiré au hasard "
                "dans le noeud ; il est légèrement plus rapide à calculer.",
                "Les deux critères conduisent le plus souvent à des arbres similaires. Le choix "
                "entre eux importe moins que la profondeur maximale et la taille minimale des "
                "feuilles.",
            ),
        ),
        (
            "Contrôler la taille d'un arbre",
            (
                "Un arbre développé jusqu'au bout sépare parfaitement les exemples "
                "d'entrainement, y compris les observations aberrantes. Son erreur de "
                "généralisation est mauvaise.",
                "L'élagage consiste à supprimer des branches après construction, en comparant "
                "l'erreur de validation avant et après la suppression.",
                "Les critères d'arrêt anticipé limitent la profondeur, le nombre minimal "
                "d'exemples par feuille ou l'amélioration minimale exigée pour poursuivre une "
                "division.",
                "Ces paramètres se règlent par validation, jamais sur le jeu de test. Un arbre "
                "réglé sur le jeu de test perd toute valeur d'estimation.",
            ),
        ),
        (
            "Bagging et forêts aléatoires",
            (
                "Le bagging entraine plusieurs modèles sur des échantillons tirés avec remise, "
                "puis moyenne leurs prédictions. La moyenne réduit la variance sans augmenter "
                "le biais de façon notable.",
                "La forêt aléatoire applique cette idée aux arbres, en ajoutant une seconde "
                "source d'aléa : à chaque division, seules quelques variables tirées au hasard "
                "sont considérées.",
                "Cette double randomisation décorrèle les arbres. Sans elle, tous les arbres "
                "seraient presque identiques et leur moyenne n'apporterait rien.",
                "Les forêts aléatoires sont parmi les méthodes les plus fiables sur données "
                "tabulaires. Elles fournissent en outre une mesure d'importance des variables, "
                "calculée à partir de la contribution de chacune aux divisions.",
            ),
        ),
        (
            "Méthodes d'ensemble par boosting",
            (
                "Le boosting combine des modèles faibles en les entrainant séquentiellement. "
                "Chaque nouveau modèle se concentre sur les exemples mal prédits par les "
                "précédents.",
                "L'algorithme AdaBoost, proposé en 1995, pondère les exemples et combine les "
                "modèles par un vote pondéré. Il offre des garanties théoriques sur l'erreur "
                "d'entrainement.",
                "Les méthodes de gradient boosting reformulent l'idée comme une descente de "
                "gradient dans l'espace des fonctions : chaque nouveau modèle approxime le "
                "gradient de la perte.",
                "Ces méthodes dominent les compétitions sur données tabulaires. Elles sont plus "
                "sensibles aux hyperparamètres que les forêts aléatoires, et demandent un "
                "réglage plus soigneux.",
            ),
        ),
        (
            "Machines à vecteurs de support",
            (
                "Parmi tous les hyperplans qui séparent deux classes, la machine à vecteurs de "
                "support choisit celui qui maximise la marge, c'est-à-dire la distance minimale "
                "aux exemples.",
                "Seuls les exemples situés sur la frontière de la marge, appelés vecteurs de "
                "support, déterminent la solution. Déplacer un exemple éloigné ne change rien au "
                "résultat.",
                "Une version relâchée autorise quelques exemples à violer la marge, ce qui est "
                "indispensable lorsque les classes ne sont pas séparables. Un paramètre contrôle "
                "le compromis entre marge large et violations acceptées.",
                "La méthode est sensible à l'échelle des variables : sans normalisation "
                "préalable, une variable exprimée dans une grande unité domine la distance et "
                "donc la solution.",
            ),
        ),
        (
            "Noyaux et frontières non linéaires",
            (
                "L'astuce du noyau consiste à calculer des produits scalaires dans un espace de "
                "dimension supérieure sans jamais y projeter explicitement les données.",
                "Cela permet d'obtenir des frontières non linéaires tout en conservant la "
                "formulation d'origine. Le noyau gaussien, fondé sur une distance, est le plus "
                "utilisé.",
                "Le choix du noyau et de ses paramètres remplace alors le choix des variables. "
                "Un noyau trop souple produit le même effet qu'un modèle trop complexe.",
                "Sur des données de taille modérée, une machine à vecteurs de support reste une "
                "option solide. Sur de très grands volumes, son cout de calcul devient "
                "dissuasif.",
            ),
        ),
        (
            "Passer de deux classes à plusieurs",
            (
                "La plupart des classifieurs sont conçus pour deux classes. Pour traiter k "
                "classes, on combine plusieurs problèmes binaires.",
                "La stratégie un contre tous entraine k classifieurs, chacun séparant une classe "
                "des autres. Elle est simple, mais chaque classifieur voit un problème "
                "déséquilibré.",
                "La stratégie un contre un entraine un classifieur par paire de classes, soit k "
                "fois k moins un sur deux classifieurs, puis décide par vote. Chacun traite un "
                "problème équilibré, mais leur nombre croit quadratiquement.",
                "Certaines méthodes, comme la régression logistique multinomiale ou les arbres, "
                "gèrent nativement plusieurs classes. Les utiliser évite l'artifice du vote.",
            ),
        ),
        (
            "Classes déséquilibrées",
            (
                "Lorsqu'une classe représente une fraction infime des exemples, l'exactitude "
                "devient trompeuse. Un modèle qui prédit toujours la classe majoritaire obtient "
                "un excellent score.",
                "Trois familles de remèdes existent. Modifier les données, en suréchantillonnant "
                "la classe minoritaire ou en sous-échantillonnant la majoritaire. Modifier la "
                "perte, en pondérant davantage les erreurs sur la classe minoritaire. Modifier le "
                "seuil de décision, en le déplaçant vers la classe majoritaire.",
                "Ces remèdes modifient l'équilibre entre précision et rappel, sans améliorer la "
                "capacité du modèle. Ils doivent être évalués avec les mesures du fascicule 4, "
                "jamais avec l'exactitude seule.",
            ),
        ),
        (
            "Regroupement par k-moyennes",
            (
                "La méthode des k-moyennes partitionne les données en k groupes en minimisant la "
                "somme des distances des points au centre de leur groupe.",
                "L'algorithme alterne deux étapes : assigner chaque point au centre le plus "
                "proche, puis recalculer chaque centre comme la moyenne de son groupe. Il "
                "converge vers un minimum local.",
                "Le résultat dépend de l'initialisation. La pratique courante est de répéter "
                "l'algorithme avec plusieurs initialisations et de conserver la meilleure "
                "partition.",
                "Le nombre de groupes doit être fixé à l'avance ou choisi par des critères "
                "externes. Aucune méthode automatique ne le détermine de façon fiable sans "
                "connaissance du problème.",
            ),
        ),
        (
            "Autres méthodes de regroupement",
            (
                "Le regroupement hiérarchique construit un arbre de fusions successives, du plus "
                "fin au plus grossier. Le résultat se lit sur un dendrogramme, qui montre la "
                "structure à toutes les échelles.",
                "La méthode DBSCAN, proposée en 1996, définit les groupes comme des régions "
                "denses séparées par des régions creuses. Elle détecte en outre les points "
                "isolés, qu'aucun groupe ne contient.",
                "Son avantage principal est de ne pas exiger le nombre de groupes. En revanche, "
                "elle dépend de deux paramètres de densité, difficiles à fixer lorsque les "
                "échelles varient d'une région à l'autre.",
                "Le choix entre ces méthodes dépend de la forme attendue des groupes : "
                "sphériques, hiérarchiques ou de densité variable.",
            ),
        ),
        (
            "Réduction de dimension",
            (
                "L'analyse en composantes principales projette les données sur les directions de "
                "variance maximale. Elle est calculable directement par une décomposition "
                "matricielle.",
                "Sa principale vertu est la visualisation : projeter des données de plusieurs "
                "dizaines de variables sur deux axes permet de repérer des groupes et des "
                "observations aberrantes.",
                "Elle est aussi utilisée en préparation, pour réduire le nombre de variables "
                "avant un modèle sensible à la dimension. Attention toutefois : les composantes "
                "obtenues sont des combinaisons de toutes les variables d'origine et perdent "
                "leur interprétation.",
                "Des variantes non linéaires existent, au prix d'un cout de calcul plus élevé et "
                "d'un réglage supplémentaire.",
            ),
        ),
        (
            "Détection d'anomalies",
            (
                "La détection d'anomalies cherche les observations qui s'écartent du "
                "comportement habituel. Elle est utilisée pour la fraude, la maintenance et la "
                "surveillance de systèmes.",
                "Le cadre est difficile parce que les anomalies sont rares et mal définies. "
                "L'étiquetage est souvent absent, ce qui rapproche le problème de "
                "l'apprentissage non supervisé.",
                "Les approches usuelles modélisent la normalité, puis signalent comme anomalie "
                "tout point dont la vraisemblance est faible. La qualité dépend entièrement de "
                "la représentation des données normales.",
                "Comme pour les classes déséquilibrées, l'évaluation exige des mesures adaptées : "
                "précision et rappel à un seuil donné, plutôt qu'exactitude globale.",
            ),
        ),
        (
            "Construire et sélectionner les variables",
            (
                "La construction de variables consiste à créer, à partir des données brutes, des "
                "descriptions plus directement utiles au modèle : ratios, écarts à une moyenne "
                "de référence, comptages sur une fenêtre glissante.",
                "Cette étape demande une connaissance du domaine plus qu'une connaissance des "
                "algorithmes. Elle reste l'un des leviers les plus efficaces sur les données "
                "tabulaires.",
                "La sélection de variables vise l'inverse : retirer les variables inutiles ou "
                "redondantes, pour réduire le bruit et le cout de calcul.",
                "Les méthodes de filtrage classent les variables par un critère statistique "
                "indépendant du modèle. Les méthodes d'enveloppe évaluent un sous-ensemble de "
                "variables en entrainant réellement le modèle, ce qui est plus couteux mais plus "
                "fiable.",
            ),
        ),
        (
            "Choisir les hyperparamètres",
            (
                "Les hyperparamètres sont les paramètres fixés avant l'entrainement : profondeur "
                "d'un arbre, nombre de voisins, force de la régularisation.",
                "La recherche exhaustive évalue toutes les combinaisons d'une grille prédéfinie. "
                "Elle est fiable mais couteuse dès que le nombre d'hyperparamètres augmente.",
                "La recherche aléatoire explore des combinaisons tirées au hasard. Elle est "
                "souvent plus efficace, car peu d'hyperparamètres influencent réellement le "
                "résultat.",
                "Les méthodes bayésiennes construisent un modèle de la performance en fonction "
                "des hyperparamètres et choisissent les essais suivants en conséquence. Elles "
                "réduisent le nombre d'entrainements nécessaires.",
            ),
        ),
        (
            "Du prototype à la production",
            (
                "Un modèle entrainé n'est pas un système. Il faut fixer le seuil de décision, "
                "définir le comportement lorsque les données d'entrée sont incomplètes ou "
                "inattendues, et prévoir un mode de secours.",
                "La surveillance en production ne se limite pas à mesurer le temps de réponse. "
                "Il faut suivre la distribution des entrées et, lorsque des étiquettes arrivent "
                "avec retard, la performance réelle du modèle.",
                "Un modèle se dégrade sans que personne ne change rien, parce que le monde "
                "change. Réentrainer périodiquement est une nécessité opérationnelle, pas une "
                "amélioration optionnelle.",
                "Enfin, chaque décision automatisée doit rester contestable. Cela suppose de "
                "conserver la version du modèle, les données utilisées et la trace de la "
                "décision.",
            ),
        ),
        (
            "Ce qu'il faut retenir de ce fascicule",
            (
                "Un modèle supervisé ajuste les paramètres d'une classe d'hypothèses pour "
                "minimiser une perte empirique. Ce que l'on veut vraiment minimiser est le "
                "risque, que l'on ne peut qu'estimer.",
                "Le choix du modèle dépend de la taille des données, de la nature des variables "
                "et du besoin d'interprétation. Un arbre lisible peut valoir mieux qu'un modèle "
                "plus précis mais inexplicable.",
                "Sur données tabulaires de taille modérée, les ensembles d'arbres sont les "
                "méthodes les plus fiables. Les machines à vecteurs de support restent solides "
                "lorsque les dimensions sont nombreuses.",
                "Enfin, aucune méthode ne compense une représentation inadéquate ni un protocole "
                "d'évaluation mal construit. Ces deux points pèsent plus lourd que le choix de "
                "l'algorithme.",
            ),
        ),
        (
            "Exercices du fascicule 3",
            (
                "Exercice 1. Sur un jeu de données tabulaire fourni, comparer une régression "
                "logistique, un arbre de décision et une forêt aléatoire. Rapporter les scores de "
                "validation et le temps d'entrainement de chacun.",
                "Exercice 2. Faire varier la profondeur maximale de l'arbre et tracer la courbe "
                "du score d'entrainement et celle du score de validation en fonction de ce "
                "paramètre.",
                "Exercice 3. Comparer la méthode des k plus proches voisins avec et sans "
                "normalisation des variables. Expliquer l'écart observé.",
                "Exercice 4. Sur un problème à trois classes déséquilibrées, comparer l'exactitude "
                "et la mesure F1 par classe, avant et après repondération de la perte.",
            ),
        ),
    ),
)


DOC_04_EVALUATION = Document(
    filename="04-evaluation-et-metriques.pdf",
    title="INF-204, fascicule 4 - évaluation et métriques",
    subject="corpus synthétique - module 4, protocole expérimental et mesure des performances",
    pages=(
        (
            "Évaluation et métriques : présentation du fascicule",
            (
                "Un modèle qui obtient un bon score n'est pas nécessairement un bon modèle. Ce "
                "fascicule traite la question qui décide de la valeur d'un résultat : comment le "
                "mesurer.",
                "Les erreurs de protocole sont les plus couteuses d'un projet d'apprentissage, "
                "parce qu'elles produisent des chiffres crédibles et faux. Elles ne se voient ni "
                "dans les courbes, ni dans les journaux d'exécution.",
                "Ce fascicule présente les protocoles d'évaluation, les mesures usuelles, et les "
                "précautions qui séparent une expérience reproductible d'une démonstration "
                "d'apparence.",
                "Il ne traite pas de la mise en production, sinon par les conséquences de "
                "l'évaluation sur la surveillance d'un modèle déployé.",
            ),
        ),
        (
            "Pourquoi l'évaluation est le problème central",
            (
                "Un modèle n'a pas de valeur en lui-même : sa valeur dépend de ce qu'il sait "
                "faire sur des données qu'il n'a jamais vues, et de la manière dont ce résultat a "
                "été établi.",
                "Deux projets peuvent annoncer la même exactitude et n'avoir aucune valeur "
                "comparable. L'un aura évalué sur un jeu représentatif, l'autre sur un jeu "
                "facile ou partiellement présent dans l'entrainement.",
                "La reproductibilité dépend de détails rarement documentés : la graine aléatoire, "
                "l'ordre des exemples, la version des bibliothèques, la manière de traiter les "
                "valeurs manquantes.",
                "Décrire précisément la procédure est donc une exigence, pas une coquetterie "
                "rédactionnelle. Un résultat sans protocole n'est pas un résultat.",
            ),
        ),
        (
            "Le découpage en trois parties",
            (
                "Le jeu d'entrainement sert à ajuster les paramètres du modèle. Le jeu de "
                "validation sert à choisir les hyperparamètres et à comparer les variantes. Le "
                "jeu de test sert à estimer la performance finale.",
                "Les proportions usuelles sont de soixante-dix, quinze et quinze pour cent. Ces "
                "valeurs ne sont pas des règles : avec peu de données, on augmente la part de "
                "validation ; avec beaucoup de données, on peut se contenter d'un pour cent pour "
                "les deux derniers.",
                "Le jeu de test est utilisé une seule fois, à la fin du projet. Chaque décision "
                "prise en regardant les scores de test consomme une partie de sa valeur "
                "d'estimation.",
                "La distinction entre décider et informer est la règle la plus souvent violée. "
                "Le jeu de validation sert à décider, le jeu de test sert à informer.",
            ),
        ),
        (
            "Comment découper correctement",
            (
                "Le découpage aléatoire simple suppose que les exemples sont indépendants et "
                "identiquement distribués. C'est rarement le cas lorsque les observations "
                "proviennent d'individus suivis dans le temps.",
                "Lorsque plusieurs observations concernent le même individu, il faut découper par "
                "individu. Sinon, le même sujet apparait dans l'entrainement et dans le test, et "
                "la performance annoncée est trop optimiste.",
                "Lorsque les données sont temporelles, il faut découper par date : entrainer sur "
                "le passé, évaluer sur le futur. Un découpage aléatoire mélange les deux et "
                "autorise le modèle à lire l'avenir.",
                "Ces règles ne relèvent pas de la statistique mais de la connaissance du "
                "dispositif de collecte. Aucun outil automatique ne les applique à votre place.",
            ),
        ),
        (
            "Les fuites de données",
            (
                "Une fuite de données survient lorsque de l'information du jeu de test "
                "influence l'entrainement. Elle produit des scores excellents qui ne se "
                "reproduisent pas en production.",
                "Fuite par prétraitement. Calculer la moyenne et l'écart-type sur l'ensemble des "
                "données, puis normaliser, fait entrer de l'information de test dans "
                "l'entrainement. Les statistiques de normalisation doivent être calculées sur le "
                "seul jeu d'entrainement.",
                "Fuite par variable. Une variable calculée après la décision, ou contenant une "
                "partie de la réponse, produit un modèle parfaitement inutile mais très "
                "performant.",
                "Fuite par répétition. Des quasi-doublons répartis entre entrainement et test "
                "transforment l'évaluation en exercice de mémorisation. Un contrôle de "
                "duplication avant découpage est indispensable.",
            ),
        ),
        (
            "La validation croisée",
            (
                "La validation croisée découpe les données en k parties. On entraine k fois le "
                "modèle, en réservant à chaque fois une partie différente pour l'évaluation, puis "
                "on moyenne les k scores obtenus.",
                "La variante stratifiée conserve la proportion des classes dans chaque partie. "
                "Elle est indispensable lorsque les classes sont déséquilibrées, sinon certaines "
                "parties peuvent ne contenir aucun exemple d'une classe.",
                "La variante par groupes respecte une structure d'appartenance : tous les "
                "exemples d'un même groupe restent du même côté du découpage.",
                "La variante temporelle fait glisser la fenêtre d'entrainement vers le futur. "
                "Elle est la seule acceptable sur des séries chronologiques.",
            ),
        ),
        (
            "Combien de parties, et pourquoi",
            (
                "La valeur usuelle est cinq ou dix. Une valeur élevée réduit le biais de "
                "l'estimation, parce que chaque modèle voit davantage de données, mais augmente "
                "le cout de calcul et la variance entre répétitions.",
                "L'extrême est la validation croisée dite à un exemple laissé de côté : chaque "
                "exemple sert une fois de test. Elle est presque sans biais, mais très couteuse et "
                "de variance élevée sur des petits jeux.",
                "Sur des jeux déséquilibrés ou de petite taille, on répète la validation croisée "
                "avec des découpages différents et l'on moyenne l'ensemble. Ce sont ces répétitions "
                "qui stabilisent l'estimation.",
                "Enfin, la validation croisée sert à comparer des modèles et à choisir des "
                "hyperparamètres. Elle ne remplace pas le jeu de test, sauf si l'on a renoncé à "
                "toute estimation finale indépendante.",
            ),
        ),
        (
            "Sur-apprentissage et sous-apprentissage",
            (
                "Le sur-apprentissage survient lorsqu'un modèle apprend par coeur les "
                "particularités du jeu d'entrainement, y compris son bruit. Le score "
                "d'entrainement devient excellent tandis que le score de validation se dégrade.",
                "Le sous-apprentissage survient à l'inverse lorsqu'un modèle est trop simple "
                "pour représenter la relation étudiée. Les deux scores restent mauvais.",
                "Ces deux régimes se reconnaissent à l'écart entre les deux courbes. Un écart "
                "faible avec des scores médiocres indique un sous-apprentissage ; un écart "
                "important indique un sur-apprentissage.",
                "Les remèdes au sur-apprentissage sont l'augmentation du volume de données, la "
                "régularisation, la réduction du nombre de variables et l'arrêt précoce de "
                "l'entrainement.",
            ),
        ),
        (
            "Le compromis biais-variance",
            (
                "L'erreur attendue d'un modèle se décompose en trois termes : le biais, la "
                "variance et le bruit irréductible des données.",
                "Le biais mesure l'écart systématique entre la prédiction moyenne du modèle et la "
                "vérité. La variance mesure la sensibilité du modèle à l'échantillon "
                "d'entrainement particulier qui lui a été fourni.",
                "Un modèle trop simple a un biais élevé et une variance faible. Un modèle trop "
                "complexe a l'inverse. La complexité optimale se situe entre les deux.",
                "Ce compromis est un cadre d'analyse, pas une recette. Il explique pourquoi "
                "ajouter des données aide un modèle à variance élevée et n'aide pas un modèle à "
                "biais élevé.",
            ),
        ),
        (
            "Lire les courbes d'apprentissage",
            (
                "Une courbe d'apprentissage trace le score d'entrainement et le score de "
                "validation en fonction du volume de données d'entrainement.",
                "Si les deux courbes convergent vers un score médiocre, le modèle manque de "
                "capacité ou les variables décrivent mal le problème : ajouter des données "
                "n'aidera pas.",
                "Si un écart persiste entre les deux courbes, le modèle a trop de capacité pour "
                "la quantité de données disponibles. Ajouter des données, ou réduire la "
                "complexité, sont les deux remèdes.",
                "Une seconde variante trace les scores en fonction de la complexité du modèle. "
                "Les deux lectures se complètent, et leur combinaison permet de choisir entre "
                "plus de données et un modèle plus simple.",
            ),
        ),
        (
            "Régularisation",
            (
                "La régularisation ajoute à la perte un terme qui pénalise la complexité du "
                "modèle. Elle limite mécaniquement la variance, au prix d'un biais supplémentaire.",
                "La pénalité quadratique, dite de ridge, contracte les coefficients vers zéro "
                "sans les annuler. Elle stabilise les estimations lorsque les variables sont "
                "corrélées.",
                "La pénalité absolue, dite lasso, proposée en 1996, annule certains coefficients "
                "exactement. Elle produit donc un modèle plus parcimonieux, utile lorsque "
                "beaucoup de variables sont inutiles.",
                "Un paramètre contrôle l'intensité de la pénalité. Il se choisit par validation, "
                "sur la même grille que les autres hyperparamètres.",
            ),
        ),
        (
            "La matrice de confusion",
            (
                "Pour une classification binaire, la matrice de confusion croise les étiquettes "
                "réelles et les prédictions, et dénombre quatre cas : vrais positifs, faux "
                "positifs, vrais négatifs et faux négatifs.",
                "Toutes les mesures usuelles s'expriment à partir de ces quatre nombres. "
                "Afficher la matrice avant les scores évite bien des malentendus.",
                "La matrice se généralise aux problèmes multi-classes : elle devient un tableau "
                "de taille k fois k, où l'on lit surtout la diagonale et les confusions les plus "
                "fréquentes hors diagonale.",
                "Les confusions entre classes ne sont pas symétriques. Savoir quelles classes "
                "sont confondues, et dans quel sens, oriente souvent mieux les améliorations "
                "qu'un score global.",
            ),
        ),
        (
            "Précision, rappel et mesure F1",
            (
                "La précision rapporte les vrais positifs aux prédictions positives. Elle répond "
                "à la question : parmi les cas signalés, quelle proportion l'était réellement ?",
                "Le rappel rapporte les vrais positifs aux positifs réels. Il répond à la "
                "question : parmi les cas à détecter, quelle proportion a été trouvée ?",
                "La mesure F1 est la moyenne harmonique des deux. Elle pénalise fortement les "
                "déséquilibres : un modèle avec une précision de un et un rappel de zéro obtient "
                "une mesure F1 de zéro.",
                "Le choix entre privilégier la précision ou le rappel dépend du cout des erreurs. "
                "Manquer un courriel indésirable se paie en désagrément ; manquer une lésion se "
                "paie autrement.",
            ),
        ),
        (
            "Courbe précision-rappel",
            (
                "Un classifieur produit un score, et le seuil transforme ce score en décision. "
                "En faisant varier le seuil, on obtient une famille de couples précision-rappel.",
                "La courbe précision-rappel montre ce compromis. Sur des classes très "
                "déséquilibrées, elle est plus informative que la courbe ROC.",
                "L'aire sous cette courbe, ou précision moyenne, résume la performance sur "
                "l'ensemble des seuils. Elle sert de mesure de référence lorsque la classe "
                "positive est rare.",
                "Comparer deux modèles sur cette courbe demande de la prudence : deux courbes "
                "peuvent se croiser, et aucun modèle n'est alors uniformément meilleur.",
            ),
        ),
        (
            "Courbe ROC et aire sous la courbe",
            (
                "La courbe ROC trace le taux de vrais positifs contre le taux de faux positifs, "
                "en faisant varier le seuil de décision. Elle provient des travaux de détection "
                "de signal des années 1940.",
                "L'aire sous cette courbe s'interprète comme la probabilité qu'un positif tiré "
                "au hasard reçoive un score supérieur à un négatif tiré au hasard.",
                "Sa valeur est indépendante du seuil et de la prévalence des classes, ce qui est "
                "à la fois un avantage et un piège : un modèle peut avoir une aire excellente et "
                "être inutilisable au seuil requis.",
                "La diagonale correspond à un classifieur aléatoire, d'aire un demi. Une aire "
                "inférieure à un demi indique une inversion systématique des scores, pas "
                "nécessairement un modèle sans information.",
            ),
        ),
        (
            "Choisir un seuil",
            (
                "Le seuil de décision n'est pas un paramètre du modèle mais une décision "
                "opérationnelle, qui dépend du cout relatif des deux erreurs et de la capacité "
                "de traitement disponible.",
                "Une méthode courante consiste à fixer le seuil qui atteint un rappel cible, "
                "puis à mesurer la précision obtenue. L'inverse est possible lorsque le cout des "
                "faux positifs domine.",
                "Sur des données déséquilibrées, le seuil optimal est souvent éloigné de la "
                "valeur neutre. Utiliser la valeur par défaut de la bibliothèque est une source "
                "fréquente de contre-performance en déploiement.",
                "Le seuil se choisit sur le jeu de validation, jamais sur le jeu de test, et il "
                "doit être réévalué lorsque la population change.",
            ),
        ),
        (
            "Calibration des probabilités",
            (
                "Un modèle peut classer correctement tout en produisant des probabilités mal "
                "calibrées. Un score de zéro virgule neuf n'a de sens que si, parmi les cas "
                "ainsi notés, environ quatre-vingt-dix pour cent sont effectivement positifs.",
                "La courbe de fiabilité compare, par tranche de score, la probabilité annoncée "
                "et la fréquence observée. Une courbe au-dessus de la diagonale indique une "
                "sous-confiance.",
                "Le score de Brier combine calibration et pouvoir discriminant en une seule "
                "valeur. Il se décompose en trois termes, dont deux correspondent à la "
                "calibration et à la résolution.",
                "La régression logistique et les méthodes d'ensemble par boosting produisent "
                "généralement des probabilités acceptables. Les machines à vecteurs de support et "
                "les forêts aléatoires demandent une correction par une procédure dédiée.",
            ),
        ),
        (
            "Mesures pour la régression",
            (
                "L'erreur absolue moyenne exprime l'écart en unités de la variable prédite. Elle "
                "est directement interprétable et peu sensible aux valeurs extrêmes.",
                "L'erreur quadratique moyenne pénalise davantage les grandes erreurs. Sa racine "
                "s'exprime dans la même unité que la variable prédite, ce qui la rend lisible.",
                "Le coefficient de détermination rapporte la variance expliquée à la variance "
                "totale. Il est utile pour comparer des modèles sur une même échelle, mais il "
                "peut être négatif lorsque le modèle fait moins bien qu'une simple moyenne.",
                "Comparer deux modèles sur ces mesures suppose le même découpage et la même "
                "définition des erreurs. Ce n'est pas toujours le cas dans la littérature publiée.",
            ),
        ),
        (
            "Mesures multi-classes",
            (
                "La moyenne macro calcule la mesure pour chaque classe, puis en fait la moyenne "
                "simple. Chaque classe pèse le même poids, quelle que soit sa fréquence.",
                "La moyenne micro agrège d'abord les dénombrements de toutes les classes, puis "
                "applique la formule. Les classes fréquentes pèsent alors davantage.",
                "La moyenne pondérée par la fréquence des classes se situe entre les deux. Avec "
                "des classes équilibrées, les trois coïncident.",
                "Annoncer une seule de ces valeurs sans préciser laquelle est une omission "
                "significative. Sur un jeu déséquilibré, l'écart entre macro et micro peut "
                "dépasser vingt points.",
            ),
        ),
        (
            "Estimer l'incertitude d'un score",
            (
                "Un score calculé sur un échantillon est une estimation, pas une valeur exacte. "
                "Sa variabilité dépend de la taille de l'échantillon et de la proportion observée.",
                "L'intervalle de confiance donne une fourchette plausible. Deux modèles dont les "
                "intervalles se recouvrent largement ne sont pas distinguables par l'expérience "
                "réalisée.",
                "Le rééchantillonnage par bootstrap, décrit par Efron en 1979, estime cette "
                "variabilité sans hypothèse de distribution : on tire de nombreux échantillons "
                "avec remise et l'on observe la dispersion du score.",
                "C'est indispensable pour les mesures non linéaires, comme la mesure F1 ou la "
                "précision moyenne, pour lesquelles aucune formule simple n'existe.",
            ),
        ),
        (
            "Comparer deux modèles",
            (
                "Comparer deux modèles sur une seule valeur est insuffisant. L'écart observé "
                "peut être entièrement attribuable à la variabilité du découpage.",
                "La pratique de référence consiste à répéter l'expérience avec plusieurs "
                "découpages et à comparer les scores appariés, c'est-à-dire calculés sur les "
                "mêmes partitions.",
                "Un test de comparaison apparié évalue si l'écart moyen est compatible avec "
                "l'hypothèse d'absence de différence. Il ne dit rien sur l'importance pratique de "
                "cet écart.",
                "Un écart statistiquement significatif de zéro virgule deux point n'a aucun "
                "intérêt opérationnel. La significativité et l'utilité sont deux questions "
                "distinctes.",
            ),
        ),
        (
            "Choisir une référence de comparaison",
            (
                "Un modèle doit toujours être comparé à une référence simple. La plus utile est "
                "la prédiction la plus fréquente, qui donne le score à battre pour établir qu'un "
                "modèle a appris quelque chose.",
                "Une seconde référence utile est la règle métier appliquée aujourd'hui, lorsqu'"
                "elle existe. Battre une référence statistique ne suffit pas si le système en "
                "place fait mieux.",
                "Sur certaines familles de problèmes, une méthode publiée sert de point de "
                "comparaison. Reproduire ce résultat avant de proposer une amélioration évite les "
                "comparaisons avec la littérature qui ne tiennent pas.",
                "Enfin, un modèle simple entrainable en quelques secondes doit être essayé avant "
                "les méthodes complexes. Il sert de plancher et permet de détecter immédiatement "
                "un problème de données.",
            ),
        ),
        (
            "Rapporter les résultats honnêtement",
            (
                "Indiquer le découpage, les proportions, la graine aléatoire et la procédure de "
                "sélection des modèles. Ces informations conditionnent la reproduction du "
                "résultat.",
                "Rapporter la dispersion, pas seulement la moyenne. Un score de quatre-vingt-dix "
                "pour cent avec un intervalle large et un score de quatre-vingt-huit pour cent "
                "stable ne conduisent pas à la même décision.",
                "Rapporter les échecs. Un modèle qui échoue sur une sous-population identifiée "
                "est plus utile qu'un score global sans analyse, parce qu'il indique où porter "
                "l'effort.",
                "Éviter la sélection du meilleur résultat parmi de nombreux essais. Comparer "
                "cinquante configurations sur le jeu de test puis rapporter la meilleure consomme "
                "le jeu de test et produit une estimation biaisée.",
            ),
        ),
        (
            "Évaluer après la mise en production",
            (
                "Les performances mesurées avant déploiement ne se reproduisent pas "
                "automatiquement. La population change, les capteurs dérivent, les usages "
                "évoluent.",
                "La dérive de données désigne un changement de distribution des entrées. La "
                "dérive de concept désigne un changement de la relation entre entrées et sortie. "
                "La seconde est invisible sans étiquettes récentes.",
                "La surveillance compare en continu les distributions observées à celles de "
                "l'entrainement, et suit les scores dès que les étiquettes deviennent "
                "disponibles.",
                "Un modèle déployé sans surveillance n'est pas évalué : il est supposé bon. Cette "
                "hypothèse est fausse dès que l'environnement change.",
            ),
        ),
        (
            "Ce qu'il faut retenir de ce fascicule",
            (
                "Le protocole d'évaluation fait partie du résultat. Un score sans protocole n'"
                "est pas interprétable, et un protocole comportant une fuite produit des chiffres "
                "flatteurs et faux.",
                "Le découpage doit respecter la structure des données : groupes, individus, "
                "ordre temporel. Aucun outil ne peut le deviner à la place du praticien.",
                "Le choix de la mesure dépend du cout des erreurs et du déséquilibre des classes. "
                "L'exactitude seule est presque toujours une mauvaise mesure.",
                "Enfin, comparer deux modèles exige de répéter l'expérience et de rapporter la "
                "dispersion. Un écart plus petit que la variabilité de la mesure n'est pas un "
                "résultat.",
            ),
        ),
        (
            "Exercices du fascicule 4",
            (
                "Exercice 1. Construire un découpage qui provoque une fuite de données, mesurer "
                "le score obtenu, puis corriger le découpage et comparer les deux scores.",
                "Exercice 2. Calculer la précision, le rappel et la mesure F1 pour un seuil donné, "
                "puis tracer la courbe précision-rappel complète sur un jeu de données fourni.",
                "Exercice 3. Estimer par rééchantillonnage l'intervalle de confiance d'une mesure "
                "F1, puis comparer deux modèles dont les intervalles se recouvrent partiellement.",
                "Exercice 4. Comparer la moyenne macro et la moyenne micro d'une même mesure sur "
                "un jeu à trois classes déséquilibrées, et expliquer l'écart obtenu.",
            ),
        ),
    ),
)


DOC_05_RESEAUX = Document(
    filename="05-reseaux-de-neurones.pdf",
    title="INF-204, fascicule 5 - réseaux de neurones",
    subject="corpus synthétique - module 5, du perceptron aux architectures profondes",
    pages=(
        (
            "Réseaux de neurones : présentation du fascicule",
            (
                "Ce dernier fascicule présente les modèles qui ont transformé la discipline "
                "depuis 2012. Ils reposent sur les mêmes principes que le fascicule 3 : ajuster "
                "les paramètres d'une fonction pour minimiser une perte.",
                "Ce qui les distingue est la manière dont la fonction est construite : par "
                "composition de transformations simples, empilées en couches, plutôt que par une "
                "forme fixée à l'avance.",
                "Cette souplesse explique à la fois leur succès sur des données non structurées "
                "et la difficulté de leur interprétation. Il n'existe pas de règle lisible "
                "associée à un réseau entrainé.",
                "Les questions d'évaluation restent celles du fascicule 4. Aucune architecture ne "
                "dispense d'un protocole expérimental rigoureux.",
            ),
        ),
        (
            "Du modèle linéaire au neurone",
            (
                "Un neurone artificiel calcule une somme pondérée de ses entrées, puis applique "
                "une fonction non linéaire au résultat. C'est une généralisation immédiate de la "
                "régression linéaire.",
                "La fonction appliquée à la sortie s'appelle fonction d'activation. Sans elle, "
                "l'empilement de couches se réduirait à une seule transformation linéaire, quelle "
                "que soit la profondeur du réseau.",
                "Le terme neurone est un héritage historique. Il ne suggère aucune propriété "
                "biologique : c'est un opérateur mathématique, dont les paramètres sont ajustés "
                "par optimisation.",
                "La terminologie reste trompeuse dans un autre sens : un réseau de neurones "
                "n'apprend ni ne comprend. Il ajuste des coefficients jusqu'à obtenir un "
                "comportement conforme aux exemples.",
            ),
        ),
        (
            "Le perceptron",
            (
                "Le perceptron, proposé par Rosenblatt en 1958, est le premier modèle de ce type "
                "à avoir été implémenté. Il produit une sortie binaire à partir d'une combinaison "
                "linéaire des entrées.",
                "Sa règle d'apprentissage est simple : lorsqu'un exemple est mal classé, on "
                "modifie les poids dans la direction qui corrige cette erreur.",
                "Il a été démontré qu'il trouve une solution en temps fini lorsque les classes "
                "sont linéairement séparables. Sa convergence est donc garantie, mais seulement "
                "dans ce cas.",
                "L'engouement initial a été suivi d'une désillusion rapide, lorsque ses limites "
                "ont été rendues publiques. Cet épisode est l'un des hivers de l'intelligence "
                "artificielle évoqués dans le fascicule 0.",
            ),
        ),
        (
            "La limite du perceptron simple",
            (
                "Un perceptron ne peut pas représenter la fonction ou-exclusif, dont les "
                "exemples positifs et négatifs ne sont pas séparables par une droite.",
                "Minsky et Papert ont publié en 1969 une analyse systématique de ces limites. "
                "Leur conclusion, souvent résumée de façon abusive, a freiné les recherches sur "
                "les réseaux pendant plus d'une décennie.",
                "L'important dans ce résultat n'est pas la limitation elle-même, mais ce qu'elle "
                "révèle : certaines relations exigent une représentation intermédiaire qui ne "
                "s'écrit pas directement en fonction des entrées.",
                "C'est précisément ce que fournit l'empilement de couches. Les neurones "
                "intermédiaires calculent des combinaisons utiles, que la couche de sortie peut "
                "ensuite combiner linéairement.",
            ),
        ),
        (
            "Réseaux à plusieurs couches",
            (
                "Un réseau à une couche cachée comporte trois étages : les entrées, une "
                "transformation non linéaire vers un espace intermédiaire, puis une sortie.",
                "Sous des hypothèses larges, un tel réseau peut approximer n'importe quelle "
                "fonction continue sur un domaine borné, à condition d'avoir suffisamment de "
                "neurones cachés.",
                "Ce résultat d'approximation universelle est une garantie d'existence, pas de "
                "faisabilité : il ne dit rien sur le nombre de neurones nécessaires, ni sur la "
                "possibilité effective de les ajuster par apprentissage.",
                "En pratique, le choix se porte sur des architectures profondes plutôt que très "
                "larges, parce qu'elles réutilisent mieux leurs paramètres.",
            ),
        ),
        (
            "Fonctions d'activation",
            (
                "La fonction logistique, ou sigmoïde, écrase la sortie dans l'intervalle entre "
                "zéro et un. Elle a été longtemps la référence, avant que ses inconvénients "
                "numériques ne soient identifiés.",
                "La tangente hyperbolique est son équivalent centré sur zéro. Ce centrage "
                "accélère la convergence dans la plupart des cas.",
                "La fonction rectifiée, nulle pour les valeurs négatives et égale à la valeur "
                "pour les positives, est aujourd'hui l'option par défaut dans les couches "
                "cachées. Son gradient est constant sur la partie positive, ce qui limite la "
                "disparition du signal.",
                "Des variantes lisses ou paramétrées existent, mais leurs gains sont marginaux "
                "sur la plupart des problèmes.",
            ),
        ),
        (
            "Propagation avant",
            (
                "La propagation avant consiste à calculer la sortie du réseau pour une entrée "
                "donnée, couche après couche. Chaque couche applique sa transformation puis sa "
                "fonction d'activation.",
                "Cette étape est un simple calcul de composition de fonctions. Elle est "
                "entièrement déterministe pour des paramètres fixés.",
                "Sur des lots de plusieurs exemples, les calculs sont exprimés par des opérations "
                "matricielles, ce qui permet d'exploiter efficacement le matériel disponible.",
                "La propagation avant est aussi l'opération exécutée en production : une fois le "
                "modèle entrainé, prédire revient exactement à ce calcul.",
            ),
        ),
        (
            "Sortie et perte",
            (
                "La forme de la couche de sortie dépend de la tâche. Pour une régression, on "
                "utilise une sortie linéaire. Pour une classification binaire, une probabilité. "
                "Pour une classification à plusieurs classes, une distribution normalisée.",
                "La perte associée est choisie en conséquence : erreur quadratique pour la "
                "régression, perte logistique pour le binaire, entropie croisée pour le "
                "multi-classe.",
                "Ces choix ne sont pas arbitraires. Ils correspondent à maximiser la vraisemblance "
                "des données sous une hypothèse de distribution donnée.",
                "La fonction utilisée pour transformer les scores en distribution, appelée "
                "softmax, produit des valeurs positives de somme égale à un. Elle est souvent "
                "combinée à l'entropie croisée, pour des raisons de stabilité numérique.",
            ),
        ),
        (
            "Rétropropagation du gradient",
            (
                "La rétropropagation calcule le gradient de la perte par rapport à chaque "
                "paramètre. Elle applique la règle de dérivation des fonctions composées, en "
                "parcourant le réseau de la sortie vers l'entrée.",
                "Pour une composition de fonctions, la dérivée est le produit des dérivées "
                "intermédiaires. Le calcul du gradient se fait donc en multipliant des termes le "
                "long du chemin, d'où le risque de disparition ou d'explosion du signal.",
                "L'algorithme réutilise les résultats des couches suivantes, ce qui évite de "
                "recalculer chaque dérivée partielle indépendamment. Son cout est comparable à "
                "celui d'une propagation avant.",
                "Sa redécouverte et sa popularisation au milieu des années 1980 ont relancé "
                "l'entrainement des réseaux multicouches, dont la règle d'apprentissage était "
                "jusque-là inconnue.",
            ),
        ),
        (
            "Graphes de calcul et différenciation automatique",
            (
                "Un graphe de calcul représente chaque opération élémentaire comme un noeud, et "
                "chaque dépendance entre valeurs comme une arête.",
                "La différenciation automatique applique la règle de la chaine sur ce graphe. "
                "Elle diffère de la différenciation symbolique, qui peut produire des expressions "
                "énormes, et de la différenciation numérique, qui est imprécise.",
                "Les bibliothèques modernes construisent ce graphe à l'exécution, à partir des "
                "opérations réellement effectuées. Cette approche simplifie l'écriture de modèles "
                "complexes.",
                "Elle explique aussi pourquoi les fuites de mémoire sont fréquentes : chaque "
                "valeur intermédiaire reste référencée tant que le graphe n'est pas libéré.",
            ),
        ),
        (
            "Descente de gradient stochastique",
            (
                "Calculer le gradient sur la totalité du jeu d'entrainement à chaque étape est "
                "couteux et inutile lorsque les données sont redondantes. La descente "
                "stochastique estime le gradient sur un petit lot tiré au hasard.",
                "Cet estimateur est bruité, mais non biaisé. Le bruit permet de traverser des "
                "régions plates et de sortir de certains points selles.",
                "Le taux d'apprentissage reste le paramètre le plus critique. Sa valeur se choisit "
                "expérimentalement, souvent par une recherche sur une échelle logarithmique.",
                "Des politiques de décroissance font varier ce taux au fil de l'entrainement : "
                "grand au début pour avancer vite, petit ensuite pour affiner.",
            ),
        ),
        (
            "Variantes modernes de l'optimisation",
            (
                "La méthode du moment accumule une moyenne des gradients passés, ce qui amortit "
                "les oscillations dans les directions où le gradient change de signe.",
                "Les méthodes à taux adaptatif divisent le pas par une estimation de l'amplitude "
                "des gradients récents, variable par variable. Elles sont robustes et demandent "
                "peu de réglage.",
                "L'algorithme Adam, proposé en 2014, combine ces deux idées. C'est l'option par "
                "défaut dans la majorité des implémentations actuelles.",
                "Ces méthodes n'offrent pas de garantie de convergence supérieure. Sur certaines "
                "tâches, une descente stochastique bien réglée les dépasse, au prix d'un réglage "
                "plus fin.",
            ),
        ),
        (
            "Taille des lots et boucles d'entrainement",
            (
                "La taille du lot contrôle l'équilibre entre le cout d'un pas et la qualité de "
                "l'estimation du gradient. Des lots plus grands donnent un gradient plus fidèle, "
                "mais moins de mises à jour par époque.",
                "L'époque désigne une passe complète sur le jeu d'entrainement. Le nombre d'"
                "époques se détermine par arrêt précoce, en observant le score de validation.",
                "L'ordre de présentation des exemples influence le résultat. Mélanger les données "
                "à chaque époque est la pratique standard, et son absence est une cause fréquente "
                "de résultats inexplicables.",
                "Enfin, la reproduction d'un entrainement suppose de fixer la graine du générateur "
                "aléatoire. Sans cette précaution, deux exécutions du même code donnent des "
                "résultats différents.",
            ),
        ),
        (
            "Initialisation des paramètres",
            (
                "Initialiser tous les poids à zéro empêche l'apprentissage : tous les neurones "
                "d'une même couche calculent la même chose et reçoivent le même gradient.",
                "L'initialisation aléatoire doit respecter l'échelle des activations. Une "
                "initialisation trop grande fait diverger le signal, trop petite l'éteint au fil "
                "des couches.",
                "Les schémas usuels tirent les poids dans une distribution dont la variance "
                "dépend du nombre d'entrées et de sorties de la couche. Ce calibrage maintient "
                "l'ordre de grandeur des activations en profondeur.",
                "Ces règles sont intégrées aux bibliothèques. Les modifier sans raison est rarement "
                "utile, mais comprendre leur rôle aide à diagnostiquer les entrainements qui ne "
                "démarrent pas.",
            ),
        ),
        (
            "Régularisation des réseaux",
            (
                "La régularisation par pénalité des poids s'applique comme dans le fascicule 4. "
                "Elle limite l'amplitude des paramètres et réduit la variance.",
                "L'abandon aléatoire, ou dropout, désactive une fraction des neurones à chaque "
                "pas d'entrainement. Le réseau ne peut plus compter sur un neurone particulier, ce "
                "qui l'oblige à répartir l'information.",
                "L'arrêt précoce reste le régularisateur le plus simple et le plus efficace : on "
                "arrête l'entrainement lorsque le score de validation cesse de progresser.",
                "L'augmentation des données est également une forme de régularisation, "
                "particulièrement adaptée aux images, où des transformations géométriques "
                "produisent des exemples plausibles supplémentaires.",
            ),
        ),
        (
            "Normalisation des activations",
            (
                "La normalisation par lots ramène les activations de chaque couche à une moyenne "
                "et un écart-type contrôlés, calculés sur le lot courant.",
                "Elle accélère l'entrainement et permet des taux d'apprentissage plus élevés. "
                "Elle atténue aussi la sensibilité à l'initialisation.",
                "Son inconvénient apparait lorsque la taille des lots est petite : les "
                "statistiques estimées deviennent bruitées. Des variantes calculent ces "
                "statistiques sur d'autres axes.",
                "À l'inférence, les statistiques ne sont plus calculées sur le lot courant mais "
                "estimées pendant l'entrainement. Cette différence de comportement entre "
                "entrainement et inférence est une source classique de bogues discrets.",
            ),
        ),
        (
            "Diagnostiquer un entrainement",
            (
                "Un signal qui disparaît couche après couche empêche les premières couches d'"
                "apprendre. C'est le cas avec des fonctions d'activation saturantes et une "
                "initialisation inadaptée.",
                "Un signal qui explose produit des valeurs non finies et interrompt "
                "l'entrainement. La coupure du gradient, qui borne sa norme, est le remède "
                "standard.",
                "Une perte qui ne diminue pas peut venir d'un taux d'apprentissage trop grand, "
                "d'une erreur dans les données, ou d'une couche de sortie mal adaptée à la tâche.",
                "Suivre la perte d'entrainement et la perte de validation, ainsi que la norme "
                "des gradients, permet de distinguer ces situations. Journaliser des mesures "
                "adaptées coute moins de temps qu'explorer les hyperparamètres au hasard.",
            ),
        ),
        (
            "Réseaux convolutifs",
            (
                "Un réseau convolutif applique des filtres de petite taille sur des voisinages "
                "de l'entrée. Chaque filtre partage ses paramètres sur toute l'image.",
                "Ce partage réduit massivement le nombre de paramètres et introduit une "
                "invariance par translation : un motif est détecté au même endroit quel que soit "
                "sa position dans l'image.",
                "L'empilement de couches de convolution, entrecoupées d'opérations de "
                "sous-échantillonnage, produit des représentations de plus en plus abstraites, "
                "des contours jusqu'aux parties d'objets.",
                "Ce principe découle d'une connaissance du domaine, à savoir la structure locale "
                "des images. C'est pourquoi il reste supérieur, sur ce type de données, à des "
                "architectures entièrement génériques.",
            ),
        ),
        (
            "Les architectures qui ont marqué la période",
            (
                "Les premiers réseaux convolutifs appliqués à la reconnaissance de chiffres "
                "manuscrits datent de la fin des années 1980. Ils contenaient déjà les éléments "
                "essentiels des architectures actuelles.",
                "En 2012, un réseau convolutif profond remporte une compétition de reconnaissance "
                "d'images avec une avance considérable sur les méthodes classiques. Cet épisode "
                "marque le début de la vague actuelle.",
                "Les années suivantes voient l'apparition d'architectures toujours plus profondes, "
                "rendues entrainables par des connexions résiduelles qui facilitent la circulation "
                "du gradient.",
                "Ces architectures reposent sur une idée simple : permettre au signal de traverser "
                "de nombreuses couches sans se dégrader.",
            ),
        ),
        (
            "Séquences et réseaux récurrents",
            (
                "Un réseau récurrent traite une séquence en conservant un état interne mis à jour "
                "à chaque élément. La même transformation est appliquée à chaque pas.",
                "Cette structure convient aux textes, aux séries temporelles et aux signaux, dont "
                "la longueur varie et dont l'ordre porte l'information.",
                "Elle souffre d'une difficulté d'optimisation : le gradient est multiplié de "
                "nombreuses fois le long de la séquence, ce qui le fait disparaitre ou exploser.",
                "Des variantes à portes, apparues dans les années 1990, atténuent ce problème en "
                "apprenant ce qu'il faut conserver et ce qu'il faut oublier. Elles ont longtemps "
                "été l'état de l'art sur les séquences.",
            ),
        ),
        (
            "Mécanismes d'attention",
            (
                "L'attention pondère les éléments d'une entrée en fonction de leur pertinence "
                "pour l'élément courant. Chaque position peut donc consulter directement toutes "
                "les autres.",
                "Cette opération supprime la contrainte de séquentialité : contrairement à un "
                "réseau récurrent, tous les calculs peuvent être menés en parallèle.",
                "L'architecture fondée uniquement sur l'attention, publiée en 2017, a transformé "
                "le traitement du langage, puis progressivement d'autres domaines.",
                "Son cout croit quadratiquement avec la longueur de la séquence, ce qui a "
                "motivé de nombreux travaux sur des variantes plus économes.",
            ),
        ),
        (
            "Pré-entrainement et adaptation",
            (
                "Le pré-entrainement consiste à entrainer un modèle sur une grande quantité de "
                "données non étiquetées, puis à l'adapter à une tâche précise avec peu d'exemples "
                "annotés.",
                "Cette stratégie s'est généralisée au point de devenir la norme. Elle déplace "
                "l'effort : l'essentiel du cout se situe dans la première étape.",
                "Les représentations apprises sont réutilisables. Un modèle pré-entrainé sur du "
                "texte fournit des vecteurs utiles pour la recherche d'information, la "
                "classification ou la similarité sémantique.",
                "L'adaptation par réglage complet des paramètres est couteuse. Des méthodes plus "
                "économiques n'ajustent qu'un petit nombre de paramètres supplémentaires, ou "
                "conditionnent le modèle par des exemples fournis en entrée.",
            ),
        ),
        (
            "Représentations et plongements",
            (
                "Un plongement associe à un objet discret, mot, image ou utilisateur, un vecteur "
                "de nombres réels. Les objets semblables se retrouvent proches dans cet espace.",
                "Ces représentations sont apprises conjointement avec la tâche, sans "
                "supervision directe sur leur forme. Leur structure émerge des régularités du jeu "
                "de données.",
                "Elles servent de base à de nombreuses applications : recherche sémantique, "
                "recommandation, déduplication, détection de similarité entre documents.",
                "Leur interprétation reste limitée. On peut mesurer des proximités et des "
                "directions privilégiées, mais attribuer un sens précis à une coordonnée n'est "
                "généralement pas possible.",
            ),
        ),
        (
            "Mise à l'échelle et loi d'échelle",
            (
                "Depuis 2020, l'observation empirique la plus discutée est la suivante : la "
                "performance des grands modèles s'améliore de façon prévisible lorsqu'on augmente "
                "simultanément le nombre de paramètres et le volume de données.",
                "Ces régularités ont orienté des investissements considérables vers des modèles "
                "toujours plus grands, dans l'hypothèse que la tendance se poursuive.",
                "Elles ont aussi montré leurs limites : au-delà d'un certain point, l'ajout de "
                "paramètres sans données supplémentaires n'apporte pas d'amélioration "
                "proportionnelle.",
                "Rien dans ces observations ne remplace les notions des fascicules précédents. "
                "Un grand modèle mal évalué reste un modèle mal évalué.",
            ),
        ),
        (
            "Cout de calcul et d'énergie",
            (
                "L'entrainement des grands modèles mobilise des moyens matériels considérables, "
                "souvent comparables à la consommation annuelle de plusieurs centaines de foyers.",
                "L'inférence, c'est-à-dire l'utilisation du modèle, domine largement le cout total "
                "lorsque le service est très sollicité. Un modèle légèrement moins précis mais "
                "trois fois plus rapide peut être le meilleur choix industriel.",
                "Ces contraintes ont relancé l'intérêt pour la compression, la quantification et "
                "les architectures économes. Ce sont des questions techniques autant "
                "qu'économiques.",
                "Elles invitent aussi à se demander si la tâche justifie le moyen. Beaucoup de "
                "problèmes traités par un grand modèle sont résolus par une méthode simple, à une "
                "fraction du cout.",
            ),
        ),
        (
            "Interprétabilité et limites",
            (
                "Un réseau entrainé n'expose pas de règle lisible. Les techniques "
                "d'interprétation produisent des indications locales, sous forme de zones "
                "importantes ou d'attributions, sans reconstituer le raisonnement.",
                "Ces indications sont utiles pour détecter des comportements anormaux, par "
                "exemple lorsqu'un modèle s'appuie sur un élément non pertinent de l'image.",
                "Elles ne constituent pas une justification. Un modèle peut produire une "
                "attribution convaincante tout en étant faux, et l'inverse.",
                "Enfin, ces modèles produisent des sorties plausibles sans aucune garantie de "
                "vérité. La vérification des réponses reste, dans la plupart des usages, une "
                "obligation de l'utilisateur ou du système qui l'encadre.",
            ),
        ),
        (
            "Ce qu'il faut retenir de ce fascicule",
            (
                "Un réseau de neurones est une fonction composée, ajustée par descente de "
                "gradient. Ses paramètres n'ont pas d'interprétation individuelle.",
                "La rétropropagation rend le calcul du gradient tractable, à condition que le "
                "signal ne disparaisse ni n'explose au fil des couches. C'est le principal point "
                "de vigilance en pratique.",
                "Les bonnes architectures encodent une connaissance du domaine : partage de "
                "paramètres pour les images, attention pour les séquences. Le choix architectural "
                "n'est jamais neutre.",
                "Enfin, le pré-entrainement a déplacé l'effort vers l'amont, mais il n'exempte ni "
                "d'un protocole d'évaluation rigoureux, ni d'une analyse du cout d'exploitation.",
            ),
        ),
        (
            "Exercices du fascicule 5",
            (
                "Exercice 1. Implémenter un perceptron simple et montrer sur un exemple que la "
                "fonction ou-exclusif n'est pas apprenable sans couche cachée.",
                "Exercice 2. Calculer à la main les gradients d'un réseau à une couche cachée de "
                "deux neurones, pour un exemple unique et une perte quadratique.",
                "Exercice 3. Comparer deux entrainements identiques à la graine aléatoire près, "
                "et mesurer l'écart de performance sur le jeu de validation.",
                "Exercice 4. Sur une tâche de classification d'images fournie, évaluer l'effet de "
                "l'augmentation des données et de l'abandon aléatoire, séparément puis ensemble.",
            ),
        ),
    ),
)


DOCUMENTS: tuple[Document, ...] = (
    DOC_00_INTRODUCTION,
    DOC_01_RECHERCHE,
    DOC_02_LOGIQUE,
    DOC_03_APPRENTISSAGE,
    DOC_04_EVALUATION,
    DOC_05_RESEAUX,
)


DOCX_TITLE = "TP 02 - jeux de données et évaluation"
DOCX_PARAGRAPHS = (
    "Objectif : mettre en pratique le découpage des données et le calcul des métriques "
    "d'évaluation présentées en cours.",
    "Exercice 1. Découper le jeu de données fourni en trois parties, en respectant les "
    "proportions vues en cours. Justifier le choix des proportions en fonction de la taille du "
    "jeu de données.",
    "Exercice 2. Entrainer un arbre de décision sur la partie d'entrainement, puis reporter les "
    "scores obtenus sur les parties de validation et de test. Expliquer tout écart observé.",
    "Exercice 3. Remplacer l'arbre par une forêt aléatoire et comparer les deux séries de "
    "scores. Indiquer si l'écart est plus grand sur le jeu de validation ou sur le jeu de test.",
    "Rendu attendu : un compte rendu de quatre pages au maximum, contenant le protocole, les "
    "tableaux de scores et une conclusion sur le choix du modèle.",
)

PPTX_TITLE = "Séance 09 - recherche dans un espace d'états"
PPTX_SLIDES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Espace d'états",
        (
            "Un état décrit une situation du problème.",
            "Une action transforme un état en un autre état.",
            "Une solution est une suite d'actions menant à un état but.",
        ),
    ),
    (
        "Recherche en largeur",
        (
            "Exploration par niveaux successifs.",
            "Optimale lorsque le cout des actions est uniforme.",
            "Mémoire proportionnelle au nombre d'états du niveau courant.",
        ),
    ),
    (
        "Recherche en profondeur",
        (
            "Exploration d'une branche jusqu'à son extrémité.",
            "Mémoire limitée à la profondeur courante.",
            "Pas de garantie d'optimalité.",
        ),
    ),
    (
        "Algorithme A étoile",
        (
            "Classement par cout payé plus estimation du cout restant.",
            "Optimal si l'heuristique est admissible.",
            "La qualité de l'heuristique fixe le nombre d'états développés.",
        ),
    ),
)

PNG_TITLE = "Evaluation metrics - TP 02"
PNG_ROWS = (
    ("model", "precision", "recall", "F1"),
    ("tree", "0.81", "0.74", "0.77"),
    ("forest", "0.86", "0.83", "0.84"),
    ("network", "0.88", "0.79", "0.83"),
)

# 测试 fixture 用的两页文档：上游带进仓库的 text_two_pages.pdf 是一份真实的课程作业说明
# （元数据里带着课程名），本模块用这份自产文档替换它，行为契约保持一致（两页、文本型 PDF）。
TEST_FIXTURE_TITLE = "TP 03 - de la source brute au passage indexable"
TEST_FIXTURE_PAGES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        TEST_FIXTURE_TITLE,
        (
            "Université de démonstration - Département d'informatique - module INF-204. Travaux "
            "pratiques numéro trois, à réaliser en binôme pendant la séance neuf. Durée prévue : "
            "deux heures. Le travail commencé en séance peut être terminé à la maison.",
            "Objectif général. Ce travail pratique fait parcourir à l'étudiant la chaîne complète "
            "qui va d'un document PDF brut jusqu'à un passage de texte indexable, c'est-à-dire un "
            "fragment de longueur raisonnable, rattaché à sa page d'origine et utilisable par un "
            "moteur de recherche sémantique.",
            "Prérequis. Les notions de la séance trois sont supposées acquises : jeux de données, "
            "protocole expérimental et mesure des performances. Aucune connaissance préalable des "
            "bases de données vectorielles n'est exigée, car les commandes nécessaires figurent "
            "dans l'énoncé.",
            "Exercice 1, extraction. À partir du document fourni, extraire le texte page par page "
            "et vérifier que le nombre de pages obtenu correspond au nombre de pages annoncé par "
            "le lecteur de PDF. Tout écart doit être expliqué dans le compte rendu, en distinguant "
            "les pages dépourvues de couche de texte des erreurs de lecture.",
            "Exercice 2, découpage. Découper le texte de chaque page en fragments d'au plus huit "
            "cents caractères, avec un recouvrement de cent vingt caractères. Chaque fragment doit "
            "conserver un lien vers sa page d'origine et vers le document dont il provient.",
            "Exercice 3, vérification. Mesurer, pour une question portant sur une notion précise "
            "du document, le rang auquel le fragment attendu apparaît dans la liste des résultats. "
            "Comparer ce rang avec et sans recouvrement des fragments.",
            "Livrable. Un compte rendu de trois pages au maximum, comprenant le protocole retenu, "
            "les mesures effectuées et une conclusion sur l'effet du recouvrement. Les scripts "
            "utilisés sont joints en annexe.",
        ),
    ),
    (
        "Modalités de rendu et barème",
        (
            "Rendu. Le compte rendu est déposé au format PDF sur la plateforme du module avant le "
            "dimanche soir qui suit la séance. Un seul dépôt par binôme. Les dépôts tardifs ne sont "
            "pas acceptés, sauf justification médicale transmise au secrétariat.",
            "Barème. La clarté du protocole compte pour quatre points, la justesse des mesures "
            "pour quatre points et la qualité de l'analyse pour deux points. Aucun point n'est "
            "attribué pour la longueur du rapport.",
            "Intégrité. Les échanges d'idées entre binômes sont encouragés, mais chaque binôme "
            "produit ses propres mesures et rédige son propre compte rendu. Les sources externes "
            "utilisées doivent être citées.",
            "Erreurs fréquentes. Comparer deux configurations sur des jeux de données différents, "
            "annoncer un rang moyen sans indiquer le nombre de questions testées, oublier de "
            "vérifier que les fragments couvrent la totalité du texte du document.",
        ),
    ),
)
