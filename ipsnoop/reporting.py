# SPDX-License-Identifier: GPL-3.0-only
"""Vergleichbare Berichte mit stabilen CSV-Schlüsseln und optionaler Anonymisierung.

Rohdaten der laufenden Anwendung werden nie verändert. Freie Diagnoseausgaben
werden im anonymisierten Bericht entfernt, da sie beliebige Identifikatoren
enthalten können. Adresse-Tokens sind nur innerhalb eines Berichts stabil.
"""
import copy
import csv
import ipaddress
import json
import re
from . import VERSION
from .observations import core_kernel_row,unsupported_queries,default_routes
from .packages import connected


def summary(snapshot):
    adapters=snapshot.get('adapters',[]);issues=snapshot.get('issues',[])
    def failed(tool):return any(i.get('code','').startswith('IS2') and i.get('detail','').split(' ')[0]==tool for i in issues)
    routes=snapshot.get('default_routes',default_routes(snapshot.get('routes',[])))
    failed_queries={i.get('detail','') for i in issues if i.get('code','').startswith('IS2')}
    # Scanner.issues erfasst Befehlsfehler einmal; deren Darstellungszeilen nicht doppelt zählen.
    if not issues:
        failed_queries.update(r.get('field','') for r in snapshot.get('extended',[]) if r.get('result','').startswith('IS'))
    return {
      'adapter_count':len(adapters),
      'physical_count':sum(a.get('classification')=='physical' for a in adapters),
      'virtual_count':sum(a.get('classification')=='virtual' for a in adapters),
      'unknown_adapter_count':sum(a.get('classification') not in ('physical','virtual') for a in adapters),
      'connected_ipv4_adapters':sum(bool(a.get('ipv4')) and connected(a) and a.get('adapter_kind')!='loopback' for a in adapters),
      'tcp_listen_sockets':'unknown' if failed('ss') else sum(s.get('protocol')=='tcp' for s in snapshot.get('services',[])),
      'udp_bound_sockets':'unknown' if failed('ss') else sum(s.get('protocol')=='udp' for s in snapshot.get('services',[])),
      'standard_gateways':list(dict.fromkeys(r['gateway'] for r in routes if r.get('gateway') and r.get('preference') in ('preferred_metric','equal_candidate'))),
      'dns_servers':list(dict.fromkeys(line for a in adapters for line in a.get('dns','').splitlines() if line)),
      'unsupported_count':len(unsupported_queries(snapshot.get('extended',[]))),
      'failed_query_count':len(failed_queries),
      'finding_count':len(snapshot.get('findings',[])),
    }


def report_data(snapshot,mode='standard',anonymize=False):
    if mode not in ('standard','full','text'):raise ValueError('report mode')
    report={'report':{'schema':'ipsnoop-report-v2','version':VERSION,'mode':mode,'anonymized':anonymize},
            'summary':summary(snapshot),'scan':snapshot.get('scan',{})}
    for section in ('adapters','neighbors','default_routes','routes','services','connections','wifi','system','live','findings','issues','diagnostics'):
        report[section]=snapshot.get(section,{} if section=='system' else [])
    report['unsupported_queries']=[{'query':q} for q in unsupported_queries(snapshot.get('extended',[]))]
    extended=snapshot.get('extended',[])
    if mode=='full':
        report['extended']=extended;report['neighbor_records']=snapshot.get('neighbor_records',[])
    else:
        report['neighbors']=[{k:v for k,v in n.items() if k!='observations'} for n in report['neighbors']]
        # Freie Treiber-, Firewall- und Topologiedetails bleiben im Vollbericht.
        report['extended']=[r for r in extended if r.get('group')=='kernel_params' and core_kernel_row(r)
                            or r.get('group')=='bluetooth'
                            or r.get('result') not in ('ok','empty') or 'group' not in r]
    report=copy.deepcopy(report)
    return anonymize_report(report) if anonymize else report


