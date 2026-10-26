"""Processing Provider untuk NIB-NOP Integrator."""
from pathlib import Path
from qgis.core import (
    QgsProcessingProvider,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterFile,
    QgsWkbTypes,
    QgsProject,
    QgsVectorFileWriter
)
from .engine import (
    read, read_pair, qa_attribute, spatial_audit, 
    determine_levels, columns, layer_from_records, make_candidate_rows,
    prepare_local  # <--- Tambahkan ini
)
from .ml import (
    train_model, predict,
    labels_for_pairs, add_historical_labeled_features, add_historical_pair_labels  # <--- Tambahkan ini
)
from .reporting_full import report1, report2, report3, report5
from .storage import zip_csv

# ==========================================
# MODUL 1: AUDIT KELENGKAPAN
# ==========================================
class NibNopQaAlgorithm(QgsProcessingAlgorithm):
    INPUT_BPN = 'INPUT_BPN'
    BPN_ID = 'BPN_ID'
    BPN_AREA = 'BPN_AREA'
    INPUT_PBB = 'INPUT_PBB'
    PBB_ID = 'PBB_ID'
    PBB_AREA = 'PBB_AREA'
    REPROJECT = 'REPROJECT'
    MIN_AREA = 'MIN_AREA'
    MAX_AREA = 'MAX_AREA'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'
    OUTPUT_BPN_LYR = 'OUTPUT_BPN_LYR'
    OUTPUT_PBB_LYR = 'OUTPUT_PBB_LYR'

    def createInstance(self): return NibNopQaAlgorithm()
    def name(self): return 'modul_1_audit_kelengkapan'
    def displayName(self): return '1. Audit Kelengkapan Atribut'
    def group(self): return 'NIB-NOP Integrator'
    def groupId(self): return 'nib_nop_integrator'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_BPN, 'Layer BPN', [QgsWkbTypes.PolygonGeometry]))
        self.addParameter(QgsProcessingParameterField(self.BPN_ID, 'Kolom identitas BPN', parentLayerParameterName=self.INPUT_BPN))
        self.addParameter(QgsProcessingParameterField(self.BPN_AREA, 'Kolom luas tertulis BPN', parentLayerParameterName=self.INPUT_BPN))
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_PBB, 'Layer PBB', [QgsWkbTypes.PolygonGeometry]))
        self.addParameter(QgsProcessingParameterField(self.PBB_ID, 'Kolom identitas PBB', parentLayerParameterName=self.INPUT_PBB))
        self.addParameter(QgsProcessingParameterField(self.PBB_AREA, 'Kolom luas tertulis PBB', parentLayerParameterName=self.INPUT_PBB))
        self.addParameter(QgsProcessingParameterBoolean(self.REPROJECT, 'Jika CRS berbeda, reproyeksikan PBB sementara ke CRS BPN', defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_AREA, 'Luas minimum pemeriksaan (m²)', type=QgsProcessingParameterNumber.Double, defaultValue=5.00))
        self.addParameter(QgsProcessingParameterNumber(self.MAX_AREA, 'Luas maksimum pemeriksaan (m²)', type=QgsProcessingParameterNumber.Double, defaultValue=10000.00))
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_FOLDER, 'Folder Hasil (PDF & ZIP Rekap)', optional=True))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_BPN_LYR, 'Output Layer BPN Audit'))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_PBB_LYR, 'Output Layer PBB Audit'))

    def processAlgorithm(self, parameters, context, feedback):
        bpn = self.parameterAsVectorLayer(parameters, self.INPUT_BPN, context)
        pbb = self.parameterAsVectorLayer(parameters, self.INPUT_PBB, context)
        b_id = self.parameterAsString(parameters, self.BPN_ID, context)
        b_area = self.parameterAsString(parameters, self.BPN_AREA, context)
        p_id = self.parameterAsString(parameters, self.PBB_ID, context)
        p_area = self.parameterAsString(parameters, self.PBB_AREA, context)
        reproject = self.parameterAsBoolean(parameters, self.REPROJECT, context)
        min_area = self.parameterAsDouble(parameters, self.MIN_AREA, context)
        max_area = self.parameterAsDouble(parameters, self.MAX_AREA, context)
        out_folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        dest_bpn = self.parameterAsOutputLayer(parameters, self.OUTPUT_BPN_LYR, context)
        dest_pbb = self.parameterAsOutputLayer(parameters, self.OUTPUT_PBB_LYR, context)

        b_recs, p_recs, _ = read_pair(bpn, pbb, reproject=reproject)
        stat_b, tables_b = qa_attribute(b_recs, b_id, b_area, min_area=min_area, max_area=max_area)
        stat_p, tables_p = qa_attribute(p_recs, p_id, p_area, min_area=min_area, max_area=max_area)

        schema_b = columns(bpn, [('id_kosong', 'int'), ('id_duplikat', 'int'), ('luas_flag', 'string')])
        schema_p = columns(pbb, [('id_kosong', 'int'), ('id_duplikat', 'int'), ('luas_flag', 'string')])
        
        out_lyr_b = layer_from_records(b_recs, bpn.crs(), schema_b, 'Audit_BPN')
        out_lyr_p = layer_from_records(p_recs, pbb.crs(), schema_p, 'Audit_PBB')

        for lyr, dest in [(out_lyr_b, dest_bpn), (out_lyr_p, dest_pbb)]:
            if dest:
                opts = QgsVectorFileWriter.SaveVectorOptions()
                opts.fileEncoding = 'UTF-8'
                opts.driverName = 'ESRI Shapefile' if dest.lower().endswith('.shp') else ('GeoJSON' if dest.lower().endswith('.geojson') else 'GPKG')
                QgsVectorFileWriter.writeAsVectorFormatV3(lyr, dest, QgsProject.instance().transformContext(), opts)

        if out_folder:
            Path(out_folder).mkdir(parents=True, exist_ok=True)
            stats = {}
            for k, v in stat_b.items(): stats['BPN ' + k] = v
            for k, v in stat_p.items(): stats['PBB ' + k] = v
            tables = {}
            for k, v in tables_b.items(): tables['bpn_' + k] = v
            for k, v in tables_p.items(): tables['pbb_' + k] = v
            try:
                report1(out_folder, (b_recs, b_id, b_area), (p_recs, p_id, p_area), stats, tables, min_area, max_area)
                zip_csv(out_folder, tables, 'rekap_csv.zip')
            except Exception as e:
                feedback.reportError(f"Gagal membuat laporan: {str(e)}")

        return {self.OUTPUT_BPN_LYR: dest_bpn, self.OUTPUT_PBB_LYR: dest_pbb, self.OUTPUT_FOLDER: out_folder}


