import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import csv
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit
from inspection_master.main_window import MainWindow
from inspection_master.models import InspectionCandidate
from inspection_master.storage import save_csv, save_json, load_json


def test_adoption_order_edit_and_export(tmp_path):
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.candidates = [InspectionCandidate(id=f'C{i}', source_type='TEXT', category='test',
        display_text=str(i), source_handle=str(i), accepted=False) for i in range(4)]
    w._refresh_table(); w.tabs.setCurrentIndex(1); w.show(); app.processEvents()
    pending = w.tables[False]; master = w.tables[True]
    pending.item(0,5).setText('確認済みの備考')
    pending.item(0,0).setCheckState(Qt.CheckState.Checked); app.processEvents()
    assert (pending.rowCount(), master.rowCount()) == (3,1)
    assert master.item(0,5).text() == '確認済みの備考'
    pending.item(0,0).setCheckState(Qt.CheckState.Checked); app.processEvents()
    pending.item(0,0).setCheckState(Qt.CheckState.Checked); app.processEvents()
    w.tabs.setCurrentIndex(0); master.selectRow(2); w._move_selected(-1)
    assert [c.id for c in w.candidates if c.accepted] == ['C0','C2','C1']
    assert [c.order for c in w.candidates if c.accepted] == [1,2,3]
    master.item(0,0).setCheckState(Qt.CheckState.Unchecked); app.processEvents()
    assert [c.order for c in w.candidates if c.accepted] == [1,2]
    assert all(c.order is None for c in w.candidates if not c.accepted)
    w._select_by_handle('0')
    assert w.tabs.currentIndex() == 1
    assert pending.item(pending.currentRow(),5).text() == '確認済みの備考'
    pending.item(pending.currentRow(),0).setCheckState(Qt.CheckState.Checked); app.processEvents()
    assert [c.id for c in w.candidates if c.accepted] == ['C2','C1','C0']
    w.tabs.setCurrentIndex(0); master.setCurrentCell(2,5)
    master.editItem(master.item(2,5)); app.processEvents()
    editor = master.findChild(QLineEdit)
    assert editor is not None
    editor.setText('編集後の備考')
    # Commit the delegate editor using the same signal as normal editing.
    master.itemDelegate().commitData.emit(editor)
    master.itemDelegate().closeEditor.emit(editor)
    app.processEvents()
    assert next(c for c in w.candidates if c.id=='C0').notes == '編集後の備考'
    save_json(tmp_path/'work.json','demo.dxf',w.candidates)
    restored = load_json(tmp_path/'work.json')[1]
    assert len(restored)==4 and sum(c.accepted for c in restored)==3
    save_csv(tmp_path/'master.csv',w.candidates)
    with (tmp_path/'master.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    assert [r['id'] for r in rows]==['C2','C1','C0']
    assert [r['order'] for r in rows]==['1','2','3']
    assert rows[-1]['notes']=='編集後の備考'
    w.close()
