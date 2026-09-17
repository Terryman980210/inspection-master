from collections import Counter
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
 QLineEdit, QCheckBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QPlainTextEdit)


class EntityInspector(QWidget):
    selected = Signal(str)
    filter_changed = Signal(object)

    def __init__(self):
        super().__init__()
        self.entities = []
        self.candidate_handles = set()
        self.rendered_handles = set()
        layout = QVBoxLayout(self)
        self.summary = QLabel('モデル空間の全要素を確認できます。')
        self.summary.setWordWrap(True); layout.addWidget(self.summary)
        controls = QHBoxLayout()
        self.types = QComboBox(); self.layers = QComboBox()
        self.handle = QLineEdit(); self.handle.setPlaceholderText('ハンドル・文字を検索')
        controls.addWidget(self.types); controls.addWidget(self.layers); controls.addWidget(self.handle)
        layout.addLayout(controls)
        self.isolate = QCheckBox('検索結果のエンティティだけ図面に表示')
        layout.addWidget(self.isolate)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(['種類', 'ハンドル', 'レイヤ', '文字', '状態'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); self.details.setMaximumHeight(130)
        layout.addWidget(self.details)
        self.types.currentIndexChanged.connect(self.refresh)
        self.layers.currentIndexChanged.connect(self.refresh)
        self.handle.textChanged.connect(self.refresh)
        self.isolate.toggled.connect(self.refresh)
        self.table.itemSelectionChanged.connect(self.show_details)

    def load(self, drawing, rendered_handles):
        self.entities = list(drawing.modelspace)
        self.candidate_handles = {c.source_handle for c in drawing.candidates}
        self.rendered_handles = set(rendered_handles)
        for combo, values in [(self.types, sorted({e.dxftype() for e in self.entities})),
                              (self.layers, sorted({e.dxf.layer for e in self.entities}))]:
            combo.blockSignals(True); combo.clear(); combo.addItem('すべて', None)
            for value in values: combo.addItem(value, value)
            combo.blockSignals(False)
        self.handle.blockSignals(True); self.handle.clear(); self.handle.blockSignals(False)
        self.isolate.blockSignals(True); self.isolate.setChecked(False); self.isolate.blockSignals(False)
        self.refresh()

    def refresh(self, *_):
        kind = self.types.currentData(); layer = self.layers.currentData(); query = self.handle.text().casefold()
        self.rows = []
        for e in self.entities:
            text = e.plain_text() if e.dxftype() == 'MTEXT' else str(e.dxf.get('text', '')) if e.dxftype() == 'TEXT' else ''
            if kind and e.dxftype() != kind: continue
            if layer and e.dxf.layer != layer: continue
            if query and query not in (e.dxf.handle + ' ' + text).casefold(): continue
            self.rows.append((e, text))
        self.table.blockSignals(True); self.table.setRowCount(len(self.rows)); self.table.clearContents()
        for r, (e, text) in enumerate(self.rows):
            status = ('候補あり' if e.dxf.handle in self.candidate_handles else '候補なし')
            if e.dxf.handle not in self.rendered_handles: status += ' / 描画未対応'
            for col, value in enumerate([e.dxftype(), e.dxf.handle, e.dxf.layer, text, status]):
                self.table.setItem(r, col, QTableWidgetItem(value))
        self.table.blockSignals(False); self.details.clear()
        counts = Counter(e.dxftype() for e in self.entities)
        self.summary.setText(f'表示 {len(self.rows)} / 全 {len(self.entities)}件（モデル空間）\n' + ' · '.join(f'{k}: {v}' for k,v in counts.items()))
        self.filter_changed.emit({e.dxf.handle for e,_ in self.rows} if self.isolate.isChecked() else None)

    def show_details(self):
        r = self.table.currentRow()
        if not 0 <= r < len(self.rows): return
        e, text = self.rows[r]
        self.details.setPlainText('\n'.join(f'{k}: {v}' for k,v in e.dxf.all_existing_dxf_attribs().items()) + '\n文字: ' + text)
        self.selected.emit(e.dxf.handle)
