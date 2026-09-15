"""DEB-Dateijournal erfasst nur neue Programmdaten, keine vorhandenen Dateien."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ipsnoop import prepare_data,register_data_file,ROOT

class SystemDataTests(unittest.TestCase):
    def test_generated_data_removed_existing_files_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);data=home/'.local/share/ipsnoop'
            (data/'languages').mkdir(parents=True)
            original=data/'languages/de.json';original.write_text('my existing translation')
            export=data/'my-report.txt';export.write_text('my report')
            with patch('ipsnoop.DATA_ROOT',data):
                prepare_data()
                register_data_file(data/'config/settings.json')
                (data/'config/settings.json').write_text('{}')
            records=json.loads((data/'.installed-files.json').read_text())
            self.assertNotIn('languages/de.json',records['files'])
            self.assertIn('config/settings.json',records['files'])
            with patch('pathlib.Path.home',return_value=home):
                exec(compile((ROOT/'packaging/data-cleanup').read_text(),'data-cleanup','exec'),{})
            self.assertEqual(original.read_text(),'my existing translation')
            self.assertEqual(export.read_text(),'my report')
            self.assertFalse((data/'config').exists())
            self.assertTrue((data/'languages').is_dir())
    def test_fresh_installation_leaves_no_data_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);data=home/'.local/share/ipsnoop'
            with patch('ipsnoop.DATA_ROOT',data):prepare_data()
            with patch('pathlib.Path.home',return_value=home):
                exec(compile((ROOT/'packaging/data-cleanup').read_text(),'data-cleanup','exec'),{})
            self.assertFalse(data.exists())