# ==========================================
# MODUL 2: KUALITAS SPASIAL
# ==========================================
class NibNopSpatialAuditAlgorithm(QgsProcessingAlgorithm):
    INPUT_BPN = 'INPUT_BPN'
    BPN_ID = 'BPN_ID'
    BPN_AREA = 'BPN_AREA'
    INPUT_PBB = 'INPUT_PBB'
    PBB_ID = 'PBB_ID'
    PBB_AREA = 'PBB_AREA'
    REPROJECT = 'REPROJECT'
    MIN_OVERLAP = 'MIN_OVERLAP'
    MIN_GAP = 'MIN_GAP'
    ADD_GAPS = 'ADD_GAPS'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'
    OUTPUT_BPN_LYR = 'OUTPUT_BPN_LYR'
    OUTPUT_PBB_LYR = 'OUTPUT_PBB_LYR'

    def createInstance(self): return NibNopSpatialAuditAlgorithm()
    def name(self): return 'modul_2_kualitas_spasial'
    def displayName(self): return '2. Kualitas Spasial dan Fix Geometry'
    def group(self): return 'NIB-NOP Integrator'
    def groupId(self): return 'nib_nop_integrator'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_BPN, 'Layer BPN', [QgsWkbTypes.PolygonGeometry]))
        self.addParameter(QgsProcessingParameterField(self.BPN_ID, 'Kolom identitas BPN', parentLayerParameterName=self.INPUT_BPN))
        self.addParameter(QgsProcessingParameterField(self.BPN_AREA, 'Kolom luas tertulis BPN', parentLayerParameterName=self.INPUT_BPN))
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_PBB, 'Layer PBB', [QgsWkbTypes.PolygonGeometry]))
        self.addParameter(QgsProcessingParameterField(self.PBB_ID, 'Kolom identitas PBB', parentLayerParameterName=self.INPUT_PBB))
        self.addParameter(QgsProcessingParameterField(self.PBB_AREA, 'Kolom luas tertulis PBB', parentLayerParameterName=self.INPUT_PBB))
        self.addParameter(QgsProcessingParameterBoolean(self.REPROJECT, 'Jika CRS berbeda, reproyeksikan PBB sementara ke CRS BPN', defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_OVERLAP, 'Minimum luas overlap internal (m²)', type=QgsProcessingParameterNumber.Double, defaultValue=0.010))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_GAP, 'Minimum gap BPN ditambahkan (m²)', type=QgsProcessingParameterNumber.Double, defaultValue=1.00))
        self.addParameter(QgsProcessingParameterBoolean(self.ADD_GAPS, 'Delineasi gap tertutup BPN (bid_tambah=1)', defaultValue=True))
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_FOLDER, 'Folder Hasil (PDF & ZIP Rekap)', optional=True))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_BPN_LYR, 'Output Layer Spasial BPN'))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_PBB_LYR, 'Output Layer Spasial PBB'))

    def processAlgorithm(self, parameters, context, feedback):
        bpn = self.parameterAsVectorLayer(parameters, self.INPUT_BPN, context)
        pbb = self.parameterAsVectorLayer(parameters, self.INPUT_PBB, context)
        b_id = self.parameterAsString(parameters, self.BPN_ID, context)
        b_area = self.parameterAsString(parameters, self.BPN_AREA, context)
        p_id = self.parameterAsString(parameters, self.PBB_ID, context)
        p_area = self.parameterAsString(parameters, self.PBB_AREA, context)
        reproject = self.parameterAsBoolean(parameters, self.REPROJECT, context)
        min_overlap = self.parameterAsDouble(parameters, self.MIN_OVERLAP, context)
        min_gap = self.parameterAsDouble(parameters, self.MIN_GAP, context)
        add_gaps = self.parameterAsBoolean(parameters, self.ADD_GAPS, context)
        out_folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        
        dest_bpn = self.parameterAsOutputLayer(parameters, self.OUTPUT_BPN_LYR, context)
        dest_pbb = self.parameterAsOutputLayer(parameters, self.OUTPUT_PBB_LYR, context)

        b_recs, p_recs, _ = read_pair(bpn, pbb, reproject=reproject)
        audited_b, overlaps_b, holes, notes_b = spatial_audit(b_recs, b_id, b_area, min_area=min_overlap, min_gap=min_gap, add_gaps=add_gaps)
        audited_p, overlaps_p, _, notes_p = spatial_audit(p_recs, p_id, p_area, min_area=min_overlap, min_gap=min_gap, add_gaps=False)

        schema_b = columns(bpn, [('geom_kosong', 'int'), ('geom_invalid', 'int'), ('geom_fixed', 'int'), ('overlap', 'int'), ('bid_tambah', 'int'), ('selisih_luas', 'double'), ('persen_selisihL', 'double')])
        schema_p = columns(pbb, [('geom_kosong', 'int'), ('geom_invalid', 'int'), ('geom_fixed', 'int'), ('overlap', 'int'), ('selisih_luas', 'double'), ('persen_selisihL', 'double')])
        
        out_layer_b = layer_from_records(audited_b, bpn.crs(), schema_b, 'Audit_Spasial_BPN')
        out_layer_p = layer_from_records(audited_p, pbb.crs(), schema_p, 'Audit_Spasial_PBB')
        
        for lyr, dest in [(out_layer_b, dest_bpn), (out_layer_p, dest_pbb)]:
            if dest:
                opts = QgsVectorFileWriter.SaveVectorOptions()
                opts.fileEncoding = 'UTF-8'
                opts.driverName = 'ESRI Shapefile' if dest.lower().endswith('.shp') else ('GeoJSON' if dest.lower().endswith('.geojson') else 'GPKG')
                QgsVectorFileWriter.writeAsVectorFormatV3(lyr, dest, QgsProject.instance().transformContext(), opts)

        if out_folder:
            Path(out_folder).mkdir(parents=True, exist_ok=True)
            try:
                stat_b = {'geom_kosong': sum(r['a'].get('geom_kosong',0) for r in audited_b), 'geom_invalid': sum(r['a'].get('geom_invalid',0) for r in audited_b), 'geom_fixed': sum(r['a'].get('geom_fixed',0) for r in audited_b), 'overlap': len(overlaps_b), 'gap_baru': len(holes)}
                stat_p = {'geom_kosong': sum(r['a'].get('geom_kosong',0) for r in audited_p), 'geom_invalid': sum(r['a'].get('geom_invalid',0) for r in audited_p), 'geom_fixed': sum(r['a'].get('geom_fixed',0) for r in audited_p), 'overlap': len(overlaps_p), 'gap_baru': 0}
                stats = {}
                for k, v in stat_b.items(): stats['bpn_' + k] = v
                for k, v in stat_p.items(): stats['pbb_' + k] = v
                
                report2(out_folder, audited_b, audited_p, stats, notes_b + notes_p, overlaps_b, overlaps_p, holes)
                zip_csv(out_folder, {'overlap_bpn.csv': overlaps_b, 'overlap_pbb.csv': overlaps_p, 'gap.csv': holes}, 'rekap_csv.zip')
            except Exception as e:
                feedback.reportError(f"Gagal laporan Modul 2: {str(e)}")

        return {self.OUTPUT_BPN_LYR: dest_bpn, self.OUTPUT_PBB_LYR: dest_pbb, self.OUTPUT_FOLDER: out_folder}


