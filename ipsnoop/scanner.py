# SPDX-License-Identifier: GPL-3.0-only
"""Netzwerkdaten mit iproute2, NetworkManager, ethtool und sysfs auslesen.

Keine Shell, Paketmitschnitte oder Netzwerkscans. Nachbarn stammen aus dem
Kernel-Cache, WLAN-Netze aus dem vorhandenen NetworkManager-Cache. Optionale
Werkzeuge dürfen fehlen; jede Abfrage ist zeitlich und in ihrer Ausgabe begrenzt.
"""
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime,timezone
from .observations import (normalize_neighbor,group_neighbors,classify_adapter,pci_details,
                           human_bytes,default_routes,findings,unsupported_queries)


def optional_ethtool_status(args, error):
    """Erwartete Treibergrenzen nur bei lesenden Detailabfragen erkennen.

    Jede Fehlerzeile muss eine bekannte harmlose Antwort sein. Gemischte
    Meldungen, Zugriffsfehler und unbekannte Fehler bleiben echte Warnungen.
    """
    if len(args)!=3 or args[0]!='ethtool' or args[1] not in ('-S','-k','-g','-c','-l','-x','-T'):
        return None
    lines=[line.strip().lower() for line in error.splitlines() if line.strip()]
    expected=('operation not supported','not supported','no data available')
    failures=('permission denied','operation not permitted','timed out','no such device','input/output error')
    if not lines or any(any(failure in line for failure in failures) or
                        not any(phrase in line for phrase in expected) for line in lines):
        return None
    return 'unsupported' if any('not supported' in line for line in lines) else 'no_data'


def pairs(text):
    """nmcli-Multiline: nur den ersten Doppelpunkt als Trenner verwenden."""
    result={}
    for line in text.splitlines():
        if ':' in line:
            key,value=line.split(':',1);result[key.strip()]=value.strip()
    return result


def escaped_columns(line):
    """Escapte Doppelpunkte und Backslashes in nmcli-Tabellen entpacken."""
    columns=[];current=[];escape=False
    for c in line:
        if escape:current.append(c);escape=False
        elif c=='\\':escape=True
        elif c==':':columns.append(''.join(current));current=[]
        else:current.append(c)
    if escape:current.append('\\')
    columns.append(''.join(current));return columns


def subnet(address, prefix):
    try:return str(ipaddress.ip_network(f'{address}/{prefix}',strict=False))
    except ValueError:return ''


