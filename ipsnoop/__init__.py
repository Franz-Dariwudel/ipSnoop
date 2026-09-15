# SPDX-License-Identifier: GPL-3.0-only
"""ipSnoop: lokale Linux-Netzwerkdaten ausschließlich lesen."""
from pathlib import Path
VERSION = '1.5.4'
ROOT = Path(__file__).resolve().parent.parent

# Systempakete halten ausführbaren Code schreibgeschützt; veränderliche Daten
# liegen getrennt pro Benutzer. Portable Ausgaben behalten ihre Ordnerstruktur.
DATA_ROOT = Path.home()/'.local/share/ipsnoop' if (ROOT/'system-package').is_file() else ROOT

def register_data_file(path):
    """Nur neue, programmgenerierte Dateien für die DEB-Deinstallation erfassen."""
    if DATA_ROOT == ROOT:return
    import json
    import os
    import tempfile
    path=Path(path)
    if path.exists():return
    relative=path.relative_to(DATA_ROOT).as_posix()
    journal=DATA_ROOT/'.installed-files.json'
    DATA_ROOT.mkdir(parents=True,exist_ok=True)
    with _journal_lock:
        records=json.loads(journal.read_text()) if journal.exists() else {'files':[],'directories':[]}
        if relative not in records['files']:records['files'].append(relative)
        fd,name=tempfile.mkstemp(dir=DATA_ROOT,prefix='.journal-')
        try:
            with os.fdopen(fd,'w') as out:json.dump(records,out)
            os.replace(name,journal)
        finally:
            if os.path.exists(name):os.unlink(name)


import threading
_journal_lock=threading.Lock()


def prepare_data():
    """Fehlende Standardressourcen ergänzen und neu angelegte Dateien erfassen."""
    if DATA_ROOT == ROOT:return
    import json
    journal=DATA_ROOT/'.installed-files.json'
    if not journal.exists():
        directories=[name for name in ('','config','logs','languages','help') if not (DATA_ROOT/name).exists()]
        DATA_ROOT.mkdir(parents=True,exist_ok=True)
        journal.write_text(json.dumps({'files':[],'directories':directories}))
    for folder in ('config','logs','languages','help'):
        (DATA_ROOT/folder).mkdir(parents=True,exist_ok=True)
    for folder in ('languages','help'):
        for source in (ROOT/folder).iterdir():
            target=DATA_ROOT/folder/source.name
            register_data_file(target)
            try:
                with target.open('xb') as out:out.write(source.read_bytes())
            except FileExistsError:pass
