from PyQt5 import QtCore
from PyQt5.QtWidgets import QCheckBox, QRadioButton, QTableWidgetItem, QHeaderView, QAbstractItemView, QInputDialog
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTransform, QFont, QBrush, QColor, QIcon
from pyqtgraph.Qt import QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt5 import uic, QtWidgets
import sys

class MyMainWindow(QMainWindow):
    def __init__(self, parent = None):
        super(MyMainWindow, self).__init__(parent)
        #pyqtgraph preference setting
        #load GUI ui file made by qt designer
        uic.loadUi('/Users/cqiu/app/PSD_controller/psd_gui.ui',self)
        # print(self.widget)
        self.pushButton_start.clicked.connect(self.widget.start)
        self.pushButton_stop.clicked.connect(self.widget.stop)
        self.doubleSpinBox.valueChanged.connect(self.update_speed)
        self.update_speed()

    def update_speed(self):
        self.widget.speed = float(self.doubleSpinBox.value())

if __name__ == "__main__":
    QApplication.setStyle("windows")
    app = QApplication(sys.argv)
    #get dpi info: dots per inch
    screen = app.screens()[0]
    dpi = screen.physicalDotsPerInch()
    myWin = MyMainWindow()
    # app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    myWin.show()
    sys.exit(app.exec_())