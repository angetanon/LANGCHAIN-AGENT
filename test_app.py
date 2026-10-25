import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from langchain_core.language_models.fake import FakeListLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import Tool
from streamlit.testing.v1 import AppTest

import app


def render_app() -> None:
    import app

    app.main()


class InterfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-openai",
                "TAVILY_API_KEY": "test-tavily",
                "WEATHERSTACK_API_KEY": "test-weather",
            },
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        configuration = patch.object(app, "load_configuration")
        configuration.start()
        self.addCleanup(configuration.stop)
        self.executor = Mock()
        factory = patch.object(app, "create_executor", return_value=self.executor)
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.page = AppTest.from_function(render_app).run()

    def submit(self, question: str) -> None:
        self.page.text_area[0].set_value(question)
        self.page.button[0].click().run()

    def test_initial_page_does_not_call_services(self) -> None:
        self.assertFalse(self.page.exception)
        self.factory.assert_not_called()

    def test_empty_question(self) -> None:
        self.submit("   ")
        self.assertTrue(self.page.warning)
        self.factory.assert_not_called()

    def test_missing_key(self) -> None:
        del os.environ["WEATHERSTACK_API_KEY"]
        self.submit("Meteo a Paris ?")
        self.assertIn("WEATHERSTACK_API_KEY", self.page.error[0].value)
        self.factory.assert_not_called()

    def test_success_and_result_persists(self) -> None:
        self.executor.invoke.return_value = {
            "output": "Paris est la capitale.",
            "intermediate_steps": [
                (SimpleNamespace(tool="search", tool_input="capitale France"), "Paris")
            ],
        }
        self.submit("  Capitale de la France ?  ")
        self.assertFalse(self.page.exception)
        self.executor.invoke.assert_called_once_with({"input": "Capitale de la France ?"})
        self.assertIn("Paris est la capitale.", [item.value for item in self.page.markdown])
        self.page.run()
        self.assertIn("Paris est la capitale.", [item.value for item in self.page.markdown])
        self.factory.assert_called_once()

    def test_search_without_weather_key(self) -> None:
        del os.environ["WEATHERSTACK_API_KEY"]
        self.executor.invoke.return_value = {"output": "Paris", "intermediate_steps": []}
        self.page.checkbox[0].uncheck().run()
        self.submit("Capitale de la France ?")
        self.factory.assert_called_once_with(False)
        self.assertFalse(self.page.error)

    def test_service_error_is_visible_without_secret(self) -> None:
        self.executor.invoke.side_effect = requests.ConnectionError("test-weather")
        self.submit("Meteo ?")
        self.assertTrue(self.page.error)
        self.assertNotIn("test-weather", self.page.error[0].value)
        self.assertNotIn("result", self.page.session_state)


class WeatherTests(unittest.TestCase):
    def test_missing_key_does_not_call_api(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch.object(app.requests, "get") as get:
            with self.assertRaisesRegex(ValueError, "WEATHERSTACK_API_KEY"):
                app.get_weather_data.invoke({"city": "Paris"})
            get.assert_not_called()

    def test_weather_success_and_api_error(self) -> None:
        response = Mock()
        response.json.return_value = {
            "current": {
                "temperature": 20,
                "weather_descriptions": ["Sunny"],
                "humidity": 50,
            }
        }
        with patch.dict(os.environ, {"WEATHERSTACK_API_KEY": "test-weather"}):
            with patch.object(app.requests, "get", return_value=response) as get:
                result = app.get_weather_data.invoke({"city": "Paris"})
                self.assertIn("20 C", result)
                self.assertIn("50%", result)
                get.assert_called_once_with(
                    "https://api.weatherstack.com/current",
                    params={"access_key": "test-weather", "query": "Paris"},
                    timeout=15,
                )
                response.raise_for_status.assert_called_once()
                response.json.return_value = {"error": {"code": 101}}
                with self.assertRaisesRegex(ValueError, "101"):
                    app.get_weather_data.invoke({"city": "Paris"})


class AgentTests(unittest.TestCase):
    def test_language_instruction_is_added_to_prompt(self) -> None:
        prompt = PromptTemplate.from_template("{input}\n{agent_scratchpad}")

        instructed_prompt = app.add_language_instruction(prompt)

        self.assertIn(
            "Answer in the same language as the user's question",
            instructed_prompt.template,
        )
        self.assertEqual(instructed_prompt.input_variables, prompt.input_variables)

    def test_real_executor_with_fake_services(self) -> None:
        search = Tool(
            name="search",
            description="Search for a city.",
            func=lambda query: "Paris",
        )
        model = FakeListLLM(
            responses=[
                "Action: search\nAction Input: capitale France",
                "Final Answer: Paris",
            ]
        )
        prompt = PromptTemplate.from_template(
            "{tools}\n{tool_names}\n{input}\n{agent_scratchpad}"
        )
        with (
            patch.object(app, "TavilySearch", return_value=search),
            patch.object(app, "ChatOpenAI", return_value=model),
            patch.object(app, "Client") as client,
        ):
            client.return_value.pull_prompt.return_value = prompt
            executor = app.create_executor(use_weather=True)
            result = executor.invoke({"input": "Capitale de la France ?"})
            self.assertEqual(result["output"], "Paris")
            self.assertEqual(result["intermediate_steps"][0][1], "Paris")
            self.assertIn(app.get_weather_data, executor.tools)
            client.return_value.pull_prompt.assert_called_once_with(
                "hwchase17/react",
                include_model=False,
                dangerously_pull_public_prompt=True,
            )


if __name__ == "__main__":
    unittest.main()