# ==========================================
# MODUL 3: PENENTUAN LEVEL PEMADUAN ATURAN
# ==========================================
class NibNopRuleMatchingAlgorithm(QgsProcessingAlgorithm):
    INPUT_BPN = 'INPUT_BPN'
    BPN_ID = 'BPN_ID'
    BPN_AREA = 'BPN_AREA'
    INPUT_PBB = 'INPUT_PBB'
    PBB_ID = 'PBB_ID'
    PBB_AREA = 'PBB_AREA'
    REPROJECT = 'REPROJECT'
    OVERLAP_PCT = 'OVERLAP_PCT'
    SIM_PCT = 'SIM_PCT'
    MAX_DEV = 'MAX_DEV'
    MIN_IRISAN = 'MIN_IRISAN'
    MIN_GAP = 'MIN_GAP'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'
    OUTPUT_L1 = 'OUTPUT_L1'
    OUTPUT_L2_BPN = 'OUTPUT_L2_BPN'
    OUTPUT_L2_PBB = 'OUTPUT_L2_PBB'

    def createInstance(self): return NibNopRuleMatchingAlgorithm()
    def name(self): return 'modul_3_penentuan_level'
    def displayName(self): return '3. Penentuan level pemaduan berbasis aturan'
    def group(self): return 'NIB-NOP Integrator'
    def groupId(self): return 'nib_nop_integrator'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_BPN, 'Layer BPN', [QgsWkbTypes.PolygonGeometry]))
        self.addParameter(QgsProcessingParameterField(self.BPN_ID, 'Kolom identitas BPN', parentLayerParameterName=self.INPUT_BPN))
        self.addParameter(QgsProcessingParameterField(self.BPN_AREA, 'Kolom luas tertulis BPN', parentLayerParameterName=self.INPUT_BPN))
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_PBB, 'Layer PBB', [QgsWkbTypes.PolygonGeometry]))
        self.addParameter(QgsProcessingParameterField(self.PBB_ID, 'Kolom identitas PBB', parentLayerParameterName=self.INPUT_PBB))
        self.addParameter(QgsProcessingParameterField(self.PBB_AREA, 'Kolom luas tertulis PBB', parentLayerParameterName=self.INPUT_PBB))
        self.addParameter(QgsProcessingParameterBoolean(self.REPROJECT, 'Jika CRS berbeda, reproyeksikan PBB sementara ke CRS BPN', defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(self.OVERLAP_PCT, 'Ambang irisan > (% luas BPN)', type=QgsProcessingParameterNumber.Double, defaultValue=50.0))
        self.addParameter(QgsProcessingParameterNumber(self.SIM_PCT, 'Kesamaan luas tertulis > (%)', type=QgsProcessingParameterNumber.Double, defaultValue=90.0))
        self.addParameter(QgsProcessingParameterNumber(self.MAX_DEV, 'Deviasi luas-geometri maksimum (%)', type=QgsProcessingParameterNumber.Double, defaultValue=50.0))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_IRISAN, 'Minimum luas irisan (m²)', type=QgsProcessingParameterNumber.Double, defaultValue=0.010))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_GAP, 'Minimum gap tertutup BPN (m²)', type=QgsProcessingParameterNumber.Double, defaultValue=1.00))
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_FOLDER, 'Folder Hasil (PDF & ZIP Rekap)', optional=True))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_L1, 'Hasil Level 1 (Padan)'))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_L2_BPN, 'Hasil BPN Level 2 (Studio)', optional=True))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_L2_PBB, 'Hasil PBB Level 2 (Studio)', optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        bpn = self.parameterAsVectorLayer(parameters, self.INPUT_BPN, context)
        pbb = self.parameterAsVectorLayer(parameters, self.INPUT_PBB, context)
        out_folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        
        dest_l1 = self.parameterAsOutputLayer(parameters, self.OUTPUT_L1, context)
        dest_l2b = self.parameterAsOutputLayer(parameters, self.OUTPUT_L2_BPN, context)
        dest_l2p = self.parameterAsOutputLayer(parameters, self.OUTPUT_L2_PBB, context)
        
        opts = {
            'bpn_id': self.parameterAsString(parameters, self.BPN_ID, context),
            'bpn_area': self.parameterAsString(parameters, self.BPN_AREA, context),
            'pbb_id': self.parameterAsString(parameters, self.PBB_ID, context),
            'pbb_area': self.parameterAsString(parameters, self.PBB_AREA, context),
            'reproject': self.parameterAsBoolean(parameters, self.REPROJECT, context),
            'min_overlap': self.parameterAsDouble(parameters, self.OVERLAP_PCT, context),
            'min_sim': self.parameterAsDouble(parameters, self.SIM_PCT, context),
            'max_dev': self.parameterAsDouble(parameters, self.MAX_DEV, context),
            'min_irisan': self.parameterAsDouble(parameters, self.MIN_IRISAN, context)
        }
        b_recs, p_recs, _ = read_pair(bpn, pbb, reproject=opts['reproject'])
        level1, lev2b, lev2p, pairs, clean = determine_levels(b_recs, p_recs, opts)
        
        schema_l1 = columns(bpn, [('nop_padanan', 'string'), ('level', 'int'), ('metode_padu', 'string'), ('overlap_pct', 'double'), ('kesamaan_pct', 'double')])
        schema_l2b = columns(bpn, [('level', 'int'), ('calon_n', 'int'), ('kode_l2', 'string'), ('alasan_l2', 'string'), ('calon_id', 'string')])
        schema_l2p = columns(pbb, [('level', 'int'), ('calon_n', 'int'), ('kode_l2', 'string'), ('alasan_l2', 'string'), ('calon_id', 'string')])

        out_layer_l1 = layer_from_records(level1, bpn.crs(), schema_l1, 'Hasil_Level_1')
        out_layer_l2b = layer_from_records(lev2b, bpn.crs(), schema_l2b, 'BPN_Level_2')
        out_layer_l2p = layer_from_records(lev2p, pbb.crs(), schema_l2p, 'PBB_Level_2')
        
        mappings = [(out_layer_l1, dest_l1), (out_layer_l2b, dest_l2b), (out_layer_l2p, dest_l2p)]
        for lyr, dest in mappings:
            if dest: 
                opts_save = QgsVectorFileWriter.SaveVectorOptions()
                opts_save.fileEncoding = 'UTF-8'
                opts_save.driverName = 'ESRI Shapefile' if dest.lower().endswith('.shp') else ('GeoJSON' if dest.lower().endswith('.geojson') else 'GPKG')
                QgsVectorFileWriter.writeAsVectorFormatV3(lyr, dest, QgsProject.instance().transformContext(), opts_save)

        if out_folder:
            Path(out_folder).mkdir(parents=True, exist_ok=True)
            try:
                stats = {'Level 1': len(level1), 'BPN Level 2': len(lev2b), 'PBB Level 2': len(lev2p)}
                report3(out_folder, level1, lev2b, lev2p, pairs, stats, [], [])
                zip_csv(out_folder, {
                    'pasangan_level1.csv': level1, 
                    'bpn_level2.csv': lev2b, 
                    'pbb_level2.csv': lev2p, 
                    'kandidat_pasangan.csv': pairs
                }, 'rekap_csv.zip')
            except Exception as e:
                feedback.reportError(f"Gagal laporan Modul 3: {str(e)}")

        return {
            self.OUTPUT_L1: dest_l1, 
            self.OUTPUT_L2_BPN: dest_l2b, 
            self.OUTPUT_L2_PBB: dest_l2p, 
            self.OUTPUT_FOLDER: out_folder
        }

