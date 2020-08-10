from PyQt5 import QtCore
from PyQt5.QtWidgets import QCheckBox, QRadioButton, QTableWidgetItem, QHeaderView, QAbstractItemView, QInputDialog
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QTransform, QFont, QBrush, QColor, QIcon, QImage, QPixmap
from pyqtgraph.Qt import QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt5 import uic, QtWidgets
import qdarkstyle
import sys,os
import cv2
import logging
import time
try:
    from . import locate_path
except:
    import locate_path
script_path = locate_path.module_path_locator()

#redirect the error stream to qt widget
class QTextEditLogger(logging.Handler):
    def __init__(self, textbrowser_widget):
        super().__init__()
        self.textBrowser_error_msg = textbrowser_widget
        # self.widget.setReadOnly(True)

    def emit(self, record):
        error_msg = self.format(record)
        separator = '-' * 80
        notice = \
        """An unhandled exception occurred. Please report the problem\n"""\
        """using the error reporting dialog or via email to <%s>.\n"""%\
        ("crqiu2@gmail.com")
        self.textBrowser_error_msg.clear()
        cursor = self.textBrowser_error_msg.textCursor()
        cursor.insertHtml('''<p><span style="color: red;">{} <br></span>'''.format(" "))
        self.textBrowser_error_msg.setText(notice + '\n' +separator+'\n'+error_msg)

