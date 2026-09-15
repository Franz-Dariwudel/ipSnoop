"""Regression: nativer Dateidialog muss den Methodenaufruf überleben."""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from ipsnoop.app import Window,Gtk,Gio,export_csv
from ipsnoop.config import Translator


class CsvDialogTests(unittest.TestCase):
    def setUp(self):
        if not Gtk.init_check():self.skipTest('Grafische Sitzung erforderlich')
        # Absichtliche Fehler dürfen weder Benutzerlogs füllen noch persönliche
        # Einstellungen lesen oder ändern. Der erwartete Logaufruf wird geprüft.
        self.test_log=Mock()
        for target,options in (
            ('ipsnoop.app.logger',{'return_value':self.test_log}),
            ('ipsnoop.config.logger',{'return_value':self.test_log}),
            ('ipsnoop.app.load',{'return_value':({'language':'de','interval':0,'show_empty':False},[])}),
            ('ipsnoop.app.save',{}),
        ):
            replacement=patch(target,**options);replacement.start();self.addCleanup(replacement.stop)
        self.window=Window(None,autostart=False)
        self.window.snapshot={k:[] for k in ('adapters','neighbors','wifi','services','routes')}
        self.window.snapshot['system']={'hostname':'example'}
    def tearDown(self):
        self.window.close_window();self.window.destroy()
    def test_native_dialog_survives_gc_and_reuses_then_cancels(self):
        self.window.export_dialog();gc.collect()
        chooser=self.window._csv_chooser
        self.assertIsNotNone(chooser);self.assertTrue(chooser.get_visible())
        self.window.export_dialog();self.assertIs(self.window._csv_chooser,chooser)
        chooser.emit('response',Gtk.ResponseType.CANCEL)
        self.assertIsNone(self.window._csv_chooser)
        self.window.export_dialog();self.assertIsNotNone(self.window._csv_chooser)
    def test_accept_exports_frozen_snapshot_and_releases_dialog(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'network.csv';fake=Mock();fake.get_file.return_value=Gio.File.new_for_path(str(target))
            with patch('ipsnoop.app.Gtk.FileChooserNative',return_value=fake):self.window.export_dialog()
            callback=fake.connect.call_args.args[1]
            self.window.snapshot['system']['hostname']='changed-after-click'
            callback(fake,Gtk.ResponseType.ACCEPT)
            self.assertIn('example',target.read_text(encoding='utf-8-sig'))
            self.assertNotIn('changed-after-click',target.read_text(encoding='utf-8-sig'))
            self.assertIsNone(self.window._csv_chooser)
    def test_cancel_does_not_write(self):
        fake=Mock()
        with patch('ipsnoop.app.Gtk.FileChooserNative',return_value=fake):self.window.export_dialog()
        with patch('ipsnoop.app.export_csv') as export:
            fake.connect.call_args.args[1](fake,Gtk.ResponseType.CANCEL)
            export.assert_not_called()
        self.assertIsNone(self.window._csv_chooser)
    def test_failed_save_reports_error_and_releases_dialog(self):
        fake=Mock();fake.get_file.return_value=None;self.window.message=Mock()
        with patch('ipsnoop.app.Gtk.FileChooserNative',return_value=fake):self.window.export_dialog()
        fake.connect.call_args.args[1](fake,Gtk.ResponseType.ACCEPT)
        self.window.message.assert_called_once();self.assertIsNone(self.window._csv_chooser)
        self.test_log.exception.assert_called_once_with('IS301: CSV')
    def test_export_mode_and_privacy_are_frozen_when_dialog_opens(self):
        fake=Mock();fake.get_file.return_value=Gio.File.new_for_path('/tmp/ipsnoop-dialog-test.csv')
        self.window.export_mode='full';self.window.anonymize=True
        with patch('ipsnoop.app.Gtk.FileChooserNative',return_value=fake):self.window.export_dialog()
        fake.set_current_name.assert_called_once_with('ipSnoop-Diagnose.csv')
        self.window.export_mode='standard';self.window.anonymize=False
        with patch('ipsnoop.app.export_csv') as export:
            fake.connect.call_args.args[1](fake,Gtk.ResponseType.ACCEPT)
            self.assertEqual(export.call_args.args[3:],('full',True))
        self.assertIsNone(self.window._csv_chooser)
    def test_text_mode_writes_short_report(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'report.txt';fake=Mock();fake.get_file.return_value=Gio.File.new_for_path(str(target))
            self.window.export_mode='text'
            with patch('ipsnoop.app.Gtk.FileChooserNative',return_value=fake):self.window.export_dialog()
            fake.set_current_name.assert_called_once_with('ipSnoop.txt')
            fake.connect.call_args.args[1](fake,Gtk.ResponseType.ACCEPT)
            content=target.read_text()
            self.assertIn('Kurzbericht',content);self.assertIn('Erkannte Adapter: 0',content)
            self.assertNotIn('section;entry;field;value',content)