def anonymize_report(report):
    """Pseudonyme statt IP/MAC; sensible Felder und freie Rohtexte entfernen."""
    tokens={}
    def token(kind,value):
        key=(kind,str(value))
        if key not in tokens:tokens[key]=f'{kind}-{1+sum(k[0]==kind for k in tokens)}'
        return tokens[key]
    mac=re.compile(r'(?i)(?<![\w:])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![\w:])')
    ipv4=re.compile(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])')
    ipv6=re.compile(r'(?<![\w:])[0-9a-fA-F]*:[0-9a-fA-F:.]+(?:%[\w.-]+)?')
    domain=re.compile(r'(?i)(?<![\w.])(?:[a-z0-9_-]+\.)+[a-z][a-z0-9_-]*(?![\w.])')
    private={'hostname','domains','machine_id','boot_id','process','pid','user','executable','resolver','connection','ssid','serial','duid','client_id'}
    def text(value):
        value=mac.sub(lambda m:token('MAC',m[0].lower()),value)
        def address(match):
            try:ip=ipaddress.ip_address(match[0].split('%')[0]);return token('IP'+str(ip.version),str(ip))
            except ValueError:return match[0]
        value=ipv4.sub(address,value);value=ipv6.sub(address,value)
        return domain.sub(lambda m:token('HOST',m[0].lower()),value)
    def walk(value,key='',section=''):
        if key in private:return '[removed]'
        if key in ('name','dev','interfaces'):
            if isinstance(value,list):return [token('IF',v) for v in value]
            return token('IF',value) if value else value
        if section=='extended' and key in ('field','value') and isinstance(value,str):
            # Numerische Werte und Statuscodes sind nützlich; freie Texte nicht.
            if key=='value' and re.fullmatch(r'-?\d+(?:\.\d+)?',value):return value
            return '[free diagnostic text removed]'
        if section in ('diagnostics','findings') and key in ('value','driver_counters'):return '[removed]'
        if key in ('detail','query'):return '[diagnostic text removed]'
        if isinstance(value,dict):return {k:walk(v,k,section) for k,v in value.items()}
        if isinstance(value,list):return [walk(v,'',section) for v in value]
        return text(value) if isinstance(value,str) else value
    return {section:walk(value,section,section) for section,value in report.items()}


def export_csv(path,snapshot,t,mode='standard',anonymize=False):
    """Vier feste Spalten; Feld- und Bereichskennungen werden nicht übersetzt."""
    def safe(value):
        if isinstance(value,bool):text='true' if value else 'false'
        elif value is None:text='unknown'
        else:text=json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else str(value)
        return "'"+text if text.lstrip().startswith(('=','+','-','@','\t','\r')) else text
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream,delimiter=';');writer.writerow(['section','entry','field','value'])
        for section,value in report_data(snapshot,mode,anonymize).items():
            rows=[value] if isinstance(value,dict) else value
            for index,data in enumerate(rows,1):
                for key,value in data.items():writer.writerow([section,index,key,safe(value)])


def export_text(path,snapshot,t,anonymize=False):
    report=report_data(snapshot,'text',anonymize)
    lines=['ipSnoop '+VERSION,t('short_report'),'']
    def show(value):
        if isinstance(value,list):return ', '.join(show(v) for v in value)
        if isinstance(value,bool):return t('yes' if value else 'no')
        return t(value) if isinstance(value,str) else str(value)
    for section in ('scan','summary'):
        lines.append(t(section))
        lines.extend(f'{t(k)}: {show(v)}' for k,v in report[section].items());lines.append('')
    lines.extend([t('default_routes'),t('routes_hint')])
    for row in report['default_routes']:
        lines.append(' · '.join(f'{t(k)}: {show(row[k])}' for k in ('family','preference','dev','gateway','metric') if k in row))
    lines.extend(['',t('findings')])
    for row in report['findings']:
        lines.extend([f'{row["name"]}: {t(row["code"])}',f'RX-Drops: {row.get("rx_dropped", "")} · {t("threshold")}: {row.get("threshold", "")}',t('driver_counters_not_additive')])
    if not report['findings']:lines.append(t('none'))
    lines.extend(['',t('unsupported_queries')]);lines.extend(q['query'] for q in report['unsupported_queries'])
    lines.extend(['',t('issues')])
    lines.extend(f'{r.get("code", "")}: {t(r.get("code", ""))} {r.get("detail", "")}' for r in report['issues'])
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
