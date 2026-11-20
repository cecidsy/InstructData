import json
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

import pandas as pd
from openpyxl import load_workbook

from instructdata.chat import ModelConfig, execute, model_plan


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            "region": ["华东", "华南", "华东", "西北"],
            "amount": [120, 80, 200, None],
        })

    def test_filter_then_aggregate_and_chart_follow_up(self):
        plan = {"operation": "sum", "field": "amount", "filter": {"field": "region", "comparison": "eq", "value": "华东"}}
        self.assertIn("320", execute(plan, self.data).message)
        chart = {"operation": "sum", "field": "amount", "group": "region", "chart": "bar"}
        result = execute(chart, self.data)
        self.assertEqual(result.chart, "bar")
        self.assertEqual(result.table.iloc[0].tolist(), ["华东", 320])
        follow_up = {**chart, "chart": "line"}
        self.assertEqual(execute(follow_up, self.data).chart, "line")

    def test_excel_fill_and_download(self):
        self.data["备注"] = ["=1+1", "保留", "", None]
        plan = {"operation": "fill_missing", "field": "amount", "value": 0}
        result = execute(plan, self.data, excel=True)
        workbook = load_workbook(BytesIO(result.download))
        self.assertEqual(workbook.active["B5"].value, 0)
        self.assertEqual(workbook.active["C2"].value, "=1+1")
        self.assertEqual(workbook.active["C2"].data_type, "s")
        self.assertTrue(pd.isna(self.data.loc[3, "amount"]))

    def test_model_receives_schema_without_data_rows(self):
        with patch("instructdata.chat.urlopen") as urlopen:
            body = {"choices": [{"message": {"content": json.dumps({"operation": "count"})}}]}
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(body).encode()
            plan = model_plan("几条记录？", self.data, config=ModelConfig("https://example.test/chat", "test-model"))
        self.assertEqual(plan, {"operation": "count"})
        request = urlopen.call_args.args[0]
        user_content = json.loads(request.data)["messages"][1]["content"]
        self.assertIn("region", user_content)
        self.assertNotIn("华东", user_content)
        with self.assertRaises(ValueError):
            execute({"operation": "run_sql"}, self.data)

    def test_http_404_distinguishes_base_url_from_model_id(self):
        for path, hint in (("/v1", "/chat/completions"), ("/v1/chat/completions", "模型 ID")):
            url = f"https://example.test{path}"
            with self.subTest(path=path), patch(
                "instructdata.chat.urlopen", side_effect=HTTPError(url, 404, "Not Found", {}, None)
            ):
                with self.assertRaisesRegex(ValueError, hint):
                    model_plan("几条记录？", self.data, config=ModelConfig(url, "test-model"))

    def test_overview_and_general_reply(self):
        overview = execute({"operation": "summary", "preview": True}, self.data)
        self.assertTrue(overview.preview.equals(self.data))
        self.assertEqual(overview.table["字段"].tolist(), ["region", "amount"])
        self.assertEqual(execute({"operation": "reply", "message": "可以分析数据。"}, None).message, "可以分析数据。")
