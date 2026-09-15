# SPDX-License-Identifier: GPL-3.0-only
"""Fehlende Abfragewerkzeuge ihren Linux-Mint-Paketen zuordnen."""
import shutil
PACKAGES={'ip':'iproute2','ss':'iproute2','bridge':'iproute2','tc':'iproute2',
'nmcli':'network-manager','ethtool':'ethtool','lspci':'pciutils','resolvectl':'systemd-resolved',
'systemctl':'systemd','sysctl':'procps','nft':'nftables','ufw':'ufw','iw':'iw','bluetoothctl':'bluez',
'ping':'iputils-ping','getent':'libc-bin','tracepath':'iputils-tracepath',
'lldpcli':'lldpd','conntrack':'conntrack','wg':'wireguard-tools','teamdctl':'libteam-utils'}
def missing_packages(issues):
    return sorted({PACKAGES[tool] for item in issues if item.get('code')=='IS201'
        for tool in [item.get('detail','').split(' ')[0]] if tool in PACKAGES and not shutil.which(tool)})

def connected(adapter):
    """Nur eindeutig nicht verbundene Adapter ausblenden; unbekannt bleibt sichtbar."""
    return adapter.get('status') not in ('DOWN','LOWERLAYERDOWN','NOTPRESENT') and adapter.get('link')!='no'