class Scanner:
    def __init__(self, sysfs=Path('/sys/class/net')):
        from .names import NameResolver
        self.names=NameResolver()
        self.sysfs=Path(sysfs);self.issues=[];self.last_status="ok"

    def issue(self,code,detail):
        entry={'code':code,'detail':detail}
        if entry not in self.issues:self.issues.append(entry)

    def command(self,args,timeout=2):
        """Prozessgruppe begrenzen; keine beliebigen Befehle aus Eingabedateien."""
        self.last_status="ok"
        executable=shutil.which(args[0])
        if not executable:
            self.last_status='IS201';self.issue('IS201',args[0]);return ''
        try:
            # Temporäre Datei verhindert unbegrenztes puffern in capture_output.
            with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
                result=subprocess.run([executable,*args[1:]],stdout=output,stderr=output if timeout>2 else errors,
                    timeout=timeout,env={**os.environ,'LC_ALL':'C'},check=False)
                if result.returncode:
                    if timeout<=2:
                        errors.seek(0);detail=errors.read(65537)
                        status=optional_ethtool_status(args,detail.decode('utf-8',errors='replace')) if len(detail)<=65536 else None
                        if status:
                            self.last_status=status;return ''
                    self.last_status='IS202';self.issue('IS202',' '.join(args))
                    if timeout<=2:return ''
                output.seek(0);data=output.read(2*1024*1024+1)
                if len(data)>2*1024*1024:
                    self.last_status='IS203';self.issue('IS203',args[0]);return ''
                return data.decode('utf-8',errors='replace')
        except (OSError,subprocess.TimeoutExpired):
            self.last_status='IS202';self.issue('IS202',' '.join(args));return ''

    def json_command(self,args):
        text=self.command(args)
        if not text:return []
        try:
            value=json.loads(text)
            if not isinstance(value,list) or not all(isinstance(v,dict) for v in value):raise ValueError()
            return value
        except ValueError:self.issue('IS203',args[0]);return []

    def read(self,interface,file):
        try:return (self.sysfs/interface/file).read_text().strip()
        except OSError:return ''

    def adapter(self,item,routes,nm):
        name=item.get('ifname','')
        if not isinstance(name,str) or '/' in name or name in ('.','..') or name.startswith('-'):return None
        data={'name':name,'type':nm.get('GENERAL.TYPE',item.get('link_type','')),
              'status':item.get('operstate',''),'mac':item.get('address',''),
              'mtu':item.get('mtu',''),'flags':', '.join(item.get('flags',[])),
              'broadcast':item.get('broadcast',''),'connection':nm.get('GENERAL.CONNECTION',''),
              'vendor':nm.get('GENERAL.VENDOR',''),'model':nm.get('GENERAL.PRODUCT',''),
              'driver':nm.get('GENERAL.DRIVER',''),'driver_version':nm.get('GENERAL.DRIVER-VERSION',''),
              'firmware':nm.get('GENERAL.FIRMWARE-VERSION','')}
        addresses=item.get('addr_info',[])
        for family,key in (('inet','ipv4'),('inet6','ipv6')):
            data[key]='\n'.join(f"{a['local']}/{a['prefixlen']}" for a in addresses
                if a.get('family')==family and 'local' in a and 'prefixlen' in a)
        data['subnet']='\n'.join(subnet(a['local'],a['prefixlen']) for a in addresses if 'local' in a and 'prefixlen' in a)
        default=[r for r in routes if r.get('dev')==name and r.get('dst')=='default']
        data['gateway']='\n'.join(str(r.get('gateway','')) for r in default)
        data['metric']='\n'.join(str(r['metric']) for r in default if 'metric' in r)
        data['dns']='\n'.join(v for k,v in nm.items() if re.fullmatch(r'IP[46]\.DNS\[\d+\]',k))
        data['domains']='\n'.join(v for k,v in nm.items() if re.fullmatch(r'IP[46]\.DOMAIN\[\d+\]',k))
        data['dhcp']=''
        uuid=nm.get('GENERAL.CON-UUID','')
        if re.fullmatch(r'[0-9a-fA-F-]{36}',uuid):
            methods=pairs(self.command(['nmcli','--terse','--escape','no','--mode','multiline','--fields','ipv4.method,ipv6.method','connection','show','uuid',uuid]))
            data['dhcp']='\n'.join(f'{k}: {v}' for k,v in methods.items())
        # Loopback hat weder physische Linkgeschwindigkeit noch Firmware.
        if item.get('link_type')!='loopback':
            raw=self.command(['ethtool',name]);detail=pairs(raw)
            info=pairs(self.command(['ethtool','-i',name]))
            permanent=pairs(self.command(['ethtool','-P',name]))
            for target,source in (('speed','Speed'),('duplex','Duplex'),('autoneg','Auto-negotiation'),('link','Link detected'),('wake','Wake-on')):
                data[target]=detail.get(source,'')
            data['wake_support']=detail.get('Supports Wake-on','')
            data['wake_supported']=(data['wake_support']!='d') if data['wake_support'] else ''
            data['wake_magic']=('g' in data['wake_support']) if data['wake_support'] else ''
            data['link_modes']=detail.get('Supported link modes','')
            # Auch eingerückte Folgezeilen der unterstützten Link-Modi erfassen.
            match=re.search(r'Supported link modes:\s*(.*?)(?=\n\s*Supported pause frame use:|\Z)',raw,re.S)
            if match:data['link_modes']=' '.join(match[1].split())
            rates=[float(n) for n in re.findall(r'(\d+(?:\.\d+)?)base',data['link_modes'])]
            data['max_speed']=str(max(rates))+' Mb/s' if rates else ''
            for target,key in (('driver','driver'),('driver_version','version'),('firmware','firmware-version'),('bus','bus-info')):
                data[target]=info.get(key,data.get(target,''))
            data['permanent_mac']=permanent.get('Permanent address','')
        for key,file in (('rx_packets','statistics/rx_packets'),('tx_packets','statistics/tx_packets'),('rx_dropped','statistics/rx_dropped'),('tx_dropped','statistics/tx_dropped'),('carrier_errors','statistics/tx_carrier_errors'),('collisions','statistics/collisions'),('multicast','statistics/multicast'),('rx_bytes','statistics/rx_bytes'),('tx_bytes','statistics/tx_bytes'),('rx_errors','statistics/rx_errors'),('tx_errors','statistics/tx_errors')):
            data[key]=self.read(name,file)
        data['classification'],data['adapter_kind']=classify_adapter(item,self.sysfs)
        data['counter_scope']='since_counter_reset'
        for direction in ('rx','tx'):data[direction+'_data']=human_bytes(data[direction+'_bytes'])
        if data['model'] in ('','--','unknown'):
            data.update(pci_details(self.sysfs,name,self.command))
        if data['classification']=='virtual':
            data['speed']='not_applicable';data['max_speed']='not_applicable'
        return data

    def scan(self):
        started=time.time();clock=time.monotonic()
        self.issues=[]
        interfaces=self.json_command(['ip','-j','-d','address','show'])
        routes=[{**r,'family':family} for flag,family in (('-4','ipv4'),('-6','ipv6'))
                for r in self.json_command(['ip','-j',flag,'route','show','table','all'])]
        adapters=[];nm_data={}
        for item in interfaces:
            name=item.get('ifname','')
            if not isinstance(name,str) or '/' in name:continue
            nm=pairs(self.command(['nmcli','--terse','--escape','no','--mode','multiline','--fields','GENERAL,IP4,IP6,DHCP4,DHCP6','device','show',name]))
            nm_data[name]=nm
            entry=self.adapter(item,routes,nm)
            if entry:adapters.append(entry)
        neighbors=[normalize_neighbor(n) for n in self.json_command(['ip','-j','-s','neigh','show'])]
        wifi=[]
        fields='IN-USE,SSID,BSSID,SIGNAL,CHAN,FREQ,RATE,SECURITY,DEVICE'
        if any(a['type']=='wifi' for a in adapters):
            for line in self.command(['nmcli','--terse','--escape','yes','--fields',fields,'device','wifi','list','--rescan','no']).splitlines():
                parts=escaped_columns(line)
                if len(parts)==9:wifi.append(dict(zip(('active','ssid','bssid','signal','channel','frequency','rate','security','name'),parts)))
        from .extended import Extended,socket_rows,local_hosts,oui_database,mac_vendor
        services=socket_rows(self.command(['ss','-H','-l','-n','-t','-u','-p']))
        connections=socket_rows(self.command(['ss','-H','-a','-n','-t','-u','-p']))
        hosts=local_hosts();vendors=oui_database()
        for n in neighbors:
            n['hostname']=hosts.get(n['ip'],'');n['vendor']=mac_vendor(n['mac'],vendors)
        self.names.resolve(neighbors,hosts)
        for n in neighbors:
            if n.get('hostname_status','').startswith('IS'):self.issue(n['hostname_status'],'getent hosts '+n['ip'])
        extended=Extended(self).collect(interfaces,nm_data)
        system={'hostname':platform.node(),'os':platform.freedesktop_os_release().get('PRETTY_NAME',platform.system()),
                'kernel':platform.release(),'architecture':platform.machine()}
        for key,path in [('machine_id','/etc/machine-id'),('boot_id','/proc/sys/kernel/random/boot_id'),('system_vendor','/sys/class/dmi/id/sys_vendor'),('system_model','/sys/class/dmi/id/product_name'),('resolver','/etc/resolv.conf')]:
            try:system[key]=Path(path).read_text().strip()
            except OSError:system[key]=''
        system['resolver']='\n'.join(line.split('#',1)[0].strip() for line in system.get('resolver','').splitlines() if line.split('#',1)[0].strip())
        system['effective_uid']=os.geteuid()
        finished=time.time()
        return {'adapters':adapters,'neighbors':group_neighbors(neighbors),'neighbor_records':neighbors,'wifi':wifi,'services':services,
                'routes':routes,'default_routes':default_routes(routes),'connections':connections,'extended':extended,
                'findings':findings(adapters,extended),'unsupported_queries':unsupported_queries(extended),
                'scan':{'started':datetime.fromtimestamp(started,timezone.utc).isoformat(),
                        'finished':datetime.fromtimestamp(finished,timezone.utc).isoformat(),
                        'duration_s':round(time.monotonic()-clock,3)},
                'diagnostics':[],'system':system,'issues':self.issues.copy(),'timestamp':finished}
