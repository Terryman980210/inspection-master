from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QStandardPaths
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHeaderView, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QTabWidget, QDockWidget, QApplication,
)
from .dxf_loader import LoadedDrawing, load_drawing
from .graphics import DrawingView
from .models import InspectionCandidate, normalize_orders
from .storage import save_csv
from .session import SessionStore
from .inspector import EntityInspector

STYLE = '''
QMainWindow, QWidget { color: #233247; background-color: #f4f6f9; }
QToolBar { background: #ffffff; border-bottom: 1px solid #dce3ec; spacing: 12px; padding: 8px; }
QTableWidget { background: #ffffff; alternate-background-color: #f8fafc;
    color: #233247; gridline-color: #e4eaf1; border: 1px solid #dce3ec;
    selection-background-color: #dceafe; selection-color: #172e4d; }
QTableWidget::item { padding: 6px; }
QTableWidget::item:selected { background: #dceafe; color: #172e4d; }
QTableWidget QLineEdit { background: #ffffff; color: #18283b;
    border: 2px solid #3b82c4; padding: 3px;
    selection-background-color: #c8e0fb; selection-color: #18283b; }
QHeaderView::section { background: #edf2f7; color: #526177; border: none;
    border-bottom: 1px solid #dce3ec; padding: 8px; }
QTabBar::tab { background: #e8edf3; padding: 10px 18px; margin-right: 3px; }
QTabBar::tab:selected { background: white; color: #175da0; border-bottom: 3px solid #3b82c4; }
QPushButton { background: white; border: 1px solid #cbd5e1; border-radius: 5px; padding: 7px 14px; }
QPushButton:hover { background: #eaf2fd; }
QPushButton:disabled { color: #94a3b8; background: #edf1f5; }
QLabel#summary { font-size: 14px; font-weight: bold; padding: 6px 0; }
'''

