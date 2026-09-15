import unittest
from unittest.mock import patch
from ipsnoop.names import NameResolver,lookup
class NamesTests(unittest.TestCase):
 def test_local_hosts_take_priority(self):
  n=[{'ip':'192.0.2.1','name':'eth0'}]
  with patch('ipsnoop.names.lookup') as query:NameResolver().resolve(n,{'192.0.2.1':'router'});query.assert_not_called()
  self.assertEqual(n[0]['hostname'],'router')
 def test_cache_and_negative_result(self):
  r=NameResolver();n=[{'ip':'192.0.2.1','name':'eth0'}]
  with patch('ipsnoop.names.lookup',return_value=('router','name_resolved')) as query:
   r.resolve(n,{});r.resolve(n,{});self.assertEqual(query.call_count,1)
  self.assertEqual(n[0]['hostname'],'router')
 def test_batch_limit_and_next_refresh(self):
  r=NameResolver();n=[{'ip':f'192.0.2.{i}','name':'eth0'} for i in range(1,21)]
  with patch('ipsnoop.names.lookup',return_value=('','name_unresolved')) as query:
   r.resolve(n,{});self.assertEqual(query.call_count,16);self.assertEqual(n[-1]['hostname_status'],'name_pending')
   r.resolve(n,{});self.assertEqual(query.call_count,20);self.assertEqual(n[-1]['hostname_status'],'name_unresolved')
 def test_invalid_address_never_runs_command(self):
  with patch('ipsnoop.names.subprocess.run') as command:
   self.assertEqual(lookup('-evil','eth0'),('','name_unresolved'));command.assert_not_called()
 def test_missing_tool_status(self):
  with patch('ipsnoop.names.shutil.which',return_value=None):self.assertEqual(lookup('192.0.2.1','eth0'),('','IS201'))
