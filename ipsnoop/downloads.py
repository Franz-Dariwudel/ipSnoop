# SPDX-License-Identifier: GPL-3.0-only
"""Geprüfte Sprachressourcen aus einem festen öffentlichen Release nachladen.

Nur JSON und HTML, niemals ausführbaren Code herunterladen. Vorhandene Dateien
werden erhalten. Erst vollständig prüfen, dann atomar ohne Überschreiben ablegen.
"""
import json
import os
import re
import pwd
import tempfile
from pathlib import Path
from urllib.request import urlopen
from . import ROOT,DATA_ROOT,register_data_file

SOURCE = 'https://raw.githubusercontent.com/Franz-Dariwudel/ipSnoop/v1.5.4'
AVAILABLE = {'de':'Deutsch','en':'English','es':'Español','fr':'Français',
             'pt':'Português','zh':'简体中文','hi':'हिन्दी','ar':'العربية',
             'ru':'Русский','tr':'Türkçe'}
LIMIT = 2 * 1024 * 1024


def default_download_dir():
    """Auch beim Administratorstart den Downloadordner des Benutzers verwenden."""
    if os.geteuid()==0:
        uid=int(os.environ.get('PKEXEC_UID') or os.environ.get('SUDO_UID') or ROOT.stat().st_uid)
        return Path(pwd.getpwuid(uid).pw_dir)/'Downloads'
    return Path.home()/'Downloads'


def install_language(code, root=DATA_ROOT, download_dir=None):
    """Fehlende Sprache und Hilfe ergänzen; Zahl neu angelegter Dateien liefern.

    Netzwerkfehler oder ungültige Inhalte verhindern das Speichern. Bei einem
    späteren Schreibfehler bleiben bereits vollständig installierte Dateien
    erhalten; Wiederholen ergänzt ausschließlich die noch fehlenden Dateien.
    """
    if code not in AVAILABLE:
        raise ValueError('Unknown language code')
    root=Path(root)
    download_dir=Path(download_dir) if download_dir is not None else default_download_dir()
    download_dir.mkdir(parents=True,exist_ok=True)
    # Nur unser eigener Unterordner wird anschließend entfernt, nie fremde Downloads.
    with tempfile.TemporaryDirectory(prefix='ipSnoop-language-',dir=download_dir) as staging:
        pending=[]
        for folder,suffix in (('languages','json'),('help','html')):
            target=root/folder/f'{code}.{suffix}'
            if target.is_symlink():raise ValueError(f'Unexpected symbolic link: {target.name}')
            if target.exists():
                if not target.is_file():raise ValueError(f'Not a file: {target.name}')
                continue
            with urlopen(f'{SOURCE}/{folder}/{code}.{suffix}',timeout=15) as response:
                raw=response.read(LIMIT+1)
            if len(raw)>LIMIT:raise ValueError(f'File too large: {target.name}')
            text=raw.decode('utf-8')
            if suffix=='json':
                data=json.loads(text)
                if not isinstance(data,dict) or not data.get('language.name') or not all(
                    isinstance(k,str) and isinstance(v,str) and v.strip() for k,v in data.items()
                ):raise ValueError(f'Invalid catalog: {target.name}')
            elif not re.search(r'<html\b[^>]*\blang=["\']'+re.escape(code)+r'["\']',text,re.I) or '</html>' not in text.lower():
                raise ValueError(f'Invalid HTML help: {target.name}')
            downloaded=Path(staging)/target.name
            downloaded.write_bytes(raw)
            pending.append((target,downloaded))
        installed=0
        for target,downloaded in pending:
            target.parent.mkdir(parents=True,exist_ok=True)
            if root==DATA_ROOT:register_data_file(target)
            fd,name=tempfile.mkstemp(prefix='.download-',dir=target.parent)
            try:
                with os.fdopen(fd,'wb') as stream:
                    stream.write(downloaded.read_bytes());stream.flush();os.fsync(stream.fileno())
                os.chmod(name,0o644)
                if os.geteuid()==0:
                    owner=target.parent.stat();os.chown(name,owner.st_uid,owner.st_gid)
                # Atomar ablegen, ohne zwischenzeitlich angelegte Dateien zu ersetzen.
                try:os.link(name,target);installed+=1
                except FileExistsError:pass
            finally:os.unlink(name)
        return installed
