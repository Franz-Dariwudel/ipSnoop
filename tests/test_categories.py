"""Kategorien dürfen keine gesammelten Daten verlieren oder Symbole doppelt nutzen."""
import hashlib
from pathlib import Path
import unittest
from ipsnoop import ROOT
from ipsnoop.categories import NAVIGATION,PAGE_ICONS,PAGE_ORDER
from ipsnoop.extended import GROUPS

class CategoryTests(unittest.TestCase):
    def test_all_collected_groups_are_accessible(self):
        self.assertEqual(set(PAGE_ORDER),set(GROUPS)|{'adapters','neighbors','wifi','services','connections','routes','diagnostics','live','system'})
        self.assertEqual(len(PAGE_ORDER),len(set(PAGE_ORDER)))
    def test_each_category_has_a_distinct_delivered_icon(self):
        hashes=[hashlib.sha256((ROOT/'resources'/PAGE_ICONS[name]).read_bytes()).hexdigest() for name in PAGE_ORDER]
        self.assertEqual(len(hashes),len(set(hashes)))
    def test_navigation_labels_exist_in_both_languages(self):
        import json
        for language in ('de','en'):
            data=json.loads((ROOT/'languages'/(language+'.json')).read_text())
            for label in [*PAGE_ORDER,*(group for group,_ in NAVIGATION)]:self.assertTrue(data.get(label),label)
