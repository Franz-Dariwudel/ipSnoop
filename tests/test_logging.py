"""Sitzungsprotokoll nur beim Start leeren; Fehler und Benutzerdaten erhalten."""
from contextlib import redirect_stderr,redirect_stdout
import io
import json
import logging
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from ipsnoop import config
from ipsnoop.__main__ import main


class LoggingTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);(self.root/'logs').mkdir()
        self.path=self.root/'logs/errors.log';self.path.write_text('Alte Meldung\n')
        self.log=logging.Logger('ipsnoop-test')
        for target,options in (
            ('ipsnoop.config.ROOT',{'new':self.root}),
            ('ipsnoop.config.logging.getLogger',{'return_value':self.log}),
        ):
            replacement=patch(target,**options);replacement.start();self.addCleanup(replacement.stop)
        self.addCleanup(self.close_handlers)

    def close_handlers(self):
        for handler in self.log.handlers[:]:
            self.log.removeHandler(handler);handler.close()

    def test_start_clears_only_own_logs_and_keeps_new_messages(self):
        for name in ('errors.log.1','errors.log.2','other.log','errors.log.notes'):
            (self.root/'logs'/name).write_text('Inhalt')
        (self.root/'config').mkdir();settings=self.root/'config/settings.json';settings.write_text('{}')
        log=config.logger(reset=True)
        self.assertEqual(self.path.read_text(),'')
        for name in ('errors.log.1','errors.log.2'):self.assertFalse((self.root/'logs'/name).exists())
        for name in ('other.log','errors.log.notes'):self.assertEqual((self.root/'logs'/name).read_text(),'Inhalt')
        self.assertEqual(settings.read_text(),'{}')
        log.error('Erste neue Meldung');config.logger().warning('Zweite neue Meldung')
        text=self.path.read_text()
        self.assertIn('Erste neue Meldung',text);self.assertIn('Zweite neue Meldung',text)
        self.assertNotIn('Alte Meldung',text);self.assertEqual(len(log.handlers),1)

    def test_next_start_resets_and_reopens_handler(self):
        config.logger(reset=True).error('Voriger Start')
        old=self.log.handlers[0]
        config.logger(reset=True).error('Aktueller Start')
        self.assertIsNone(old.stream)
        self.assertNotIn('Voriger Start',self.path.read_text())
        self.assertIn('Aktueller Start',self.path.read_text())

    def test_lazy_logger_alone_does_not_reset(self):
        config.logger().warning('Neue Meldung')
        self.assertIn('Alte Meldung',self.path.read_text())
        self.assertIn('Neue Meldung',self.path.read_text())

    def test_reset_failure_falls_back_to_stderr(self):
        stderr=io.StringIO();stdout=io.StringIO()
        with patch('ipsnoop.config.Path.write_text',side_effect=PermissionError('denied')), redirect_stderr(stderr),redirect_stdout(stdout):
            config.logger(reset=True).error('Aktueller Fehler')
        self.assertIn('IS101',stderr.getvalue());self.assertIn('Aktueller Fehler',stderr.getvalue())
        self.assertEqual(stdout.getvalue(),'');self.assertEqual(self.path.read_text(),'Alte Meldung\n')

    def test_admin_log_uses_directory_owner(self):
        owner=(self.root/'logs').stat()
        with patch('ipsnoop.config.os.geteuid',return_value=0),patch('ipsnoop.config.os.chown') as chown:
            config.logger(reset=True)
        chown.assert_called_once_with(self.path,owner.st_uid,owner.st_gid)

    def test_scan_resets_before_collecting(self):
        def scan():
            self.assertEqual(self.path.read_text(),'')
            return {'adapters':[{'name':'test'}]}
        with patch('sys.argv',['ipsnoop','--scan']),patch('ipsnoop.__main__.Scanner') as scanner,redirect_stdout(io.StringIO()) as output:
            scanner.return_value.scan.side_effect=scan
            self.assertEqual(main(),0)
        self.assertEqual(json.loads(output.getvalue())['adapters'][0]['name'],'test')

    def test_gui_resets_before_application_start(self):
        def run(args):
            self.assertEqual(self.path.read_text(),'')
            config.logger().error('Startfehler bleibt erhalten');return 0
        app=Mock();app.return_value.run.side_effect=run
        with patch('sys.argv',['ipsnoop']),patch.dict('sys.modules',{'ipsnoop.app':SimpleNamespace(Application=app)}):
            self.assertEqual(main(),0)
        self.assertIn('Startfehler bleibt erhalten',self.path.read_text())

    def test_help_and_version_do_not_erase_logs(self):
        for option in ('--help','--version'):
            with patch('sys.argv',['ipsnoop',option]),redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as result:
                main()
            self.assertEqual(result.exception.code,0)
            self.assertEqual(self.path.read_text(),'Alte Meldung\n')


if __name__=='__main__':unittest.main()
