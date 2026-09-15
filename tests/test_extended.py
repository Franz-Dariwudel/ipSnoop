"""Neue Abfragen mit reproduzierbaren Linux-Ausgaben und Fehlerpfaden prüfen."""
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ipsnoop.extended import Extended,dhcp_options,protocol_counters,socket_rows,mac_vendor,oui_database,diagnostic,flatten
from ipsnoop.scanner import Scanner


class ExtendedTests(unittest.TestCase):
    def test_dhcp_ipv4_ipv6_preserves_values(self):
        self.assertEqual(dhcp_options({'DHCP4.OPTION[1]':'dhcp_lease_time = 3600','DHCP6.OPTION[2]':'client_id = 00:01:02','GENERAL.STATE':'100'}),{'DHCP4.dhcp_lease_time':'3600','DHCP6.client_id':'00:01:02'})

    def test_protocol_headers_do_not_become_counters(self):
        result=protocol_counters('Tcp: ActiveOpens RetransSegs\nTcp: 12 0\nUdp: InErrors\nUdp: 3\n')
        self.assertEqual(result,{'Tcp.ActiveOpens':'12','Tcp.RetransSegs':'0','Udp.InErrors':'3'})

    def test_socket_processes_and_missing_permissions(self):
        with patch('ipsnoop.extended.os.readlink',side_effect=PermissionError):
            rows=socket_rows('tcp ESTAB 0 0 [::1]:80 [::1]:40000 users:(("app",pid=99999999,fd=3))\nudp UNCONN 0 0 0.0.0.0:53 0.0.0.0:*')
        self.assertEqual(rows[0]['pid'],'99999999');self.assertEqual(rows[0]['peer'],'[::1]:40000');self.assertEqual(rows[0]['executable'],'')
        self.assertEqual(rows[1]['pid'],'')

    def test_local_mac_never_misidentified(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'oui';p.write_text('00-11-22   (hex)     Example Hardware\n')
            db=oui_database([p])
            self.assertEqual(mac_vendor('00:11:22:33:44:55',db),'Example Hardware')
            self.assertEqual(mac_vendor('02:11:22:33:44:55',db),'locally_administered')

    def test_failed_firewall_is_not_empty_or_disabled(self):
        scanner=Scanner();extended=Extended(scanner)
        def failure(args):scanner.last_status='IS202';return ''
        with patch.object(scanner,'command',side_effect=failure):extended.query('firewall','',['nft','list','ruleset'])
        self.assertEqual(extended.rows[0]['result'],'IS202')
        self.assertEqual(extended.rows[0]['value'],'')
        scanner.last_status='ok'
        with patch.object(scanner,'command',return_value=''):extended.query('firewall','',['nft','list','ruleset'])
        self.assertEqual(extended.rows[1]['result'],'empty')

    def test_flatten_preserves_false_and_zero(self):
        self.assertEqual(dict(flatten({'flag':False,'stats':[0]})),{'flag':False,'stats[0]':0})

    def test_diagnostic_rejects_options_and_shell_input(self):
        with patch.object(Scanner,'command') as command:
            for target in ('-c 999','x;touch /tmp/wrong','$(id)','foo bar',''):
                with self.assertRaises(ValueError):diagnostic('ping',target)
            command.assert_not_called()

    def test_diagnostic_has_bounded_explicit_arguments(self):
        with patch.object(Scanner,'command',return_value='4 packets transmitted') as command:
            result=diagnostic('ping','127.0.0.1')
            command.assert_called_once_with(['ping','-n','-c','4','-W','2','127.0.0.1'],timeout=20)
            self.assertEqual(result['result'],'ok')

    def test_virtual_speed_is_not_physical_bandwidth(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'virbr0').mkdir();scanner=Scanner(Path(d))
            with patch.object(scanner,'command',return_value='Speed: 10000Mb/s'):
                data=scanner.adapter({'ifname':'virbr0','link_type':'ether'},[],{})
            self.assertEqual(data['speed'],'not_applicable')
            self.assertEqual(data['max_speed'],'not_applicable')

    def test_extended_csv_includes_nested_and_error_data(self):
        from ipsnoop.app import export_csv
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.csv'
            export_csv(p,{'extended':[{'value':0,'result':'IS202'}],'connections':[{'pid':'5'}],'diagnostics':[{'value':'=formula'}]},lambda x:x)
            rows=list(csv.reader(io.StringIO(p.read_text(encoding='utf-8-sig')),delimiter=';'))
        self.assertIn(['extended','1','value','0'],rows)
        self.assertIn(['extended','1','result','IS202'],rows)
        self.assertIn(['diagnostics','1','value',"'=formula"],rows)

if __name__=='__main__':unittest.main()
