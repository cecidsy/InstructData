import unittest

import pandas as pd

from instructdata.analysis import column_summary, group_summary


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            "region": ["east", "south", "east", None],
            "amount": [120, None, 200, 30],
        })

    def test_column_summary(self):
        summary = column_summary(self.data)
        self.assertEqual(summary.loc["region", "非空不同值"], 2)
        self.assertEqual(summary.loc["amount", "缺失值"], 1)

    def test_group_summary_includes_missing_group(self):
        totals = group_summary(self.data, "region", "求和", "amount")
        averages = group_summary(self.data, "region", "平均值", "amount")
        counts = group_summary(self.data, "region", "计数")
        self.assertEqual(totals.loc["east"], 320)
        self.assertTrue(pd.isna(totals.loc["south"]))
        self.assertEqual(totals[totals.index.isna()].item(), 30)
        self.assertEqual(averages.loc["east"], 160)
        self.assertEqual(counts.sum(), len(self.data))
