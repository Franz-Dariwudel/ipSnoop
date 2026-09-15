#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""Reproduzierbare DEB-Struktur mit dpkg-verwalteten Startern und Polkit-Aktion."""
from pathlib import Path
import shutil
import subprocess
import tempfile
from ipsnoop import ROOT,VERSION

def main():
    (ROOT/'dist').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ipsnoop-deb-') as temp:
        stage=Path(temp);app=stage/'usr/share/ipsnoop';app.mkdir(parents=True)
        for name in ('ipsnoop','languages','help','resources'):
            shutil.copytree(ROOT/name,app/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        (app/'system-package').touch()
        def copy(src,dst,mode=0o644):
            dst=stage/dst;dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/src,dst);dst.chmod(mode)
        for name in ('ipsnoop','ipsnoop-admin'):copy('packaging/'+name,'usr/bin/'+name,0o755)
        copy('packaging/admin-launch','usr/lib/ipsnoop/admin-launch',0o755)
        copy('packaging/data-cleanup','usr/lib/ipsnoop/data-cleanup',0o755)
        for name in ('desktop-setup','desktop-dispatch'):
            copy('packaging/'+name,'usr/lib/ipsnoop/'+name,0o755)
        copy('packaging/ipsnoop-desktop-setup.desktop','etc/xdg/autostart/ipsnoop-desktop-setup.desktop')
        for name in ('ipsnoop','ipsnoop-admin'):copy('packaging/'+name+'.desktop','usr/share/applications/'+name+'.desktop')
        copy('resources/ipsnoop-app-3d.png','usr/share/icons/hicolor/256x256/apps/ipsnoop.png')
        copy('resources/security-3d.png','usr/share/icons/hicolor/256x256/apps/ipsnoop-admin.png')
        copy('packaging/eu.dogtruck.ipsnoop.policy','usr/share/polkit-1/actions/eu.dogtruck.ipsnoop.policy')
        for name in ('README.md','LICENSE','CHANGELOG.md'):copy(name,'usr/share/doc/ipsnoop/'+name)
        for name in ('postinst','prerm'):copy('packaging/'+name,'DEBIAN/'+name,0o755)
        (stage/'DEBIAN/control').write_text(f'''Package: ipsnoop
Version: {VERSION}
Section: net
Priority: optional
Architecture: all
Maintainer: Josef Lehner <office@dogtruck.eu>
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0 (>= 4.8), iproute2, policykit-1, xdg-user-dirs, libnotify-bin
Recommends: network-manager, ethtool
Installed-Size: {sum(p.stat().st_size for p in stage.rglob('*') if p.is_file())//1024}
Homepage: https://dogtruck.eu
Description: GTK 4 network diagnostics with normal and administrator launchers
 Local network information, live counters, reports and downloadable languages.
''')
        subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(ROOT/'dist'/f'ipsnoop_{VERSION}_all.deb')],check=True)
if __name__=='__main__':main()
