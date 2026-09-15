# SPDX-License-Identifier: GPL-3.0-only
"""Erweiterte, ausschließlich lesende Linux-Abfragen.

Technische Schlüsselnamen der Werkzeuge bleiben erhalten. Jede Abfrage erhält
Quelle und Status; ein leerer erfolgreicher Befund ist kein Abfragefehler.
Aktive Diagnose ist separat und wird nie von scan() gestartet.
"""
import ipaddress
import json
import os
from pathlib import Path
import pwd
import re

GROUPS = ('adapter_extra','dns_details','policy','topology','firewall','protocol_stats',
          'kernel_params','traffic','wifi_details','bluetooth','namespaces','tcp_quality','lldp','conntrack','vpn')


def text_file(path):
    try:return Path(path).read_text(errors='replace').strip()
    except OSError:return ''


def flatten(value,prefix=''):
    """Verschachtelte Werkzeugdaten verlustfrei in Feld/Wert-Zeilen zerlegen."""
    if isinstance(value,dict):
        for key,item in value.items():yield from flatten(item,f'{prefix}.{key}' if prefix else key)
    elif isinstance(value,list):
        for index,item in enumerate(value):yield from flatten(item,f'{prefix}[{index}]')
    else:yield prefix,value


def protocol_counters(text):
    lines=text.splitlines();result={}
    for i in range(0,len(lines)-1,2):
        keys=lines[i].split();values=lines[i+1].split()
        if keys and values and keys[0]==values[0] and len(keys)==len(values):
            for key,value in zip(keys[1:],values[1:]):result[keys[0].rstrip(':')+'.'+key]=value
    return result


def dhcp_options(nm):
    """NetworkManager OPTIONS[n] enthalten jeweils 'name = value'."""
    result={}
    for key,value in nm.items():
        if key.startswith(('DHCP4.OPTION','DHCP6.OPTION')) and '=' in value:
            name,data=value.split('=',1);result[key.split('.')[0]+'.'+name.strip()]=data.strip()
    return result


def socket_rows(text):
    result=[]
    for line in text.splitlines():
        values=line.split(None,6)
        if len(values)<6:continue
        row=dict(zip(('protocol','status','receive_queue','send_queue','local','peer','process'),values+([''] if len(values)==6 else [])))
        pids=list(dict.fromkeys(re.findall(r'pid=(\d+)',row['process'])))
        row['pid']=', '.join(pids);row['user']='';row['executable']=''
        users=[];executables=[]
        for pid in pids:
            try:users.append(pwd.getpwuid(Path('/proc',pid).stat().st_uid).pw_name)
            except (OSError,KeyError):pass
            try:executables.append(os.readlink('/proc/'+pid+'/exe'))
            except OSError:pass
        row['user']=', '.join(dict.fromkeys(users));row['executable']='\n'.join(dict.fromkeys(executables))
        result.append(row)
    return result


def local_hosts(path='/etc/hosts'):
    result={}
    for line in text_file(path).splitlines():
        parts=line.split('#',1)[0].split()
        if len(parts)>1:result[parts[0]]=' '.join(parts[1:])
    return result


def oui_database(paths=None):
    """Lokale IEEE/arp-scan/nmap-Daten nutzen; keine Datenbank herunterladen."""
    result={}
    for path in paths or ('/usr/share/ieee-data/oui.txt','/usr/share/arp-scan/ieee-oui.txt','/usr/share/nmap/nmap-mac-prefixes'):
        for line in text_file(path).splitlines():
            m=re.match(r'^([0-9A-Fa-f]{2}[-:]?[0-9A-Fa-f]{2}[-:]?[0-9A-Fa-f]{2})\s+(?:\((?:hex|base 16)\)\s+)?(.+)$',line)
            if m:result[re.sub('[:-]','',m[1]).upper()]=m[2].strip()
    return result


def mac_vendor(mac,db):
    try:
        if int(mac.split(':')[0],16)&2:return 'locally_administered'
    except ValueError:return ''
    return db.get(mac.replace(':','').upper()[:6],'')


