import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from instructdata.model_settings import load_model_settings


class ModelSettingsTests(unittest.TestCase):
    def test_form_saves_and_loads_in_a_new_session(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        path = folder / ".streamlit" / "model-settings.json"
        self.enterContext(patch("instructdata.model_settings.SETTINGS_PATH", path))
        self.enterContext(patch.dict("os.environ", {
            "INSTRUCTDATA_MODEL_URL": "", "INSTRUCTDATA_MODEL": "", "INSTRUCTDATA_MODEL_API_KEY": "",
        }))

        entrypoint = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(entrypoint), default_timeout=20).run()
        app.sidebar.text_input[0].set_value("https://model.example/v1/chat/completions")
        app.sidebar.text_input[1].set_value("demo-model")
        app.sidebar.text_input[2].set_value("test-key")
        app.sidebar.button[0].click().run()
        self.assertFalse(app.exception)
        config = load_model_settings()
        self.assertEqual(config.api_key, "test-key")

        reopened = AppTest.from_file(str(entrypoint), default_timeout=20).run()
        self.assertFalse(reopened.exception)
        self.assertEqual(reopened.sidebar.text_input[0].value, config.url)
        self.assertEqual(reopened.sidebar.text_input[1].value, config.name)
        self.assertEqual(reopened.sidebar.text_input[2].value, "")
        self.assertFalse(reopened.chat_input[0].proto.disabled)
