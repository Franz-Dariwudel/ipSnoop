# ipSnoop 1.4.4

GTK-4-Programm für Linux Mint zum Auslesen eigener Netzwerkadapter und vorhandener Netzwerkdaten. Zeigt IPv4/IPv6 mit Präfix, MAC und permanente MAC, Subnetze, Gateway, DNS, Routing-Metrik, IP-Konfigurationsmethode, Treiber/Firmware, Link-Modi, Geschwindigkeit, Duplex, MTU und Fehlerzähler.

Weitere Ansichten zeigen bekannte Nachbarn aus dem Kernel-Cache, WLAN-Netze aus dem NetworkManager-Cache, lokale TCP-/UDP-Sockets, Routen und Systeminformationen. Die Nachbarliste ist keine vollständige Liste aller LAN-Geräte. Das Programm verändert keine Netzwerkeinstellungen, startet keinen aktiven Netzwerkscan und zeichnet keinen Datenverkehr auf. In einer VM sieht es die Netzwerksicht des Gasts.

## Voraussetzungen und Start

Linux Mint, Python 3.10+, GTK 4.8+, `python3-gi`, `gir1.2-gtk-4.0`, `iproute2`; ergänzend `network-manager` und `ethtool`. Die Oberfläche startet mit Cairo-Rendering auch ohne GPU-Zugriff. Systemthema und Systemschrift bleiben wirksam.

```bash
python3 -m ipsnoop
python3 -m ipsnoop --version
python3 -m ipsnoop --help
python3 -m ipsnoop --check
python3 -m ipsnoop --scan
```

`--scan` gibt JSON aus, auch ohne grafische Sitzung. Exitcode 0 bei erkannten Adaptern, sonst 1. `--check` prüft Sprach-/Hilferessourcen und Icons; Exitcode 1 bei Fehlern. JSON/CSV können IP-Adressen, MACs, Maschinenkennungen und lokale Prozessangaben enthalten.

## Bedienung

**Aktualisieren** liest neue Daten im Hintergrund. Standardmäßig wird nur beim Start und auf Knopfdruck aktualisiert. **Bearbeiten → Einstellungen** bietet 5, 10 oder 30 Sekunden sowie die Sprachauswahl. Suchfeld und Schalter filtern die Anzeige; bekannte Fehler und unbekannte Zustände bleiben sichtbar. Die Adapterauswahl unter der Übersicht zeigt sämtliche Details zum ausgewählten Gerät. **Bericht speichern** exportiert den gewählten Bericht, unabhängig vom Suchfilter. Fehlende Daten stehen rot; Nullwerte bleiben gültig.

IPv4-Methode `auto` bezeichnet gewöhnlich DHCP. Bei IPv6 kann `auto` auch SLAAC verwenden; daraus wird kein DHCPv6-Status geraten. Die maximale Geschwindigkeit wird ausschließlich aus gemeldeten Link-Modi abgeleitet. Ein Port in der lokalen Socketliste ist nicht zwangsläufig von außen erreichbar. STALE bezeichnet einen Cachezustand, nicht automatisch ein ausgeschaltetes Gerät. Fehlende optionale Daten lösen keine Installation oder Rechteanhebung aus.

## Sprachen, Hilfe und Dateien

Deutsch und Englisch sind enthalten. `languages/<code>.json` ist ein UTF-8-JSON-Objekt mit Textschlüsseln und Textwerten. Beim Öffnen der Einstellungen werden die Kataloge neu erkannt. Englische Texte dienen als Rückfall; genau eine gültige Sprache wird ohne Auswahl verwendet. Die HTML-Hilfe wird beim Aufruf passend zur aktuellen Sprache neu gelesen (`help/<code>.html`), ohne Wechsel zu einer anderen Sprache.

