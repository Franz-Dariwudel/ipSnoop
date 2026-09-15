import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ipsnoop.scanner import Scanner,escaped_columns,subnet
from ipsnoop.config import Translator
from install import install,uninstall


class CoreTests(unittest.TestCase):
    def test_wifi_escaped_colons_and_backslashes(self):
        self.assertEqual(escaped_columns(r'Office\:WiFi:aa\:bb\:cc:one\\two'),['Office:WiFi','aa:bb:cc','one\\two'])
    def test_subnet_ipv4_ipv6_and_invalid(self):
        self.assertEqual(subnet('192.0.2.10',24),'192.0.2.0/24')
        self.assertEqual(subnet('2001:db8::5',64),'2001:db8::/64')
        self.assertEqual(subnet('invalid',24),'')
    def test_zero_values_and_default_route_association(self):
        scanner=Scanner()
        with patch.object(scanner,'command',return_value=''),patch.object(scanner,'read',return_value='0'):
            a=scanner.adapter({'ifname':'lo','link_type':'loopback','mtu':0,'addr_info':[{'local':'127.0.0.1','prefixlen':8,'family':'inet'}]},[{'dev':'other','dst':'default','gateway':'192.0.2.1'}],{})
        self.assertEqual(a['mtu'],0);self.assertEqual(a['rx_errors'],'0');self.assertEqual(a['gateway'],'')
        self.assertEqual(a['ipv4'],'127.0.0.1/8')
    def test_link_mode_maximum_not_current_speed(self):
        scanner=Scanner()
        def command(args):
            if args==['ethtool','eth0']:return 'Supported link modes: 100baseT/Full\n                        1000baseT/Full\nSupported pause frame use: No\nSpeed: 100Mb/s\nDuplex: Full'
            return ''
        with patch.object(scanner,'command',side_effect=command),patch.object(scanner,'read',return_value=''):
            a=scanner.adapter({'ifname':'eth0','link_type':'ether'},[],{})
        self.assertEqual(a['speed'],'100Mb/s');self.assertEqual(a['max_speed'],'1000.0 Mb/s')
    def test_malformed_tool_json_is_reported(self):
        scanner=Scanner()
        with patch.object(scanner,'command',return_value='{}'):self.assertEqual(scanner.json_command(['ip','-j']),[])
        self.assertEqual(scanner.issues[0]['code'],'IS203')
    def test_missing_helper_is_reported(self):
        scanner=Scanner()
        with patch('ipsnoop.scanner.shutil.which',return_value=None):self.assertEqual(scanner.command(['ip','-j']), '')
        self.assertEqual(scanner.issues,[{'code':'IS201','detail':'ip'}])
    def test_single_language_and_dynamic_english_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'fr.json').write_text('{"hello":"Bonjour"}')
            t=Translator(directory=p);self.assertEqual(t.language,'fr')
            (p/'en.json').write_text('{"extra":"Extra"}');t.reload();self.assertEqual(t('extra'),'Extra')
            (p/'fr.json').unlink();t.reload();self.assertEqual(t.language,'en')
    def test_install_uninstall_preserves_runtime_and_foreign_files(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);source=p/'source';source.mkdir()
            (source/'build-info.json').write_text('{"kind":"source"}')
            (source/'program.py').write_text('# test')
            target=install(source,p/'target');(target/'config/personal.json').write_text('{}')
            uninstall(target)
            self.assertFalse((target/'program.py').exists());self.assertFalse((target/'installation.json').exists())
            self.assertTrue((target/'config/personal.json').exists())
    def test_clean_uninstall_removes_all_installation_files(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);source=p/'source';source.mkdir();(source/'build-info.json').write_text('{"kind":"source"}')
            target=install(source,p/'target');uninstall(target);self.assertFalse(target.exists())
    def test_uninstall_rejects_escape_before_deleting(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);target=p/'target';target.mkdir();victim=p/'keep';victim.write_text('keep')
            (target/'installation.json').write_text(json.dumps({'files':['../keep'],'directories':[]}))
            with self.assertRaises(ValueError):uninstall(target)
            self.assertTrue(victim.exists())
    def test_translations_have_equal_keys_and_error_help(self):
        from ipsnoop import ROOT
        de=json.loads((ROOT/'languages/de.json').read_text());en=json.loads((ROOT/'languages/en.json').read_text())
        self.assertEqual(set(de),set(en))
        for code in ('de','en'):
            help_text=(ROOT/'help'/(code+'.html')).read_text()
            for key in de:
                if key.startswith('IS'):self.assertIn(key,help_text)


if __name__=='__main__':unittest.main()
