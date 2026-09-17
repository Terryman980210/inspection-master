from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser(description="2D DXF 検査項目マスタ作成ツール")
    parser.add_argument("dxf", nargs="?", help="起動時に開くDXF")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Inspection Master")
    window = MainWindow()
    window.show()
    if args.dxf:
        window.load_path(args.dxf)
    else:
        window.restore_last()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

