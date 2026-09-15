import unittest
from unittest.mock import patch
from ipsnoop.packages import connected,missing_packages
class PackageTests(unittest.TestCase):
 def test_only_missing_packages_not_permissions(self):
  with patch('ipsnoop.packages.shutil.which',return_value=None):
   self.assertEqual(missing_packages([{'code':'IS201','detail':'lldpcli'},{'code':'IS202','detail':'nft list ruleset'},{'code':'IS201','detail':'conntrack'}]),['conntrack','lldpd'])
 def test_unknown_is_not_disconnected(self):
  self.assertTrue(connected({'status':'UNKNOWN'}))
  self.assertFalse(connected({'status':'DOWN'}))
  self.assertFalse(connected({'status':'UP','link':'no'}))
