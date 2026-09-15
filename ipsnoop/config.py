# SPDX-License-Identifier: GPL-3.0-only
"""JSON-Konfiguration, Protokolle und dynamische Sprachdateien."""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import tempfile
from . import ROOT


def logger(reset=False):
    """Protokoll beim Prozesseinstieg zurücksetzen, danach nur anhängen.

    Normale Logaufrufe, Aktualisierungen und Dialoge erhalten alle Meldungen
    der laufenden Sitzung. Nur der Einstieg ruft diese Funktion mit reset auf.
    """
    log=logging.getLogger('ipsnoop')
    if reset:
        for handler in log.handlers[:]:
            log.removeHandler(handler);handler.close()
    if not log.handlers:
        log.setLevel(logging.INFO)
        handler=None
        try:
            folder=ROOT/'logs';folder.mkdir(exist_ok=True)
            path=folder/'errors.log'
            if reset:
                path.write_text('',encoding='utf-8')
                for name in ('errors.log.1','errors.log.2'):
                    (folder/name).unlink(missing_ok=True)
            handler=RotatingFileHandler(path,maxBytes=300000,backupCount=2,encoding='utf-8')
            # Auch nach einem Adminstart muss der normale Benutzer schreiben können.
            if os.geteuid()==0:
                owner=folder.stat();os.chown(path,owner.st_uid,owner.st_gid)
        except OSError as error:
            if handler is not None:handler.close()
            handler=logging.StreamHandler();print(f'IS101: logs/errors.log: {error}',file=sys.stderr)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        log.addHandler(handler)
    return log


def load():
    defaults={'language':'de','interval':0,'show_empty':False}
    try:
        path=ROOT/'config/settings.json'
        if os.geteuid()==0 and path.is_file():
            owner=path.parent.stat();os.chown(path,owner.st_uid,owner.st_gid)
        data=json.loads(path.read_text())
        if not isinstance(data,dict):raise ValueError()
        if isinstance(data.get('language'),str):defaults['language']=data['language']
        if type(data.get('interval')) is int and data['interval'] in (0,5,10,30):defaults['interval']=data['interval']
        if isinstance(data.get('show_empty'),bool):defaults['show_empty']=data['show_empty']
        errors=[]
    except FileNotFoundError:errors=[]
    except (OSError,ValueError,UnicodeError):logger().error('IS102: config/settings.json');errors=['IS102']
    try:
        visibility=json.loads((ROOT/'config/visibility.json').read_text())
        if type(visibility.get('show_empty')) is bool:defaults['show_empty']=visibility['show_empty']
    except FileNotFoundError:pass
    except (OSError,ValueError,AttributeError):errors.append('IS102')
    return defaults,errors


def save(data):
    folder=ROOT/'config';folder.mkdir(exist_ok=True)
    fd,name=tempfile.mkstemp(dir=folder,prefix='.settings-')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(data,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
        if os.geteuid()==0:
            owner=folder.stat();os.chown(name,owner.st_uid,owner.st_gid)
        os.replace(name,folder/'settings.json')
        # Separaten Anzeige-Wunsch auch nach erneutem Speichern erhalten.
        visibility=folder/'visibility.json'
        fd2,temp=tempfile.mkstemp(dir=folder,prefix='.visibility-')
        try:
            with os.fdopen(fd2,'w') as stream:json.dump({'show_empty':data['show_empty']},stream)
            if os.geteuid()==0:
                owner=folder.stat();os.chown(temp,owner.st_uid,owner.st_gid)
            os.replace(temp,visibility)
        finally:
            if os.path.exists(temp):os.unlink(temp)
    finally:
        if os.path.exists(name):os.unlink(name)


class Translator:
    def __init__(self,language='de',directory=None):
        self.directory=Path(directory or ROOT/'languages');self.language=language;self.catalogs={};self.errors=[];self.reload()

    def reload(self):
        self.catalogs={};self.errors=[]
        for path in sorted(self.directory.glob('*.json')):
            try:
                data=json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(data,dict) or not data or not all(isinstance(k,str) and isinstance(v,str) for k,v in data.items()):raise ValueError()
                self.catalogs[path.stem]=data
            except (OSError,ValueError,UnicodeError):self.errors.append('IS103');logger().error('IS103: %s',path.name)
        if len(self.catalogs)==1:self.language=next(iter(self.catalogs))
        elif self.language not in self.catalogs:self.language='de' if 'de' in self.catalogs else 'en'
        if not self.catalogs:self.errors.append('IS103')

    def __call__(self,key,**values):
        text=self.catalogs.get(self.language,{}).get(key,self.catalogs.get('en',{}).get(key,key))
        try:return text.format(**values)
        except (KeyError,ValueError):return text
