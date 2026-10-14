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