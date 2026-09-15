"""Alle ausgelieferten Sprachen: Platzhalter, Fehlerhilfe und dynamische Erkennung."""
import json
import re
import tempfile
import unittest
from pathlib import Path
from string import Formatter
from ipsnoop import ROOT, VERSION
from ipsnoop.config import Translator

class LanguageTests(unittest.TestCase):
    def test_ten_catalogs_and_matching_help(self):
        codes={'de','en','es','fr','pt','zh','hi','ar','ru','tr'}
        self.assertEqual({p.stem for p in (ROOT/'languages').glob('*.json')},codes)
        self.assertEqual({p.stem for p in (ROOT/'help').glob('*.html')},codes)
        base=json.loads((ROOT/'languages/en.json').read_text())
        def fields(text):return sorted(field for _,field,_,_ in Formatter().parse(text) if field)
        for code in codes:
            with self.subTest(language=code):
                catalog=json.loads((ROOT/'languages'/f'{code}.json').read_text())
                self.assertEqual(set(catalog),set(base))
                for key in base:
                    self.assertTrue(catalog[key].strip(),key)
                    self.assertEqual(fields(catalog[key]),fields(base[key]),key)
                help_text=(ROOT/'help'/f'{code}.html').read_text()
                self.assertIn(f'lang="{code}"',help_text)
                self.assertIn(VERSION,help_text)
                for key in base:
                    if re.fullmatch(r'IS\d{3}',key):self.assertIn(key,help_text)
                self.assertNotIn('start.sh',help_text)
                self.assertNotIn('admin-start',help_text)
                if code=='ar':self.assertIn('dir="rtl"',help_text)

    def test_added_removed_and_single_language_without_help(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            path.joinpath('en.json').write_text('{"language.name":"English","refresh":"Refresh"}')
            tr=Translator('de',path)
            self.assertEqual(tr.language,'en')
            path.joinpath('ar.json').write_text((ROOT/'languages/ar.json').read_text())
            tr.reload();self.assertEqual(set(tr.catalogs),{'en','ar'})
            tr.language='ar';self.assertEqual(tr('refresh'),'تحديث')
            path.joinpath('ar.json').unlink();tr.reload();self.assertEqual(tr.language,'en')

if __name__=='__main__':unittest.main()