Konfiguration: `config/settings.json`. Fehlerlogs: `logs/errors.log` mit Rotation innerhalb der laufenden Sitzung. Beim Programmstart (Oberfläche, `--scan` oder `--check`) wird die Datei geleert; `errors.log.1` und `errors.log.2` werden entfernt. Aktualisieren und Dialoge erhalten die aktuellen Meldungen. `--help` und `--version` verändern das Protokoll nicht. Fehlercodes IS001–IS401 sind in beiden HTML-Hilfen dokumentiert. Systemabfragen sind auf je zwei Sekunden begrenzt und laufen außerhalb des GTK-Threads. Der Wortlaut technischer Kernel-/Werkzeugwerte bleibt unverändert.

## Tests, Build, Installation und Deinstallation

```bash
python3 -m unittest discover -s tests
python3 build.py
python3 install.py --directory /absoluter/leerer/zielordner
python3 /absoluter/leerer/zielordner/install.py --uninstall
```

Der Installer benötigt die entpackte Ausgabe mit `build-info.json`. Die kompilierte Ausgabe benötigt dieselbe Python-Haupt-/Nebenversion wie der Build (3.12 in der bereitgestellten Ausgabe), GTK und PyGObject. Sie ist kein unabhängiges natives Binary.

Der Installer erfasst alle installierten Dateien in `installation.json`. Deinstallation entfernt diese Dateien und leere eigene Ordner; später erzeugte persönliche Dateien bleiben erhalten. Es werden keine Desktop- oder Menüdateien installiert. Auslieferungen enthalten weder Benutzereinstellungen noch Logs oder Test-Scanergebnisse.

## Lizenz und Herkunft

GNU GPL Version 3 ausschließlich (`GPL-3.0-only`), vollständiger Text in LICENSE. Autor: Josef Lehner. Website: https://dogtruck.eu.

Das Netzwerkicon und die blaue Info-Wolke stammen aus der vorhandenen persönlichen 3D-Sammlung und wurden ursprünglich mit OpenAI-Bildgenerierung für pcMonitor erstellt; siehe `resources/HERKUNFT.md`. Linux, Python, GTK, PyGObject, iproute2, NetworkManager und ethtool stammen von ihren jeweiligen Entwicklergemeinschaften.

## Detailabfragen

Im Menü Kategorien die gewünschte Detailkategorie auswählen. Adapter-/DHCP-Daten, ethtool-Statistiken, PCI, DNS, IPv6, Policy Routing, Firewall, VLAN/Bridge/Bond, virtuelle Netze, Protokollzähler, Kernelparameter, QoS, WLAN, Bluetooth und benannte Namespaces werden lokal gelesen. Prozessdaten und Firewall-Regeln hängen von den Rechten des gestarteten Benutzers ab. Nicht verfügbare Angaben werden nicht geschätzt.

**Verbindungen** ergänzt die Dienste um aktive TCP-/UDP-Sockets mit PID, Benutzer und Programmdatei. Nachbarn erhalten Cache-Details und vorhandene lokale Hosts-/OUI-Zuordnungen. Unter **Verbindungstests** können Ping, Namensauflösung und Tracepath ausdrücklich gestartet werden (20 Sekunden Zeitlimit). Ziel selbst eingeben; diese Tests können Netzwerkverkehr senden. Die vollständige Diagnose-CSV enthält alle zusätzlichen Daten und Statusangaben.

Optionale Programme: `lspci`, `resolvectl`, `sysctl`, `bridge`, `tc`, `nft`, `ufw`, `iw`, `bluetoothctl`, `ping`, `getent`, `tracepath`; Docker/Podman nur falls installiert, ausschließlich lokal. Die deutsche und englische HTML-Hilfe beschreibt Voraussetzungen und Grenzen.

Die Bereichsauswahl befindet sich im Menü Kategorien; die Ergebnisse nutzen die Fensterbreite.

## Live-Daten und zusätzliche Detailabfragen (1.3.0)

