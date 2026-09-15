"""Downloads: keine Teilinhalte, keine überschriebenen Nutzerdateien."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ipsnoop.downloads import install_language,LIMIT

CATALOG=b'{"language.name":"Espa\\u00f1ol","refresh":"Actualizar"}'
HELP=b'<html lang="es"><body>Ayuda</body></html>'

class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'app';self.root.mkdir()
        self.downloads=Path(self.tmp.name)/'Downloads';self.downloads.mkdir()
        (self.downloads/'private.txt').write_text('keep')
    def test_install_and_preserve_existing_without_network(self):
        with patch('ipsnoop.downloads.urlopen',side_effect=[io.BytesIO(CATALOG),io.BytesIO(HELP)]):
            self.assertEqual(install_language('es',self.root,self.downloads),2)
        self.assertEqual((self.root/'languages/es.json').read_bytes(),CATALOG)
        with patch('ipsnoop.downloads.urlopen') as fetch:
            self.assertEqual(install_language('es',self.root,self.downloads),0);fetch.assert_not_called()
    def tearDown(self):
        self.assertEqual([p.name for p in self.downloads.iterdir()],['private.txt'])
        self.assertEqual((self.downloads/'private.txt').read_text(),'keep')
    def test_existing_custom_help_is_preserved(self):
        (self.root/'help').mkdir();(self.root/'help/es.html').write_text('Custom help')
        with patch('ipsnoop.downloads.urlopen',return_value=io.BytesIO(CATALOG)):
            self.assertEqual(install_language('es',self.root,self.downloads),1)
        self.assertEqual((self.root/'help/es.html').read_text(),'Custom help')
    def test_failed_second_download_writes_nothing(self):
        with patch('ipsnoop.downloads.urlopen',side_effect=[io.BytesIO(CATALOG),TimeoutError('offline')]):
            with self.assertRaises(TimeoutError):install_language('es',self.root,self.downloads)
        self.assertEqual(list(self.root.rglob('*')),[])
    def test_invalid_or_oversized_catalog_rejected(self):
        for data in [b'[]',b'{"language.name":1}',b'\xff',b'x'*(LIMIT+1)]:
            with self.subTest(data=data[:30]),patch('ipsnoop.downloads.urlopen',return_value=io.BytesIO(data)):
                with self.assertRaises((ValueError,UnicodeError)):install_language('es',self.root,self.downloads)
        self.assertEqual(list(self.root.rglob('*')),[])
    def test_wrong_help_language_rejected(self):
        with patch('ipsnoop.downloads.urlopen',side_effect=[io.BytesIO(CATALOG),io.BytesIO(b'<html lang="en"></html>')]):
            with self.assertRaises(ValueError):install_language('es',self.root,self.downloads)
        self.assertEqual(list(self.root.rglob('*')),[])
    def test_untrusted_code_rejected_without_network(self):
        with patch('ipsnoop.downloads.urlopen') as fetch:
            with self.assertRaises(ValueError):install_language('../de',self.root,self.downloads)
            fetch.assert_not_called()
    def test_write_error_leaves_no_temporary_files(self):
        with patch('ipsnoop.downloads.urlopen',side_effect=[io.BytesIO(CATALOG),io.BytesIO(HELP)]),patch('ipsnoop.downloads.os.link',side_effect=PermissionError('read only')):
            with self.assertRaises(PermissionError):install_language('es',self.root,self.downloads)
        self.assertEqual(list(self.root.rglob('.*')),[])

if __name__=='__main__':unittest.main()