class MyMainWindow(QMainWindow):
    start_exchange = QtCore.pyqtSignal()
    def __init__(self, parent = None):
        super(MyMainWindow, self).__init__(parent)
        #load GUI ui file made by qt designer
        ui_path = os.path.join(script_path,'psd_gui_beta.ui')
        uic.loadUi(ui_path,self)

        self.lineEdit_frame_path.setText(os.path.join(script_path,'images'))

        self.psd_server = 'psd server'

        self.widget_terminal.update_name_space('psd_widget',self.widget_psd)
        self.widget_terminal.update_name_space('main_gui',self)
        self.widget_terminal.update_name_space('psd_server',self.psd_server)

        #set redirection of error message to embeted text browser widget
        logTextBox = QTextEditLogger(self.textBrowser_error_msg)
        # You can format what is printed to text box
        logTextBox.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(logTextBox)
        # You can control the logging level
        logging.getLogger().setLevel(logging.DEBUG)

        self.auto_refilling_elapsed_time = 0
        self.image = None
        self.frame_number = 0
        self.pushButton_catch_frame.clicked.connect(self.catch_frame)

        self.pushButton_start.clicked.connect(self.init_start)
        self.pushButton_stop.clicked.connect(self.stop)
        self.start_exchange.connect(self.start)
        self.pushButton_reset_exchange.clicked.connect(self.reset_exchange)
        self.pushButton_fill.clicked.connect(self.fill)
        self.pushButton_dispense.clicked.connect(self.dispense)
        self.pushButton_fill_init_mode.clicked.connect(self.fill_init_mode)
        self.pushButton_dispense_init_mode.clicked.connect(self.dispense_init_mode)
        self.pushButton_update.clicked.connect(self.update_basic_settings)
        self.pushButton_empty_all.clicked.connect(self.update_mode_empty_all)
        self.pushButton_refill_all.clicked.connect(self.update_mode_refill_all)
        self.pushButton_stop_all.clicked.connect(self.stop_all_motion)
        self.radioButton_exchange_mode.clicked.connect(self.update_to_autorefilling_mode)
        self.radioButton_single_mode.clicked.connect(self.update_to_normal_mode)
        self.doubleSpinBox.valueChanged.connect(self.update_speed)
        self.update_speed()
        self.update_basic_settings()
        self.label_cam.setScaledContents(True)

        self.pushButton_start_webcam.clicked.connect(self.start_webcam)
        self.pushButton_stop_webcam.clicked.connect(self.stop_webcam)

        self.timer_webcam = QTimer(self)
        self.timer_webcam.timeout.connect(self.viewCam)

        #auto_refilling_mode
        self.timer_update = QTimer(self)
        self.timer_update.timeout.connect(self.update_volume)
        self.timer_update.timeout.connect(self.update_volume_waste_reservoir)
        self.timer_update.timeout.connect(self.widget_psd.update)

        #single_mode, operating on one specific syringe
        self.timer_update_normal_mode = QTimer(self)
        self.timer_update_normal_mode.timeout.connect(self.update_volume_normal_mode)
        self.timer_update_normal_mode.timeout.connect(self.update_volume_waste_reservoir_normal_mode)
        self.timer_update_normal_mode.timeout.connect(self.widget_psd.update)

        #action done before auto_refilling, serve purpose to fill the cell first
        self.timer_update_init_mode = QTimer(self)
        self.timer_update_init_mode.timeout.connect(self.update_volume_init_mode)
        self.timer_update_init_mode.timeout.connect(self.widget_psd.update)

        # in this mode, all syringes will be empty
        self.timer_update_empty_all_mode = QTimer(self)
        self.timer_update_empty_all_mode.timeout.connect(self.update_volume_empty_all_mode)
        self.timer_update_empty_all_mode.timeout.connect(self.widget_psd.update)

        # in this mode, all syringes will be filled
        self.timer_update_fill_all_mode = QTimer(self)
        self.timer_update_fill_all_mode.timeout.connect(self.update_volume_fill_all_mode)
        self.timer_update_fill_all_mode.timeout.connect(self.widget_psd.update)

        # in this mode, all syringes will be half-filled (internally actived before auto_refilling mode)
        self.timer_update_fill_half_mode = QTimer(self)
        self.timer_update_fill_half_mode.timeout.connect(self.update_volume_fill_half_mode)
        self.timer_update_fill_half_mode.timeout.connect(self.widget_psd.update)

        self.timers = [self.timer_update_fill_half_mode, self.timer_update_fill_all_mode, self.timer_update,self.timer_update_empty_all_mode,self.timer_update_normal_mode, self.timer_update_init_mode]

    #save a snapshot of webcam
    def catch_frame(self):
        if self.timer_webcam.isActive():
            frame_path = os.path.join(self.lineEdit_frame_path.text(),self.lineEdit_frame_name.text())
            cv2.imwrite(frame_path, self.image)
            self.frame_number+=1
            self.lineEdit_frame_name.setText('cam_frame{}.png'.format(self.frame_number))
            self.statusbar.showMessage('Cam Image is saved at {}!'.format(frame_path))
        else:
            pass

    def stop_all_timers(self):
        for timer in self.timers:
            if timer.isActive():
                timer.stop()

    def init_start(self):
        #half fill the associated syringes first
        self.widget_psd.operation_mode = 'pre_auto_refilling'
        self.timer_update_fill_half_mode.start(100)

    def viewCam(self):
        # read image in BGR format
        ret, image = self.cap.read()
        self.image = image
        # convert image to RGB format
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # get image infos
        height, width, channel = image.shape
        step = channel * width
        # create QImage from image
        qImg = QImage(image.data, width, height, step, QImage.Format_RGB888)
        # show image in img_label
        self.label_cam.setPixmap(QPixmap.fromImage(qImg))

    # start/stop webcam
    def start_webcam(self):
        self.cap = cv2.VideoCapture(int(self.lineEdit_camera_index.text()))
        if not self.cap.isOpened():
            logging.getLogger().exception('\nOpenCV: camera failed to properly initialize! \nOpenCV: out device of bound: {}'.format(int(self.lineEdit_camera_index.text())))
            self.tabWidget.setCurrentIndex(2) 
        else:
            self.tabWidget.setCurrentIndex(0) 
            self.timer_webcam.start(20)

    def stop_webcam(self):
        if self.timer_webcam.isActive():
            # stop timer
            self.timer_webcam.stop()
            # release video capture
            self.cap.release()
        else:
            pass

    def stop_all_motion(self):
        for each in self.timers:
            try:
                each.stop()
            except:
                pass

    def update_to_autorefilling_mode(self):
        self.widget_psd.operation_mode = 'auto_refilling'
        self.widget_psd.update()

    def update_to_init_mode(self):
        self.widget_psd.operation_mode = 'init_mode'
        self.widget_psd.update()

    def update_to_normal_mode(self):
        self.widget_psd.operation_mode = 'normal_mode'
        self.widget_psd.update()
        
    def update_mode_empty_all(self):
        self.widget_psd.operation_mode = 'empty_all_mode'
        self.stop_all_timers()
        self.timer_update_empty_all_mode.start(100)

    def update_mode_refill_all(self):
        self.widget_psd.operation_mode = 'fill_all_mode'
        self.stop_all_timers()
        self.timer_update_fill_all_mode.start(100)

    #update the volume of resevoir bottle/waste bottle and syringe size and default speed
    def update_basic_settings(self):
        self.widget_psd.syringe_size = float(self.lineEdit_syringe_size.text())
        self.widget_psd.waste_volumn_total = float(self.lineEdit_waste_bottle_size.text())
        self.widget_psd.resevoir_volumn_total = float(self.lineEdit_resevoir_bottle_size.text())
        self.widget_psd.speed_by_default = self.doubleSpinBox_default_speed.value()
        self.widget_psd.update()

    def fill_init_mode(self):
        self.radioButton_init_mode.setChecked(True)
        self.update_to_init_mode()
        #which one is the syringe to pull electrolyte from cell
        self.widget_psd.actived_pulling_syringe_init_mode = int(self.comboBox_pulling_syringe_init_mode.currentText())
        #which one is the syringe to push electrolyte to cell
        self.widget_psd.actived_pushing_syringe_init_mode = int(self.comboBox_pushing_syringe_init_mode.currentText())
        self.widget_psd.actived_syringe_motion_init_mode = 'fill'
        self.widget_psd.connect_valve_port[self.widget_psd.actived_pulling_syringe_init_mode] = 'left'
        self.widget_psd.connect_valve_port[self.widget_psd.actived_pushing_syringe_init_mode] = 'right'
        self.widget_psd.speed_init_mode = float(self.spinBox_speed_init_mode.value())/1000#in uL on GUI, so change to unit of ml
        self.widget_psd.volume_init_mode = float(self.spinBox_volume_init_mode.value())/1000#in uL on GUI, so change to unit of ml
        self.stop_all_timers()
        self.timer_update_init_mode.start(100)

    def dispense_init_mode(self):
        self.radioButton_init_mode.setChecked(True)
        self.update_to_init_mode()
        self.widget_psd.actived_pulling_syringe_init_mode = int(self.comboBox_pulling_syringe_init_mode.currentText())
        self.widget_psd.actived_pushing_syringe_init_mode = int(self.comboBox_pushing_syringe_init_mode.currentText())
        self.widget_psd.actived_syringe_motion_init_mode = 'dispense'
        self.widget_psd.connect_valve_port[self.widget_psd.actived_pulling_syringe_init_mode] = 'left'
        self.widget_psd.connect_valve_port[self.widget_psd.actived_pushing_syringe_init_mode] = 'right'
        self.widget_psd.speed_init_mode = float(self.spinBox_speed_init_mode.value())/1000
        self.widget_psd.volume_init_mode = float(self.spinBox_volume_init_mode.value())/1000
        self.stop_all_timers()
        self.timer_update_init_mode.start(100)

    def fill(self):
        self.radioButton_single_mode.setChecked(True)
        self.update_to_normal_mode()
        self.widget_psd.actived_syringe_normal_mode=int(self.comboBox_syringe_number.currentText())
        self.widget_psd.actived_syringe_motion_normal_mode = 'fill'
        self.widget_psd.connect_valve_port[self.widget_psd.actived_syringe_normal_mode] = self.comboBox_valve_port.currentText()
        self.widget_psd.speed_normal_mode = self.doubleSpinBox_speed_normal_mode.value()
        self.widget_psd.volume_normal_mode = self.widget_psd.syringe_size*self.doubleSpinBox_stroke_factor.value()
        self.stop_all_timers()
        self.timer_update_normal_mode.start(100)

    def dispense(self):
        self.radioButton_single_mode.setChecked(True)
        self.update_to_normal_mode()
        self.widget_psd.actived_syringe_normal_mode=int(self.comboBox_syringe_number.currentText())
        self.widget_psd.actived_syringe_motion_normal_mode = 'dispense'
        self.widget_psd.connect_valve_port[self.widget_psd.actived_syringe_normal_mode] = self.comboBox_valve_port.currentText()
        self.widget_psd.speed_normal_mode = self.doubleSpinBox_speed_normal_mode.value()
        self.widget_psd.volume_normal_mode = self.widget_psd.syringe_size*self.doubleSpinBox_stroke_factor.value()
        self.stop_all_timers()
        self.timer_update_normal_mode.start(100)

    #reset the volume of resevoir and waste bottom
    def reset_exchange(self):
        self.widget_psd.waste_volumn = 0
        self.widget_psd.resevoir_volumn = self.widget_psd.resevoir_volumn_total
        self.widget_psd.update()

    #start auto_refilling mode
    def start(self):
        self.stop_all_timers()
        self.widget_psd.connect_valve_port = {1:'left',2:'right',3:'left',4:'up'}
        self.widget_psd.filling = True
        self.widget_psd.filling2 = False
        self.widget_psd.filling3 = True
        self.widget_psd.filling4 = False
        self.radioButton_exchange_mode.setChecked(True)
        self.update_to_autorefilling_mode()
        self.auto_refilling_elapsed_time = time.time()
        self.timer_update.start(100)

    #stop auto_refilling mode
    def stop(self):
        self.timer_update.stop()

    #update the volume of waste and reservoir bottle during refilling mode
    def update_volume_waste_reservoir(self):
        waste_volumn = self.widget_psd.waste_volumn + self.widget_psd.speed/10
        resevoir_volumn = self.widget_psd.resevoir_volumn - self.widget_psd.speed/10
        if waste_volumn > 250:
            self.timer_update.stop()
        else:
            self.widget_psd.waste_volumn = waste_volumn
            self.widget_psd.resevoir_volumn = resevoir_volumn

    def update_volume_waste_reservoir_normal_mode(self):
        if self.widget_psd.actived_syringe_motion_normal_mode=='fill':
            resevoir_volumn = self.widget_psd.resevoir_volumn - self.widget_psd.speed_normal_mode/10
            if resevoir_volumn<=0:
                self.widget_psd.resevoir_volumn = 0
            else:
                self.widget_psd.resevoir_volumn = resevoir_volumn
        elif self.widget_psd.actived_syringe_motion_normal_mode=='dispense':
            waste_volumn = self.widget_psd.waste_volumn + self.widget_psd.speed_normal_mode/10
            if waste_volumn>self.widget_psd.waste_volumn_total:
                self.widget_psd.waste_volumn = self.widget_psd.waste_volumn_total
            else:
                self.widget_psd.waste_volumn = waste_volumn

    def update_volume_init_mode(self):
        if self.widget_psd.actived_syringe_motion_init_mode == 'fill':
            self.update_volume_filling_init_mode()
        else:
            self.update_volume_dispense_init_mode()

    def update_volume_filling_init_mode(self):
        syringe_index_map_tab = {1:'volume', 2:'volume2', 3:'volume3',4:'volume4'}
        syringe_name = syringe_index_map_tab[self.widget_psd.actived_pushing_syringe_init_mode]
        syringe_vol = getattr(self.widget_psd, syringe_name)
        syringe_vol_change = self.widget_psd.speed_init_mode/10
        self.widget_psd.volume_init_mode = self.widget_psd.volume_init_mode - syringe_vol_change
        if (syringe_vol - syringe_vol_change) < 0:
            setattr(self.widget_psd, syringe_name,0)
            self.widget_psd.volume_of_electrolyte_in_cell = self.widget_psd.volume_of_electrolyte_in_cell + syringe_vol
            self.timer_update_init_mode.stop()
            logging.getLogger().exception('\n Error during filling cell in init_mode: aborted before reaching the target volume.\nNot enough solution left in the syringe.')
            self.tabWidget.setCurrentIndex(2) 

        else:
            if self.widget_psd.volume_init_mode<0:
                setattr(self.widget_psd, syringe_name,syringe_vol - (self.widget_psd.volume_init_mode+syringe_vol_change))
                self.widget_psd.volume_of_electrolyte_in_cell = self.widget_psd.volume_of_electrolyte_in_cell + (self.widget_psd.volume_init_mode+syringe_vol_change)
                self.widget_psd.volume_init_mode = 0
                self.timer_update_init_mode.stop()
            else:
                setattr(self.widget_psd, syringe_name,syringe_vol - syringe_vol_change)
                self.widget_psd.volume_of_electrolyte_in_cell = self.widget_psd.volume_of_electrolyte_in_cell + syringe_vol_change 

    def update_volume_dispense_init_mode(self):
        syringe_index_map_tab = {1:'volume', 2:'volume2', 3:'volume3',4:'volume4'}
        syringe_name = syringe_index_map_tab[self.widget_psd.actived_pulling_syringe_init_mode]
        syringe_vol = getattr(self.widget_psd, syringe_name)
        syringe_vol_change = self.widget_psd.speed_init_mode/10
        self.widget_psd.volume_init_mode = self.widget_psd.volume_init_mode - syringe_vol_change
        if (syringe_vol + syringe_vol_change) > self.widget_psd.syringe_size:
            setattr(self.widget_psd, syringe_name,self.widget_psd.syringe_size)
            self.widget_psd.volume_of_electrolyte_in_cell = self.widget_psd.volume_of_electrolyte_in_cell - (syringe_vol + syringe_vol_change - self.widget_psd.syringe_size)
            self.timer_update_init_mode.stop()
            logging.getLogger().exception('\n Error during withdrawing solution from cell in init_mode: aborted before reaching the target volume.\nReach the maximum size of the syringe.')
            self.tabWidget.setCurrentIndex(2) 
        else:
            if self.widget_psd.volume_init_mode<0:
                setattr(self.widget_psd, syringe_name,syringe_vol + (self.widget_psd.volume_init_mode+syringe_vol_change))
                self.widget_psd.volume_of_electrolyte_in_cell = self.widget_psd.volume_of_electrolyte_in_cell - (self.widget_psd.volume_init_mode+syringe_vol_change)
                self.widget_psd.volume_init_mode = 0
                self.timer_update_init_mode.stop()
            else:
                setattr(self.widget_psd, syringe_name,syringe_vol + syringe_vol_change)
                self.widget_psd.volume_of_electrolyte_in_cell = self.widget_psd.volume_of_electrolyte_in_cell - syringe_vol_change

    def update_volume_normal_mode(self):
        self.widget_psd.volume_normal_mode = self.widget_psd.volume_normal_mode - self.widget_psd.speed_normal_mode/10
        syringe_index_map_tab = {1:'volume', 2:'volume2', 3:'volume3',4:'volume4'}

        def _update_volume(syringe_number, timer = self.timer_update_normal_mode, widget = self.widget_psd):
            speed = widget.speed_normal_mode/10*[-1,1][int(widget.actived_syringe_motion_normal_mode=='fill')]
            setattr(widget,syringe_index_map_tab[syringe_number],getattr(widget,syringe_index_map_tab[syringe_number])+speed)
            if getattr(widget,syringe_index_map_tab[syringe_number])>widget.syringe_size:
                setattr(widget,syringe_index_map_tab[syringe_number],widget.syringe_size)
                timer.stop()
            if getattr(widget,syringe_index_map_tab[syringe_number])<0:
                setattr(widget,syringe_index_map_tab[syringe_number],0)
                timer.stop()
            if getattr(widget,'volume_normal_mode')<=0:
                setattr(widget,'volume_normal_mode',0)
                timer.stop()
        _update_volume(self.widget_psd.actived_syringe_normal_mode)
        """
        if self.widget_psd.actived_syringe_normal_mode==1:
            self.widget_psd.volume = self.widget_psd.volume + self.widget_psd.speed_normal_mode/10*[-1,1][int(self.widget_psd.actived_syringe_motion_normal_mode=='fill')]
            if self.widget_psd.volume>12.5:
                self.widget_psd.volume = 12.5
                self.timer_update_normal_mode.stop()
            if self.widget_psd.volume<0:
                self.widget_psd.volume = 0
                self.timer_update_normal_mode.stop()
            if self.widget_psd.volume_normal_mode<=0:
                self.widget_psd.volume_normal_mode = 0
                self.timer_update_normal_mode.stop()
        elif self.widget_psd.actived_syringe_normal_mode==2:
            self.widget_psd.volume2 = self.widget_psd.volume2 + self.widget_psd.speed_normal_mode/10*[-1,1][int(self.widget_psd.actived_syringe_motion_normal_mode=='fill')]
            if self.widget_psd.volume2>12.5:
                self.widget_psd.volume2 = 12.5
                self.timer_update_normal_mode.stop()
            if self.widget_psd.volume2<0:
                self.widget_psd.volume2 = 0
                self.timer_update_normal_mode.stop()
            if self.widget_psd.volume_normal_mode<=0:
                self.widget_psd.volume_normal_mode = 0
                self.timer_update_normal_mode.stop()
        elif self.widget_psd.actived_syringe_normal_mode==3:
            self.widget_psd.volume3 = self.widget_psd.volume3 + self.widget_psd.speed_normal_mode/10*[-1,1][int(self.widget_psd.actived_syringe_motion_normal_mode=='fill')]
            if self.widget_psd.volume3>12.5:
                self.widget_psd.volume3 = 12.5
                self.timer_update_normal_mode.stop()
            if self.widget_psd.volume3<0:
                self.widget_psd.volume3 = 0
                self.timer_update_normal_mode.stop()
            if self.widget_psd.volume_normal_mode<=0:
                self.widget_psd.volume_normal_mode = 0
                self.timer_update_normal_mode.stop()
        elif self.widget_psd.actived_syringe_normal_mode==4:
            self.widget_psd.volume4 = self.widget_psd.volume4 + self.widget_psd.speed_normal_mode/10*[-1,1][int(self.widget_psd.actived_syringe_motion_normal_mode=='fill')]
            if self.widget_psd.volume4>12.5:
                self.widget_psd.volume4 = 12.5
                self.timer_update_normal_mode.stop()
            if self.widget_psd.volume4<0:
                self.widget_psd.volume4 = 0
                self.timer_update_normal_mode.stop()
            if self.widget_psd.volume_normal_mode<=0:
                self.widget_psd.volume_normal_mode = 0
                self.timer_update_normal_mode.stop()
        """

    def update_volume_empty_all_mode(self):
        waste_volumn = self.widget_psd.waste_volumn + self.widget_psd.speed_by_default/10*4
        if waste_volumn>self.widget_psd.waste_volumn_total:
            self.timer_update_empty_all_mode.stop()
            return
        else:
            self.widget_psd.waste_volumn = waste_volumn
        self.widget_psd.volume = self.widget_psd.volume - self.widget_psd.speed_by_default/10
        if self.widget_psd.volume<0:
            self.widget_psd.volume = 0
        self.widget_psd.volume2 = self.widget_psd.volume2 - self.widget_psd.speed_by_default/10
        if self.widget_psd.volume2<0:
            self.widget_psd.volume2 = 0
        self.widget_psd.volume3 = self.widget_psd.volume3 - self.widget_psd.speed_by_default/10
        if self.widget_psd.volume3<0:
            self.widget_psd.volume3 = 0
        self.widget_psd.volume4 = self.widget_psd.volume4 - self.widget_psd.speed_by_default/10
        if self.widget_psd.volume4<0:
            self.widget_psd.volume4 = 0
        if (self.widget_psd.volume+self.widget_psd.volume2+self.widget_psd.volume3+self.widget_psd.volume4)==0:
           self.timer_update_empty_all_mode.stop()

    def update_volume_fill_all_mode(self):
        resevoir_volumn = self.widget_psd.resevoir_volumn - self.widget_psd.speed_by_default/10*4
        if resevoir_volumn<0:
            self.timer_update_fill_all_mode.stop()
            return
        else:
            self.widget_psd.resevoir_volumn = resevoir_volumn
        self.widget_psd.volume = self.widget_psd.volume + self.widget_psd.speed_by_default/10
        if self.widget_psd.volume>self.widget_psd.syringe_size:
            self.widget_psd.volume = self.widget_psd.syringe_size
        self.widget_psd.volume2 = self.widget_psd.volume2 + self.widget_psd.speed_by_default/10
        if self.widget_psd.volume2>self.widget_psd.syringe_size:
            self.widget_psd.volume2 = self.widget_psd.syringe_size
        self.widget_psd.volume3 = self.widget_psd.volume3 + self.widget_psd.speed_by_default/10
        if self.widget_psd.volume3>self.widget_psd.syringe_size:
            self.widget_psd.volume3 = self.widget_psd.syringe_size
        self.widget_psd.volume4 = self.widget_psd.volume4 + self.widget_psd.speed_by_default/10
        if self.widget_psd.volume4>self.widget_psd.syringe_size:
            self.widget_psd.volume4 = self.widget_psd.syringe_size

        if (self.widget_psd.volume+self.widget_psd.volume2+self.widget_psd.volume3+self.widget_psd.volume4)==self.widget_psd.syringe_size*4:
           self.timer_update_fill_all_mode.stop()

    def update_volume_fill_half_mode(self):
        def _update_resevoir_waste_volume(add_volume_syringe):
            if add_volume_syringe>0:#syringe pickup solution
                if (self.widget_psd.resevoir_volumn - add_volume_syringe) >= 0:
                    self.widget_psd.resevoir_volumn = self.widget_psd.resevoir_volumn - add_volume_syringe
                else:
                    self.timer_update_fill_half_mode.stop()
            elif add_volume_syringe<0:#syringe dispense solution
                if self.widget_psd.waste_volumn - add_volume_syringe <= self.widget_psd.waste_volumn_total:
                    self.widget_psd.waste_volumn = self.widget_psd.waste_volumn - add_volume_syringe
                else:
                    self.timer_update_fill_half_mode.stop()

        def _update_volume(full_volume,original_volume, add_volume):
            filling = True
            if original_volume == full_volume/2:
                return original_volume, filling
            elif original_volume > full_volume/2:
                _update_resevoir_waste_volume(add_volume_syringe = -add_volume)
                return original_volume - add_volume, not filling
            elif original_volume < full_volume/2:
                _update_resevoir_waste_volume(add_volume_syringe = add_volume)
                return original_volume + add_volume, filling

        self.widget_psd.volume, self.widget_psd.filling = _update_volume(self.widget_psd.syringe_size, self.widget_psd.volume, self.widget_psd.speed_by_default/10)
        if abs(self.widget_psd.volume-self.widget_psd.syringe_size/2)<self.widget_psd.speed_by_default/10:
            self.widget_psd.volume = self.widget_psd.syringe_size/2
        self.widget_psd.volume2,self.widget_psd.filling2 = _update_volume(self.widget_psd.syringe_size, self.widget_psd.volume2, self.widget_psd.speed_by_default/10)
        if abs(self.widget_psd.volume2-self.widget_psd.syringe_size/2)<self.widget_psd.speed_by_default/10:
            self.widget_psd.volume2 = self.widget_psd.syringe_size/2
        self.widget_psd.volume3,self.widget_psd.filling3 = _update_volume(self.widget_psd.syringe_size, self.widget_psd.volume3, self.widget_psd.speed_by_default/10)
        if abs(self.widget_psd.volume3-self.widget_psd.syringe_size/2)<self.widget_psd.speed_by_default/10:
            self.widget_psd.volume3 = self.widget_psd.syringe_size/2
        self.widget_psd.volume4, self.widget_psd.filling4 = _update_volume(self.widget_psd.syringe_size, self.widget_psd.volume4, self.widget_psd.speed_by_default/10)
        if abs(self.widget_psd.volume4-self.widget_psd.syringe_size/2)<self.widget_psd.speed_by_default/10:
            self.widget_psd.volume4 = self.widget_psd.syringe_size/2

        if (self.widget_psd.volume+self.widget_psd.volume2+self.widget_psd.volume3+self.widget_psd.volume4)==self.widget_psd.syringe_size*2:
            self.timer_update_fill_half_mode.stop()
            self.widget_psd.operation_mode = 'auto_refilling'#starting auto refilling mode
            self.start_exchange.emit()

    def update_volume(self):
        vol_tags = ['volume','volume2','volume3','volume4']
        fill_tags = ['filling','filling2','filling3','filling4']
        for vol_tag, fill_tag in zip(vol_tags,fill_tags):
            self._update_volume(vol_tag,fill_tag)
        self.lcdNumber_exchange_volume.display(self.widget_psd.waste_volumn)
        self.lcdNumber_time.display(int(time.time()-self.auto_refilling_elapsed_time))

    def _update_volume(self,vol_tag='volume',fill_tag='filling'):
        if (12.5-getattr(self.widget_psd,vol_tag))<=0:
            setattr(self.widget_psd,vol_tag,12.5)
            setattr(self.widget_psd,fill_tag, False)
        elif getattr(self.widget_psd,vol_tag)<=0:
            setattr(self.widget_psd,vol_tag, 0)
            setattr(self.widget_psd,fill_tag, True)
        else:
            pass
        if getattr(self.widget_psd,fill_tag):
            setattr(self.widget_psd,vol_tag, getattr(self.widget_psd,vol_tag)+self.widget_psd.speed/10)
        else:
            setattr(self.widget_psd,vol_tag, getattr(self.widget_psd,vol_tag)-self.widget_psd.speed/10)

    def update_speed(self):
        self.widget_psd.speed = float(self.doubleSpinBox.value())

if __name__ == "__main__":
    QApplication.setStyle("fusion")
    app = QApplication(sys.argv)
    #get dpi info: dots per inch
    screen = app.screens()[0]
    dpi = screen.physicalDotsPerInch()
    myWin = MyMainWindow()
    # app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    myWin.show()
    sys.exit(app.exec_())