Im Kategorienmenü **Live-Daten** für sekündliche RX/TX-Raten in Bytes/s, Paketen/s und Fehlern/s auswählen. Eigene Kategorien bieten TCP-Qualität, LLDP, Connection Tracking und VPN-Erkennung; NIC-Details ergänzen Kanäle, RSS und Timestamping. nftables-Zähler erscheinen, soweit konfiguriert. Optionale Werkzeuge: lldpcli, conntrack, wg. Rechte und laufende lokale Dienste bestimmen die Verfügbarkeit. Die HTML-Hilfe beschreibt Grenzen und Messverfahren.

Bekannte Geräte erhalten automatisch Namen über `/etc/hosts` und `getent` (lokale NSS-/DNS-/mDNS-Konfiguration). Diese begrenzte Namensauflösung kann Netzwerkverkehr erzeugen.

## Bereichsauswahl (1.3.0)

24 Kategorien in fünf Themengruppen ersetzen die bisherige Sammelauswahl Erweitert. Die Menüeinträge werden ohne Icons angezeigt. Im Kategorienmenü hilft die Bereichssuche beim Auffinden einer Kategorie. Die obere Suche filtert deren Ergebnisse; Tabellenköpfe bleiben fixiert. CSV v2 verwendet feste technische Feldkennungen; der Vollbericht erhält zusätzlich die einzelnen Nachbarbeobachtungen.

Optionale ethtool-Detailabfragen: Nicht unterstützte Funktionen und „No data available“ erscheinen neutral. Fehlende Werkzeuge, Zugriffsfehler und Zeitüberschreitungen bleiben Warnungen. Beim nächsten Programmstart wird das Protokoll wie oben beschrieben zurückgesetzt.

## Berichte ab 1.4.4

Oberhalb der Ergebnisse den Export wählen: **Standard-CSV**, **Vollständige Diagnose-CSV** oder **Kurzbericht (TXT)**. Die Standard-CSV enthält Zusammenfassung, Scan-Zeiten, Adapter, gruppierte Nachbarn, Routen, Sockets, Live-Daten, Auffälligkeiten, Abfragestatus und die zentrale Kernelauswahl. Umfangreiche freie Treiber-/Firewall-/Topologiedaten stehen im Vollbericht einschließlich aller erfassten sysctl-net-Werte und einzelnen Nachbarbeobachtungen. Fehlende Daten werden nicht ergänzt oder geschätzt. CSV hat vier feste Spalten `section;entry;field;value`; Bereichs- und Feldkennungen bleiben sprachunabhängig. Die Schema-Kennung ist `ipsnoop-report-v2`. Bestehende Auswertungen müssen die neuen technischen Feldnamen berücksichtigen.

**Persönliche Daten anonymisieren** wirkt nur auf die Exportkopie: IP-/MAC-Adressen erhalten innerhalb des Berichts gleiche Pseudonyme, Hostnamen, SSIDs, Maschinen-/Boot-ID und Prozessinformationen werden entfernt. Freie Diagnosetexte werden entfernt, da sie weitere Identifikatoren enthalten können. Das Ergebnis ist ein pseudonymisierter technischer Bericht; strukturierte Hardware-/Netzwerkmerkmale können weiterhin erkennbar sein. Vor einer Veröffentlichung den Bericht prüfen. Die Originaldaten in der Anwendung bleiben vollständig.

Nachbarn werden über eine brauchbare MAC gruppiert; IP-Adressen und Schnittstellen bleiben in der Gruppe erhalten. Ohne MAC wird nicht über verschiedene IPs/Schnittstellen hinweg gruppiert. Eine MAC ist keine globale Identitätsgarantie (z. B. geklonte MACs oder verschiedene Netzsegmente). Altersfelder `neighbor_used_s`, `neighbor_confirmed_s`, `neighbor_updated_s` sind Sekunden seit dem jeweiligen Ereignis. `router: null` im iproute2-JSON ist ein gesetztes Router-Flag und wird `true`; fehlende Markierung bleibt `unknown`. Das ist keine abschließende Aussage über die Routerfähigkeit eines Geräts.

