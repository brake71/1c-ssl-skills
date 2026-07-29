import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "ci" / "validate_key_methods.py"
API_PATH = REPO_ROOT / "skills" / "bsp" / "scripts" / "bsp_api.py"
FIXTURE_SRC = REPO_ROOT / "tests" / "fixtures" / "cf"
VALID_REFERENCE = REPO_ROOT / "tests" / "fixtures" / "references" / "valid.md"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validator = load_module(VALIDATOR_PATH, "validate_key_methods")
bsp_api = load_module(API_PATH, "bsp_api_for_tests")


class BspApiParserTests(unittest.TestCase):
    def setUp(self):
        self.module_path = (
            FIXTURE_SRC / "CommonModules" / "ТестовыйМодуль" / "Ext" / "Module.bsl"
        )
        self.methods = {
            name: region
            for name, region, _signature, _doc in bsp_api.parse_export_methods(self.module_path)
        }

    def test_regions_and_non_exported_method(self):
        self.assertEqual(
            self.methods["СтабильныйМетод"],
            bsp_api.STABLE_REGION,
        )
        self.assertEqual(
            self.methods["ВложенныйСтабильныйМетод"],
            bsp_api.STABLE_REGION,
        )
        self.assertEqual(
            self.methods["СлужебныйМетод"],
            "СлужебныйПрограммныйИнтерфейс",
        )
        self.assertNotIn("ВнутреннийМетод", self.methods)

    def test_signature_longer_than_thirty_lines(self):
        self.assertIn("ДлиннаяСигнатура", self.methods)


class ApiClaimsValidatorTests(unittest.TestCase):
    def test_valid_fixture(self):
        collection = validator.collect_claims([VALID_REFERENCE])
        self.assertEqual(len(collection.claims), 6)
        self.assertEqual(len(collection.files_with_claims), 1)

        issues, checked = validator.validate_claims(
            collection.claims,
            FIXTURE_SRC,
            bsp_api.parse_export_methods,
        )
        self.assertEqual(checked, 6)
        self.assertEqual(issues, [])

    def test_missing_positive_claim_is_error(self):
        collection = self._collection(
            "`ТестовыйМодуль.Опечатка() Экспорт` — регион "
            "`ПрограммныйИнтерфейс`.\n"
        )
        issues, _checked = validator.validate_claims(
            collection.claims,
            FIXTURE_SRC,
            bsp_api.parse_export_methods,
        )
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["severity"], "ERROR")
        self.assertIn("not found as an export", issues[0]["message"])

    def test_stale_negative_claim_is_error(self):
        collection = self._collection(
            "`ТестовыйМодуль.СтабильныйМетод()` — метод не существует.\n"
        )
        issues, _checked = validator.validate_claims(
            collection.claims,
            FIXTURE_SRC,
            bsp_api.parse_export_methods,
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("documented as absent", issues[0]["message"])

    def test_region_mismatch_is_error(self):
        collection = self._collection(
            "`ТестовыйМодуль.СлужебныйМетод() Экспорт` — регион "
            "`ПрограммныйИнтерфейс`.\n"
        )
        issues, _checked = validator.validate_claims(
            collection.claims,
            FIXTURE_SRC,
            bsp_api.parse_export_methods,
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("declared region", issues[0]["message"])

    def test_coverage_floor_cannot_be_zero(self):
        collection = validator.collect_claims([VALID_REFERENCE])
        issues = validator.evaluate_coverage(
            collection,
            min_claims=7,
            min_files=1,
            min_coverage=95,
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("unique API claims", issues[0])
        with self.assertRaises(Exception):
            validator._integer_at_least(validator.DEFAULT_MIN_CLAIMS)("599")
        with self.assertRaises(Exception):
            validator._coverage_percent("94.9")

    def _collection(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claim.md"
            path.write_text(text, encoding="utf-8")
            return validator.collect_claims([path])


if __name__ == "__main__":
    unittest.main()
