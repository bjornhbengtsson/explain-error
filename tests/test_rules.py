"""Every rule must load, match its own examples, and only use placeholders it captures."""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from explain_error.matcher import _PLACEHOLDER, explain, fill, find_location, load_rules  # noqa: E402

ID_FORMAT = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class RuleDatabaseTests(unittest.TestCase):
    rules = load_rules()

    def test_has_rules(self):
        self.assertGreaterEqual(len(self.rules), 100)

    def test_ids_are_unique_and_kebab_case(self):
        seen = set()
        for r in self.rules:
            self.assertRegex(r.id, ID_FORMAT, r.id)
            self.assertNotIn(r.id, seen, f"duplicate id {r.id}")
            seen.add(r.id)

    def test_every_rule_has_examples_and_fixes(self):
        for r in self.rules:
            with self.subTest(rule=r.id):
                self.assertTrue(r.examples, "add at least one example error")
                self.assertTrue(r.fixes, "add at least one fix")

    def test_every_example_matches_its_rule(self):
        for r in self.rules:
            for example in r.examples:
                with self.subTest(rule=r.id, example=example):
                    self.assertIsNotNone(r.pattern.search(example))

    def test_placeholders_name_captured_groups(self):
        for r in self.rules:
            groups = set(r.pattern.groupindex)
            for text in (r.title, r.explain, *r.fixes):
                for m in _PLACEHOLDER.finditer(text):
                    # Braces that aren't group names are allowed (code like {user}),
                    # but a filter means it was meant as a placeholder.
                    if m.group(2):
                        with self.subTest(rule=r.id, placeholder=m.group(0)):
                            self.assertIn(m.group(1), groups)

    def test_examples_fill_every_placeholder(self):
        for r in self.rules:
            for example in r.examples:
                groups = r.pattern.search(example).groupdict()
                with self.subTest(rule=r.id, example=example):
                    self.assertNotIn("<", fill(r.title, groups).replace("<!", ""))


class MatchingTests(unittest.TestCase):
    def test_pip_name_mapping(self):
        [best, *_] = explain("ModuleNotFoundError: No module named 'cv2'")
        self.assertEqual(best.rule.id, "py-module-not-found")
        self.assertIn("pip install opencv-python", best.fixes[0])

    def test_submodule_maps_to_root_package(self):
        [best, *_] = explain("ModuleNotFoundError: No module named 'sklearn.ensemble'")
        self.assertIn("pip install scikit-learn", best.fixes[0])

    def test_specific_rule_beats_generic(self):
        text = "AttributeError: 'NoneType' object has no attribute 'group'"
        self.assertEqual(explain(text)[0].rule.id, "py-attr-none")

    def test_ts_beats_node_for_ts2307(self):
        text = "src/a.ts(1,1): error TS2307: Cannot find module 'zod' or its corresponding type declarations."
        self.assertEqual(explain(text)[0].rule.id, "ts2307-cannot-find-module")

    def test_no_match(self):
        self.assertEqual(explain("everything is fine"), [])

    def test_python_location_prefers_user_code(self):
        tb = '''Traceback (most recent call last):
  File "/home/me/app/main.py", line 12, in <module>
    run()
  File "/home/me/app/main.py", line 8, in run
    requests.get(url)
  File "/venv/lib/python3.12/site-packages/requests/api.py", line 73, in get
    return request("get", url)
ValueError: bad url'''
        loc = find_location(tb)
        self.assertEqual((loc.file, loc.line), ("/home/me/app/main.py", 8))

    def test_node_location(self):
        trace = """TypeError: Cannot read properties of undefined (reading 'map')
    at List (/app/src/List.jsx:7:22)
    at renderWithHooks (/app/node_modules/react-dom/cjs/react-dom.development.js:14985:18)"""
        loc = find_location(trace)
        self.assertEqual((loc.file, loc.line, loc.column), ("/app/src/List.jsx", 7, 22))

    def test_rust_location(self):
        text = "error[E0382]: borrow of moved value: `s`\n --> src/main.rs:5:20\n"
        loc = find_location(text)
        self.assertEqual(str(loc), "src/main.rs:5:20")


if __name__ == "__main__":
    unittest.main()
