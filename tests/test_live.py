import tempfile
import unittest
from pathlib import Path
from ipsnoop.live import Rates,COUNTERS

class RateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.device=self.root/'eth0';(self.device/'statistics').mkdir(parents=True)
        (self.device/'ifindex').write_text('2');(self.device/'address').write_text('00:11:22:33:44:55')
        self.write(100);self.rates=Rates(self.root)
    def tearDown(self):self.tmp.cleanup()
    def write(self,value):
        for key in COUNTERS:(self.device/'statistics'/key).write_text(str(value))
    def test_actual_elapsed_time_and_first_sample(self):
        self.assertEqual(self.rates.sample(10)[0]['rate_status'],'warming_up')
        self.write(150);row=self.rates.sample(12.5)[0]
        self.assertEqual(row['rx_bytes_s'],20);self.assertEqual(row['tx_errors_s'],20)
    def test_zero_is_valid(self):
        self.rates.sample(1);row=self.rates.sample(2)[0]
        self.assertEqual(row['rx_packets_s'],0);self.assertEqual(row['rate_status'],'ok')
    def test_reset_and_recovery(self):
        self.rates.sample(1);self.write(1)
        row=self.rates.sample(2)[0];self.assertEqual(row['rate_status'],'counter_reset');self.assertNotIn('rx_bytes_s',row)
        self.write(3);self.assertEqual(self.rates.sample(3)[0]['rx_bytes_s'],2)
    def test_replacement_and_inaccessible_counter(self):
        self.rates.sample(1);(self.device/'ifindex').write_text('3');self.write(1000)
        self.assertEqual(self.rates.sample(2)[0]['rate_status'],'warming_up')
        (self.device/'statistics/rx_bytes').unlink()
        self.assertEqual(self.rates.sample(3)[0]['rate_status'],'unavailable')
        self.assertFalse(self.rates.previous)
    def test_no_forward_time_never_divides_by_zero(self):
        self.rates.sample(2);self.assertEqual(self.rates.sample(2)[0]['rate_status'],'warming_up')

if __name__=='__main__':unittest.main()

class ExtraRateTests(unittest.TestCase):
    setUp=RateTests.setUp
    tearDown=RateTests.tearDown
    write=RateTests.write
    def test_drops_utilization_time_and_zero(self):
        link={'eth0':{'classification':'physical','speed':'1000Mb/s'}}
        self.rates.sample(1,wall_time=1000,links=link)
        self.write(1250100);row=self.rates.sample(2,wall_time=1001,links=link)[0]
        self.assertEqual(row['rx_dropped_s'],1250000);self.assertEqual(row['rx_utilization_pct'],1)
        self.assertEqual(row['interval_s'],1);self.assertIn('1970-',row['measured_at'])
    def test_virtual_utilization_is_not_fabricated(self):
        link={'eth0':{'classification':'virtual','speed':'10000Mb/s'}}
        self.rates.sample(1,links=link);self.write(150)
        self.assertEqual(self.rates.sample(2,links=link)[0]['rx_utilization_pct'],'not_applicable')
    def test_window_expires_and_reset_discards_old_extremes(self):
        self.rates.sample(1);self.write(120);first=self.rates.sample(2)[0]
        self.assertEqual(first['rx_bytes_s_max'],20)
        self.write(220);row=self.rates.sample(72)[0]
        self.assertAlmostEqual(row['rx_bytes_s_max'],round(100/70,2))
        self.write(1);self.assertEqual(self.rates.sample(73)[0]['rate_status'],'counter_reset')
        self.write(2);self.assertEqual(self.rates.sample(74)[0]['rx_bytes_s_max'],1)
