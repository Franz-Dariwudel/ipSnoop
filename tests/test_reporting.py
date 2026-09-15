"""Stabile Exportfelder, kompakte Berichte und Datenschutz prüfen."""
import copy,csv,io,json,tempfile,unittest
from pathlib import Path
from ipsnoop.config import Translator
from ipsnoop.observations import normalize_neighbor,group_neighbors
from ipsnoop.reporting import export_csv,export_text,report_data,summary

class ReportTests(unittest.TestCase):
 def test_csv_keys_are_language_independent_and_no_ui_placeholders(self):
  row=normalize_neighbor({'dst':'192.0.2.1','dev':'eth0','updated':5,'router':None})
  snapshot={'neighbors':group_neighbors([row]),'neighbor_records':[row]}
  with tempfile.TemporaryDirectory() as d:
   values=[]
   for lang in ('de','en'):
    p=Path(d)/(lang+'.csv');export_csv(p,snapshot,Translator(lang),'full');values.append(p.read_text(encoding='utf-8-sig'))
   self.assertEqual(values[0],values[1]);self.assertNotIn('{count}',values[0]);self.assertNotIn('{time}',values[0])
   rows=list(csv.reader(io.StringIO(values[0]),delimiter=';'))
   self.assertIn(['neighbor_records','1','neighbor_updated_s','5'],rows)
   self.assertIn(['neighbor_records','1','router','true'],rows)
 def test_standard_report_limits_kernel_and_full_keeps_all(self):
  details=[{'group':'kernel_params','field':f'sysctl net · net.ipv4.conf.eth{i}.arp_filter = 0','value':0,'result':'ok'} for i in range(3000)]
  details.append({'group':'kernel_params','field':'sysctl net · net.ipv4.ip_forward = 0','value':0,'result':'ok'})
  data={'extended':details}
  self.assertEqual(len(report_data(data)['extended']),1);self.assertEqual(len(report_data(data,'full')['extended']),3001)
 def test_unsupported_summary_deduplicates_without_creating_issues(self):
  row={'group':'adapter_extra','name':'eth0','field':'ethtool -l eth0','value':'','result':'unsupported'}
  result=report_data({'extended':[row,row]})
  self.assertEqual(result['summary']['unsupported_count'],1);self.assertEqual(result['summary']['failed_query_count'],0);self.assertEqual(result['issues'],[])
 def test_anonymization_removes_identifiers_from_nested_and_free_text(self):
  snapshot={'system':{'hostname':'privatepc','machine_id':'secret-machine','boot_id':'secret-boot'},
   'adapters':[{'name':'eth0','mac':'aa:11:22:33:44:55','ipv4':'192.0.2.88/24','ipv6':'2001:db8::88/64','connection':'personal connection'}],
   'services':[{'local':'[2001:db8::88]:443','peer':'192.0.2.88:12345','process':'secret-process','pid':'12345','user':'secret-user','executable':'/home/secret-user/app'}],
   'neighbors':[{'hostname':['hidden.example.org'],'mac':'aa:11:22:33:44:55','observations':[{'hostname':'hidden.example.org','ip':'192.0.2.88'}]}],
   'extended':[{'group':'tcp_quality','name':'eth0','field':'ss · secret-process hidden.example.org','value':'arbitrary secret-machine text','result':'ok'}],
   'diagnostics':[{'name':'hidden.example.org','field':'ping','value':'secret trace'}],
   'wifi':[{'ssid':'private-wifi','bssid':'aa:11:22:33:44:55'}]}
  original=copy.deepcopy(snapshot);data=report_data(snapshot,'full',True);text=json.dumps(data)
  for secret in ('privatepc','secret-machine','secret-boot','personal connection','aa:11:22:33:44:55','192.0.2.88','2001:db8::88','secret-process','secret-user','/home/','hidden.example.org','private-wifi','secret trace'):
   self.assertNotIn(secret,text)
  self.assertIn('MAC-1',text);self.assertIn('IP4-1',text);self.assertIn('IP6-1',text);self.assertEqual(snapshot,original)
 def test_export_formula_protection_and_unknown_router(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'report.csv';export_csv(p,{'neighbors':[{'hostname':'=formula','router':'unknown'}]},lambda x:x)
   rows=list(csv.reader(io.StringIO(p.read_text(encoding='utf-8-sig')),delimiter=';'))
   self.assertIn(['neighbors','1','hostname',"'=formula"],rows);self.assertIn(['neighbors','1','router','unknown'],rows)
 def test_txt_contains_timing_and_actionable_findings(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'report.txt';export_text(p,{'scan':{'duration_s':6.2},'findings':[{'code':'rx_drops_review','name':'eth0','rx_dropped':20000,'threshold':10000}]},Translator('de'))
   text=p.read_text();self.assertIn('6.2',text);self.assertIn('20000',text);self.assertIn('kein Nachweis eines Hardwaredefekts',text)

if __name__=='__main__':unittest.main()
