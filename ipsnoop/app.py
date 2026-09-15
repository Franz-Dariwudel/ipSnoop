# SPDX-License-Identifier: GPL-3.0-only
"""GTK-4-Oberfläche: Abfragen im Hintergrund, nur Darstellung im GTK-Thread."""
from concurrent.futures import ThreadPoolExecutor
import csv
import datetime
import json
import os
import platform
import subprocess
from pathlib import Path
import gi
os.environ.setdefault('GSK_RENDERER','cairo')
gi.require_version('Gtk','4.0')
from gi.repository import Gtk,Gio,GLib,Gdk
from . import ROOT,VERSION
from .scanner import Scanner
from .extended import GROUPS,diagnostic
from .live import Rates
from .packages import missing_packages,connected
from .config import Translator,load,save,logger


from .categories import NAVIGATION,PAGE_ICONS,PAGE_ORDER
from .observations import group_neighbors,core_kernel_row,unsupported_queries
from .reporting import summary,export_csv,export_text


class Window(Gtk.ApplicationWindow):
    def __init__(self,application,autostart=True):
        super().__init__(application=application,title='ipSnoop '+VERSION,default_width=1150,default_height=780)
        self.settings,self.config_errors=load();self.tr=Translator(self.settings['language'])
        self.scanner=Scanner();self.snapshot=None;self.busy=False;self.closed=False;self.timer=0
        self.executor=ThreadPoolExecutor(max_workers=1);self.selected=None;self.filter_text='';self._csv_chooser=None;self.active_page="adapters";self.category_filter='';self.diagnostic_busy=False;self.diagnostic_rows=[]
        self.export_mode="standard";self.anonymize=False;self.show_all_kernel=False
        self.rates=Rates();self.live_rows=[];self.live_timer=0;self.live_running=True
        self.connect('close-request',self.close_window)
        Gtk.IconTheme.get_for_display(self.get_display()).add_search_path(str(ROOT/'resources'))
        self.set_icon_name('ipsnoop-app-3d')
        self.build();self.polling()
        self.live_timer=GLib.timeout_add_seconds(1,self.sample_live)
        if autostart:self.refresh()

    def icon(self,filename,size=32):
        """3D-Ressource laden; bei defekten Dateien bleibt die Bedienung verfügbar."""
        image=Gtk.Image(pixel_size=size)
        try:image.set_from_paintable(Gdk.Texture.new_from_filename(str(ROOT/'resources'/filename)))
        except (GLib.Error,OSError):
            logger().error('IS106: %s',filename)
            image.set_tooltip_text('IS106: '+self.tr('IS106'))
            self.config_errors=list(dict.fromkeys(self.config_errors+['IS106']))
        return image

    def label(self,text,wrap=False):
        label=Gtk.Label(label=str(text),xalign=0,selectable=True,wrap=wrap)
        label.set_valign(Gtk.Align.START);return label

    def build(self):
        # Die arabische Oberfläche einschließlich Dialogen folgt ihrer Schreibrichtung.
        Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL if self.tr.language=='ar' else Gtk.TextDirection.LTR)
        t=self.tr;outer=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);self.set_child(outer)
        menu=Gio.Menu();help_menu=Gio.Menu()
        for key,items in [('file',[('quit',self.close)]),('edit',[('settings',self.settings_dialog)]),('help',[('help_open',self.show_help),('show_logs',self.show_logs),('about',self.about),('info',self.info)])]:
            submenu=Gio.Menu()
            for name,callback in items:
                action=Gio.SimpleAction.new(name.replace('_','-'),None);action.connect('activate',lambda a,p,c=callback:c());self.add_action(action)
                submenu.append(t(name),'win.'+name.replace('_','-'))
            (help_menu if key=='help' else menu).append_submenu(t(key),submenu)
        bar=Gtk.PopoverMenuBar.new_from_model(menu)
        if not hasattr(self,'_menu_css'):
            self._menu_css=Gtk.CssProvider()
            # Mint berücksichtigt auch unsichtbare Scrollbalken bei der Mindesthöhe.
            # Nur kurze eigene Menüs korrigieren; Systemfarben bleiben unverändert.
            self._menu_css.load_from_data(b'''
                popover.ipsnoop-short-menu scrollbar.vertical,
                popover.ipsnoop-short-menu scrollbar.vertical range,
                popover.ipsnoop-short-menu scrollbar.vertical trough,
                popover.ipsnoop-short-menu scrollbar.vertical slider { min-height: 0; }
            ''')
            Gtk.StyleContext.add_provider_for_display(self.get_display(),self._menu_css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        def compact(widget,short=False):
            if isinstance(widget,Gtk.PopoverMenu):
                model=widget.get_menu_model();short=model is not None and model.get_n_items()==1
                if short:widget.add_css_class('ipsnoop-short-menu')
            if short and isinstance(widget,Gtk.Stack):widget.set_vhomogeneous(False)
            child=widget.get_first_child()
            while child:
                compact(child,short);child=child.get_next_sibling()
        compact(bar);bar.connect('map',lambda *_:compact(bar))
        menu_row=Gtk.Box(spacing=8);menu_row.append(bar);outer.append(menu_row)
        self.category_menu=Gtk.MenuButton(label=t('categories'))
        self.category_popover=Gtk.Popover()
        self.category_menu.set_popover(self.category_popover);menu_row.append(self.category_menu)
        menu_row.append(Gtk.PopoverMenuBar.new_from_model(help_menu))
        body=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
        for side in ('top','bottom','start','end'):getattr(body,'set_margin_'+side)(12)
        outer.append(body)
        bar=Gtk.Box(spacing=12);body.append(bar)
        bar.append(self.icon('ipsnoop-app-3d.png',48))
        self.refresh_button=Gtk.Button(label=t('refresh'));self.refresh_button.connect('clicked',lambda *_:self.refresh());bar.append(self.refresh_button)
        self.export_button=Gtk.Button(label=t('export'));self.export_button.connect('clicked',self.export_dialog);self.export_button.set_sensitive(self.snapshot is not None);bar.append(self.export_button)
        self.search=Gtk.SearchEntry(placeholder_text=t('search'),hexpand=True);self.search.set_text(self.filter_text);self.search.connect('search-changed',self.search_changed);bar.append(self.search)
        self.empty=Gtk.CheckButton(label=t('show_empty'),active=self.settings['show_empty']);self.empty.connect('toggled',self.empty_changed);bar.append(self.empty)
        report_bar=Gtk.Box(spacing=12);body.append(report_bar)
        formats=Gtk.ComboBoxText(halign=Gtk.Align.START)
        for mode in ('standard','full','text'):formats.append(mode,t('export_'+mode))
        formats.set_active_id(self.export_mode)
        formats.connect('changed',lambda widget:setattr(self,'export_mode',widget.get_active_id()))
        report_bar.append(formats)
        private=Gtk.CheckButton(label=t('anonymize'),active=self.anonymize)
        private.set_tooltip_text(t('anonymize_hint'))
        private.connect('toggled',lambda widget:setattr(self,'anonymize',widget.get_active()));report_bar.append(private)
        self.status=self.label(t('ready'));body.append(self.status)
        self.package_banner=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=4);body.append(self.package_banner)
        self.category_title=self.label(t(self.active_page));self.category_title.add_css_class('heading');body.append(self.category_title)
        self.navigation=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6)
        self.navigation.add_css_class('navigation-sidebar')
        nav_scroll=Gtk.ScrolledWindow(vexpand=True,min_content_height=0,max_content_height=480,propagate_natural_height=True);nav_scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        nav_scroll.set_child(self.navigation)
        sidebar=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        category_search=Gtk.SearchEntry(placeholder_text=t('category_search'))
        category_search.set_text(self.category_filter)
        category_search.connect('search-changed',lambda entry:self.filter_categories(entry.get_text()))
        sidebar.append(category_search);sidebar.append(nav_scroll);self.category_popover.set_child(sidebar)
        self.results=Gtk.Stack(vexpand=True,hexpand=True)
        self.results.set_hhomogeneous(False);self.results.set_vhomogeneous(False)
        body.append(self.results)
        self.pages={};self.navigation_rows={};self.navigation_headers={};self.navigation_lists={}
        if not hasattr(self,'expanded_groups'):self.expanded_groups=set()
        for group,names in NAVIGATION:
            header=Gtk.Expander(label=t(group),expanded=group in self.expanded_groups)
            header.set_margin_top(4);header.set_margin_bottom(4)
            group_list=Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE,activate_on_single_click=True)
            header.set_child(group_list);self.navigation.append(header);self.navigation_headers[group]=header
            self.navigation_lists[group]=group_list
            def remember(widget,_param,key=group):
                if self.category_filter.strip():return
                if widget.get_expanded():self.expanded_groups.add(key)
                else:self.expanded_groups.discard(key)
            header.connect('notify::expanded',remember)
            for name in names:
                page=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10)
                for side in ('top','bottom','start','end'):getattr(page,'set_margin_'+side)(12)
                row=Gtk.ListBoxRow();row.page_name=name
                tab=Gtk.Box(spacing=10)
                for side in ('top','bottom','start','end'):getattr(tab,'set_margin_'+side)(8)
                tab.append(Gtk.Label(label=t(name),xalign=0))
                row.set_child(tab);group_list.append(row);self.navigation_rows[name]=row
                self.results.add_named(page,name);self.pages[name]=page
        def choose(_list,row):
            if row is not None and hasattr(row,'page_name'):
                for other in self.navigation_lists.values():
                    if other is not _list:other.unselect_all()
                self.active_page=row.page_name;self.results.set_visible_child_name(self.active_page)
                self.category_title.set_text(t(self.active_page));self.category_popover.popdown()
                if self.active_page in GROUPS:self.render_extended(self.active_page)
                elif self.active_page=='live':self.render_live()
        for group_list in self.navigation_lists.values():group_list.connect('row-activated',choose)
        row=self.navigation_rows.get(self.active_page,self.navigation_rows['adapters'])
        row.get_parent().select_row(row);self.results.set_visible_child_name(row.page_name)
        self.filter_categories(self.category_filter)
        self.issues_box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=5)
        self.issues_expander=Gtk.Expander(label=t('issues'));self.issues_expander.set_child(self.issues_box);body.append(self.issues_expander)
        self.render()

    def filter_categories(self,text):
        """Bereiche nach übersetztem Namen oder Gruppenbezeichnung auffinden."""
        self.category_filter=text;query=text.strip().casefold()
        if not hasattr(self,'navigation_rows'):return
        for group,names in NAVIGATION:
            any_visible=False
            for name in names:
                visible=query in (self.tr(group)+' '+self.tr(name)).casefold()
                self.navigation_rows[name].set_visible(visible);any_visible|=visible
            self.navigation_headers[group].set_visible(any_visible)
            self.navigation_headers[group].set_expanded(any_visible if query else group in self.expanded_groups)

    def clear(self,box):
        while box.get_first_child():box.remove(box.get_first_child())

    def matches(self,data):
        return self.filter_text.casefold() in ' '.join(str(v) for v in data.values()).casefold()

    def value(self,value):
        missing=value is None or value=='' or value==[]
        enums=('not_applicable','locally_administered','physical','virtual','unknown','since_counter_reset',
               'not_present','bluetooth_unavailable_hint','preferred_metric','equal_candidate','alternative',
               'driver_counters_not_additive','all_interfaces','direct','source_auto')
        if isinstance(value,bool):text=self.tr('yes' if value else 'no')
        elif isinstance(value,list):text='\n'.join(str(v) for v in value)
        elif isinstance(value,str) and value in enums:text=self.tr(value)
        else:text=value
        label=self.label(self.tr('missing') if missing else text,True)
        if missing:label.add_css_class('error')
        return label

    def table(self,box,rows,fields,fixed=True):
        grid=Gtk.Grid(column_spacing=22,row_spacing=9,hexpand=True)
        header=Gtk.Grid(column_spacing=22,hexpand=True) if fixed else grid
        groups=[Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL) for _ in fields] if fixed else []
        for col,key in enumerate(fields):
            label=self.label(self.tr(key));label.add_css_class('heading');header.attach(label,col,0,1,1)
            if fixed:groups[col].add_widget(label)
        for row,data in enumerate(rows,1):
            for col,key in enumerate(fields):
                cell=self.value(data.get(key,''))
                if data.get('_error') and key in ('value','result'):cell.add_css_class('error')
                grid.attach(cell,col,row,1,1)
                if fixed:groups[col].add_widget(cell)
        if fixed:
            # Gleiche Spaltenbreiten und horizontale Position; nur Daten vertikal scrollen.
            grid.set_valign(Gtk.Align.START)
            body=Gtk.ScrolledWindow(vexpand=True,hexpand=True);body.set_child(grid)
            head=Gtk.ScrolledWindow(hexpand=True);head.set_policy(Gtk.PolicyType.EXTERNAL,Gtk.PolicyType.NEVER)
            head.set_hadjustment(body.get_hadjustment());head.set_child(header)
            box.append(head);box.append(body)
            if not rows:grid.attach(self.label(self.tr('none'),True),0,1,len(fields),1)
            self.fixed_header=header;self.fixed_body=body
        else:
            box.append(grid)
            if not rows:box.append(self.label(self.tr('none'),True))

    def render(self):
        for box in self.pages.values():self.clear(box)
        self.clear(self.issues_box);self.clear(self.package_banner)
        if not self.snapshot:return
        t=self.tr;s=self.snapshot
        adapters=[a for a in s['adapters'] if self.matches(a) and (self.settings['show_empty'] or connected(a))]
        box=self.pages['adapters']
        self.table(box,adapters,('name','classification','adapter_kind','status','ipv4','ipv6','mac'))
        self.fixed_body.set_vexpand(False);self.fixed_body.set_min_content_height(100)
        selector=Gtk.ComboBoxText(halign=Gtk.Align.START)
        for a in adapters:selector.append(a['name'],a['name'])
        names=[a['name'] for a in adapters]
        if self.selected not in names:self.selected=names[0] if names else None
        if self.selected:selector.set_active_id(self.selected)
        box.append(selector)
        details=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,vexpand=True);box.append(details)
        def detail_changed(*_):
            self.selected=selector.get_active_id();self.clear(details)
            a=next((a for a in adapters if a['name']==self.selected),None)
            if a:
                driver_rows=[]
                for finding in s.get('findings',[]):
                    if finding['name']==a['name']:
                        notice=self.label(t(finding['code'])+' '+t('drop_threshold',count=finding['threshold']),True)
                        notice.add_css_class('heading');details.append(notice)
                        details.append(self.label(t('driver_counters_not_additive'),True))
                        for counter in finding['driver_counters']:driver_rows.append({'field':counter['field'],'value':counter['value']})
                self.table(details,[{'field':t(k),'value':v} for k,v in a.items()]+driver_rows,('field','value'))
        selector.connect('changed',detail_changed);detail_changed()
        self.pages['neighbors'].append(self.label(t('neighbors_hint'),True))
        neighbor_rows=[]
        grouped=s['neighbors']
        if grouped and 'observations' not in grouped[0]:grouped=group_neighbors(grouped)
        for n in grouped:
            if not self.matches(n):continue
            cache=[]
            for item in n.get('observations',[]):
                fields=[f'{t(k)}: {item[k]}' for k in ('neighbor_used_s','neighbor_confirmed_s','neighbor_updated_s','neighbor_probes','refcnt') if k in item]
                if item.get('hostname_status'):fields.append(t('hostname_status')+': '+t(item['hostname_status']))
                cache.append(item.get('ip','')+' ['+item.get('name','')+']\n'+' · '.join(fields))
            neighbor_rows.append({**n,'cache_details':'\n'.join(cache)})
        self.table(self.pages['neighbors'],neighbor_rows,('mac','ipv4','ipv6','interfaces','hostname','router','vendor','cache_details'))
        self.pages['wifi'].append(self.label(t('wifi_hint'),True))
        self.table(self.pages['wifi'],[n for n in s['wifi'] if self.matches(n)],('name','active','ssid','bssid','signal','channel','frequency','rate','security'))
        self.pages['services'].append(self.label(t('services_hint_admin' if os.geteuid()==0 else 'services_hint'),True))
        self.table(self.pages['services'],[n for n in s['services'] if self.matches(n)],('protocol','status','local','peer','process','pid','user','executable'))
        self.pages['connections'].append(self.label(t('services_hint_admin' if os.geteuid()==0 else 'services_hint'),True))
        self.table(self.pages['connections'],[n for n in s.get('connections',[]) if self.matches(n)],('protocol','status','local','peer','process','pid','user','executable'))
        route_page=self.pages['routes']
        route_page.append(self.label(t('routes_hint'),True))
        if s.get('default_routes'):
            self.table(route_page,s['default_routes'],('family','preference','dev','gateway','metric'))
            self.fixed_body.set_vexpand(False);self.fixed_body.set_min_content_height(100)
        self.table(route_page,[n for n in s['routes'] if self.matches(n)],('family','dst','gateway','dev','prefsrc','metric','protocol','table'))
        system_rows=[{'field':t(k),'value':v} for k,v in {**summary(s),**s.get('scan',{}),**s['system']}.items() if self.matches({k:v})]
        self.table(self.pages['system'],system_rows,('field','value'))
        if self.active_page in GROUPS:self.render_extended(self.active_page)
        self.render_diagnostics()
        self.render_live()
        errors=s['issues']+[{'code':c,'detail':''} for c in self.config_errors+self.tr.errors]
        packages=missing_packages(errors)
        if packages:
            heading=self.label(t('missing_packages'));heading.add_css_class('error');heading.add_css_class('heading');self.package_banner.append(heading)
            self.package_banner.append(self.label(', '.join(packages),True))
            self.package_banner.append(self.label('sudo apt install '+' '.join(packages),True))
        self.package_banner.set_visible(bool(packages))
        for error in errors:
            label=self.label(error['code']+': '+t(error['code'])+' '+error['detail'],True);label.add_css_class('error');self.issues_box.append(label)
        self.issues_expander.set_label(t('issues')+f' ({len(errors)})')
        self.status.set_text(t('updated',time=datetime.datetime.fromtimestamp(s['timestamp']).strftime('%H:%M:%S'),count=len(s['adapters']))+' · '+t('mode_admin' if os.geteuid()==0 else 'mode_user'))
        self.export_button.set_sensitive(True)

    def render_extended(self,group):
        """Nur die gewählte Detailkategorie aufbauen; Kopf bleibt fixiert."""
        box=self.pages[group];self.clear(box)
        heading=Gtk.Box(spacing=10)
        heading.append(self.icon(PAGE_ICONS[group],40))
        title=self.label(self.tr(group));title.add_css_class('title-3');heading.append(title);box.append(heading)
        if not self.snapshot:return
        if group=='kernel_params':
            all_parameters=Gtk.CheckButton(label=self.tr('all_kernel'),active=self.show_all_kernel,halign=Gtk.Align.START)
            def show_all(widget):
                self.show_all_kernel=widget.get_active();self.render_extended(group)
            all_parameters.connect('toggled',show_all);box.append(all_parameters)
        rows=[];failed=False
        for row in self.snapshot.get('extended',[]):
            if row['group']!=group or not self.matches(row):continue
            if group=='kernel_params' and not self.show_all_kernel and not core_kernel_row(row):continue
            status=row['result'];error=status not in ('ok','empty','unsupported','no_data');failed|=error
            rows.append({'name':row['name'] or self.tr('all_interfaces'),'field':self.tr(row['field']),
                'value':row['value'] if status=='ok' else self.tr(status),
                'result':self.tr(status),'_error':error})
        if failed:
            label=self.label(self.tr('extended_missing'),True);label.add_css_class('error');box.append(label)
        self.table(box,rows,('name','field','value','result'),fixed=True)
        if group=='adapter_extra':
            queries=unsupported_queries(self.snapshot.get('extended',[]))
            if queries:
                expander=Gtk.Expander(label=self.tr('unsupported_queries')+f' ({len(queries)})')
                expander.set_child(self.label('\n'.join(queries),True));box.append(expander)

    def render_diagnostics(self):
        box=self.pages['diagnostics'];box.append(self.label(self.tr('diagnostics_hint'),True))
        row=Gtk.Box(spacing=10);box.append(row)
        mode=Gtk.ComboBoxText()
        for name in ('ping','lookup','trace'):mode.append(name,self.tr(name))
        mode.set_active_id('ping');row.append(mode)
        target=Gtk.Entry(placeholder_text=self.tr('target'));row.append(target)
        button=Gtk.Button(label=self.tr('run_test'));row.append(button);button.set_sensitive(not self.diagnostic_busy)
        def run(*_):
            if self.diagnostic_busy:return
            chosen=mode.get_active_id();address=target.get_text()
            self.diagnostic_busy=True;button.set_sensitive(False)
            future=self.executor.submit(diagnostic,chosen,address)
            def complete():
                if self.closed:return False
                self.diagnostic_busy=False
                try:self.diagnostic_rows.append(future.result())
                except ValueError:self.message('IS204: '+self.tr('IS204'))
                except Exception:logger().exception('IS299: diagnosis');self.message('IS299: '+self.tr('IS299'))
                if self.snapshot:self.snapshot['diagnostics']=self.diagnostic_rows.copy();self.snapshot['live']=self.live_rows.copy()
                self.clear(box);self.render_diagnostics();return False
            future.add_done_callback(lambda *_:GLib.idle_add(complete))
        button.connect('clicked',run)
        self.table(box,[{**r,'result':self.tr(r['result'])} for r in self.diagnostic_rows],('name','field','value','result'))

    def sample_live(self):
        if self.closed:return False
        if self.live_running:
            self.live_rows=self.rates.sample(links={a['name']:a for a in self.snapshot['adapters']} if self.snapshot else None)
            if self.snapshot:self.snapshot['live']=self.live_rows.copy()
            if self.active_page=='live':self.render_live()
        return True

    def render_live(self):
        box=self.pages['live']
        previous=getattr(self,'live_scroll',None)
        horizontal=previous.get_hadjustment().get_value() if previous else 0
        self.clear(box)
        box.append(self.label(self.tr('live_hint'),True))
        button=Gtk.CheckButton(label=self.tr('live_running'),active=self.live_running,halign=Gtk.Align.START)
        def toggled(widget):
            self.live_running=widget.get_active();self.rates.previous.clear()
        button.connect('toggled',toggled);box.append(button)
        rows=[{**row,'rate_status':self.tr(row['rate_status'])} for row in self.live_rows if self.matches(row)]
        self.table(box,rows,('name','rx_data_s','tx_data_s','rx_bytes_s','tx_bytes_s','rx_packets_s','tx_packets_s','rx_errors_s','tx_errors_s','rx_dropped_s','tx_dropped_s','rx_utilization_pct','tx_utilization_pct','interval_s','measured_at','rx_bytes_s_min','rx_bytes_s_max','tx_bytes_s_min','tx_bytes_s_max','rate_status'),fixed=True)
        self.live_scroll=self.fixed_body
        if horizontal:
            adjustment=self.live_scroll.get_hadjustment()
            adjustment.connect('changed',lambda a:a.set_value(min(horizontal,max(0,a.get_upper()-a.get_page_size()))))

    def search_changed(self,entry):self.filter_text=entry.get_text();self.render()

    def persist(self):
        try:save(self.settings)
        except OSError:logger().error('IS102: save');self.message('IS102: '+self.tr('IS102'))

    def empty_changed(self,button):
        self.settings['show_empty']=button.get_active();self.persist();self.render()

    def refresh(self):
        if self.busy or self.closed:return
        self.status.remove_css_class('success')
        self.busy=True;self.refresh_button.set_sensitive(False);self.status.set_text(self.tr('busy'))
        future=self.executor.submit(self.scanner.scan)
        def complete():
            if self.closed:return False
            self.busy=False;self.refresh_button.set_sensitive(True)
            try:
                self.snapshot=future.result();self.snapshot['diagnostics']=self.diagnostic_rows.copy();self.snapshot['live']=self.live_rows.copy()
                for issue in self.snapshot['issues']:logger().warning('%s: %s',issue['code'],issue['detail'])
                self.render()
            except Exception:
                logger().exception('IS299');self.status.set_text('IS299: '+self.tr('IS299'))
            return False
        future.add_done_callback(lambda *_:GLib.idle_add(complete))

    def polling(self):
        if self.timer:GLib.source_remove(self.timer);self.timer=0
        if self.settings['interval']:
            self.timer=GLib.timeout_add_seconds(self.settings['interval'],lambda:(self.refresh(),True)[1])

    def settings_dialog(self):
        self.tr.reload();t=self.tr
        dialog=Gtk.Dialog(title=t('settings'),transient_for=self,modal=True)
        dialog.add_button(t('cancel'),Gtk.ResponseType.CANCEL);dialog.add_button(t('save'),Gtk.ResponseType.OK)
        box=dialog.get_content_area();box.set_spacing(12)
        for side in ('top','bottom','start','end'):getattr(box,'set_margin_'+side)(18)
        languages=Gtk.ComboBoxText();codes=list(self.tr.catalogs)
        for code in codes:languages.append(code,self.tr.catalogs[code].get('language.name',code))
        if len(codes)>1:
            box.append(self.label(t('language')));box.append(languages);languages.set_active_id(t.language)
        interval=Gtk.ComboBoxText()
        for seconds in (0,5,10,30):interval.append(str(seconds),t('manual') if not seconds else t('seconds',count=seconds))
        interval.set_active_id(str(self.settings['interval']));box.append(self.label(t('interval')));box.append(interval)
        def done(d,response):
            if response==Gtk.ResponseType.OK:
                self.settings['language']=languages.get_active_id() if len(codes)>1 else t.language
                self.tr.language=self.settings['language'];self.settings['interval']=int(interval.get_active_id())
                self.persist();self.build();self.polling()
            d.destroy()
        dialog.connect('response',done);dialog.present()

    def message(self,text):
        dialog=Gtk.MessageDialog(transient_for=self,modal=True,text=text,buttons=Gtk.ButtonsType.CLOSE)
        dialog.connect('response',lambda d,*_:d.destroy());dialog.present()

    def show_logs(self):
        """Aktuelles Sitzungsprotokoll nur lesen; Aktualisieren löscht keine Meldungen."""
        t=self.tr
        dialog=Gtk.Dialog(title=t('show_logs'),transient_for=self,default_width=800,default_height=500)
        dialog.add_button(t('refresh'),Gtk.ResponseType.APPLY)
        dialog.add_button(t('close'),Gtk.ResponseType.CLOSE)
        box=dialog.get_content_area();box.set_spacing(10)
        for side in ('top','bottom','start','end'):getattr(box,'set_margin_'+side)(12)
        box.append(self.label(t('logs_hint'),True))
        view=Gtk.TextView(editable=False,cursor_visible=False,wrap_mode=Gtk.WrapMode.WORD_CHAR)
        scroll=Gtk.ScrolledWindow(hexpand=True,vexpand=True);scroll.set_child(view);box.append(scroll)
        def reload_log():
            try:
                content=(ROOT/'logs/errors.log').read_text(encoding='utf-8')
                view.get_buffer().set_text(content or t('logs_empty'))
            except (OSError,UnicodeError):
                view.get_buffer().set_text('IS107: '+t('IS107'))
                logger().error('IS107: logs/errors.log')
        def respond(widget,response):
            if response==Gtk.ResponseType.APPLY:reload_log()
            else:widget.destroy()
        dialog.connect('response',respond);reload_log();dialog.present()

    def show_help(self):
        path=ROOT/'help'/(self.tr.language+'.html')
        try:
            if '<html' not in path.read_text(encoding='utf-8').lower():raise ValueError()
            Gio.AppInfo.launch_default_for_uri(path.as_uri(),self.get_display().get_app_launch_context())
        except (OSError,ValueError,GLib.Error):logger().error('IS105: %s',path.name);self.message('IS105: '+self.tr('IS105'))

    def about(self):
        dialog=Gtk.AboutDialog(transient_for=self,modal=True,program_name='ipSnoop',version=VERSION,authors=['Josef Lehner'],website='https://dogtruck.eu',license_type=Gtk.License.GPL_3_0_ONLY)
        dialog.set_title(self.tr('about_title'))
        try:dialog.set_logo(Gdk.Texture.new_from_filename(str(ROOT/'resources/ipsnoop-logo-3d.png')))
        except (GLib.Error,OSError):logger().error('IS106: ipsnoop-logo-3d.png')
        dialog.present()

    def info(self):
        dialog=Gtk.Dialog(title=self.tr('info_title'),transient_for=self,modal=True,default_width=500)
        dialog.add_button(self.tr('close'),Gtk.ResponseType.CLOSE)
        row=Gtk.Box(spacing=22);row.set_margin_top(20);row.set_margin_bottom(20);row.set_margin_start(20);row.set_margin_end(20)
        image=Gtk.Image.new_from_file(str(ROOT/'resources/info-3d.png'));image.set_pixel_size(64);image.set_valign(Gtk.Align.START);row.append(image)
        versions=[f'Python {platform.python_version()} — Python Software Foundation',f'GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()} — GTK Team',f'PyGObject {gi.__version__} — PyGObject Team',f'Linux {platform.release()} — Linux Kernel Community']
        for command,author in [(['ip','-V'],'iproute2 contributors'),(['nmcli','--version'],'NetworkManager Team'),(['ethtool','--version'],'ethtool contributors'),(['ss','-V'],'iproute2 contributors'),(['lspci','--version'],'pciutils contributors'),(['resolvectl','--version'],'systemd contributors'),(['systemctl','--version'],'systemd contributors'),(['sysctl','--version'],'procps-ng contributors'),(['nft','--version'],'Netfilter Project'),(['ufw','--version'],'UFW contributors'),(['iw','--version'],'Linux wireless contributors'),(['bluetoothctl','--version'],'BlueZ Project'),(['ping','-V'],'iputils contributors'),(['tracepath','-V'],'iputils contributors'),(['getent','--version'],'GNU C Library contributors'),(['lldpcli','-v'],'lldpd contributors'),(['conntrack','-V'],'Netfilter Project'),(['wg','--version'],'WireGuard contributors')]:
            try:r=subprocess.run(command,capture_output=True,text=True,timeout=1);v=r.stdout.strip() if not r.returncode else self.tr('missing')
            except (OSError,subprocess.TimeoutExpired):v=self.tr('missing')
            versions.append(v+' — '+author)
        row.append(self.label('\n\n'.join(versions),True));dialog.get_content_area().append(row)
        dialog.connect('response',lambda d,*_:d.destroy());dialog.present()

    def export_dialog(self,*_):
        if self._csv_chooser is not None:
            self._csv_chooser.show();return
        if not self.snapshot:return
        snapshot=json.loads(json.dumps(self.snapshot));mode=self.export_mode;anonymize=self.anonymize
        chooser=Gtk.FileChooserNative(title=self.tr('export'),transient_for=self,action=Gtk.FileChooserAction.SAVE,accept_label=self.tr('save'),cancel_label=self.tr('cancel'))
        # NativeDialog hält sich nicht selbst am Leben; bis zur Antwort behalten.
        self._csv_chooser=chooser
        folder=Path.home()/'Downloads'
        if not folder.is_dir():folder=Path.home()
        chooser.set_current_folder(Gio.File.new_for_path(str(folder)))
        chooser.set_current_name('ipSnoop.txt' if mode=='text' else 'ipSnoop-Diagnose.csv' if mode=='full' else 'ipSnoop.csv')
        def done(d,response):
            if response==Gtk.ResponseType.ACCEPT:
                try:
                    file=d.get_file();path=file.get_path() if file else None
                    if not path:raise OSError()
                    export_text(Path(path),snapshot,self.tr,anonymize) if mode=='text' else export_csv(Path(path),snapshot,self.tr,mode,anonymize)
                    self.status.set_text(self.tr('exported'));self.status.add_css_class('success')
                except (OSError,ValueError,GLib.Error):logger().exception('IS301: CSV');self.message('IS301: '+self.tr('IS301'))
            d.destroy()
            if self._csv_chooser is d:self._csv_chooser=None
        chooser.connect('response',done);chooser.show()

    def close_window(self,*_):
        self.closed=True
        if self.live_timer:GLib.source_remove(self.live_timer);self.live_timer=0
        if self._csv_chooser is not None:
            self._csv_chooser.destroy();self._csv_chooser=None
        if self.timer:GLib.source_remove(self.timer)
        self.executor.shutdown(wait=False,cancel_futures=True)
        return False



class Application(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='eu.dogtruck.ipSnoop',flags=Gio.ApplicationFlags.NON_UNIQUE);self.window=None
    def do_activate(self):
        if self.window is None:self.window=Window(self)
        self.window.present()
