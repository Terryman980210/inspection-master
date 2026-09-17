from pathlib import Path

import ezdxf


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "demo_part.dxf"
    doc = ezdxf.new("R2010", setup=True)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True, dxfattribs={"layer": "PART"})
    msp.add_circle((25, 25), radius=5, dxfattribs={"layer": "PART"})
    msp.add_circle((75, 25), radius=4, dxfattribs={"layer": "PART"})
    msp.add_text("φ10", height=3, dxfattribs={"insert": (20, 35), "layer": "NOTE"})
    msp.add_mtext("2-φ8\nC0.5", dxfattribs={"insert": (70, 38), "char_height": 3, "layer": "NOTE"})
    msp.add_text("材質: A5052", height=3, dxfattribs={"insert": (0, -15), "layer": "NOTE"})
    msp.add_linear_dim(base=(50, -10), p1=(0, 0), p2=(100, 0), angle=0, override={"dimdec": 1}).render()
    msp.add_linear_dim(base=(-10, 25), p1=(0, 0), p2=(0, 50), angle=90, override={"dimdec": 1}).render()
    doc.saveas(output)
    print(output)


if __name__ == "__main__":
    main()
