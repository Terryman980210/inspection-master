from pathlib import Path
import json
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtTest import QTest
from inspection_master.main_window import MainWindow
from inspection_master.session import SessionStore
from inspection_master.dxf_loader import load_drawing

DEMO = Path(__file__).resolve().parents[1] / 'demo_part.dxf'


def test_restart_restores_edits_order_and_open_editor(tmp_path):
    app = QApplication.instance() or QApplication([])
    w = MainWindow(session_dir=tmp_path)
    w.show(); w.load_path(str(DEMO)); app.processEvents()
    first_id = w.candidates[0].id
    w.table.item(0,0).setCheckState(Qt.CheckState.Unchecked); app.processEvents()
    w.table.selectRow(1); w._move_selected(-1)
    expected_ids = [c.id for c in w.candidates]
    edited_id = w._candidate_at(w.table,0).id
    w.table.setCurrentCell(0,5); w.table.editItem(w.table.item(0,5)); app.processEvents()
    editor = w.table.findChild(QLineEdit); assert editor is not None
    editor.setFocus(); QTest.keyClicks(editor, 'restart note'); app.processEvents()
    w.close(); app.processEvents()
    assert not w._dirty
    other = MainWindow(session_dir=tmp_path); other.restore_last()
    assert [c.id for c in other.candidates] == expected_ids
    assert next(c for c in other.candidates if c.id==first_id).accepted is False
    assert next(c for c in other.candidates if c.id==edited_id).notes == 'restart note'
    assert all(c.order is None for c in other.candidates if not c.accepted)
    assert other.drawing.path.resolve() == DEMO
    other.close()


def test_changed_drawing_and_corrupt_snapshot(tmp_path):
    drawing = tmp_path/'copy.dxf'; drawing.write_bytes(DEMO.read_bytes())
    store=SessionStore(tmp_path/'state'); identity=store.identity(drawing)
    candidates=load_drawing(drawing).candidates; candidates[0].notes='old'
    store.save(identity,candidates)
    drawing.write_bytes(drawing.read_bytes()+b'\n')
    fresh=load_drawing(DEMO).candidates
    result, restored=store.restore(store.identity(drawing),fresh)
    assert not restored and result[0].notes==''
    snapshot=store.root/(identity[2]+'.json'); snapshot.write_text('{bad')
    with pytest.raises(ValueError): store.restore(identity,fresh)
    assert snapshot.read_text()=='{bad'


def test_inspector_filters_raw_non_candidates_and_resets(tmp_path):
    app=QApplication.instance() or QApplication([])
    w=MainWindow(session_dir=tmp_path); w.load_path(str(DEMO)); w.show()
    assert not w.debug_dock.isVisible()
    w.debug_dock.show(); app.processEvents()
    panel=w.inspector
    panel.types.setCurrentIndex(panel.types.findData('CIRCLE'))
    assert panel.table.rowCount()==2
    panel.isolate.setChecked(True); app.processEvents()
    circles={e.dxf.handle for e in w.drawing.modelspace.query('CIRCLE')}
    for handle,items in w.view._item_map.items():
        assert all(i.isVisible()==(handle in circles) for i in items)
    panel.table.selectRow(0); app.processEvents()
    assert w.view._selected_handle in circles
    assert 'radius' in panel.details.toPlainText()
    w.debug_dock.hide(); app.processEvents()
    assert all(i.isVisible() for items in w.view._item_map.values() for i in items)
    w.close()


def test_save_failure_keeps_dirty_state_and_blocks_drawing_switch(tmp_path, monkeypatch):
    app=QApplication.instance() or QApplication([])
    w=MainWindow(session_dir=tmp_path); w.load_path(str(DEMO))
    w.candidates[0].notes='pending'; w._schedule_save()
    def fail(*args): raise OSError('test disk failure')
    with monkeypatch.context() as m:
        m.setattr(w.session,'save',fail)
        assert not w._autosave() and w._dirty
        assert '失敗' in w.save_status.text()
        w.load_path(str(DEMO))
        assert w.candidates[0].notes=='pending'
    assert w._autosave() and not w._dirty
    w.close()
