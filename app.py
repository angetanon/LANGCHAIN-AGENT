import os
from pathlib import Path

import certifi
import requests
import streamlit as st
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_tavily import TavilySearch
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langsmith import Client
from langsmith.utils import LangSmithError
from openai import OpenAIError


def load_configuration() -> None:
    load_dotenv(Path(__file__).with_name(".env"))
    os.environ["SSL_CERT_FILE"] = certifi.where()


def add_language_instruction(prompt: PromptTemplate) -> PromptTemplate:
    instruction = (
        "Answer in the same language as the user's question. "
        "Keep proper nouns and technical terms unchanged when appropriate.\n\n"
    )
    return PromptTemplate.from_template(
        instruction + prompt.template,
        template_format=prompt.template_format,
        metadata=prompt.metadata,
    )


@tool
def get_weather_data(city: str) -> str:
    """Fetch current weather information for a city using Weatherstack."""
    api_key = os.getenv("WEATHERSTACK_API_KEY")
    if not api_key:
        raise ValueError("WEATHERSTACK_API_KEY manque dans la configuration.")
    response = requests.get(
        "https://api.weatherstack.com/current",
        params={"access_key": api_key, "query": city},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if "current" not in data:
        error_code = data.get("error", {}).get("code", "inconnu")
        raise ValueError(
            f"Weatherstack ne fournit pas de meteo (code {error_code}). "
            "Verifiez la cle, la ville et la prise en charge HTTPS de votre abonnement."
        )
    current = data["current"]
    return (
        f"City: {city}\n"
        f"Temperature: {current['temperature']} C\n"
        f"Weather: {current['weather_descriptions'][0]}\n"
        f"Humidity: {current['humidity']}%"
    )


def create_executor(use_weather: bool) -> AgentExecutor:
    tools: list[BaseTool] = [TavilySearch(max_results=2)]
    if use_weather:
        tools.append(get_weather_data)
    llm = ChatOpenAI(model="gpt-3.5-turbo-0125", temperature=0, timeout=30, max_retries=1)
    # Public prompt explicitly trusted for this demo, as in the notebook.
    prompt = Client().pull_prompt(
        "hwchase17/react",
        include_model=False,
        dangerously_pull_public_prompt=True,
    )
    prompt = add_language_instruction(prompt)
    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        return_intermediate_steps=True,
        max_iterations=6,
        max_execution_time=120,
    )


def main() -> None:
    st.set_page_config(page_title="Agent recherche et meteo", page_icon="🌍", layout="wide")
    load_configuration()
    st.title("Agent recherche et météo")
    st.caption("Posez une question : l'agent utilise Tavily et, si nécessaire, Weatherstack.")

    with st.sidebar:
        st.header("Configuration")
        for key in ("OPENAI_API_KEY", "TAVILY_API_KEY", "WEATHERSTACK_API_KEY"):
            st.write(f"{'✅' if os.getenv(key) else '❌'} {key}")
        st.caption("Les clés sont lues depuis .env et ne sont jamais affichées.")
        use_weather = st.checkbox("Activer l'outil météo", value=True)
        st.info(
            "Chaque question est indépendante. Les appels OpenAI, Tavily "
            "et Weatherstack peuvent consommer vos crédits."
        )
        st.caption("Le prompt public de confiance hwchase17/react est téléchargé au lancement d'une question.")

    with st.form("question_form"):
        question = st.text_area(
            "Votre question",
            placeholder="Quelle est la capitale de l'Inde et quelle météo y fait-il actuellement ?",
            height=120,
        )
        submitted = st.form_submit_button("Interroger l'agent", type="primary")

    if submitted:
        st.session_state.pop("result", None)
        required = ["OPENAI_API_KEY", "TAVILY_API_KEY"]
        if use_weather:
            required.append("WEATHERSTACK_API_KEY")
        missing = [key for key in required if not os.getenv(key)]
        if not question.strip():
            st.warning("Saisissez une question avant de lancer l'agent.")
        elif missing:
            st.error("Clés manquantes dans .env : " + ", ".join(missing))
        else:
            try:
                with st.spinner("Recherche et préparation de la réponse..."):
                    executor = create_executor(use_weather)
                    result = executor.invoke({"input": question.strip()})
                    st.session_state["result"] = result
            except (OpenAIError, LangSmithError, requests.RequestException):
                st.error(
                    "Un service externe est inaccessible ou a refusé la requête. "
                    "Vérifiez la connexion, les clés API, les quotas et les abonnements."
                )
            except ValueError as error:
                st.error(f"L'agent n'a pas pu terminer la demande : {error}")

    if "result" in st.session_state:
        result = st.session_state["result"]
        st.subheader("Réponse")
        st.markdown(result["output"])
        with st.expander("Outils utilisés et résultats"):
            for action, observation in result.get("intermediate_steps", []):
                st.markdown(f"**Outil :** `{action.tool}`")
                st.write("Entrée :", action.tool_input)
                st.write(observation)


if __name__ == "__main__":
    main()