Zähler sind kumuliert seit ihrer letzten Rücksetzung; deren genauer Zeitpunkt ist unbekannt. Ab **10.000 RX-Drops** erscheint ein Prüfhinweis. Diese dokumentierte Sichtungsschwelle ist kein allgemeiner Grenzwert für Hardwaredefekte. Passende ethtool-Treiberzähler werden getrennt daneben gezeigt und wegen möglicher Überschneidungen nicht addiert. Bytes bleiben als Rohwerte erhalten und erhalten zusätzlich IEC-Einheiten (KiB/MiB/GiB).

Physische und virtuelle Adapter werden anhand von sysfs und Kernel-Gerätetypen unterschieden. Virtio gilt als virtuell; nicht eindeutig zuordenbare Geräte bleiben unbekannt. Fehlende Modelle werden aus dem zum Gerät gehörenden PCI-Eintrag von lspci ergänzt; sonst dient eine exakt gelesene PCI-ID als Fallback. Es werden keine Modellnamen aus Treiber-/Firmware-Namen geraten.

Live-Daten ergänzen RX/TX-Drops pro Sekunde, tatsächliche Messdauer, UTC-Zeit und rollende Minima/Maxima der Byte-Raten über maximal 60 Sekunden. Eine neue Messbasis oder Zählerrücksetzung verwirft alte Extremwerte. Prozentwerte setzen eine gemeldete physische Linkgeschwindigkeit voraus und sind getrennt für RX/TX berechnet, nicht als Internetgeschwindigkeit. Virtuelle oder unbekannte Links bekommen keinen erfundenen Prozentwert.

Die Standardroutenübersicht vergleicht nur die Haupttabelle nach Metrik, getrennt nach IPv4/IPv6. Policy Routing, Router-Präferenzen, gleichrangige Wege und das Ziel können die reale Auswahl ändern. Bluetooth zeigt getrennt Kernel-Hardware, aktiven BlueZ-Dienst und nutzbaren Standard-Controller; ein erfolgreicher leerer Befund ist kein Fehler.

Die Kernelansicht zeigt zunächst zehn zentrale Schlüssel; **Alle Kernel-Netzwerkparameter anzeigen** öffnet die gesamte erfasste Auswahl. Der Vollbericht exportiert diese unabhängig vom Ansichtsfilter. Beispielschlüssel: `net.ipv4.ip_forward`, `net.ipv6.conf.all.forwarding`, `net.ipv4.conf.all.rp_filter`, `net.ipv4.tcp_syncookies`, `net.ipv4.tcp_congestion_control`, `net.ipv4.tcp_mtu_probing`, `net.ipv6.conf.all.disable_ipv6`, `net.ipv6.conf.all.accept_ra`, `net.mptcp.enabled`, `net.netfilter.nf_conntrack_max`. Nicht vorhandene Schlüssel werden nicht erfunden.

Technische Grundlagen: [iproute2-Nachbarcache](https://github.com/iproute2/iproute2/blob/main/ip/ipneigh.c), [Linux-Schnittstellenstatistiken](https://www.kernel.org/doc/html/latest/networking/statistics.html).

## Kategorienmenü und Logs (1.4.4)

Das Menü **Kategorien** bündelt die 24 Ansichten in fünf Gruppen mit Suche. Die Ergebnisansicht nutzt die gesamte Breite. **Hilfe → Logs anzeigen** öffnet das aktuelle Sitzungsprotokoll schreibgeschützt mit Aktualisieren. IS107 meldet eine fehlende, nicht lesbare oder ungültig kodierte Logdatei.

Die fünf Gruppen im Kategorienmenü sind separat aufklappbar und anfangs geschlossen. Die Suche öffnet passende Gruppen vorübergehend.

## Downloads

- [Quellcodepaket 1.4.4](downloads/ipSnoop-1.4.4-quellcode.zip)
- [Kompilierte Ausgabe für Python 3.12](downloads/ipSnoop-1.4.4-python3.12-kompiliert.tar.gz)
- [SHA256-Prüfsummen](downloads/ipSnoop-1.4.4-SHA256SUMS.txt)
