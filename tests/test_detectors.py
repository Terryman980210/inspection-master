import ezdxf

from inspection_master.detectors import DetectorRegistry, TextDimensionDetector


def test_text_detector_recognizes_common_inspection_annotations():
    doc = ezdxf.new()
    msp = doc.modelspace()
    for index, text in enumerate(["φ12", "R5", "C0.5", "M6×1", "25±0.02", "材質 A5052"]):
        msp.add_text(text, dxfattribs={"insert": (index * 10, 0)})
    found = TextDimensionDetector().detect(msp)
    assert [item.category for item in found] == [
        "diameter",
        "radius",
        "chamfer",
        "thread",
        "toleranced_dimension",
    ]


def test_registry_assigns_stable_candidate_ids_and_order():
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_text("R2", dxfattribs={"insert": (0, 20)})
    msp.add_text("φ8", dxfattribs={"insert": (0, 10)})
    found = DetectorRegistry().detect(msp)
    assert [item.id for item in found] == ["C0001", "C0002"]
    assert [item.order for item in found] == [1, 2]


def test_mtext_can_produce_multiple_candidates():
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_mtext("2-φ8\nC0.5", dxfattribs={"insert": (0, 0)})
    found = TextDimensionDetector().detect(msp)
    assert [(item.category, item.display_text) for item in found] == [
        ("diameter", "2-φ8"),
        ("chamfer", "C0.5"),
    ]


def test_numeric_text_candidates_require_review_and_exclude_part_numbers():
    from inspection_master.detectors import NumericTextDetector
    doc = ezdxf.new()
    msp = doc.modelspace()
    for text in ["100", "50", "25.5", "LRK-2550", "A5052", "1:2", "φ10"]:
        msp.add_text(text)
    msp.add_mtext("70\\P35")
    found = NumericTextDetector().detect(msp)
    assert [c.value for c in found] == [100, 50, 25.5, 70, 35]
    assert all(not c.accepted for c in found)
    assert all(c.source_handle in doc.entitydb for c in found)
