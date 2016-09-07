import os
import shutil
import tempfile
from datetime import datetime
import unicodedata

import cv2
import numpy as np

from PyQt4.QtCore import Qt, QTimer, QSize
from PyQt4.QtGui import QLabel, QPushButton, QImage, QPixmap, QSizePolicy, QLineEdit

from Orange.data import Table, Domain, StringVariable
from Orange.widgets import gui, widget, settings


class OWNWebcamCapture(widget.OWWidget):
    name = "Webcam Capture"
    description = "Capture a still image using the first detected webcam."
    icon = "icons/WebcamCapture.svg"

    OUTPUT = 'Selfie'
    outputs = [(OUTPUT, Table)]

    want_main_area = False

    avatar_filter = settings.Setting(False)
    full_name = ''

    DEFAULT_NAME = 'One Happy Orange'

    class Error(widget.OWWidget.Error):
        no_webcam = widget.Msg("Couldn't acquire webcam")

    def __init__(self):
        super().__init__()
        self.cap = None
        self.snapshot_flash = 0
        self.IMAGE_DIR = tempfile.mkdtemp(prefix='Orange-WebcamCapture-')

        self.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum))
        box = self.controlArea
        image = self.imageLabel = QLabel(
            margin=0,
            sizePolicy=QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding))
        box.layout().addWidget(image, 100)

        self.name_edit = line_edit = gui.lineEdit(
            box, self, 'full_name', 'Name:', orientation=Qt.Horizontal)
        line_edit.setPlaceholderText(self.DEFAULT_NAME)

        hbox = gui.hBox(box)
        gui.checkBox(hbox, self, 'avatar_filter', 'Avatar filter')
        button = self.capture_button = QPushButton('Capture', self,
                                                   clicked=self.capture_image)
        hbox.layout().addWidget(button, 1000)
        box.layout().addWidget(hbox)

        timer = QTimer(self, interval=40)
        timer.timeout.connect(self.update_webcam_image)
        timer.start()

    def sizeHint(self):
        return QSize(640, 550)

    @staticmethod
    def bgr2rgb(frame):
        return frame[:, :, ::-1].copy()

    def update_webcam_image(self):
        if not self.isVisible():
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            return
        if self.cap is None:
            self.cap = cv2.VideoCapture(0)
        cap = self.cap
        self.capture_button.setDisabled(not cap.isOpened())
        success, frame = cap.read()
        if not cap.isOpened() or not success:
            self.Error.no_webcam()
            return
        else:
            self.Error.no_webcam.clear()
        if self.snapshot_flash > 0:
            np.clip(frame.astype(np.int16) + self.snapshot_flash, 0, 255, out=frame)
            self.snapshot_flash -= 15
        image = QImage(frame if self.avatar_filter else self.bgr2rgb(frame),
                       frame.shape[1], frame.shape[0], QImage.Format_RGB888)
        pix = QPixmap.fromImage(image).scaled(self.imageLabel.size(),
                                             Qt.KeepAspectRatio | Qt.SmoothTransformation)
        self.imageLabel.setPixmap(pix)

    def capture_image(self):
        cap = self.cap
        for i in range(3):  # Need some warmup time; use the last frame
            success, frame = cap.read()
            if success:
                self.Error.no_webcam.clear()
            else:
                self.Error.no_webcam()
                return

        def normalize(name):
            return ''.join(ch for ch in unicodedata.normalize('NFD', name.replace(' ', '_'))
                           if unicodedata.category(ch) in 'LuLlPcPd')

        full_name, self.full_name = self.full_name or self.DEFAULT_NAME, ''
        path = os.path.join(
            self.IMAGE_DIR, '{name}_{ts}.png'.format(
                name=normalize(full_name),
                ts=datetime.now().strftime('%Y%m%d%H%M%S')))
        cv2.imwrite(path,
                    # imwrite expects original bgr image, so this is reversed
                    self.bgr2rgb(frame) if self.avatar_filter else frame)

        image_var = StringVariable('image')
        image_var.attributes['type'] = 'image'
        table = Table.from_numpy(Domain([], metas=[StringVariable('name'), image_var]),
                                 np.empty((1, 0)), metas=np.array([[full_name, path]]))
        self.send(self.OUTPUT, table)
        self.snapshot_flash = 80

    def __del__(self):
        shutil.rmtree(self.IMAGE_DIR, ignore_errors=True)


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    a = QApplication([])
    ow = OWNWebcamCapture()
    ow.show()
    a.exec()
