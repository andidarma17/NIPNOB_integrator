"""Interactive map-based studio verification: QGIS dock, inspect & label pairs."""
import csv
from datetime import datetime
from pathlib import Path
from qgis.core import QgsGeometry,QgsCoordinateTransform,QgsProject
from qgis.gui import QgsMapLayerComboBox,QgsMapToolEmitPoint
from qgis.PyQt.QtWidgets import (QDockWidget,QWidget,QVBoxLayout,QFormLayout,
    QHBoxLayout,QPushButton,QLineEdit,QLabel,QTableWidget,QTableWidgetItem,
    QHeaderView,QMessageBox,QFileDialog,QComboBox,QAbstractItemView,QCheckBox)
from .engine import read_pair,prepare_local,make_candidate_rows,fix_geometry
from .logic import ident
from .fieldwidgets import LayerFieldComboBox
from .storage import zip_csv
from .reporting_full import report6


class VerificationDock(QDockWidget):
    """Operators choose candidate pair, zoom and highlight both source polygons.

    Decisions saved to CSV immediately, no dependence on Excel.
    """
    def __init__(self,iface,parent=None):
        super().__init__('NIB-NOP | Modul 6 - Verifikasi Studio',parent)
        self.iface=iface;self.candidates=[];self.decisions={};self.current=None
        self.setObjectName('NibNopVerificationStudio')
        wrapper=QWidget();self.setWidget(wrapper)
        layout=QVBoxLayout(wrapper)
        form=QFormLayout()
        self.bpn=QgsMapLayerComboBox();self.pbb=QgsMapLayerComboBox()
        self.bpn_id=LayerFieldComboBox('bpn', 'identity')
        self.pbb_id=LayerFieldComboBox('pbb', 'identity')
        self.bpn_area=LayerFieldComboBox('bpn', 'area')
        self.pbb_area=LayerFieldComboBox('pbb', 'area')
        self.bpn.layerChanged.connect(self.bpn_id.setLayer)
        self.bpn.layerChanged.connect(self.bpn_area.setLayer)
        self.pbb.layerChanged.connect(self.pbb_id.setLayer)
        self.pbb.layerChanged.connect(self.pbb_area.setLayer)
        # Set initial fields explicitly; layerChanged is not fired on first open.
        self.bpn_id.setLayer(self.bpn.currentLayer());self.bpn_area.setLayer(self.bpn.currentLayer())
        self.pbb_id.setLayer(self.pbb.currentLayer());self.pbb_area.setLayer(self.pbb.currentLayer())
        form.addRow('BPN:',self.bpn);form.addRow('NIB:',self.bpn_id)
        form.addRow('Luas BPN:',self.bpn_area)
        form.addRow('PBB:',self.pbb);form.addRow('NOP:',self.pbb_id)
        form.addRow('Luas PBB:',self.pbb_area)
        self.csv_path=QLineEdit();loadcsv=QPushButton('Pilih CSV kandidat...')
        loadcsv.clicked.connect(self.choose_csv)
        row=QHBoxLayout();row.addWidget(self.csv_path);row.addWidget(loadcsv)
        form.addRow('CSV Modul 3/5 (opsional):',row)
        self.labels_path=QLineEdit(str(Path.home()/'NIBNOP_HASIL'/'verifikasi_studio.csv'))
        labelsbtn=QPushButton('Simpan ke...');labelsbtn.clicked.connect(self.choose_save)
        rr=QHBoxLayout();rr.addWidget(self.labels_path);rr.addWidget(labelsbtn)
        form.addRow('CSV keputusan:',rr)
        self.radius=QLineEdit('15');form.addRow('Radius cari (meter):',self.radius)
        self.reproject=QCheckBox('Samakan CRS PBB terhadap BPN')
        form.addRow('',self.reproject)
        layout.addLayout(form)
        find=QPushButton('Buat / Buka Daftar Kandidat');find.clicked.connect(self.load_candidates)
        layout.addWidget(find)
        self.pick=QPushButton('Klik bidang BPN pada peta untuk memilih kandidat')
        self.pick.clicked.connect(self.enable_map_pick)
        layout.addWidget(self.pick)
        self.map_tool=None
        self.info=QLabel('Belum ada kandidat. Pilih kedua layer dan mulai.')
        self.info.setWordWrap(True);layout.addWidget(self.info)
        self.table=QTableWidget(0,6)
        self.table.setHorizontalHeaderLabels(['NIB','NOP','Overlap BPN %','Overlap PBB %','Skor AI','Label'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        layout.addWidget(self.table)
        paginator=QHBoxLayout();prev=QPushButton('◀ Sebelum');nex=QPushButton('Berikut ▶')
        self.page=0;self.page_size=200
        prev.clicked.connect(lambda:self.change_page(-1));nex.clicked.connect(lambda:self.change_page(1))
        paginator.addWidget(prev);paginator.addWidget(nex);layout.addLayout(paginator)
        self.lbl=QLabel('Pilih baris untuk menyorot kedua bidang di peta.');self.lbl.setWordWrap(True)
        layout.addWidget(self.lbl)
        self.operator=QLineEdit();self.operator.setPlaceholderText('Nama operator')
        self.source=QLineEdit();self.source.setPlaceholderText('Bukti verifikasi (dokumen, survei, arsip...)')
        self.notes=QLineEdit();self.notes.setPlaceholderText('Catatan / alasan')
        form2=QFormLayout();form2.addRow('Operator:',self.operator)
        form2.addRow('Sumber verifikasi:',self.source)
        form2.addRow('Catatan:',self.notes);layout.addLayout(form2)
        actions=QHBoxLayout()
        for title,label in [('Cocok (1)','1'),('Tidak cocok (0)','0'),('Belum pasti','')]:
            bt=QPushButton(title);bt.clicked.connect(lambda _=False,value=label:self.mark(value));actions.addWidget(bt)
        layout.addLayout(actions)
        export=QPushButton('Simpan CSV & PDF Rekap Verifikasi');export.clicked.connect(self.export)
        layout.addWidget(export)
        self.original_selections=[]

    def choose_csv(self):
        path=QFileDialog.getOpenFileName(self,'CSV pasangan kandidat','','CSV (*.csv)')[0]
        if path:self.csv_path.setText(path)
    def choose_save(self):
        path=QFileDialog.getSaveFileName(self,'Simpan label operator',self.labels_path.text(),'CSV (*.csv)')[0]
        if path:self.labels_path.setText(path)
    def load_candidates(self):
        try:
            b=self.bpn.currentLayer();p=self.pbb.currentLayer()
            if not b or not p:raise ValueError('Pilih layer BPN dan PBB.')
            rows_b,rows_p,notes=read_pair(b,p,self.reproject.isChecked())
            fix_geometry(rows_b);fix_geometry(rows_p)
            self.brecords={r['idx']:r for r in rows_b}
            self.precords={r['idx']:r for r in rows_p}
            prepare_local(rows_b,self.bpn_id.currentField(),self.bpn_area.currentField(),50)
            prepare_local(rows_p,self.pbb_id.currentField(),self.pbb_area.currentField(),50)
            csv_file=self.csv_path.text().strip()
            if csv_file:
                with open(csv_file,encoding='utf-8-sig',newline='') as f:
                    raw=list(csv.DictReader(f))
                self.candidates=[]
                for r in raw:
                    if not r.get('record_bpn') or not r.get('record_pbb'):continue
                    try:
                        i=int(float(r['record_bpn']));j=int(float(r['record_pbb']))
                    except ValueError:continue
                    if i in self.brecords and j in self.precords:
                        r['record_bpn']=i;r['record_pbb']=j
                        r.setdefault('pair_id','B%06d_P%06d'%(i,j))
                        self.candidates.append(r)
            else:
                self.candidates=make_candidate_rows(rows_b,rows_p,.01,float(self.radius.text()))
            # Reload existing operator decisions, if present
            self.decisions={}
            file=Path(self.labels_path.text())
            if file.exists():
                with open(file,encoding='utf-8-sig',newline='') as f:
                    for r in csv.DictReader(f):self.decisions[r.get('pair_id')]=r
            self.page=0;self.refresh_table()
        except Exception as e:
            QMessageBox.critical(self,'Verifikasi Studio',str(e))
    def enable_map_pick(self):
        if not self.candidates:
            QMessageBox.warning(self,'Verifikasi Studio','Muat kandidat terlebih dahulu.');return
        try:
            if self.map_tool is None:
                self.map_tool=QgsMapToolEmitPoint(self.iface.mapCanvas())
                self.map_tool.canvasClicked.connect(self.map_point_clicked)
            self.iface.mapCanvas().setMapTool(self.map_tool)
            self.lbl.setText('Klik pada poligon BPN di kanvas peta QGIS.')
        except Exception as e:QMessageBox.warning(self,'Verifikasi Studio',str(e))
    def map_point_clicked(self,point,button):
        try:
            b=self.bpn.currentLayer()
            tr=QgsCoordinateTransform(self.iface.mapCanvas().mapSettings().destinationCrs(),b.crs(),QgsProject.instance())
            q=tr.transform(point)
            from qgis.core import QgsPointXY,QgsGeometry
            pointgeom=QgsGeometry.fromPointXY(QgsPointXY(q.x(),q.y()))
            candidates=[r['idx'] for r in self.brecords.values() if not r['geom'].isNull() and r['geom'].contains(pointgeom)]
            if not candidates:
                self.lbl.setText('Tidak ada BPN di lokasi klik.');return
            bidx=candidates[0]
            idx=next((i for i,c in enumerate(self.candidates) if c['record_bpn']==bidx),None)
            if idx is None:
                self.lbl.setText('Bidang BPN ini belum memiliki calon pasangan dalam daftar.');return
            self.page=idx//self.page_size
            self.refresh_table()
            self.table.selectRow(idx%self.page_size)
        except Exception as e:self.lbl.setText('Gagal memilih bidang dari peta: '+str(e))
    def change_page(self,direction):
        self.page=max(0,min((len(self.candidates)-1)//self.page_size,self.page+direction)) if self.candidates else 0
        self.refresh_table()
    def refresh_table(self):
        rows=self.candidates[self.page*self.page_size:(self.page+1)*self.page_size]
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            shown=[r.get('NIB',''),r.get('NOP',''),r.get('overlap_bpn_pct',''),
                   r.get('overlap_pbb_pct',''),r.get('skor_ai',''),
                   self.decisions.get(r['pair_id'],{}).get('label','')]
            for j,value in enumerate(shown):
                try:
                    if isinstance(value,(int,float)):value=('%0.2f'%value)
                except Exception:pass
                self.table.setItem(i,j,QTableWidgetItem(str(value)))
        self.table.blockSignals(False)
        self.info.setText('%s kandidat | halaman %s / %s | terverifikasi: %s' %
                          (len(self.candidates),self.page+1,max(1,(len(self.candidates)+self.page_size-1)//self.page_size),
                           len(self.decisions)))
    def on_row_selected(self):
        s=self.table.selectedItems()
        if not s:return
        row=s[0].row();idx=self.page*self.page_size+row
        if idx>=len(self.candidates):return
        candidate=self.candidates[idx];self.current=candidate
        try:
            b=self.bpn.currentLayer();p=self.pbb.currentLayer()
            rb=self.brecords[candidate['record_bpn']];rp=self.precords[candidate['record_pbb']]
            b.selectByIds([rb['fid']]);p.selectByIds([rp['fid']])
            extent=rb['geom'].boundingBox()
            if p.crs()!=b.crs():
                # rp geometry was already transformed by read_pair
                extent.combineExtentWith(rp['geom'].boundingBox())
            else:extent.combineExtentWith(rp['geom'].boundingBox())
            extent.scale(1.7)
            if self.iface.mapCanvas().mapSettings().destinationCrs()!=b.crs():
                tr=QgsCoordinateTransform(b.crs(),self.iface.mapCanvas().mapSettings().destinationCrs(),QgsProject.instance())
                extent=tr.transformBoundingBox(extent)
            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()
            prev=self.decisions.get(candidate['pair_id'],{})
            self.source.setText(prev.get('sumber_verifikasi',''))
            self.notes.setText(prev.get('catatan',''))
            self.operator.setText(prev.get('operator',self.operator.text()))
            self.lbl.setText('NIB: %s   NOP: %s\nIrisan BPN: %s%%; PBB: %s%%' %
                             (candidate.get('NIB'),candidate.get('NOP'),
                              candidate.get('overlap_bpn_pct'),candidate.get('overlap_pbb_pct')))
        except Exception as e:
            self.lbl.setText('Tidak dapat menyorot pasangan: '+str(e))
    def mark(self,label):
        if self.current is None:
            QMessageBox.warning(self,'Verifikasi Studio','Pilih kandidat pada tabel terlebih dahulu.');return
        if label in ('0','1') and (not self.operator.text().strip() or not self.source.text().strip()):
            QMessageBox.warning(self,'Verifikasi Studio','Label 0/1 wajib diisi operator dan sumber verifikasi.');return
        pair=self.current
        data={'pair_id':pair['pair_id'],'record_bpn':pair['record_bpn'],
              'record_pbb':pair['record_pbb'],'NIB':pair.get('NIB',''),
              'NOP':pair.get('NOP',''),'label':label,
              'status_verifikasi':'DIVERIFIKASI' if label in ('0','1') else 'BELUM_PASTI',
              'sumber_verifikasi':self.source.text().strip() if label else '',
              'operator':self.operator.text().strip(),'catatan':self.notes.text().strip(),
              'waktu':datetime.now().isoformat(timespec='seconds')}
        self.decisions[pair['pair_id']]=data
        self.write_csv()
        self.refresh_table()
        self.lbl.setText('Keputusan disimpan: '+('COCOK' if label=='1' else 'TIDAK COCOK' if label=='0' else 'BELUM PASTI'))
    def write_csv(self):
        path=Path(self.labels_path.text()).expanduser()
        path.parent.mkdir(parents=True,exist_ok=True)
        fields=['pair_id','record_bpn','record_pbb','NIB','NOP','label','status_verifikasi',
                'sumber_verifikasi','operator','catatan','waktu']
        with open(path,'w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for entry in self.decisions.values():w.writerow({k:entry.get(k,'') for k in fields})
        return path
    def export(self):
        try:
            csvpath=self.write_csv();folder=csvpath.parent
            vals=list(self.decisions.values())
            accepted=sum(x.get('label')=='1' for x in vals)
            rejected=sum(x.get('label')=='0' for x in vals)
            b_rows=p_rows=None
            try:
                # Geometry is used only to illustrate verified pairs in the report.
                b_rows,p_rows,_=read_pair(self.bpn.currentLayer(),self.pbb.currentLayer(),
                                          self.reproject.isChecked())
            except Exception:
                pass
            report=report6(folder,vals,self.candidates,b_rows,p_rows,
                           ['Keputusan operator tersimpan dalam CSV dengan bukti verifikasi.',
                            'Belum pasti dan Level 2 tidak otomatis menjadi label 0.'])
            zipcsv=zip_csv(folder,{'verifikasi_studio.csv':vals},'rekap_verifikasi.zip')
            QMessageBox.information(self,'Verifikasi Studio',
                  'Hasil disimpan:\n%s\n%s\n%s'%(csvpath,report,zipcsv))
        except Exception as e:QMessageBox.critical(self,'Verifikasi Studio',str(e))

    def closeEvent(self,event):
        try:
            if self.map_tool and self.iface.mapCanvas().mapTool()==self.map_tool:
                self.iface.mapCanvas().unsetMapTool(self.map_tool)
        except Exception:
            pass
        super().closeEvent(event)
