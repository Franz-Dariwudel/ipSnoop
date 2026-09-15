#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Bereinigte Ausgaben ohne Benutzerdaten, Logs und private Startdateien erstellen."""
import hashlib
import json
from pathlib import Path
import py_compile
import shutil
import sys
import tarfile
import tempfile
import zipfile
from ipsnoop import ROOT,VERSION


def main():
    (ROOT/'dist').mkdir(exist_ok=True);(ROOT/'work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT/'work',prefix='build-') as d:
        stage=Path(d)/('ipSnoop-'+VERSION);stage.mkdir()
        for name in ('ipsnoop','languages','help','resources','tests'):
            shutil.copytree(ROOT/name,stage/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for name in ('install.py','build.py','README.md','CHANGELOG.md','LICENSE','pyproject.toml'):
            shutil.copy2(ROOT/name,stage/name)
        for name in ('config','logs'):(stage/name).mkdir()
        info={'version':VERSION,'kind':'source','python':f'{sys.version_info.major}.{sys.version_info.minor}','personal_data':False}
        (stage/'build-info.json').write_text(json.dumps(info,indent=2)+'\n')
        for path in stage.rglob('*'):path.chmod(0o755 if path.is_dir() else 0o644)
        archive=ROOT/'dist'/f'ipSnoop-{VERSION}-quellcode.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(stage.rglob('*')):z.write(p,p.relative_to(stage.parent))
        for p in (stage/'ipsnoop').glob('*.py'):
            py_compile.compile(str(p),cfile=str(p.with_suffix('.pyc')),dfile=str(p.relative_to(stage)),doraise=True);p.unlink()
        shutil.rmtree(stage/'tests');(stage/'build.py').unlink()
        info['kind']='bytecode';(stage/'build-info.json').write_text(json.dumps(info,indent=2)+'\n')
        archive=ROOT/'dist'/f'ipSnoop-{VERSION}-python{info["python"]}-kompiliert.tar.gz'
        with tarfile.open(archive,'w:gz') as t:t.add(stage,arcname=stage.name)
    files=sorted((ROOT/'dist').glob(f'ipSnoop-{VERSION}-*.zip'))+sorted((ROOT/'dist').glob(f'ipSnoop-{VERSION}-*.tar.gz'))
    (ROOT/'dist'/f'ipSnoop-{VERSION}-SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
    for p in files:print(p)

if __name__=='__main__':main()
