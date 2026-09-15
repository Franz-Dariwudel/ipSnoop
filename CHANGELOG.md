# 1.5.0

- Zehn vollständige Sprachkataloge: de, en, es, fr, pt, zh, hi, ar, ru, tr; jeweils 281 Texte.
- Passende HTML-Hilfe für alle zehn Sprachen einschließlich Fehlercodes und Bedienung.
- Arabische Oberfläche und Hilfe mit Schreibrichtung von rechts nach links.
- Dynamische Spracherkennung und englischer Textrückfall bleiben erhalten.

# 1.4.4

- Icons aus den Einträgen im Kategorienmenü entfernt.

# 1.4.3

- Menüfolge: Datei, Bearbeiten, Kategorien, Hilfe.

# 1.4.2

- Kategoriengruppen separat auf- und zuklappbar; Suche öffnet Treffergruppen vorübergehend.

# 1.4.1

- Linke Kategorienleiste in das Menü Kategorien verlagert; fünf Gruppen, 3D-Icons und Suche bleiben erhalten.
- Hilfe → Logs anzeigen mit schreibgeschützter Ansicht, Aktualisieren und Fehlermeldung IS107.

# 1.4.0

- Nachbarcache mit eigenen Altersfeldern, klarer Router-Markierung und MAC-Gruppierung; Detailbeobachtungen bleiben erhalten.
- Adapterklasse, PCI-Modellergänzung, lesbare Datenmengen und kumulierte Zähler. RX-Drop-Prüfhinweis ab 10.000 mit getrennten Treiberzählern.
- Standardrouten nach Familie/Metrik, Bluetooth-Status, neutrale Liste nicht unterstützter Abfragen und Ergebnisübersicht.
- Live-Drops/s, Linkauslastung für bekannte physische Links, UTC-Zeitstempel, Messdauer und 60-Sekunden-Minima/Maxima.
- Scan-Beginn/-Ende/-Dauer; Kernelansicht standardmäßig auf zentrale Parameter begrenzt, Gesamtansicht zuschaltbar.
- Drei Berichtsarten: Standard-CSV, vollständige Diagnose-CSV und TXT-Kurzbericht. CSV v2 mit festen technischen Schlüsseln und Zusammenfassung.
- Optionale Anonymisierung der Exportkopie: IP/MAC-Pseudonyme, entfernte Namen/Prozessinformationen und freie Diagnoseausgaben. Lokale Rohdaten unverändert.

# 1.3.1

- Fehlerprotokoll beim Programmstart zurücksetzen, einschließlich der beiden Rotationsdateien. Meldungen der laufenden Sitzung bleiben bis zum nächsten Start erhalten.
- Adminstart erhält den Eigentümer des Protokollordners für die Logdatei; Probleme beim Zurücksetzen werden mit IS101 im Terminal gemeldet.
- Absichtliche CSV-Fehlertests verwenden einen separaten Testlogger und keine persönlichen Einstellungen.

# 1.3.0

- Erwartete Treibergrenzen optionaler ethtool-Detailabfragen erscheinen neutral und ohne IS202-Warnung. Echte Fehler bleiben sichtbar.

- 24 direkt auswählbare Kategorien mit jeweils eigenem 3D-Icon, gegliedert in fünf Themengruppen.
- Bisherige Kategorien aus Erweitert direkt in die Seitenleiste aufgenommen.
- Eigene Suche für Kategorien und Themengruppen; Ergebnissuche bleibt unabhängig.
- Detailansichten werden bei Auswahl aufgebaut; fixierte Köpfe, Adminhinweise, Live-Daten und CSV-Datenstruktur bleiben erhalten.

# 1.2.5

- Effektive Benutzer-ID für den Startmodus prüfen und im Status anzeigen.
- Hinweise auf fehlende Administratorrechte bei lokalen Diensten und Verbindungen nur im normalen Benutzermodus anzeigen.
- Tatsächliche Abfragefehler bleiben auch im Administratormodus sichtbar.

# 1.2.4

