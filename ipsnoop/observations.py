# SPDX-License-Identifier: GPL-3.0-only
"""Befunde strukturieren, ohne fehlende Hardware- oder Routingdaten zu erraten."""
import ipaddress
from pathlib import Path
import re
import shlex

# Bewusst eine dokumentierte Sichtungsschwelle, keine Hardwarediagnose.
RX_DROP_REVIEW_THRESHOLD=10000
CORE_KERNEL_PARAMS=(
 'net.ipv4.ip_forward','net.ipv6.conf.all.forwarding','net.ipv4.conf.all.rp_filter',
 'net.ipv4.tcp_syncookies','net.ipv4.tcp_congestion_control','net.ipv4.tcp_mtu_probing',
 'net.ipv6.conf.all.disable_ipv6','net.ipv6.conf.all.accept_ra','net.mptcp.enabled',
 'net.netfilter.nf_conntrack_max',
)


def human_bytes(value):
    try:number=float(value)
    except (ValueError,TypeError):return ''
    for unit in ('B','KiB','MiB','GiB','TiB','PiB'):
        if abs(number)<1024 or unit=='PiB':return f'{number:.2f} {unit}'
        number/=1024


def normalize_neighbor(item):
    """iproute2: Alterswerte in Sekunden, router:null ist ein gesetztes Flag.

    Quelle: https://github.com/iproute2/iproute2/blob/main/ip/ipneigh.c
    Ein nicht gemeldetes Router-Flag wird nicht als fehlende Routerfähigkeit gedeutet.
    """
    data={k:v for k,v in item.items() if k not in ('dst','dev','lladdr','state','router','used','confirmed','updated','probes')}
    state=item.get('state',[])
    data.update(ip=item.get('dst',''),name=item.get('dev',''),mac=item.get('lladdr',''),
                status=', '.join(state) if isinstance(state,list) else str(state))
    router=item.get('router','unknown')
    data['router']=True if 'router' in item and router is None else router if type(router) is bool else 'unknown'
    for source,target in (('used','neighbor_used_s'),('confirmed','neighbor_confirmed_s'),('updated','neighbor_updated_s'),('probes','neighbor_probes')):
        if source in item:data[target]=item[source]
    return data