# ==========================================
# MODUL 4: TRAINING AI
# ==========================================
class NibNopTrainingAiAlgorithm(QgsProcessingAlgorithm):
    INPUT_BPN = 'INPUT_BPN'
    BPN_ID = 'BPN_ID'
    BPN_AREA = 'BPN_AREA'
    INPUT_PBB = 'INPUT_PBB'
    PBB_ID = 'PBB_ID'
    PBB_AREA = 'PBB_AREA'
    REPROJECT = 'REPROJECT'
    SILVER_CSV = 'SILVER_CSV'
    HIST_FEAT_CSV = 'HIST_FEAT_CSV'
    HIST_CSV = 'HIST_CSV'
    USE_HIST_GEO = 'USE_HIST_GEO'
    HIST_GEO_CSV = 'HIST_GEO_CSV'
    RADIUS = 'RADIUS'
    TARGET_PRECISION = 'TARGET_PRECISION'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'

    def createInstance(self): return NibNopTrainingAiAlgorithm()
    def name(self): return 'modul_4_training_ai'
    def displayName(self): return '4. Training AI'
    def group(self): return 'NIB-NOP Integrator'
    def groupId(self): return 'nib_nop_integrator'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_BPN, 'Layer BPN', [QgsWkbTypes.PolygonGeometry]))
        self.addParameter(QgsProcessingParameterField(self.BPN_ID, 'Kolom identitas BPN', parentLayerParameterName=self.INPUT_BPN))
        self.addParameter(QgsProcessingParameterField(self.BPN_AREA, 'Kolom luas tertulis BPN', parentLayerParameterName=self.INPUT_BPN))
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_PBB, 'Layer PBB', [QgsWkbTypes.PolygonGeometry]))
        self.addParameter(QgsProcessingParameterField(self.PBB_ID, 'Kolom identitas PBB', parentLayerParameterName=self.INPUT_PBB))
        self.addParameter(QgsProcessingParameterField(self.PBB_AREA, 'Kolom luas tertulis PBB', parentLayerParameterName=self.INPUT_PBB))
        self.addParameter(QgsProcessingParameterBoolean(self.REPROJECT, 'Jika CRS berbeda, reproyeksikan PBB sementara ke CRS BPN', defaultValue=False))
        self.addParameter(QgsProcessingParameterFile(self.SILVER_CSV, 'CSV kandidat Modul 3 (silver)', optional=True))
        self.addParameter(QgsProcessingParameterFile(self.HIST_FEAT_CSV, 'CSV fitur historis terverifikasi (opsional)', optional=True))
        self.addParameter(QgsProcessingParameterFile(self.HIST_CSV, 'CSV label operator pada layer yang dipilih (opsional)', optional=True))
        self.addParameter(QgsProcessingParameterBoolean(self.USE_HIST_GEO, 'Gunakan pasangan GeoJSON historis + CSV label (opsional)', defaultValue=False))
        self.addParameter(QgsProcessingParameterFile(self.HIST_GEO_CSV, 'CSV pasangan historis berlabel', optional=True))
        self.addParameter(QgsProcessingParameterNumber(self.RADIUS, 'Radius pencarian kandidat (meter)', type=QgsProcessingParameterNumber.Double, defaultValue=15.00))
        self.addParameter(QgsProcessingParameterNumber(self.TARGET_PRECISION, 'Target precision GOLD', type=QgsProcessingParameterNumber.Double, defaultValue=0.990))
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_FOLDER, 'Folder hasil model dan laporan', optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        bpn = self.parameterAsVectorLayer(parameters, self.INPUT_BPN, context)
        pbb = self.parameterAsVectorLayer(parameters, self.INPUT_PBB, context)
        out_folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        
        opts = {
            'bpn_id': self.parameterAsString(parameters, self.BPN_ID, context),
            'bpn_area': self.parameterAsString(parameters, self.BPN_AREA, context),
            'pbb_id': self.parameterAsString(parameters, self.PBB_ID, context),
            'pbb_area': self.parameterAsString(parameters, self.PBB_AREA, context),
            'reproject': self.parameterAsBoolean(parameters, self.REPROJECT, context),
            'radius': self.parameterAsDouble(parameters, self.RADIUS, context),
            'target_precision': self.parameterAsDouble(parameters, self.TARGET_PRECISION, context),
            'silver_csv': self.parameterAsString(parameters, self.SILVER_CSV, context) or None,
            'hist_feat_csv': self.parameterAsString(parameters, self.HIST_FEAT_CSV, context) or None,
            'hist_csv': self.parameterAsString(parameters, self.HIST_CSV, context) or None,
            'use_hist_geo': self.parameterAsBoolean(parameters, self.USE_HIST_GEO, context),
            'hist_geo_csv': self.parameterAsString(parameters, self.HIST_GEO_CSV, context) or None
        }

        b_recs, p_recs, _ = read_pair(bpn, pbb, reproject=opts['reproject'])
        
        if out_folder:
            Path(out_folder).mkdir(parents=True, exist_ok=True)
            try:
                # Siapkan data lokal, buat kandidat pasangan, dan mapping label silver/gold
                prepare_local(b_recs, opts['bpn_id'], opts['bpn_area'], 50.0)
                prepare_local(p_recs, opts['pbb_id'], opts['pbb_area'], 50.0)
                candidates = make_candidate_rows(b_recs, p_recs, radius=opts['radius'])
                
                silver, gold, unresolved = labels_for_pairs(
                    candidates, 
                    historical_csv=opts['hist_csv'], 
                    silver_csv=opts['silver_csv']
                )
                
                if opts['hist_feat_csv']:
                    add_historical_labeled_features(gold, opts['hist_feat_csv'])
                
                if opts['use_hist_geo'] and opts['hist_geo_csv']:
                    add_historical_pair_labels(gold, candidates, opts['hist_geo_csv'])
                
                # Jalankan training model dengan dataset silver & gold yang valid
                train_model(silver, gold, out_folder, min_precision=opts['target_precision'])
                feedback.pushInfo(f"Training AI sukses! Model dan metadata tersimpan di: {out_folder}")
            except Exception as e:
                feedback.reportError(f"Gagal melakukan Training AI (Modul 4): {str(e)}")

        return {self.OUTPUT_FOLDER: out_folder}

