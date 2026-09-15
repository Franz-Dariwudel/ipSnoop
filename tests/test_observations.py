"""Interpretation echter Linux-Feldformate mit eindeutig prüfbaren Grenzen."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from ipsnoop.observations import (normalize_neighbor,group_neighbors,pci_details,classify_adapter,
 default_routes,findings,human_bytes,core_kernel_row)
from ipsnoop.extended import Extended
from ipsnoop.scanner import Scanner

class ObservationTests(unittest.TestCase):
 def test_neighbor_router_null_is_a_flag_and_ages_do_not_collide(self):
  row=normalize_neighbor({'dst':'192.0.2.1','dev':'eth0','lladdr':'00:11:22:33:44:55','router':None,'used':0,'confirmed':5,'updated':10,'probes':2})
  self.assertIs(row['router'],True);self.assertNotIn('updated',row)
  self.assertEqual(row['neighbor_used_s'],0);self.assertEqual(row['neighbor_updated_s'],10)
  self.assertEqual(normalize_neighbor({})['router'],'unknown')
  self.assertIs(normalize_neighbor({'router':False})['router'],False)
 def test_same_mac_groups_addresses_and_interfaces_without_losing_observations(self):
  rows=[normalize_neighbor({'dst':ip,'dev':dev,'lladdr':mac,'updated':i}) for i,(ip,dev,mac) in enumerate([
   ('192.0.2.1','eth0','AA:11:22:33:44:55'),('192.0.2.1','eth1','aa:11:22:33:44:55'),('2001:db8::1','eth0','aa:11:22:33:44:55')])]
  grouped=group_neighbors(rows);self.assertEqual(len(grouped),1)
  self.assertEqual(grouped[0]['ipv4'],['192.0.2.1']);self.assertEqual(grouped[0]['ipv6'],['2001:db8::1'])
  self.assertEqual(grouped[0]['interfaces'],['eth0','eth1']);self.assertEqual(len(grouped[0]['observations']),3)
 def test_unknown_mac_does_not_merge_unrelated_devices(self):
  rows=[{'ip':ip,'name':dev,'mac':mac} for ip,dev,mac in [('192.0.2.1','eth0',''),('192.0.2.2','eth0',''),('192.0.2.1','eth1',''),('192.0.2.3','eth0','00:00:00:00:00:00')]]
  self.assertEqual(len(group_neighbors(rows)),4)
 def test_pci_model_from_reported_label_or_exact_ids(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pci=root/'devices/0000:01:00.0';pci.mkdir(parents=True)
   (pci/'vendor').write_text('0x10ec');(pci/'device').write_text('0x8126')
   net=root/'net';(net/'eth0').mkdir(parents=True);(net/'eth0/device').symlink_to(pci)
   command=Mock(return_value='0000:01:00.0 "Ethernet controller [0200]" "Realtek [10ec]" "RTL8126 5GbE Controller [8126]"\n')
   data=pci_details(net,'eth0',command);self.assertEqual(data['model'],'RTL8126 5GbE Controller [8126]');self.assertEqual(data['model_source'],'lspci')
   command.return_value='';data=pci_details(net,'eth0',command);self.assertEqual(data['model'],'PCI-ID 10ec:8126')
   command.return_value='0000:02:00.0 "x" "x" "Wrong device"';self.assertEqual(pci_details(net,'eth0',command)['model'],'PCI-ID 10ec:8126')
 def test_classification_uses_device_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'eth0/device').mkdir(parents=True);(root/'vnet0').mkdir()
   self.assertEqual(classify_adapter({'ifname':'eth0','link_type':'ether'},root),('physical','ethernet'))
   self.assertEqual(classify_adapter({'ifname':'vnet0','linkinfo':{'info_kind':'tun'}},root),('virtual','tun'))
   self.assertEqual(classify_adapter({'ifname':'lo','link_type':'loopback'},root),('virtual','loopback'))
   self.assertEqual(classify_adapter({'ifname':'missing'},root)[0],'unknown')
 def test_default_routes_keep_families_tables_and_equal_metrics_separate(self):
  rows=[{'family':family,'dst':'default','dev':name,'metric':metric,'table':table} for family,name,metric,table in [('ipv4','eth0',100,'main'),('ipv4','eth1',101,'main'),('ipv6','eth0',200,'main'),('ipv4','vpn',1,'100')]]
  ranked=default_routes(rows);self.assertEqual(len(ranked),3)
  self.assertEqual([r['preference'] for r in ranked],['preferred_metric','alternative','preferred_metric'])
  rows[1]['metric']=100;self.assertEqual(default_routes(rows)[0]['preference'],'equal_candidate')
 def test_drop_review_is_threshold_based_and_driver_counters_are_separate(self):
  counters=[{'name':'eth0','field':'ethtool -S eth0 · rx_missed','value':'12','result':'ok'}]
  self.assertEqual(findings([{'name':'eth0','rx_dropped':'9999'}],counters),[])
  result=findings([{'name':'eth0','rx_dropped':'78464'}],counters)[0]
  self.assertEqual(result['rx_dropped'],78464);self.assertEqual(result['driver_counters'][0]['value'],'12')
  self.assertEqual(result['interpretation'],'driver_counters_not_additive')
 def test_human_bytes_preserves_raw_zero(self):
  self.assertEqual(human_bytes(0),'0.00 B');self.assertEqual(human_bytes(1048576),'1.00 MiB');self.assertEqual(human_bytes(None),'')
 def test_core_parameter_selection_keeps_failure_status(self):
  self.assertTrue(core_kernel_row({'field':'sysctl net · net.ipv4.ip_forward = 0','result':'ok'}))
  self.assertFalse(core_kernel_row({'field':'sysctl net · net.ipv4.conf.eth0.arp_filter = 0','result':'ok'}))
  self.assertTrue(core_kernel_row({'field':'sysctl net','result':'IS202'}))
 def test_sysctl_separates_parameter_and_value(self):
  scanner=Scanner();scanner.last_status='ok';ext=Extended(scanner)
  with patch.object(scanner,'command',return_value='net.ipv4.ip_forward = 0\nnet.ipv4.tcp_congestion_control = cubic\n'):
   ext.query('kernel_params','',['sysctl','net'])
  self.assertEqual(ext.rows[0]['field'],'sysctl net · net.ipv4.ip_forward')
  self.assertEqual(ext.rows[0]['value'],'0');self.assertTrue(core_kernel_row(ext.rows[0]))
  self.assertEqual(ext.rows[1]['value'],'cubic')
 def test_bluetooth_empty_controller_is_neutral_and_failure_remains_error(self):
  scanner=Scanner();ext=Extended(scanner)
  def command(args):
   scanner.last_status='ok'
   return 'LoadState=loaded\nActiveState=active\n' if args[0]=='systemctl' else ''
  with patch.object(scanner,'command',side_effect=command):ext.bluetooth()
  result={r['field']:r for r in ext.rows}
  self.assertIs(result['bluetooth_service_available']['value'],True)
  self.assertIs(result['bluetooth_controller_available']['value'],False)
  self.assertEqual(result['bluetooth_default_controller']['value'],'not_present')
  self.assertTrue(all(r['result']=='ok' for r in ext.rows))
  ext=Extended(scanner)
  def failure(args):scanner.last_status='IS202';return ''
  with patch.object(scanner,'command',side_effect=failure):ext.bluetooth()
  self.assertTrue(any(r['result']=='IS202' for r in ext.rows))

if __name__=='__main__':unittest.main()
