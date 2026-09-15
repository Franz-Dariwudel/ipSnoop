# SPDX-License-Identifier: GPL-3.0-only
"""Passive Raten, Drops und 60-Sekunden-Minima/Maxima aus Linux-Zählern.

Monotone Zeit für Differenzen, UTC-Zeitstempel für Berichte. Linkauslastung ist
nur bei bekannter physischer Linkgeschwindigkeit sinnvoll, kein Internettest.
"""
from collections import deque
from datetime import datetime,timezone
from pathlib import Path
import re
import time
from .observations import human_bytes

COUNTERS=('rx_bytes','tx_bytes','rx_packets','tx_packets','rx_errors','tx_errors','rx_dropped','tx_dropped')

class Rates:
    def __init__(self,root=Path('/sys/class/net')):
        self.root=Path(root);self.previous={};self.history={}

    def sample(self,now=None,wall_time=None,links=None):
        now=time.monotonic() if now is None else now
        stamp=datetime.fromtimestamp(time.time() if wall_time is None else wall_time,timezone.utc).isoformat()
        current={};rows=[];histories={}
        try:interfaces=sorted(self.root.iterdir())
        except OSError:return [{'name':'sysfs','rate_status':'unavailable','measured_at':stamp}]
        for interface in interfaces:
            row={'name':interface.name,'measured_at':stamp,'window_s':60};values={}
            try:
                identity=(interface.name,(interface/'ifindex').read_text().strip(),(interface/'address').read_text().strip())
                for key in COUNTERS:
                    values[key]=int((interface/'statistics'/key).read_text())
                    if values[key]<0:raise ValueError()
            except (OSError,ValueError):
                row['rate_status']='unavailable';rows.append(row);continue
            previous=self.previous.get(identity);history=self.history.get(identity,deque())
            row['rate_status']='warming_up';row['rx_utilization_pct']=row['tx_utilization_pct']='not_applicable'
            if previous and now>previous[0]:
                elapsed=now-previous[0];row['interval_s']=round(elapsed,4)
                if any(values[key]<previous[1][key] for key in COUNTERS):row['rate_status']='counter_reset';history=deque()
                else:
                    row['rate_status']='ok'
                    for key in COUNTERS:row[key+'_s']=round((values[key]-previous[1][key])/elapsed,2)
                    history.append((now,row['rx_bytes_s'],row['tx_bytes_s']))
                    while history and history[0][0]<now-60:history.popleft()
                    speed=self.speed(interface,links)
                    for direction,index in (('rx',1),('tx',2)):
                        row[direction+'_data_s']=human_bytes(row[direction+'_bytes_s'])+'/s'
                        row[direction+'_bytes_s_min']=min(item[index] for item in history)
                        row[direction+'_bytes_s_max']=max(item[index] for item in history)
                        if speed:row[direction+'_utilization_pct']=round(row[direction+'_bytes_s']*8/(speed*1000000)*100,2)
                    row['window_elapsed_s']=round(now-history[0][0],3)
            else:history=deque()
            current[identity]=(now,values);histories[identity]=history;rows.append(row)
        self.previous=current;self.history=histories
        return rows

    def speed(self,interface,links):
        if links is not None:
            link=links.get(interface.name,{})
            if link.get('classification')!='physical':return None
            match=re.fullmatch(r'(\d+(?:\.\d+)?)\s*Mb/s',str(link.get('speed','')))
            return float(match[1]) if match and float(match[1])>0 else None
        try:
            if not (interface/'device').exists() or 'virtio' in str((interface/'device').resolve()):return None
            speed=float((interface/'speed').read_text())
            return speed if speed>0 else None
        except (OSError,ValueError):return None