- Nicht verbundene Adapter standardmäßig ausgeblendet; unbekannter Zustand bleibt sichtbar.
- Fehlende Pakete oberhalb der Ergebnisse mit Paketnamen und Installationsbefehl hervorgehoben.
- Admin-Speicherung erhält den Eigentümer des Konfigurationsordners; bestehende Root-Einstellungen werden beim nächsten Adminstart korrigiert.

# 1.2.3

- Bekannte Geräte: automatische Reverse-Namensauflösung über getent/NSS (DNS und konfiguriertes mDNS).
- Lokale Hosts-Datei hat Vorrang. Begrenzte parallele Abfragen, Zeitlimit und kurzzeitiger Cache.
- Namensauflösungsstatus unterscheidet fehlende Namen, ausstehende und fehlgeschlagene Abfragen.

# 1.2.2

- Überhöhte kurze Menüs Datei und Bearbeiten unter Linux Mint korrigiert.
- Mindesthöhe unsichtbarer Scrollbalken nur in diesen Menüs aufgehoben; Systemthema und Menübedienung bleiben erhalten.

# 1.2.1

- Fixierte Spaltenüberschriften in sämtlichen Bereichen.
- Auswahlfelder und Bedienung bleiben sichtbar; Tabellen scrollen separat mit synchronem horizontalem Kopf.
- Nachbar-Cache-Details in gemeinsamer Ergebnistabelle statt vieler einzelner Tabellen.

# 1.2.0

- TCP-Qualität über ss -ti, NIC-Kanäle/RSS/Zeitstempel über ethtool -l/-x/-T.
- LLDP, Connection Tracking, nftables-Zähler und VPN-/WireGuard-Erkennung.
- Separater Live-Bereich mit Bytes/s, Paketen/s und Fehlern/s je Richtung und Schnittstelle.
- Sekündliche passive Messung mit monotoner Zeit; erste Messung, Resets und Gerätewechsel liefern keine falschen Spitzen.

# 1.1.3

- Im Bereich Erweitert bleiben Kategorieauswahl und Spaltenüberschriften beim vertikalen Scrollen sichtbar.
- Horizontales Scrollen hält Kopf und Ergebniszeilen spaltengleich.

# 1.1.2

- Bereiche mit 3D-Icons links als vertikale Auswahl; Ergebnisse rechts.
- Seitenleiste separat scrollbar und Breite verstellbar; Auswahl bleibt bei Sprachwechsel erhalten.

# 1.1.1

- Neue 3D-Grafiken in Symbolleiste, Reitern und erweiterten Kategorien integriert.
- Eigenes ipSnoop-Logo in der Über-Box und Programmsymbol für das Fenster.

# 1.1.0

- Erweiterte Linux-Netzwerkabfragen: Adapterstatistiken, Wake-on-LAN, ethtool, PCI, DHCP, DNS, IPv6, Policy Routing, VLAN/Bridge/Bond, Firewall, Verbindungen und Prozesse, Protokollzähler, Kernelparameter, QoS, WLAN, Bluetooth und Namespaces.
- Lokale Hosts- und OUI-Zuordnung; virtuelle Linkgeschwindigkeit als nicht anwendbar.
- Separater, manuell gestarteter Ping-, Namensauflösungs- und Tracepath-Test.
- Vollständiger CSV-Export der zusätzlichen Daten und Abfragestatus.

# 1.0.1

- Lebensdauer des nativen CSV-Speicherdialogs korrigiert; Ordnerabfrage wird nicht mehr vorzeitig abgebrochen.
- Vorhandenen Dialog wiederverwenden und beim Schließen des Hauptfensters aufräumen.

# 1.0.0

- Erste GTK-4-Ausgabe mit sechs Ansichten für lokale Linux-Netzwerkdaten.
- IP/MAC, DNS/Gateway, Linkdaten, bekannte Nachbarn, WLAN-Cache und lokale Sockets.
- Hintergrundabfragen, Suche, CSV, Einstellungen sowie Deutsch und Englisch mit HTML-Hilfe.
- Bereinigte Quellcode- und Bytecode-Ausgabe mit Installation und Dateijournal zur Deinstallation.
