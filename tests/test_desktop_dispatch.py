"""Desktopbenutzer auch bei grafischer Installation ohne sudo-Umgebung finden."""
import runpy
import unittest
from unittest.mock import patch
from ipsnoop import ROOT

class DesktopDispatchTests(unittest.TestCase):
    def setUp(self):self.users=runpy.run_path(str(ROOT/'packaging/desktop-dispatch'))['users']
    def test_graphical_session_without_sudo_environment(self):
        with patch.dict('os.environ',{},clear=True),patch('subprocess.check_output',side_effect=['c1 1000 user seat0 tty7\n','User=1000\nType=x11\nActive=yes\n']):
            self.assertEqual(self.users(),{1000})
    def test_ambiguous_graphical_sessions_defer_to_login(self):
        with patch.dict('os.environ',{},clear=True),patch('subprocess.check_output',side_effect=['c1 1000 a\nc2 1001 b\n','User=1000\nType=x11\nActive=yes\n','User=1001\nType=wayland\nActive=yes\n']):
            self.assertEqual(self.users(),set())
    def test_no_session_defer_to_login(self):
        with patch.dict('os.environ',{},clear=True),patch('subprocess.check_output',return_value=''):
            self.assertEqual(self.users(),set())
