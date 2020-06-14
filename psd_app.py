from PyQt5 import QtCore
from PyQt5.QtWidgets import QCheckBox, QRadioButton, QTableWidgetItem, QHeaderView, QAbstractItemView, QInputDialog
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTransform, QFont, QBrush, QColor, QIcon
from pyqtgraph.Qt import QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt5 import uic, QtWidgets
import qdarkstyle
import sys

class MyMainWindow(QMainWindow):
    def __init__(self, parent = None):
        super(MyMainWindow, self).__init__(parent)
        #pyqtgraph preference setting
        #load GUI ui file made by qt designer
        uic.loadUi('/Users/cqiu/app/PSD_controller/psd_gui.ui',self)
        # print(self.widget)
        self.pushButton_start.clicked.connect(self.start)
        self.pushButton_stop.clicked.connect(self.stop)
        self.pushButton_reset_exchange.clicked.connect(self.reset_exchange)
        self.pushButton_fill.clicked.connect(self.fill)
        self.pushButton_dispense.clicked.connect(self.dispense)
        self.pushButton_update.clicked.connect(self.update_basic_settings)
        self.pushButton_empty_all.clicked.connect(self.update_mode_empty_all)
        self.pushButton_refill_all.clicked.connect(self.update_mode_refill_all)
        self.pushButton_stop_all.clicked.connect(self.stop_all_motion)
        self.radioButton_1.clicked.connect(self.update_mode_1)
        self.radioButton_3.clicked.connect(self.update_mode_3)
        self.doubleSpinBox.valueChanged.connect(self.update_speed)
        self.update_speed()
        self.update_basic_settings()

        # self.initUI()
        self.timer_update = QTimer(self)
        self.timer_update.timeout.connect(self.update_volume)
        self.timer_update.timeout.connect(self.update_volume_waste_reservoir)
        self.timer_update.timeout.connect(self.widget.update)

        self.timer_update_normal_mode = QTimer(self)
        self.timer_update_normal_mode.timeout.connect(self.update_volume_normal_mode)
        self.timer_update_normal_mode.timeout.connect(self.update_volume_waste_reservoir_normal_mode)
        self.timer_update_normal_mode.timeout.connect(self.widget.update)

        self.timer_update_empty_all_mode = QTimer(self)
        self.timer_update_empty_all_mode.timeout.connect(self.update_volume_empty_all_mode)
        self.timer_update_empty_all_mode.timeout.connect(self.widget.update)
        # self.timer_update.start(1)

        self.timer_update_fill_all_mode = QTimer(self)
        self.timer_update_fill_all_mode.timeout.connect(self.update_volume_fill_all_mode)
        self.timer_update_fill_all_mode.timeout.connect(self.widget.update)

        self.timers = [self.timer_update_fill_all_mode,self.timer_update,self.timer_update_empty_all_mode,self.timer_update_normal_mode]

    def stop_all_motion(self):
        for each in self.timers:
            try:
                each.stop()
            except:
                pass

    def update_mode_1(self):
        self.widget.operation_mode = 'auto_refilling'

    def update_mode_3(self):
        self.widget.operation_mode = 'normal_mode'
        
    def update_mode_empty_all(self):
        self.widget.operation_mode = 'empty_all_mode'
        try:
            self.timer_update_normal_mode.stop()
        except:
            pass
        try:
            self.timer_update.stop()
        except:
            pass
        try:
            self.timer_update_fill_all_mode.stop()
        except:
            pass
        self.timer_update_empty_all_mode.start(100)

    def update_mode_refill_all(self):
        self.widget.operation_mode = 'fill_all_mode'
        try:
            self.timer_update_normal_mode.stop()
        except:
            pass
        try:
            self.timer_update.stop()
        except:
            pass
        try:
            self.timer_update_empty_all_mode.stop()
        except:
            pass
        self.timer_update_fill_all_mode.start(100)

    def update_basic_settings(self):
        self.widget.syringe_size = float(self.lineEdit_syringe_size.text())
        self.widget.waste_volumn_total = float(self.lineEdit_waste_bottle_size.text())
        self.widget.resevoir_volumn_total = float(self.lineEdit_resevoir_bottle_size.text())
        self.widget.speed_by_default = self.doubleSpinBox_default_speed.value()
        self.widget.update()

    def fill(self):
        # self.widget.operation_mode = 'normal_mode'
        self.radioButton_3.setChecked(True)
        self.update_mode_3()
        self.widget.actived_syringe_normal_mode=int(self.comboBox_syringe_number.currentText())
        self.widget.actived_syringe_motion_normal_mode = 'fill'
        self.widget.connect_valve_port[self.widget.actived_syringe_normal_mode] = self.comboBox_valve_port.currentText()
        self.widget.speed_normal_mode = self.doubleSpinBox_speed_normal_mode.value()
        self.widget.volume_normal_mode = self.widget.syringe_size*self.doubleSpinBox_stroke_factor.value()
        try:
            self.timer_update.stop()
        except:
            pass
        try:
            self.timer_update_empty_all_mode.stop()
        except:
            pass
        try:
            self.timer_update_fill_all_mode.stop()
        except:
            pass
        self.timer_update_normal_mode.start(100)

    def dispense(self):
        self.radioButton_3.setChecked(True)
        self.update_mode_3()
        self.widget.actived_syringe_normal_mode=int(self.comboBox_syringe_number.currentText())
        self.widget.actived_syringe_motion_normal_mode = 'dispense'
        self.widget.connect_valve_port[self.widget.actived_syringe_normal_mode] = self.comboBox_valve_port.currentText()
        self.widget.speed_normal_mode = self.doubleSpinBox_speed_normal_mode.value()
        self.widget.volume_normal_mode = self.widget.syringe_size*self.doubleSpinBox_stroke_factor.value()
        self.timer_update_normal_mode.start(100)

    def reset_exchange(self):
        self.widget.waste_volumn = 0
        self.widget.resevoir_volumn = self.widget.resevoir_volumn_total
        self.widget.update()

    def start(self):
        try:
            self.timer_update_normal_mode.stop()
        except:
            pass
        try:
            self.timer_update_empty_all_mode.stop()
        except:
            pass
        try:
            self.timer_update_fill_all_mode.stop()
        except:
            pass
        # self.widget.operation_mode = 'auto_refilling'
        self.widget.connect_valve_port = {1:'left',2:'right',3:'left',4:'up'}
        self.widget.filling = True
        self.widget.filling2 = False
        self.widget.filling3 = True
        self.widget.filling4 = False
        self.radioButton_1.setChecked(True)
        self.update_mode_1()
        self.timer_update.start(100)

    def stop(self):
        self.timer_update.stop()

    def update_volume_waste_reservoir(self):
        waste_volumn = self.widget.waste_volumn + self.widget.speed/10
        resevoir_volumn = self.widget.resevoir_volumn - self.widget.speed/10
        if waste_volumn > 250:
            self.timer_update.stop()
        else:
            self.widget.waste_volumn = waste_volumn
            self.widget.resevoir_volumn = resevoir_volumn

    def update_volume_waste_reservoir_normal_mode(self):
        if self.widget.actived_syringe_motion_normal_mode=='fill':
            resevoir_volumn = self.widget.resevoir_volumn - self.widget.speed_normal_mode/10
            if resevoir_volumn<=0:
                self.widget.resevoir_volumn = 0
            else:
                self.widget.resevoir_volumn = resevoir_volumn
        elif self.widget.actived_syringe_motion_normal_mode=='dispense':
            waste_volumn = self.widget.waste_volumn + self.widget.speed_normal_mode/10
            if waste_volumn>self.widget.waste_volumn_total:
                self.widget.waste_volumn = self.widget.waste_volumn_total
            else:
                self.widget.waste_volumn = waste_volumn

    def update_volume_normal_mode(self):
        self.widget.volume_normal_mode = self.widget.volume_normal_mode - self.widget.speed_normal_mode/10
        if self.widget.actived_syringe_normal_mode==1:
            self.widget.volume = self.widget.volume + self.widget.speed_normal_mode/10*[-1,1][int(self.widget.actived_syringe_motion_normal_mode=='fill')]
            if self.widget.volume>12.5:
                self.widget.volume = 12.5
                self.timer_update_normal_mode.stop()
            if self.widget.volume<0:
                self.widget.volume = 0
                self.timer_update_normal_mode.stop()
            if self.widget.volume_normal_mode<=0:
                self.widget.volume_normal_mode = 0
                self.timer_update_normal_mode.stop()
        elif self.widget.actived_syringe_normal_mode==2:
            self.widget.volume2 = self.widget.volume2 + self.widget.speed_normal_mode/10*[-1,1][int(self.widget.actived_syringe_motion_normal_mode=='fill')]
            if self.widget.volume2>12.5:
                self.widget.volume2 = 12.5
                self.timer_update_normal_mode.stop()
            if self.widget.volume2<0:
                self.widget.volume2 = 0
                self.timer_update_normal_mode.stop()
            if self.widget.volume_normal_mode<=0:
                self.widget.volume_normal_mode = 0
                self.timer_update_normal_mode.stop()
        elif self.widget.actived_syringe_normal_mode==3:
            self.widget.volume3 = self.widget.volume3 + self.widget.speed_normal_mode/10*[-1,1][int(self.widget.actived_syringe_motion_normal_mode=='fill')]
            if self.widget.volume3>12.5:
                self.widget.volume3 = 12.5
                self.timer_update_normal_mode.stop()
            if self.widget.volume3<0:
                self.widget.volume3 = 0
                self.timer_update_normal_mode.stop()
            if self.widget.volume_normal_mode<=0:
                self.widget.volume_normal_mode = 0
                self.timer_update_normal_mode.stop()
        elif self.widget.actived_syringe_normal_mode==4:
            self.widget.volume4 = self.widget.volume4 + self.widget.speed_normal_mode/10*[-1,1][int(self.widget.actived_syringe_motion_normal_mode=='fill')]
            if self.widget.volume4>12.5:
                self.widget.volume4 = 12.5
                self.timer_update_normal_mode.stop()
            if self.widget.volume4<0:
                self.widget.volume4 = 0
                self.timer_update_normal_mode.stop()
            if self.widget.volume_normal_mode<=0:
                self.widget.volume_normal_mode = 0
                self.timer_update_normal_mode.stop()

    def update_volume_empty_all_mode(self):
        waste_volumn = self.widget.waste_volumn + self.widget.speed_by_default/10*4
        if waste_volumn>self.widget.waste_volumn_total:
            self.timer_update_empty_all_mode.stop()
            return
        else:
            self.widget.waste_volumn = waste_volumn
        self.widget.volume = self.widget.volume - self.widget.speed_by_default/10
        if self.widget.volume<0:
            self.widget.volume = 0
        self.widget.volume2 = self.widget.volume2 - self.widget.speed_by_default/10
        if self.widget.volume2<0:
            self.widget.volume2 = 0
        self.widget.volume3 = self.widget.volume3 - self.widget.speed_by_default/10
        if self.widget.volume3<0:
            self.widget.volume3 = 0
        self.widget.volume4 = self.widget.volume4 - self.widget.speed_by_default/10
        if self.widget.volume4<0:
            self.widget.volume4 = 0
        if (self.widget.volume+self.widget.volume2+self.widget.volume3+self.widget.volume4)==0:
           self.timer_update_empty_all_mode.stop()

    def update_volume_fill_all_mode(self):
        resevoir_volumn = self.widget.resevoir_volumn - self.widget.speed_by_default/10*4
        if resevoir_volumn<0:
            self.timer_update_fill_all_mode.stop()
            return
        else:
            self.widget.resevoir_volumn = resevoir_volumn
        self.widget.volume = self.widget.volume + self.widget.speed_by_default/10
        if self.widget.volume>self.widget.syringe_size:
            self.widget.volume = self.widget.syringe_size
        self.widget.volume2 = self.widget.volume2 + self.widget.speed_by_default/10
        if self.widget.volume2>self.widget.syringe_size:
            self.widget.volume2 = self.widget.syringe_size
        self.widget.volume3 = self.widget.volume3 + self.widget.speed_by_default/10
        if self.widget.volume3>self.widget.syringe_size:
            self.widget.volume3 = self.widget.syringe_size
        self.widget.volume4 = self.widget.volume4 + self.widget.speed_by_default/10
        if self.widget.volume4>self.widget.syringe_size:
            self.widget.volume4 = self.widget.syringe_size

        if (self.widget.volume+self.widget.volume2+self.widget.volume3+self.widget.volume4)==self.widget.syringe_size*4:
           self.timer_update_fill_all_mode.stop()

    def update_volume(self):
        vol_tags = ['volume','volume2','volume3','volume4']
        fill_tags = ['filling','filling2','filling3','filling4']
        # self.counts = self.counts + 1
        # if self.counts%10==0:
        for vol_tag, fill_tag in zip(vol_tags,fill_tags):
            self._update_volume(vol_tag,fill_tag)
        self.lcdNumber_exchange_volume.display(self.widget.waste_volumn)

    def _update_volume(self,vol_tag='volume',fill_tag='filling'):
        if (12.5-getattr(self.widget,vol_tag))<=0:
            setattr(self.widget,vol_tag,12.5)
            setattr(self.widget,fill_tag, False)
        elif getattr(self.widget,vol_tag)<=0:
            setattr(self.widget,vol_tag, 0)
            setattr(self.widget,fill_tag, True)
        else:
            pass
        if getattr(self.widget,fill_tag):
            setattr(self.widget,vol_tag, getattr(self.widget,vol_tag)+self.widget.speed/10)
        else:
            setattr(self.widget,vol_tag, getattr(self.widget,vol_tag)-self.widget.speed/10)

    def update_speed(self):
        self.widget.speed = float(self.doubleSpinBox.value())

if __name__ == "__main__":
    QApplication.setStyle("windows")
    app = QApplication(sys.argv)
    #get dpi info: dots per inch
    screen = app.screens()[0]
    dpi = screen.physicalDotsPerInch()
    myWin = MyMainWindow()
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    myWin.show()
    sys.exit(app.exec_())