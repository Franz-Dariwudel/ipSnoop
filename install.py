#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Portable Installation in einen leeren Ordner mit vollständigem Dateijournal.

Deinstallation: install.py --uninstall in der installierten Ausgabe. Nur durch
die Installation angelegte Pfade entfernen; später erzeugte Benutzerdaten und
fremde Dateien bleiben erhalten. Es werden keine Desktopdateien angelegt.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys


def install(source,target):
    source=Path(source).resolve();target=Path(target).expanduser()
    if not target.is_absolute():raise ValueError('Absoluter Zielpfad erforderlich / absolute path required')
    target=target.resolve()
    if target==source or target.is_relative_to(source):raise ValueError('Ziel liegt im Paket / target inside package')
    if target.exists() and (not target.is_dir() or any(target.iterdir())):raise ValueError('Zielordner muss leer sein / target must be empty')
    info=json.loads((source/'build-info.json').read_text())
    if info['kind']=='bytecode' and info['python']!=f'{sys.version_info.major}.{sys.version_info.minor}':raise ValueError('Python '+info['python']+' erforderlich / required')
    target.mkdir(parents=True,exist_ok=True)
    files=[];directories=[]
    for path in sorted(source.rglob('*')):
        relative=path.relative_to(source)
        if '__pycache__' in relative.parts:continue
        if path.is_symlink():raise ValueError('Unerwarteter Link / unexpected symlink')
        if path.is_dir():directories.append(relative.as_posix())
        else:files.append(relative.as_posix())
    for name in ('config','logs'):
        if name not in directories:directories.append(name)
    # Journal zuerst: auch eine unterbrochene Installation lässt sich entfernen.
    journal={'files':files,'directories':directories}
    (target/'installation.json').write_text(json.dumps(journal,indent=2)+'\n')
    for name in directories:(target/name).mkdir(parents=True,exist_ok=True)
    for name in files:shutil.copy2(source/name,target/name)
    return target


def uninstall(target):
    target=Path(target).resolve();journal=target/'installation.json'
    data=json.loads(journal.read_text())
    # Manipulierte Pfade dürfen nicht aus der Installation herausführen.
    for name in data['files']+data['directories']:
        path=Path(name)
        if path.is_absolute() or '..' in path.parts or not path.parts:raise ValueError('Ungültiger Journalpfad / invalid journal path')
        if any(p.is_symlink() for p in (target/path).parents if p!=target and p.is_relative_to(target)):raise ValueError('Verlinkter Elternordner / linked parent')
    for name in data['files']:(target/name).unlink(missing_ok=True)
    for name in sorted(data['directories'],key=lambda n:len(Path(n).parts),reverse=True):
        path=target/name
        if path.is_dir() and not path.is_symlink() and not any(path.iterdir()):path.rmdir()
    journal.unlink()
    if not any(target.iterdir()):target.rmdir()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--directory',type=Path);group.add_argument('--uninstall',action='store_true')
    args=parser.parse_args();source=Path(__file__).resolve().parent
    try:
        if args.uninstall:uninstall(source);print('Deinstalliert / removed')
        else:print('Installiert / installed: '+str(install(source,args.directory)))
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print('IS401: '+str(exc),file=sys.stderr);return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