# ==========================================
# MODUL 5: INFERENCE AI
# ==========================================
class NibNopInferenceAiAlgorithm(QgsProcessingAlgorithm):
    INPUT_BPN = 'INPUT_BPN'
    BPN_ID = 'BPN_ID'
    BPN_AREA = 'BPN_AREA'
    INPUT_PBB = 'INPUT_PBB'
    PBB_ID = 'PBB_ID'
    PBB_AREA = 'PBB_AREA'
    REPROJECT = 'REPROJECT'
    OVERLAP_PCT = 'OVERLAP_PCT'
    SIM_PCT = 'SIM_PCT'
    MAX_DEV = 'MAX_DEV'
    MIN_IRISAN = 'MIN_IRISAN'
    MIN_GAP = 'MIN_GAP'
    MODEL_FILE = 'MODEL_FILE'
    METADATA_FILE = 'METADATA_FILE'
    RADIUS = 'RADIUS'
    MIN_SCORE = 'MIN_SCORE'
    SCORE_DIFF = 'SCORE_DIFF'
    ALLOW_AI = 'ALLOW_AI'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'
    OUTPUT_L1 = 'OUTPUT_L1'
    OUTPUT_L2_BPN = 'OUTPUT_L2_BPN'
    OUTPUT_L2_PBB = 'OUTPUT_L2_PBB'

    def createInstance(self): return NibNopInferenceAiAlgorithm()
    def name(self): return 'modul_5_inference_ai'
    def displayName(self): return '5. Inference AI dan Level 1/2'
    def group(self): return 'NIB-NOP Integrator'
    def groupId(self): return 'nib_nop_integrator'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_BPN, 'Layer BPN', [QgsWkbTypes.PolygonGeometry]))
        self.addParameter(QgsProcessingParameterField(self.BPN_ID, 'Kolom identitas BPN', parentLayerParameterName=self.INPUT_BPN))
        self.addParameter(QgsProcessingParameterField(self.BPN_AREA, 'Kolom luas tertulis BPN', parentLayerParameterName=self.INPUT_BPN))
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_PBB, 'Layer PBB', [QgsWkbTypes.PolygonGeometry]))
        self.addParameter(QgsProcessingParameterField(self.PBB_ID, 'Kolom identitas PBB', parentLayerParameterName=self.INPUT_PBB))
        self.addParameter(QgsProcessingParameterField(self.PBB_AREA, 'Kolom luas tertulis PBB', parentLayerParameterName=self.INPUT_PBB))
        self.addParameter(QgsProcessingParameterBoolean(self.REPROJECT, 'Jika CRS berbeda, reproyeksikan PBB sementara ke CRS BPN', defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(self.OVERLAP_PCT, 'Ambang irisan > (% luas BPN)', type=QgsProcessingParameterNumber.Double, defaultValue=50.0))
        self.addParameter(QgsProcessingParameterNumber(self.SIM_PCT, 'Kesamaan luas tertulis > (%)', type=QgsProcessingParameterNumber.Double, defaultValue=90.0))
        self.addParameter(QgsProcessingParameterNumber(self.MAX_DEV, 'Deviasi luas-geometri maksimum (%)', type=QgsProcessingParameterNumber.Double, defaultValue=50.0))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_IRISAN, 'Minimum luas irisan (m²)', type=QgsProcessingParameterNumber.Double, defaultValue=0.010))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_GAP, 'Minimum gap tertutup BPN (m²)', type=QgsProcessingParameterNumber.Double, defaultValue=1.00))
        self.addParameter(QgsProcessingParameterFile(self.MODEL_FILE, 'Model terlatih (.joblib)'))
        self.addParameter(QgsProcessingParameterFile(self.METADATA_FILE, 'Metadata model (.json)'))
        self.addParameter(QgsProcessingParameterNumber(self.RADIUS, 'Radius kandidat AI (meter)', type=QgsProcessingParameterNumber.Double, defaultValue=15.00))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_SCORE, 'Skor minimum AI', type=QgsProcessingParameterNumber.Double, defaultValue=0.950))
        self.addParameter(QgsProcessingParameterNumber(self.SCORE_DIFF, 'Selisih skor kandidat ke-1 vs ke-2', type=QgsProcessingParameterNumber.Double, defaultValue=0.150))
        self.addParameter(QgsProcessingParameterBoolean(self.ALLOW_AI, 'Izinkan tambahan Level 1 berbasis AI HANYA bila GOLD telah diverifikasi', defaultValue=False))
        self.addParameter(QgsProcessingParameterFolderDestination(self.OUTPUT_FOLDER, 'Folder Hasil (PDF & ZIP Rekap)', optional=True))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_L1, 'Hasil Level 1 (Padan AI)', optional=True))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_L2_BPN, 'Hasil BPN Level 2 AI', optional=True))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT_L2_PBB, 'Hasil PBB Level 2 AI', optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        bpn = self.parameterAsVectorLayer(parameters, self.INPUT_BPN, context)
        pbb = self.parameterAsVectorLayer(parameters, self.INPUT_PBB, context)
        out_folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        
        dest_l1 = self.parameterAsOutputLayer(parameters, self.OUTPUT_L1, context)
        dest_l2b = self.parameterAsOutputLayer(parameters, self.OUTPUT_L2_BPN, context)
        dest_l2p = self.parameterAsOutputLayer(parameters, self.OUTPUT_L2_PBB, context)

        opts = {
            'bpn_id': self.parameterAsString(parameters, self.BPN_ID, context),
            'bpn_area': self.parameterAsString(parameters, self.BPN_AREA, context),
            'pbb_id': self.parameterAsString(parameters, self.PBB_ID, context),
            'pbb_area': self.parameterAsString(parameters, self.PBB_AREA, context),
            'reproject': self.parameterAsBoolean(parameters, self.REPROJECT, context),
            'min_overlap': self.parameterAsDouble(parameters, self.OVERLAP_PCT, context),
            'min_sim': self.parameterAsDouble(parameters, self.SIM_PCT, context),
            'max_dev': self.parameterAsDouble(parameters, self.MAX_DEV, context),
            'min_irisan': self.parameterAsDouble(parameters, self.MIN_IRISAN, context),
            'radius': self.parameterAsDouble(parameters, self.RADIUS, context),
            'min_score': self.parameterAsDouble(parameters, self.MIN_SCORE, context),
            'score_diff': self.parameterAsDouble(parameters, self.SCORE_DIFF, context),
            'allow_ai': self.parameterAsBoolean(parameters, self.ALLOW_AI, context),
            'model_file': self.parameterAsString(parameters, self.MODEL_FILE, context),
            'metadata_file': self.parameterAsString(parameters, self.METADATA_FILE, context)
        }

        b_recs, p_recs, _ = read_pair(bpn, pbb, reproject=opts['reproject'])
        
        try:
            prepare_local(b_recs, opts['bpn_id'], opts['bpn_area'], opts['max_dev'])
            prepare_local(p_recs, opts['pbb_id'], opts['pbb_area'], opts['max_dev'])
            
            # 1. Jalankan rule matching dasar untuk mendapatkan baseline Level 1 & Level 2
            level1, lev2b, lev2p, pairs, clean = determine_levels(b_recs, p_recs, opts)
            
            # 2. Buat kandidat dan jalankan inferensi AI
            candidates = make_candidate_rows(b_recs, p_recs, radius=opts['radius'])
            metadata = predict(candidates, opts['model_file'], opts['metadata_file'])
            
            schema_l1 = columns(bpn, [('nop_padanan', 'string'), ('level', 'int'), ('metode_padu', 'string'), ('skor_ai', 'double')])
            schema_l2b = columns(bpn, [('level', 'int'), ('calon_n', 'int'), ('kode_l2', 'string'), ('alasan_l2', 'string')])
            schema_l2p = columns(pbb, [('level', 'int'), ('calon_n', 'int'), ('kode_l2', 'string'), ('alasan_l2', 'string')])

            out_layer_l1 = layer_from_records(level1, bpn.crs(), schema_l1, 'Level_1_AI')
            out_layer_l2b = layer_from_records(lev2b, bpn.crs(), schema_l2b, 'BPN_Level_2_AI')
            out_layer_l2p = layer_from_records(lev2p, pbb.crs(), schema_l2p, 'PBB_Level_2_AI')

            mappings = [(out_layer_l1, dest_l1), (out_layer_l2b, dest_l2b), (out_layer_l2p, dest_l2p)]
            for lyr, dest in mappings:
                if dest and lyr:
                    opts_save = QgsVectorFileWriter.SaveVectorOptions()
                    opts_save.fileEncoding = 'UTF-8'
                    opts_save.driverName = 'ESRI Shapefile' if dest.lower().endswith('.shp') else ('GeoJSON' if dest.lower().endswith('.geojson') else 'GPKG')
                    QgsVectorFileWriter.writeAsVectorFormatV3(lyr, dest, QgsProject.instance().transformContext(), opts_save)

            if out_folder:
                Path(out_folder).mkdir(parents=True, exist_ok=True)
                stats = {'Level 1': len(level1), 'BPN Level 2': len(lev2b), 'PBB Level 2': len(lev2p)}
                report5(out_folder, level1, lev2b, lev2p, pairs, candidates, [], stats, [], metadata, [])
                zip_csv(out_folder, {'inference_level1.csv': level1}, 'rekap_csv.zip')

        except Exception as e:
            feedback.reportError(f"Gagal menjalankan Inference AI (Modul 5): {str(e)}")

        return {
            self.OUTPUT_L1: dest_l1,
            self.OUTPUT_L2_BPN: dest_l2b,
            self.OUTPUT_L2_PBB: dest_l2p,
            self.OUTPUT_FOLDER: out_folder
        }

# ==========================================
# PROVIDER REGISTRY
# ==========================================
class NibNopProvider(QgsProcessingProvider):
    def loadAlgorithms(self, *args):
        self.addAlgorithm(NibNopQaAlgorithm())
        self.addAlgorithm(NibNopSpatialAuditAlgorithm())
        self.addAlgorithm(NibNopRuleMatchingAlgorithm())
        self.addAlgorithm(NibNopTrainingAiAlgorithm())
        self.addAlgorithm(NibNopInferenceAiAlgorithm())

    def id(self): return 'nib_nop_integrator'
    def name(self): return 'NIB–NOP Integrator'