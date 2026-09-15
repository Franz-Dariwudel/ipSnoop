"""Treibergrenzen von echten Abfragefehlern unterscheiden."""
import subprocess
import unittest
from unittest.mock import patch

from ipsnoop.extended import Extended
from ipsnoop.scanner import Scanner


class OptionalEthtoolTests(unittest.TestCase):
    def run_command(self, args, stderr='', stdout='', returncode=1, timeout=2):
        scanner=Scanner()
        def run(argv, **kwargs):
            kwargs['stdout'].write(stdout.encode())
            kwargs['stderr'].write(stderr.encode())
            return subprocess.CompletedProcess(argv,returncode)
        with patch('ipsnoop.scanner.shutil.which',return_value='/usr/sbin/'+args[0]), patch('ipsnoop.scanner.subprocess.run',side_effect=run):
            output=scanner.command(args,timeout=timeout)
        return scanner,output

    def test_unsupported_optional_queries_are_neutral(self):
        for flag in ('-S','-k','-g','-c','-l','-x','-T'):
            with self.subTest(flag=flag):
                scanner,output=self.run_command(['ethtool',flag,'eth0'],stderr='netlink error: Operation not supported\n')
                self.assertEqual((output,scanner.last_status,scanner.issues),('','unsupported',[]))

    def test_no_data_has_distinct_neutral_status(self):
        scanner,output=self.run_command(['ethtool','-x','eth0'],stderr='Cannot get RX flow hash configuration: No data available\n')
        self.assertEqual((output,scanner.last_status,scanner.issues),('','no_data',[]))

    def test_real_and_mixed_errors_still_warn(self):
        for error in ('Permission denied','Operation not permitted','No such device','Input/output error','',
                      'Operation not supported\nPermission denied',
                      'Operation not supported: Permission denied',
                      'Operation not supported\nUnexpected reply'):
            with self.subTest(error=error):
                scanner,output=self.run_command(['ethtool','-l','eth0'],stderr=error)
                self.assertEqual(scanner.last_status,'IS202');self.assertEqual(output,'')
                self.assertEqual(scanner.issues,[{'code':'IS202','detail':'ethtool -l eth0'}])

    def test_other_commands_and_basic_queries_are_not_suppressed(self):
        for args in (['nft','list','ruleset'],['ethtool','eth0'],['ethtool','-i','eth0']):
            scanner,_=self.run_command(args,stderr='Operation not supported')
            self.assertEqual(scanner.last_status,'IS202');self.assertTrue(scanner.issues)

    def test_success_preserves_output(self):
        scanner,output=self.run_command(['ethtool','-l','eth0'],stdout='Combined: 4\n',returncode=0)
        self.assertEqual(output,'Combined: 4\n');self.assertEqual(scanner.last_status,'ok')
        self.assertEqual(scanner.issues,[])

    def test_timeout_and_missing_tool_remain_errors(self):
        scanner=Scanner()
        with patch('ipsnoop.scanner.shutil.which',return_value='/usr/sbin/ethtool'), patch('ipsnoop.scanner.subprocess.run',side_effect=subprocess.TimeoutExpired('ethtool',2)):
            self.assertEqual(scanner.command(['ethtool','-c','eth0']),'')
        self.assertEqual(scanner.last_status,'IS202')
        with patch('ipsnoop.scanner.shutil.which',return_value=None):
            scanner.command(['ethtool','-c','eth0'])
        self.assertEqual(scanner.last_status,'IS201')

    def test_oversized_error_does_not_hide_failures(self):
        scanner,_=self.run_command(['ethtool','-c','eth0'],stderr='Not supported\n'*6000)
        self.assertEqual(scanner.last_status,'IS202')

    def test_diagnostic_stderr_is_still_returned(self):
        scanner,output=self.run_command(['ping','127.0.0.1'],stderr='unreachable\n',stdout='start\n',timeout=20)
        self.assertEqual(output,'start\nunreachable\n');self.assertEqual(scanner.last_status,'IS202')

    def test_neutral_status_reaches_result_rows(self):
        scanner=Scanner();extended=Extended(scanner)
        def unsupported(args):
            scanner.last_status='unsupported';return ''
        with patch.object(scanner,'command',side_effect=unsupported):
            extended.query('adapter_extra','eth0',['ethtool','-x','eth0'])
        self.assertEqual(extended.rows,[{'group':'adapter_extra','name':'eth0','field':'ethtool -x eth0','value':'','result':'unsupported'}])


if __name__=='__main__':unittest.main()
