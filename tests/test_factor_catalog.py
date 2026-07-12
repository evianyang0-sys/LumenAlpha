import unittest

from lumen_qlib.factor_catalog import build_lumen_catalog, build_payload, build_qlib_catalog


class FactorCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = build_qlib_catalog() + build_lumen_catalog()

    def item(self, name, family):
        return next(
            item
            for item in self.items
            if item["name"] == name and item["family"] == family
        )

    def test_every_catalog_item_has_a_calculation_explanation(self):
        self.assertEqual(607, len(self.items))
        missing = [item["name"] for item in self.items if not str(item["formula"]).strip()]
        self.assertEqual([], missing)

        stats = build_payload(self.items)["stats"]
        self.assertEqual(607, stats["formulaCount"])
        self.assertEqual(0, stats["missingFormulaCount"])
        self.assertEqual(1, stats["unimplementedCount"])

    def test_standard_signal_formula_is_extracted_from_source_condition(self):
        formula = self.item("MACD金叉", "SignalGenerator")["formula"]
        self.assertIn("DIF[t] > DEA[t]", formula)
        self.assertIn("DIF[t-1] <= DEA[t-1]", formula)

    def test_advanced_signal_formula_matches_thresholds(self):
        formula = self.item("突破20日新高", "AdvancedSignalGenerator")["formula"]
        self.assertIn("Max(Close[t-20:t-1])", formula)
        self.assertIn("1.3×VOL_MA5[t]", formula)

    def test_unimplemented_signal_is_disclosed(self):
        formula = self.item("N型反包", "AdvancedSignalGenerator")["formula"]
        self.assertIn("当前源码未实现", formula)


if __name__ == "__main__":
    unittest.main()
