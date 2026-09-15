# SPDX-License-Identifier: GPL-3.0-only
"""Direkt erreichbare Kategorien, Themengruppen und eindeutige 3D-Symbole.

Die Gruppierung betrifft die Oberfläche. Berichte verwenden eigene stabile
Bereichs- und Feldkennungen; die Exportaufbereitung liegt in reporting.py.
"""
NAVIGATION=(
    ('group_devices',('adapters','adapter_extra','neighbors','wifi','wifi_details','bluetooth','lldp')),
    ('group_routing',('dns_details','routes','policy','topology','namespaces')),
    ('group_connections',('services','connections','conntrack','firewall','vpn')),
    ('group_diagnostics',('live','tcp_quality','protocol_stats','traffic','diagnostics')),
    ('group_system',('system','kernel_params')),
)
PAGE_ICONS={
    'adapters':'network-3d.png','adapter_extra':'pcie-3d.png','neighbors':'connections-3d.png',
    'wifi':'wifi-3d.png','wifi_details':'wifi-details-3d.png','bluetooth':'bluetooth-3d.png','lldp':'lldp-3d.png',
    'dns_details':'dns-3d.png','routes':'routing-3d.png','policy':'policy-routing-3d.png',
    'topology':'topology-3d.png','namespaces':'overview-3d.png',
    'services':'services-3d.png','connections':'connection-duplex-3d.png','conntrack':'conntrack-3d.png',
    'firewall':'security-3d.png','vpn':'vpn-3d.png','live':'live-meter-3d.png',
    'tcp_quality':'tcp-quality-3d.png','protocol_stats':'protocol-stats-3d.png','traffic':'traffic-qos-3d.png',
    'diagnostics':'diagnostics-3d.png','system':'linux-3d.png','kernel_params':'kernel-3d.png',
}
PAGE_ORDER=tuple(name for _,names in NAVIGATION for name in names)