def group_neighbors(records):
    """MAC zusammenfassen; fehlende/Null-/Broadcast-MACs nicht zusammenwerfen."""
    groups={}
    for row in records:
        mac=str(row.get('mac','')).lower()
        valid=bool(re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',mac)) and mac not in ('00:00:00:00:00:00','ff:ff:ff:ff:ff:ff')
        key=('mac',mac) if valid else ('address',row.get('name',''),row.get('ip',''))
        groups.setdefault(key,[]).append(row)
    result=[]
    for rows in groups.values():
        def unique(field):return list(dict.fromkeys(str(r[field]) for r in rows if r.get(field) not in (None,'')))
        data={'mac':rows[0].get('mac',''),'interfaces':unique('name'),'hostname':unique('hostname'),
              'vendor':unique('vendor'),'status':unique('status'),'ipv4':[],'ipv6':[],
              'router':True if any(r.get('router') is True for r in rows) else False if all(r.get('router') is False for r in rows) else 'unknown',
              'observations':[dict(r) for r in rows]}
        for address in unique('ip'):
            try:family='ipv4' if ipaddress.ip_address(address.split('%')[0]).version==4 else 'ipv6'
            except ValueError:continue
            if address not in data[family]:data[family].append(address)
        result.append(data)
    return result


def classify_adapter(item,sysfs):
    path=Path(sysfs)/item.get('ifname','');kind=item.get('linkinfo',{}).get('info_kind','')
    if item.get('link_type')=='loopback':return 'virtual','loopback'
    if kind in ('bridge','veth','tun','tap','wireguard','xfrm','vlan','bond','team','dummy','vxlan','macvlan','ipvlan','gre','gretap','ipip','sit','vti','vrf'):
        return 'virtual',kind
    if not path.exists():return 'unknown',kind or item.get('link_type','unknown')
    if not (path/'device').exists():return 'virtual',kind or item.get('link_type','unknown')
    device=str((path/'device').resolve())
    if 'virtio' in device:return 'virtual','virtio'
    return 'physical','wifi' if (path/'wireless').exists() else 'ethernet'


def pci_details(sysfs,name,command):
    device=(Path(sysfs)/name/'device').resolve()
    pci=next((p for p in (device,*device.parents) if re.fullmatch(r'[\da-fA-F]{4}:[\da-fA-F]{2}:[\da-fA-F]{2}\.[0-7]',p.name)),None)
    if pci is None:return {}
    def read_id(key):
        try:value=(pci/key).read_text().strip().lower().removeprefix('0x')
        except OSError:return ''
        return value if re.fullmatch('[0-9a-f]{4}',value) else ''
    vendor=read_id('vendor');product=read_id('device')
    data={'pci_address':pci.name}
    if vendor and product:data.update(pci_id=vendor+':'+product,model='PCI-ID '+vendor+':'+product,model_source='sysfs')
    output=command(['lspci','-D','-mm','-nn','-s',pci.name])
    for line in output.splitlines():
        try:parts=shlex.split(line)
        except ValueError:continue
        if len(parts)>=4 and parts[0]==pci.name:
            # Nur eine benannte Gerätebeschreibung verwenden; reine IDs bleiben Fallback.
            model=re.sub(r'\s*\[[0-9a-fA-F]{4}\]$','',parts[3]).strip()
            if model and model.casefold() not in ('device','unknown device') and not re.fullmatch('[0-9a-fA-F]{4}',model):
                data.update(model=parts[3],model_source='lspci')
            data['pci_vendor']=parts[2];break
    return data


def default_routes(routes):
    """Metrikvergleich der Haupttabelle, keine Simulation von Policy Routing."""
    result=[]
    for family in ('ipv4','ipv6'):
        candidates=[]
        for r in routes:
            if r.get('family')!=family or r.get('dst') not in ('default','0.0.0.0/0','::/0'):continue
            if r.get('table','main') not in ('main',254,'254'):continue
            if r.get('type','unicast')!='unicast':continue
            candidates.append(r)
        eligible=[r for r in candidates if not any(f in r.get('flags',[]) for f in ('dead','linkdown'))]
        def metric(r):
            try:return int(r.get('metric',0))
            except (ValueError,TypeError):return None
        known=[metric(r) for r in eligible if metric(r) is not None]
        lowest=min(known) if known else None
        winners=sum(metric(r)==lowest for r in eligible) if lowest is not None else 0
        for r in sorted(candidates,key=lambda r:metric(r) if metric(r) is not None else float('inf')):
            best=r in eligible and lowest is not None and metric(r)==lowest
            result.append({**r,'preference':'equal_candidate' if best and winners>1 else 'preferred_metric' if best else 'alternative'})
    return result


def findings(adapters,extended):
    rows=[]
    for a in adapters:
        try:drops=int(a.get('rx_dropped',0))
        except (ValueError,TypeError):continue
        if drops<RX_DROP_REVIEW_THRESHOLD:continue
        stats=[{'field':r['field'],'value':r['value']} for r in extended if r.get('name')==a['name'] and r.get('field','').startswith('ethtool -S ') and r.get('result')=='ok' and re.search(r'drop|discard|miss|no.?buffer',r['field'],re.I)]
        rows.append({'code':'rx_drops_review','name':a['name'],'rx_dropped':drops,'threshold':RX_DROP_REVIEW_THRESHOLD,'driver_counters':stats,'interpretation':'driver_counters_not_additive'})
    return rows


def unsupported_queries(extended):
    return list(dict.fromkeys(row.get('field','') for row in extended if row.get('result')=='unsupported'))


def core_kernel_row(row):
    field=row.get('field','').split(' · ',1)[-1].split('=',1)[0].strip()
    return field in CORE_KERNEL_PARAMS or row.get('result') not in ('ok','empty')