class MainWindow(QMainWindow):
    COLUMNS = ['採用', '測定順', '検査項目', '分類', '測定器', '備考', '元要素']

    def __init__(self, session_dir=None):
        super().__init__()
        self.setWindowTitle('検査項目マスタ作成ツール')
        self.resize(1500, 860)
        self.setStyleSheet(STYLE)
        self.drawing: LoadedDrawing | None = None
        self.candidates: list[InspectionCandidate] = []
        self._updating_table = False
        self.session = SessionStore(session_dir or (Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / 'inspection-master' / 'autosave'))
        self._identity = None
        self._dirty = False
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(600)
        self.save_timer.timeout.connect(self._autosave)
        self._build_ui()

    def _build_ui(self):
        toolbar = QToolBar('メイン', self)
        self.addToolBar(toolbar)
        for title, callback, shortcut in [
            ('DXFを開く', self.open_dxf, QKeySequence.StandardKey.Open),
            ('検査マスタをCSV出力', self.export_csv, None),
        ]:
            action = QAction(title, self)
            if shortcut: action.setShortcut(shortcut)
            action.triggered.connect(callback)
            toolbar.addAction(action)
        self.view = DrawingView()
        self.view.source_selected.connect(self._select_by_handle)
        side = QWidget()
        layout = QVBoxLayout(side)
        self.summary = QLabel('DXFを開いてください')
        self.summary.setObjectName('summary')
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.tabs = QTabWidget()
        self.tables = {}
        self.up = QPushButton('↑ 上へ')
        self.down = QPushButton('↓ 下へ')
        self.up.clicked.connect(lambda: self._move_selected(-1))
        self.down.clicked.connect(lambda: self._move_selected(1))
        for accepted in (True, False):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            hint = QLabel('採用した項目だけを測定順に並べます。チェックを外すと候補へ戻ります。' if accepted else '採用にチェックすると検査マスタの末尾に追加されます。')
            hint.setWordWrap(True)
            page_layout.addWidget(hint)
            table = QTableWidget(0, len(self.COLUMNS))
            table.setHorizontalHeaderLabels(self.COLUMNS)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            table.setAlternatingRowColors(True)
            table.setShowGrid(False)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setDefaultSectionSize(36)
            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
            table.setColumnHidden(1, not accepted)
            table.setColumnHidden(6, True)
            table.itemSelectionChanged.connect(lambda t=table: self._table_selection_changed(t))
            table.itemChanged.connect(lambda item, t=table: self._table_item_changed(t, item))
            self.tables[accepted] = table
            page_layout.addWidget(table)
            if accepted:
                buttons = QHBoxLayout()
                buttons.addWidget(self.up); buttons.addWidget(self.down); buttons.addStretch()
                page_layout.addLayout(buttons)
            self.tabs.addTab(page, '検査マスタ' if accepted else '候補一覧')
        self.tabs.currentChanged.connect(self._tab_changed)
        layout.addWidget(self.tabs)
        splitter = QSplitter()
        splitter.addWidget(self.view); splitter.addWidget(side)
        splitter.setSizes([740, 760])
        self.setCentralWidget(splitter)
        self.statusBar().showMessage('測定器・備考はダブルクリックで編集できます')
        self.save_status = QLabel('自動保存：図面未読込')
        self.statusBar().addPermanentWidget(self.save_status)
        self.inspector = EntityInspector()
        self.debug_dock = QDockWidget('エンティティ確認（開発者用）', self)
        self.debug_dock.setWidget(self.inspector)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.debug_dock)
        self.debug_dock.hide()
        options = self.menuBar().addMenu('表示')
        options.addAction(self.debug_dock.toggleViewAction())
        self.inspector.selected.connect(self._inspect_handle)
        self.inspector.filter_changed.connect(self._filter_entities)
        self.debug_dock.visibilityChanged.connect(self._debug_visibility)
        self._update_buttons()

    @property
    def table(self):
        return self.tables[self.tabs.currentIndex() == 0]

    def open_dxf(self):
        path, _ = QFileDialog.getOpenFileName(self, 'DXFを開く', '', 'DXF (*.dxf)')
        if path: self.load_path(path)

    def load_path(self, path):
        self._commit_editor()
        if not self._autosave(): return
        try:
            identity = self.session.identity(path)
            drawing = load_drawing(path)
            candidates, restored = self.session.restore(identity, drawing.candidates)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            QMessageBox.warning(self, '読込・復元エラー', str(exc))
            return
        self.drawing = drawing
        self._identity = identity
        self.candidates = candidates
        self.view.load_entities(drawing.modelspace)
        self.inspector.load(drawing, self.view._item_map)
        self._refresh_table()
        self.tabs.setCurrentIndex(0 if any(c.accepted for c in self.candidates) else 1)
        self._tab_changed()
        self._dirty = True
        if self._autosave():
            self.save_status.setText('前回の作業を復元しました' if restored else '自動保存済み')

    def restore_last(self):
        try:
            path = self.session.last_path()
            if path and Path(path).is_file(): self.load_path(path)
            elif path: self.save_status.setText('前回のDXFが見つかりません。DXFを開いてください')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.save_status.setText('前回の作業を復元できません')
            QMessageBox.warning(self, '復元エラー', str(exc))

    def _commit_editor(self):
        widget = QApplication.focusWidget()
        if widget is not None and widget is not self:
            widget.clearFocus()

    def _schedule_save(self):
        if self._identity is None: return
        self._dirty = True
        self.save_status.setText('自動保存待ち…')
        self.save_timer.start()

    def _autosave(self):
        self.save_timer.stop()
        if not self._dirty or self._identity is None: return True
        try:
            self.session.save(self._identity, self.candidates)
        except (OSError, ValueError, TypeError) as exc:
            self.save_status.setText('自動保存失敗：変更は未保存です')
            self.save_status.setToolTip(str(exc))
            return False
        self._dirty = False
        self.save_status.setText('自動保存済み')
        self.save_status.setToolTip('')
        return True

    def closeEvent(self, event):
        self._commit_editor()
        if self._autosave(): event.accept()
        else:
            QMessageBox.warning(self, '保存できません', '自動保存に失敗しました。保存先の空き容量・権限を確認してください。変更を保持するため画面を開いたままにします。')
            event.ignore()

    def _filter_entities(self, handles):
        if not self.debug_dock.isVisible(): handles = None
        for handle, items in self.view._item_map.items():
            for item in items: item.setVisible(handles is None or handle in handles)

    def _debug_visibility(self, visible):
        if visible: self.inspector.refresh()
        else: self._filter_entities(None)

    def _inspect_handle(self, handle):
        self.view.highlight(handle)
        items = self.view._item_map.get(handle, [])
        if items:
            self.view.centerOn(items[0])
            self.statusBar().showMessage(f'エンティティ {handle} を強調表示', 5000)
        else:
            self.statusBar().showMessage(f'{handle}：このビューアでは描画未対応です。属性を確認してください', 8000)

    def _candidate_at(self, table, row):
        item = table.item(row, 0)
        if item is None: return None
        cid = item.data(Qt.ItemDataRole.UserRole)
        return next((c for c in self.candidates if c.id == cid), None)

    def _refresh_table(self, selected_id=None):
        normalize_orders(self.candidates)
        self._updating_table = True
        for accepted, table in self.tables.items():
            previous = self._candidate_at(table, table.currentRow())
            keep = selected_id or (previous.id if previous else None)
            rows = [c for c in self.candidates if c.accepted == accepted]
            table.blockSignals(True)
            table.clearContents(); table.setRowCount(len(rows))
            table.setCurrentCell(-1, -1)
            for row, c in enumerate(rows):
                check = QTableWidgetItem()
                check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
                check.setCheckState(Qt.CheckState.Checked if c.accepted else Qt.CheckState.Unchecked)
                check.setData(Qt.ItemDataRole.UserRole, c.id)
                table.setItem(row, 0, check)
                values = [c.order, c.display_text, c.category, c.instrument, c.notes, f'{c.source_type}:{c.source_handle}']
                for col, value in enumerate(values, 1):
                    item = QTableWidgetItem('' if value is None else str(value))
                    item.setData(Qt.ItemDataRole.UserRole, c.id)
                    item.setToolTip(f'{c.display_text}\nレイヤ: {c.layer}\n元要素: {c.source_type}:{c.source_handle}')
                    if col not in (4, 5): item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    table.setItem(row, col, item)
                if c.id == keep: table.selectRow(row)
            table.blockSignals(False)
            self.tabs.setTabText(0 if accepted else 1, f'{"検査マスタ" if accepted else "候補一覧"}（{len(rows)}）')
        self._updating_table = False
        if self.drawing:
            n = sum(c.accepted for c in self.candidates)
            self.summary.setText(f'{self.drawing.path.name}\n採用 {n}件 ／ 未採用 {len(self.candidates)-n}件')
        self._tab_changed()

    def _table_selection_changed(self, table):
        if self._updating_table or table is not self.table: return
        c = self._candidate_at(table, table.currentRow())
        self.view.highlight(c.source_handle if c else None)
        self._update_buttons()

    def _tab_changed(self, *_):
        self._table_selection_changed(self.table)

    def _table_item_changed(self, table, item):
        if self._updating_table: return
        c = self._candidate_at(table, item.row())
        if not c: return
        if item.column() == 0:
            c.accepted = item.checkState() == Qt.CheckState.Checked
            # Append newly adopted items after the current master; stable IDs preserve edits.
            self.candidates.remove(c); self.candidates.append(c)
            normalize_orders(self.candidates)
            # Rebuild only after Qt finishes dispatching the checkbox event.
            QTimer.singleShot(0, self._refresh_table)
        elif item.column() == 4: c.instrument = item.text()
        elif item.column() == 5: c.notes = item.text()
        self._schedule_save()

    def _select_by_handle(self, handle):
        c = next((c for c in self.candidates if c.source_handle == handle), None)
        if c is None: return
        self.tabs.setCurrentIndex(0 if c.accepted else 1)
        for row in range(self.table.rowCount()):
            if self._candidate_at(self.table, row).id == c.id:
                self.table.selectRow(row)
                self.table.scrollToItem(self.table.item(row, 2)); return

    def _update_buttons(self):
        row = self.table.currentRow()
        master = self.tabs.currentIndex() == 0
        self.up.setEnabled(master and row > 0)
        self.down.setEnabled(master and 0 <= row < self.table.rowCount()-1)

    def _move_selected(self, delta):
        if self.tabs.currentIndex() != 0: return
        rows = [c for c in self.candidates if c.accepted]
        row = self.table.currentRow(); target = row + delta
        if not (0 <= row < len(rows) and 0 <= target < len(rows)): return
        selected = rows[row].id
        a = self.candidates.index(rows[row]); b = self.candidates.index(rows[target])
        self.candidates[a], self.candidates[b] = self.candidates[b], self.candidates[a]
        self._refresh_table(selected)
        self._schedule_save()

    def export_csv(self):
        if not any(c.accepted for c in self.candidates):
            QMessageBox.information(self, 'CSV出力', '採用した検査項目がありません'); return
        path, _ = QFileDialog.getSaveFileName(self, '検査マスタをCSV出力', 'inspection_master.csv', 'CSV (*.csv)')
        if path:
            try: save_csv(path, self.candidates)
            except OSError as exc: QMessageBox.critical(self, '保存エラー', str(exc)); return
            self.statusBar().showMessage('採用した検査項目だけを測定順に出力しました', 5000)
