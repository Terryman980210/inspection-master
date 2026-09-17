from inspection_master.models import InspectionCandidate
from inspection_master.storage import load_json, save_csv, save_json


def sample_candidate():
    return InspectionCandidate(
        id="C0001",
        source_type="TEXT",
        category="diameter",
        display_text="φ10",
        value=10.0,
        source_handle="2A",
        position=(10.0, 20.0),
        order=1,
    )


def test_json_roundtrip(tmp_path):
    path = tmp_path / "master.json"
    save_json(path, "part.dxf", [sample_candidate()])
    drawing, candidates = load_json(path)
    assert drawing == "part.dxf"
    assert candidates[0].display_text == "φ10"
    assert candidates[0].position == (10.0, 20.0)


def test_csv_uses_excel_friendly_utf8_bom(tmp_path):
    path = tmp_path / "master.csv"
    save_csv(path, [sample_candidate()])
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert "φ10" in raw.decode("utf-8-sig")