class Extended:
    def __init__(self,scanner):self.s=scanner;self.rows=[]

    def add(self,group,name,field,value,status='ok'):
        self.rows.append(dict(group=group,name=name,field=field,value=value,result=status))

    def query(self,group,name,args):
        output=self.s.command(args)
        status=self.s.last_status
        source=' '.join(args)
        if status!='ok':self.add(group,name,source,'',status)
        elif not output.strip():self.add(group,name,source,'','empty')
        else:
            # JSON-Ausgaben strukturiert darstellen; Textwerkzeuge zeilenweise.
            try:value=json.loads(output)
            except ValueError:value=None
            if isinstance(value,(dict,list)):
                entries=list(flatten(value))
                if not entries:self.add(group,name,source,'','empty')
                for key,item in entries:self.add(group,name,source+' · '+key,item)
            else:
                for line in output.splitlines():
                    if not line.strip():continue
                    field,sep,value=line.strip().partition('=' if args[0]=='sysctl' else ':')
                    field=field.strip()
                    self.add(group,name,source+' · '+field,value.strip() if sep else line.strip())
        return output

    def bluetooth(self):
        """Kernel-Sicht, BlueZ-Dienst und nutzbare Controller getrennt darstellen."""
        hardware=Path('/sys/class/bluetooth')
        try:present=bool(list(hardware.glob('hci*'))) if hardware.exists() else False
        except OSError:present='unknown'
        self.add('bluetooth','','bluetooth_hardware_present',present)
        service=self.s.command(['systemctl','show','bluetooth.service','--property=LoadState','--property=ActiveState'])
        if self.s.last_status=='ok':
            props=dict(line.split('=',1) for line in service.splitlines() if '=' in line)
            state=props.get('ActiveState','unknown')
            self.add('bluetooth','','bluetooth_service_available',state=='active' if state!='unknown' else 'unknown')
        else:self.add('bluetooth','','bluetooth_service_available','',self.s.last_status)
        controllers=self.s.command(['bluetoothctl','list']);status=self.s.last_status
        addresses=re.findall(r'^Controller ([0-9A-Fa-f:]{17})',controllers,re.M)
        self.add('bluetooth','','bluetooth_controller_available',bool(addresses) if status=='ok' else '',status)
        if status!='ok':return
        default=re.search(r'^Controller ([0-9A-Fa-f:]{17}).*\[default\]',controllers,re.M)
        self.add('bluetooth','','bluetooth_default_controller',default[1] if default else 'not_present' if not addresses else 'unknown')
        if not addresses:
            self.add('bluetooth','','bluetooth_note','bluetooth_unavailable_hint')
            return
        for address in addresses:self.query('bluetooth',address,['bluetoothctl','show',address])
        devices=self.query('bluetooth','',['bluetoothctl','devices'])
        for address in re.findall(r'^Device ([0-9A-Fa-f:]{17})',devices,re.M):
            self.query('bluetooth',address,['bluetoothctl','info',address])

    def collect(self,interfaces,nm_data):
        for item in interfaces:
            name=item.get('ifname','')
            if not name or '/' in name or name.startswith('-'):continue
            physical=(self.s.sysfs/name/'device').exists()
            if physical:
                for flag in ('-S','-k','-g','-c','-l','-x','-T'):self.query('adapter_extra',name,['ethtool',flag,name])
                device=(self.s.sysfs/name/'device').resolve()
                # Virtio-Geräte liegen unter dem eigentlichen PCI-Gerät.
                pci=next((p for p in (device,*device.parents) if re.fullmatch(r'[\da-fA-F]{4}:[\da-fA-F]{2}:[\da-fA-F]{2}\.[0-7]',p.name)),None)
                if pci:
                    self.add('adapter_extra',name,'PCI address',pci.name)
                    for field in ('current_link_speed','max_link_speed','current_link_width','max_link_width','vendor','device','subsystem_vendor','subsystem_device'):
                        value=text_file(pci/field);self.add('adapter_extra',name,'PCI '+field,value,'ok' if value else 'unavailable')
                    self.query('adapter_extra',name,['lspci','-nn','-s',pci.name])
            options=dhcp_options(nm_data.get(name,{}))
            for key,value in options.items():self.add('adapter_extra',name,key,value)
            if not options:self.add('adapter_extra',name,'DHCP lease/options','','unavailable')
            for key,value in flatten(item.get('addr_info',[])):
                self.add('adapter_extra',name,'address.'+key,value)
            for family,fields in (('ipv4',('forwarding','rp_filter')),('ipv6',('forwarding','use_tempaddr','accept_ra','autoconf'))):
                for field in fields:
                    value=text_file(Path('/proc/sys/net')/family/'conf'/name/field)
                    self.add('adapter_extra',name,f'{family}.{field}',value,'ok' if value else 'unavailable')
            self.query('traffic',name,['tc','-j','qdisc','show','dev',name])
            self.query('traffic',name,['tc','-j','class','show','dev',name])
            for parent in (('root',),('ingress',),('egress',)):
                self.query('traffic',name,['tc','-j','filter','show','dev',name,*parent])
            if (self.s.sysfs/name/'wireless').exists():
                self.query('wifi_details',name,['iw','dev',name,'link'])
                self.query('wifi_details',name,['iw','dev',name,'get','power_save'])
                self.query('wifi_details',name,['iw','dev',name,'station','dump'])
            bond=Path('/proc/net/bonding')/name
            if bond.exists():self.add('topology',name,'bonding',text_file(bond))
            if item.get('linkinfo',{}).get('info_kind')=='team':self.query('topology',name,['teamdctl',name,'state','dump'])
        self.query('dns_details','',['resolvectl','status','--no-pager'])
        self.query('topology','',['ip','-j','-d','link','show'])
        self.query('topology','',['bridge','-j','-d','link','show'])
        self.query('topology','',['bridge','-j','vlan','show'])
        for family in ('-4','-6'):self.query('policy','',['ip','-j',family,'rule','show'])
        # Status nur aus wirklichen Ergebnissen; ein Lesefehler bedeutet nicht 'aus'.
        self.query('firewall','',['nft','-j','list','ruleset'])
        self.query('tcp_quality','',['ss','-H','-t','-i','-n','-p'])
        self.query('lldp','',['lldpcli','-f','json','show','neighbors','details'])
        self.query('conntrack','',['conntrack','-S'])
        self.query('conntrack','',['conntrack','-L','-o','extended'])
        for field in ('nf_conntrack_count','nf_conntrack_max'):
            value=text_file('/proc/sys/net/netfilter/'+field)
            self.add('conntrack','',field,value,'ok' if value else 'unavailable')
        from .scanner import escaped_columns
        raw=self.s.command(['nmcli','--terse','--escape','yes','--fields','NAME,TYPE,DEVICE','connection','show','--active'])
        if self.s.last_status!='ok':self.add('vpn','','NetworkManager VPN','',self.s.last_status)
        else:
            found=False
            for line in raw.splitlines():
                parts=escaped_columns(line)
                if len(parts)==3 and parts[1] in ('vpn','wireguard','tun','ip-tunnel'):
                    self.add('vpn',parts[2],parts[0],parts[1]);found=True
            if not found:self.add('vpn','','NetworkManager VPN','','empty')
        for item in interfaces:
            kind=item.get('linkinfo',{}).get('info_kind','')
            if kind in ('tun','wireguard','xfrm','ppp') or item.get('link_type')=='ppp':
                self.add('vpn',item.get('ifname',''),'vpn_candidate',kind or item.get('link_type'))
        import shutil
        if shutil.which('wg'):
            devices=self.query('vpn','',['wg','show','interfaces'])
            for name in devices.split():
                if not re.fullmatch(r'[A-Za-z0-9_.-]{1,15}',name) or name.startswith('-'):continue
                # Niemals dump/private-key abfragen: diese Ausgaben enthalten Schlüssel.
                for field in ('public-key','endpoints','latest-handshakes','transfer'):
                    self.query('vpn',name,['wg','show',name,field])
        self.query('firewall','',['ufw','status','verbose'])
        for path in ('/proc/net/snmp','/proc/net/netstat'):
            value=text_file(path)
            for key,item in protocol_counters(value).items():self.add('protocol_stats','',key,item)
            if not value:self.add('protocol_stats','',path,'','unavailable')
        for line in text_file('/proc/net/snmp6').splitlines():
            parts=line.split()
            if len(parts)==2:self.add('protocol_stats','',parts[0],parts[1])
        self.query('kernel_params','',['sysctl','net'])
        if any((self.s.sysfs/i.get('ifname','')/'wireless').exists() for i in interfaces):
            self.query('wifi_details','',['iw','dev']);self.query('wifi_details','',['iw','phy'])
        self.bluetooth()
        namespaces=self.query('namespaces','',['ip','netns','list'])
        try:self.add('namespaces','','current_namespace',os.readlink('/proc/self/ns/net'))
        except OSError:self.add('namespaces','','current_namespace','','unavailable')
        for line in namespaces.splitlines():
            name=line.split()[0]
            if name.startswith('-') or '/' in name:continue
            self.query('namespaces',name,['ip','-n',name,'-j','address','show'])
            for family in ('-4','-6'):self.query('namespaces',name,['ip','-n',name,'-j',family,'route','show','table','all'])
        # Container-Inventar bleibt lokal; entfernte Docker-Kontexte nicht aufrufen.
        import shutil
        if shutil.which('docker'):
            self.query('topology','docker',['docker','--host','unix:///var/run/docker.sock','network','ls','--format','{{json .}}'])
        if shutil.which('podman'):
            self.query('topology','podman',['podman','--remote=false','network','ls','--format','json'])
        return self.rows


def diagnostic(mode,target):
    """Nur explizit angeforderte, begrenzte Tests; niemals Shell-Interpolation."""
    from .scanner import Scanner
    target=target.strip()
    try:ipaddress.ip_address(target.split('%',1)[0]);valid=True
    except ValueError:valid=bool(re.fullmatch(r'(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',target))
    if not valid or '%' in target:raise ValueError('IS204')
    commands={'ping':['ping','-n','-c','4','-W','2',target],
              'lookup':['getent','hosts',target],
              'trace':['tracepath','-n','-m','12',target]}
    if mode not in commands:raise ValueError('IS204')
    scanner=Scanner();output=scanner.command(commands[mode],timeout=20)
    return {'group':'diagnostics','name':target,'field':mode,'value':output,'result':scanner.last_status}
