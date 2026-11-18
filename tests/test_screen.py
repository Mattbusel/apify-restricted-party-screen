import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.screen import clean_names, norm, parse_feed, result_item, screen  # noqa: E402

FEED = [
    {"DATA_SOURCE": "US_DOD_1260H", "RECORD_ID": "us_dod_1260h-bgi-genomics-co-ltd", "NAME_ORG": "BGI Genomics Co., Ltd.",
     "NAMES": [{"NAME_TYPE": "PRIMARY", "NAME_ORG": "BGI Genomics Co., Ltd."}, {"NAME_TYPE": "ALIAS", "NAME_ORG": "BGI"}],
     "LIST_NAME": "DoD Chinese Military Companies (Section 1260H)", "LISTED_ON": "2026-06-10",
     "SOURCE_URL": "https://www.federalregister.gov/d/2026-11571", "SOURCE_DOC": "2026-11571", "PARENT_NAME": "BGI Group"},
    {"DATA_SOURCE": "US_FAR_889", "RECORD_ID": "us_far_889-hangzhou-hikvision", "NAME_ORG": "Hangzhou Hikvision Digital Technology Company",
     "NAMES": [{"NAME_TYPE": "ALIAS", "NAME_ORG": "Hikvision"}], "LIST_NAME": "Section 889", "LISTED_ON": "2019-08-13",
     "SOURCE_URL": "https://www.ecfr.gov/current/title-48/section-52.204-25", "SOURCE_DOC": "FAR 52.204-25", "INCLUDES_AFFILIATES": True},
]
LINES = [json.dumps(r) for r in FEED]


class ScreenTest(unittest.TestCase):
    def setUp(self):
        self.recs = parse_feed(LINES)

    def test_norm_drops_suffixes_and_punctuation(self):
        self.assertEqual(norm("BGI Genomics Co., Ltd."), "bgi genomics")
        self.assertEqual(norm("  Ltd. "), "")

    def test_exact_alias_match(self):
        hits = screen("HIKVISION", self.recs)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["matchType"], "exact")
        self.assertTrue(hits[0]["includesAffiliates"])
        self.assertEqual(hits[0]["matchedName"], "Hikvision")

    def test_suffix_variant_is_exact(self):
        hits = screen("BGI Genomics Company Limited", self.recs)
        self.assertEqual(hits[0]["score"], 1.0)
        self.assertEqual(hits[0]["parentName"], "BGI Group")

    def test_fuzzy_floor(self):
        self.assertTrue(screen("BGI Genomic", self.recs, floor=0.88))
        self.assertFalse(screen("Acme Industrial Supply", self.recs))

    def test_contained_distinctive_name(self):
        recs = parse_feed([json.dumps({**FEED[1], "NAMES": []})])
        hits = screen("Hikvision", recs)
        self.assertEqual((hits[0]["score"], hits[0]["matchType"]), (0.9, "contained"))
        self.assertFalse(screen("Digital Technology", recs))
        self.assertFalse(screen("Hikvision", recs, floor=1.0))

    def test_list_filter(self):
        recs = parse_feed(LINES, ["US_FAR_889"])
        self.assertEqual([r.raw["DATA_SOURCE"] for r in recs], ["US_FAR_889"])
        self.assertFalse(screen("BGI Genomics", recs))

    def test_result_item_and_clean_names(self):
        self.assertEqual(clean_names(["a", " a ", "", None, "b  c", "d"], 3), ["a", "b c", "d"])
        item = result_item("Acme", [], {"release": "v1", "builtAt": "x"})
        self.assertFalse(item["hit"])
        self.assertIsNone(item["bestScore"])


if __name__ == "__main__":
    unittest.main()
