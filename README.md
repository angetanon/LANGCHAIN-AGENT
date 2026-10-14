conda create -n langagent python=3.11 -y
conda activate langagent

Or with venv:

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate


pip install -r requirements.txt

## Interface web Streamlit

Depuis PowerShell, a la racine du projet :

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run .\app.py
```

L'interface reprend l'agent ReAct de `venv/research/agent_demo.ipynb`.
Configurez ces variables dans le fichier `.env` a la racine, sans publier vos cles :

```dotenv
OPENAI_API_KEY=votre_cle_openai
TAVILY_API_KEY=votre_cle_tavily
WEATHERSTACK_API_KEY=votre_cle_weatherstack
```

Saisissez une question puis cliquez sur **Interroger l'agent**. La reponse
et les resultats des outils sont affiches. Chaque question est independante.
La meteo peut etre desactivee pour utiliser uniquement la recherche Tavily.
Weatherstack utilise HTTPS : votre abonnement doit prendre en charge cet acces.
Le prompt public de confiance `hwchase17/react` est charge via LangSmith,
avec autorisation explicite comme dans le notebook. Les appels aux services
externes peuvent consommer des credits.

Validation locale sans appels aux API :

```powershell
python -m unittest test_app -v
```

## Structure du projet

Arborescence actuelle simplifiee (les fichiers internes de Git et les
dependances installees ne sont pas detailles) :

```text
LANGCHAIN-AGENT\
|-- .vscode\
|   |-- langchain.code-snippets  # Extraits de code pour VS Code
|   |-- settings.json           # Configuration de l'editeur
|   `-- tasks.json              # Tache de lancement Streamlit
|-- venv\
|   |-- research\
|   |   `-- agent_demo.ipynb    # Demonstration interactive de l'agent
|   |-- Scripts\               # Interpreteur Python et activation du venv
|   `-- Lib\                   # Dependances Python installees
|-- .env                       # Cles API locales - ne pas publier
|-- .gitignore                 # Fichiers exclus du suivi Git
|-- app.py                     # Interface Streamlit et logique de l'agent web
|-- main.py                    # Demonstration en ligne de commande
|-- test_app.py                # Tests de l'interface, de la meteo et de ReAct
|-- requirements.txt           # Dependances du projet
`-- README.md                  # Installation, utilisation et architecture
```

Les trois points d'entree sont `app.py` pour l'interface web, `main.py`
pour le terminal et `venv\research\agent_demo.ipynb` pour le notebook.
Le dossier `__pycache__` est genere automatiquement par Python.

**Attention :** le notebook se trouve actuellement dans `venv`.
Conservez-en une copie avant de supprimer ou recreer cet environnement.
Pour une future reorganisation, il est preferable de placer les notebooks
dans un dossier `research` a la racine, independant du venv.

## Schema d'architecture

Le schema suivant represente l'architecture actuelle. Le projet utilise
un seul agent ReAct avec deux outils, et non un pipeline multi-agent.
Les blocs applicatifs ci-dessous sont definis dans `app.py`.

```text
                    ┌─────────────────────────────────────────┐
                    │         Utilisateur - navigateur        │
                    └────────────────────┬────────────────────┘
                                         │ Question
                    ┌────────────────────▼────────────────────┐
                    │          Streamlit UI (app.py)          │
                    │      Saisie, configuration, resultats   │
                    │       Cles API : .env / environnement   │
                    └────────────────────┬────────────────────┘
                                         │ Demande validee
                    ┌────────────────────▼────────────────────┐
                    │              AgentExecutor              │
                    │       Orchestration de la boucle ReAct  │
                    │       6 iterations maximum              │
                    └────────────────────┬────────────────────┘
                                         │ Planification
                    ┌────────────────────▼────────────────────┐
                    │           Agent ReAct unique            │
                    │       Choix des actions et des outils   │
                    └──────────┬───────────────────┬──────────┘
                               │                   │
           ┌───────────────────▼───────┐   ┌───────▼───────────────────┐
           │        ChatOpenAI         │   │     Prompt LangSmith      │
           │   gpt-3.5-turbo-0125       │   │     hwchase17/react        │
           │       API OpenAI          │   │   Charge a la creation     │
           └───────────────────────────┘   └───────────────────────────┘

       Outils executes par AgentExecutor selon les actions de l'agent
                                         │
                         ┌───────────────┴───────────────┐
                         │                               │
           ┌─────────────▼─────────────┐   ┌─────────────▼─────────────┐
           │    TavilySearchResults    │   │      get_weather_data     │
           │       Recherche web       │   │      Meteo optionnelle     │
           └─────────────┬─────────────┘   └─────────────┬─────────────┘
                         │ HTTPS                         │ HTTPS
           ┌─────────────▼─────────────┐   ┌─────────────▼─────────────┐
           │         API Tavily        │   │      API Weatherstack     │
           │    2 resultats maximum    │   │        Meteo actuelle      │
           └───────────────────────────┘   └───────────────────────────┘

       Resultats des outils ──▶ AgentExecutor ──▶ Etape ReAct suivante
       Reponse finale       ──▶ Etat de session ──▶ Affichage Streamlit
```

### Composants

| Composant | Role |
|---|---|
| Streamlit | Saisie de la question, verification de la configuration et affichage des resultats. |
| AgentExecutor | Execute la boucle ReAct et appelle les outils choisis par l'agent. |
| ChatOpenAI | Utilise le modele OpenAI pour choisir les actions et produire la reponse finale. |
| LangSmith | Fournit le prompt public de confiance, sans charger de modele associe. |
| TavilySearchResults | Effectue les recherches web avec un maximum de deux resultats. |
| get_weather_data | Interroge Weatherstack via HTTPS lorsque la meteo est activee. |
| Etat de session | Conserve la derniere reponse et les etapes des outils entre les rafraichissements Streamlit. |

### Fonctionnement et limites

1. L'application charge la configuration depuis `.env` et les variables
   d'environnement, puis verifie les cles necessaires avant tout appel.
2. A chaque question valide, elle charge le prompt et construit un nouvel agent.
3. L'agent choisit les outils utiles ; leurs resultats alimentent les etapes
   suivantes jusqu'a la reponse finale ou l'arret de la boucle.
4. L'interface affiche la reponse et permet de consulter les outils utilises.

Il n'y a pas de base de donnees ni de memoire conversationnelle.
L'etat de session conserve seulement le dernier resultat : les questions
restent independantes. L'execution est limitee a six iterations et un budget
de boucle de 120 secondes, controle entre les etapes, avec des delais d'attente
specifiques pour les appels OpenAI et Weatherstack.

`main.py` et `venv/research/agent_demo.ipynb` sont des points d'entree
alternatifs pour la demonstration ; l'interface ne les execute pas.
Les tests de `test_app.py` simulent les services externes pour valider
l'interface, l'outil meteo et l'assemblage ReAct sans consommer de credits.