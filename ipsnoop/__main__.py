# SPDX-License-Identifier: GPL-3.0-only
"""CLI-Einstieg; JSON-Erfassung funktioniert auch ohne grafische Sitzung."""
import argparse
import json
import sys
from . import ROOT,VERSION
from .config import Translator,logger
from .scanner import Scanner
from .categories import PAGE_ICONS


def main():
    parser=argparse.ArgumentParser(description='ipSnoop – lokale Netzwerkdaten lesen / read local network data')
    parser.add_argument('--version',action='version',version=VERSION)
    parser.add_argument('--scan',action='store_true',help='Netzwerkdaten als JSON / network data as JSON')
    parser.add_argument('--check',action='store_true',help='Dateien prüfen / check resources')
    args=parser.parse_args()
    # Nach --help/--version, aber vor Konfiguration, Prüfung und Erfassung.
    logger(reset=True)
    if args.scan:
        data=Scanner().scan();print(json.dumps(data,ensure_ascii=False,indent=2))
        return 1 if not data['adapters'] else 0
    if args.check:
        translator=Translator();errors=translator.errors.copy()
        # Auch nachgelieferte Sprach- und Hilfedateien vollständig prüfen.
        codes={'de','en'}|set(translator.catalogs)|{p.stem for p in (ROOT/'help').glob('*.html')}
        for code in sorted(codes):
            try:
                if '<html' not in (ROOT/'help'/(code+'.html')).read_text().lower():raise ValueError()
            except (OSError,ValueError,UnicodeError):errors.append('IS105')
        for name in set(PAGE_ICONS.values())|{'ipsnoop.png','info-3d.png','ipsnoop-app-3d.png','ipsnoop-logo-3d.png'}:
            if not (ROOT/'resources'/name).is_file():errors.append('IS106')
        print('\n'.join(errors) if errors else 'ipSnoop '+VERSION+': OK');return 1 if errors else 0
    try:
        from .app import Application
        return Application().run([sys.argv[0]])
    except (ImportError,ValueError):
        print('IS001: Python 3.10+, python3-gi, gir1.2-gtk-4.0',file=sys.stderr);return 1
    except Exception:
        logger().exception('IS299');return 1


if __name__=='__main__':raise SystemExit(main())
