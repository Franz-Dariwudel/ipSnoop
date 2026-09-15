# SPDX-License-Identifier: GPL-3.0-only
"""Begrenzte Reverse-Auflösung über die lokale NSS-Konfiguration (DNS/mDNS).

getent nutzt die Resolver des Systems. Nur bereits bekannte Nachbaradressen
werden abgefragt; Antworten und negative Ergebnisse werden kurz gespeichert.
"""
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import os
import shutil
import subprocess
import tempfile
import time


def lookup(address,interface):
    try:ip=ipaddress.ip_address(address)
    except ValueError:return '', 'name_unresolved'
    executable=shutil.which('getent')
    if not executable:return '', 'IS201'
    target=str(ip)
    if ip.version==6 and ip.is_link_local:
        if not interface or '/' in interface or '%' in interface:return '', 'name_unresolved'
        target+='%' + interface
    try:
        with tempfile.TemporaryFile() as output:
            result=subprocess.run([executable,'hosts',target],stdout=output,stderr=subprocess.DEVNULL,
                timeout=1.5,check=False,env={**os.environ,'LC_ALL':'C'})
            if result.returncode==2:return '', 'name_unresolved'
            if result.returncode:return '', 'IS202'
            output.seek(0);raw=output.read(65537)
            if len(raw)>65536:return '', 'IS203'
        names=[]
        for line in raw.decode('utf-8',errors='replace').splitlines():
            parts=line.split()
            if len(parts)<2:continue
            try:
                if ipaddress.ip_address(parts[0].split('%')[0])!=ip:continue
            except ValueError:continue
            for name in parts[1:]:
                try:ipaddress.ip_address(name);continue
                except ValueError:pass
                if len(name)<=253 and name not in names:names.append(name)
        return (' '.join(names),'name_resolved') if names else ('','name_unresolved')
    except (OSError,subprocess.TimeoutExpired):return '', 'IS202'


class NameResolver:
    def __init__(self):self.cache={}

    def resolve(self,neighbors,hosts):
        now=time.monotonic()
        active={(n['ip'],n['name']) for n in neighbors}
        self.cache={k:v for k,v in self.cache.items() if k in active and v[0]>now}
        pending=list(dict.fromkeys((n['ip'],n['name']) for n in neighbors if not hosts.get(n['ip']) and (n['ip'],n['name']) not in self.cache))[:16]
        # Höchstens vier gleichzeitige Prozesse, 16 Abfragen pro Aktualisierung.
        with ThreadPoolExecutor(max_workers=4) as pool:
            for key,result in zip(pending,pool.map(lambda key:lookup(*key),pending)):
                self.cache[key]=(time.monotonic()+(300 if result[0] else 60),result)
        for n in neighbors:
            if hosts.get(n['ip']):n['hostname']=hosts[n['ip']];n['hostname_status']='name_local'
            else:
                record=self.cache.get((n['ip'],n['name']))
                n['hostname'],n['hostname_status']=record[1] if record else ('','name_pending')
