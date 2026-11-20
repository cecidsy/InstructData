import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from streamlit.testing.v1 import AppTest

from instructdata.sources import (
    ROW_LIMIT,
    database_connection,
    list_tables,
    open_workbook,
    read_sheet,
    read_table,
    sqlite_url,
)


class ExcelTests(unittest.TestCase):
    def test_select_sheet_and_read_limit(self):
        upload = io.BytesIO()
        upload.name = "sales.xlsx"
        with pd.ExcelWriter(upload, engine="openpyxl") as writer:
            pd.DataFrame({"amount": [120, 200]}).to_excel(writer, sheet_name="Sales", index=False)
            pd.DataFrame({"id": range(ROW_LIMIT + 5)}).to_excel(writer, sheet_name="Long", index=False)

        with open_workbook(upload) as workbook:
            self.assertEqual(workbook.sheet_names, ["Sales", "Long"])
            self.assertEqual(read_sheet(workbook, "Sales")["amount"].tolist(), [120, 200])
            self.assertEqual(len(read_sheet(workbook, "Long")), ROW_LIMIT + 1)


class SQLiteTests(unittest.TestCase):
    def setUp(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = folder / "示例 #1.db"
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                'CREATE TABLE "sales records" (id INTEGER PRIMARY KEY, region TEXT, amount INTEGER)'
            )
            connection.executemany(
                'INSERT INTO "sales records" VALUES (?, ?, ?)',
                [(3, "east", 200), (1, "east", 120), (2, "south", 80)],
            )
        self.url = sqlite_url(str(self.path))

    def test_read_quoted_table_in_primary_key_order(self):
        self.assertEqual(list_tables(self.url, None), ["sales records"])
        self.assertEqual(read_table(self.url, None, "sales records")["id"].tolist(), [1, 2, 3])

    def test_connection_is_read_only(self):
        with self.assertRaises(OperationalError), database_connection(self.url) as connection:
            connection.execute(text('DELETE FROM "sales records"'))

    def test_web_form_reads_sqlite_data(self):
        self.enterContext(patch("instructdata.model_settings.SETTINGS_PATH", self.path.with_suffix(".json")))
        entrypoint = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(entrypoint), default_timeout=20).run()
        self.assertFalse(app.exception)
        app.radio[0].set_value("关系数据库").run()
        app.text_input[0].set_value(str(self.path))
        app.button[0].click().run()
        self.assertFalse(app.error)
        self.assertEqual(app.selectbox[1].value, "sales records")
        app.button[1].click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(app.metric[0].value, "3")
        with patch.dict("os.environ", {"INSTRUCTDATA_MODEL_URL": "", "INSTRUCTDATA_MODEL": ""}):
            app.run()
            self.assertTrue(app.chat_input[0].proto.disabled)
        with patch.dict("os.environ", {"INSTRUCTDATA_MODEL_URL": "https://example.test/chat",
                                       "INSTRUCTDATA_MODEL": "test-model"}), patch(
            "instructdata.chat_view.model_plan",
            return_value={"operation": "sum", "field": "amount", "group": "region", "chart": "bar"},
        ) as planner:
            app.run()
            app.chat_input[0].set_value("各地一共卖了多少？帮我画出来").run()
            self.assertEqual(planner.call_count, 1)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.chat_message), 2)
        self.assertEqual(app.chat_message[1].dataframe[0].value.iloc[0].tolist(), ["east", 320])
