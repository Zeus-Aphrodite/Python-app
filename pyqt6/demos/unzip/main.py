import os
import random
import sys
import types

from MainWindow import Ui_MainWindow
from PyQt6.QtCore import (
    Qt,
    QThreadPool,
    QTimer,
)
from PyQt6.QtGui import QPainter, QTransform
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
)
from workers import UnzipWorker

PROGRESS_ON = """
QLabel {
    background-color: rgb(233,30,99);
    border: 2px solid rgb(194,24,91);
    color: rgb(136,14,79);
}
"""

PROGRESS_OFF = """
QLabel {
    color: rgba(0,0,0,0);
}
"""


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAcceptDrops(True)

        self.prev_pos = None

        # Create a threadpool to run our unzip worker in.
        self.threadpool = QThreadPool()

        self.head.raise_()

        def patch_mousePressEvent(self_, e):
            if e.button() == Qt.MouseButton.LeftButton and self.worker is not None:
                # Extract the archive.
                self_.current_rotation = random.randint(-15, +15)
                self_.current_y = 30

                # Redraw the mainwindow
                self.update()

                # Perform the unzip
                self.threadpool.start(self.worker)
                self.worker = None  # Remove the worker so it is not double-triggered.

            elif e.button() == Qt.MouseButton.RightButton:
                pass  # Open a new zip.

        def patch_paintEvent(self, event):
            p = QPainter(self)
            rect = event.rect()

            # Translate
            transform = QTransform()
            transform.translate(rect.width() / 2, rect.height() / 2)
            transform.rotate(self.current_rotation)
            transform.translate(-rect.width() / 2, -rect.height() / 2)
            p.setTransform(transform)

            # Calculate rect to center the pixmap on the QLabel.
            prect = self.pixmap().rect()
            rect.adjust(
                int((rect.width() - prect.width()) / 2),
                int(self.current_y + (rect.height() - prect.height()) / 2),
                int(-(rect.width() - prect.width()) / 2),
                int(self.current_y + -(rect.height() - prect.height()) / 2),
            )
            p.drawPixmap(rect, self.pixmap())

        self.head.mousePressEvent = types.MethodType(patch_mousePressEvent, self.head)
        self.head.paintEvent = types.MethodType(patch_paintEvent, self.head)

        self.timer = QTimer()
        self.timer.timeout.connect(self.timer_triggered)
        self.timer.start(5)

        # Initialize
        self.head.current_rotation = 0
        self.head.current_y = 0
        self.head.locked = True
        self.worker = None

        # Reset bar to complete (empty)
        self.update_progress(1)

        self.show()

    def timer_triggered(self):
        if self.head.current_y > 0:
            self.head.current_y -= 1

        if self.head.current_rotation > 0:
            self.head.current_rotation -= 1

        elif self.head.current_rotation < 0:
            self.head.current_rotation += 1

        self.head.update()

        if self.head.current_y == 0 and self.head.current_rotation == 0:
            self.head.locked = False

    def dragEnterEvent(self, e):
        data = e.mimeData()
        if data.hasUrls():
            # We are passed urls as a list, but only accept one.
            url = data.urls()[0].toLocalFile()
            if os.path.splitext(url)[1].lower() == ".zip":
                e.accept()

    def dropEvent(self, e):
        data = e.mimeData()
        path = data.urls()[0].toLocalFile()

        # Load the zipfile and pass to the worker which will extract.
        self.worker = UnzipWorker(path)
        self.worker.signals.progress.connect(self.update_progress)
        self.worker.signals.finished.connect(self.unzip_finished)
        self.worker.signals.error.connect(self.unzip_error)
        self.update_progress(0)

    def mousePressEvent(self, e):
        self.prev_pos = e.globalPosition()

    def mouseMoveEvent(self, e):
        if self.prev_pos:
            delta = e.globalPosition() - self.prev_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.prev_pos = e.globalPosition()

    def update_progress(self, pc):
        """
        Accepts progress as float in
        :param pc: float 0-1 of completion.
        :return:
        """
        current_n = int(pc * 10)
        for n in range(1, 11):
            getattr(self, "progress_%d" % n).setStyleSheet(
                PROGRESS_ON if n > current_n else PROGRESS_OFF
            )

    def unzip_finished(self):
        pass

    def unzip_error(self, err):
        exctype, value, traceback_str = err

        self.update_progress(1)  # Reset the Pez bar.

        dlg = QMessageBox(self)
        dlg.setText(traceback_str)
        dlg.setIcon(QMessageBox.Icon.Critical)
        dlg.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    app.exec()
