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
import functools
try:
    from . import locate_path
except:
    import locate_path
from operationmode.operations import initOperationMode, normalOperationMode, advancedRefillingOperationMode, simpleRefillingOperationMode
script_path = locate_path.module_path_locator()

#redirect the error stream to qt widge_syiit
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
        """using the error reporting dialog or via email to <%s>."""%\
        ("crqiu2@gmail.com")
        self.textBrowser_error_msg.clear()
        cursor = self.textBrowser_error_msg.textCursor()
        cursor.insertHtml('''<p><span style="color: red;">{} <br></span>'''.format(" "))
        self.textBrowser_error_msg.setText(notice + '\n' +separator+'\n'+error_msg)

class MyMainWindow(QMainWindow):
    def __init__(self, parent = None):
        super(MyMainWindow, self).__init__(parent)
        #load GUI ui file made by qt designer
        ui_path = os.path.join(script_path,'psd_gui_beta.ui')
        uic.loadUi(ui_path,self)
        self.connected_mvp_channel = None #like 'channel_1'

        self.pump_settings = {}
        self.pushButton_apply_settings.clicked.connect(self.apply_pump_settings)
        self.apply_pump_settings()

        self.cam_frame_path = os.path.join(script_path,'images')

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

        self.image = None
        self.frame_number = 0
        self.pushButton_catch_frame.clicked.connect(self.catch_frame)

        self.pushButton_start.clicked.connect(self.init_start)
        self.pushButton_stop.clicked.connect(self.stop)
        self.pushButton_exchange.clicked.connect(self.start_exchange)

        self.pushButton_fill_syringe_1.clicked.connect(lambda:self.fill_syringe(1))
        self.pushButton_dispense_syringe_1.clicked.connect(lambda:self.dispense_syringe(1))
        self.pushButton_fill_syringe_2.clicked.connect(lambda:self.fill_syringe(2))
        self.pushButton_dispense_syringe_2.clicked.connect(lambda:self.dispense_syringe(2))
        self.pushButton_fill_syringe_3.clicked.connect(lambda:self.fill_syringe(3))
        self.pushButton_dispense_syringe_3.clicked.connect(lambda:self.dispense_syringe(3))
        self.pushButton_fill_syringe_4.clicked.connect(lambda:self.fill_syringe(4))
        self.pushButton_dispense_syringe_4.clicked.connect(lambda:self.dispense_syringe(4))
        self.pushButton_stop_normal.clicked.connect(self.stop_timer_normal_mode)
        self.comboBox_valve_port_1.currentTextChanged.connect(lambda:self.update_to_normal_mode(1))
        self.comboBox_valve_port_2.currentTextChanged.connect(lambda:self.update_to_normal_mode(2))
        self.comboBox_valve_port_3.currentTextChanged.connect(lambda:self.update_to_normal_mode(3))
        self.comboBox_valve_port_4.currentTextChanged.connect(lambda:self.update_to_normal_mode(4))

        self.pushButton_connect_mvp_syringe_1.clicked.connect(lambda:self.update_mvp_connection(1))
        self.pushButton_connect_mvp_syringe_2.clicked.connect(lambda:self.update_mvp_connection(2))
        self.pushButton_connect_mvp_syringe_3.clicked.connect(lambda:self.update_mvp_connection(3))
        self.pushButton_connect_mvp_syringe_4.clicked.connect(lambda:self.update_mvp_connection(4))

        self.actionStop_all_motions.triggered.connect(self.stop_all_motion)
        self.actionReset_resevoir_and_waste_volume.triggered.connect(self.reset_exchange)
        self.doubleSpinBox.valueChanged.connect(self.update_speed)
        self.update_speed()
        self.label_cam.setScaledContents(True)

        self.pushButton_fill_init_mode.clicked.connect(self.fill_init_mode)
        self.pushButton_dispense_init_mode.clicked.connect(self.dispense_init_mode)

        self.pushButton_start_webcam.clicked.connect(self.start_webcam)
        self.pushButton_stop_webcam.clicked.connect(self.stop_webcam)

        ###set timmers###
        #webcam timer
        self.timer_webcam = QTimer(self)
        self.timer_webcam.timeout.connect(self.viewCam)

        #timer to check limits
        self.timer_check_limit = QTimer(self)
        self.timer_check_limit.timeout.connect(self.check_limit)
        self.timer_check_limit.start(10)

        #auto_refilling_mode
        self.timer_update = QTimer(self)

        #simple mode of auto_refilling
        self.timer_update_simple = QTimer(self)

        #premotion before simple mode of auto_refilling
        self.timer_update_simple_pre = QTimer(self)

        #single_mode, operating on one specific syringe
        self.timer_update_normal_mode = QTimer(self)

        #action done before auto_refilling, serve purpose to fill the cell first
        self.timer_update_init_mode = QTimer(self)

        #timer to add/remove extra amount of solution to/from cell during simple or advance exchange mode
        self.timer_extra_amount = QTimer(self)
        self.timer_extra_amount.timeout.connect(self.empty_func)

        # in this mode, all syringes will be half-filled (internally actived before auto_refilling mode)
        self.timer_update_fill_half_mode = QTimer(self)

        self.timers = [self.timer_update_simple, self.timer_update_simple_pre, self.timer_update_fill_half_mode,  self.timer_update,self.timer_update_normal_mode, self.timer_update_init_mode]
        self.timers_partial = [self.timer_update_simple_pre, self.timer_update_fill_half_mode, self.timer_update_normal_mode, self.timer_update_init_mode]

        self.pushButton_connect_mvp_syringe_1.click()
        #instances of operation modes
        self.init_operation = initOperationMode(self.widget_psd,self.textBrowser_error_msg, None, self.timer_update_init_mode, 100, self.pump_settings, \
                                                settings = {'pull_syringe_handle':self.get_pulling_syringe_simple_exchange_mode,
                                                            'push_syringe_handle':self.get_pushing_syringe_simple_exchange_mode,
                                                            'vol_handle':self.spinBox_amount.value,
                                                            'speed_handle':self.spinBox_speed.value})

        self.normal_operation = normalOperationMode(self.widget_psd,self.textBrowser_error_msg, None, self.timer_update_normal_mode, 100, self.pump_settings, \
                                                settings = {'syringe_handle':self.get_syringe_index_handle_normal_mode,
                                                            'valve_position_handle':self.get_valve_position_handle_normal_mode,
                                                            'valve_connection_handle':self.get_valve_connection_handle_normal_mode,
                                                            'vol_handle':self.get_vol_handle_normal_mode,
                                                            'speed_handle':self.get_speed_handle_normal_mode})

        self.advanced_exchange_operation = advancedRefillingOperationMode(self.widget_psd, self.textBrowser_error_msg, self.timer_update_fill_half_mode, self.timer_update, 100, self.pump_settings, \
                                                settings = {'premotion_speed_handle':self.doubleSpinBox_premotion_speed.value,
                                                            'exchange_speed_handle':self.doubleSpinBox.value,
                                                            'time_record_handle':self.display_exchange_time,
                                                            'volume_record_handle':self.display_exchange_volume,
                                                            'extra_amount_timer':self.timer_extra_amount,
                                                            'extra_amount_handle':self.spinBox_amount.value,
                                                            'extra_amount_speed_handle':self.spinBox_speed.value})

        self.simple_exchange_operation = simpleRefillingOperationMode(self.widget_psd,self.textBrowser_error_msg, self.timer_update_simple_pre, self.timer_update_simple, 100, self.pump_settings, \
                                                settings = {'pull_syringe_handle':self.get_pulling_syringe_simple_exchange_mode,
                                                            'push_syringe_handle':self.get_pushing_syringe_simple_exchange_mode,
                                                            'refill_speed_handle':self.doubleSpinBox_premotion_speed.value,
                                                            'exchange_speed_handle':self.doubleSpinBox.value})
        
    def display_exchange_time(self):
        pass
    
    def empty_func(self):
        pass

    def display_exchange_volume(self, vol):
        self.statusbar.clearMessage()
        self.statusbar.showMessage('Exchange vol: {} ml'.format(vol))

    def get_pulling_syringe_simple_exchange_mode(self):
        syringe = None
        #each looks like : S1_left
        for each in self.pump_settings:
            if self.pump_settings[each] == 'cell_outlet':
                syringe = each
                break
        if syringe != None:
            return int(''.join(syringe.rsplit('_')[0][1:]))
        else:
            logging.getLogger().exception('Error: Could not find syringe to pull electrolyte from cell. Check your setting table!')
            self.tabWidget.setCurrentIndex(2)

    def get_pushing_syringe_simple_exchange_mode(self):
        for each in self.pump_settings:
            if self.pump_settings[each] == self.connected_mvp_channel:
                return int(''.join(each.rsplit('_')[0][1:]))
        logging.getLogger().exception('No MVP channel is actived now. Connect it first!')
        self.tabWidget.setCurrentIndex(2) 

    def update_cell_volume(self):
        self.widget_psd.cell_volume_in_total = self.spinBox_cell_volume.value()

    def get_syringe_index_handle_normal_mode(self):
        radioButtons = [getattr(self, 'radioButton_syringe_{}'.format(i)) for i in range(1,16) if hasattr(self, 'radioButton_syringe_{}'.format(i))]
        for i in range(0,len(radioButtons)):
            if radioButtons[i].isChecked():
                return int(i+1)
        logging.getLogger().exception('No radioButton has been clicked! Click one button to activate normal mode!')

    def get_valve_position_handle_normal_mode(self,index):
        if isinstance(index, int):
            return eval('self.comboBox_valve_port_{}.currentText()'.format(index))

    def get_valve_connection_handle_normal_mode(self, index):
        if isinstance(index, int):
            return self.pump_settings['S{}_{}'.format(index, self.widget_psd.connect_valve_port[index])]

    def get_speed_handle_normal_mode(self,index):
        if isinstance(index, int):
            return eval('self.doubleSpinBox_speed_normal_mode_{}.value()'.format(index))

    def get_vol_handle_normal_mode(self,index):
        if isinstance(index, int):
            return eval('self.doubleSpinBox_stroke_factor_{}.value()'.format(index))

    def apply_pump_settings(self):
        i = 1
        while True:
            try:
                items = ['left','right','up','mvp']
                for each in items:
                    self.pump_settings['S{}_{}'.format(i,each)] = getattr(self,'comboBox_S{}_{}'.format(i, each)).currentText()
                self.pump_settings['S{}_solution'.format(i)] = getattr(self, 'lineEdit_sol_{}'.format(i)).text()
                self.pump_settings['S{}_volume'.format(i)] = eval(getattr(self, 'lineEdit_vol_{}'.format(i)).text())
                i += 1
            except:
                break
        setattr(self.widget_psd, 'pump_settings', self.pump_settings)
        self.widget_psd.set_resevoir_volumes()

    def check_limit(self):
        limits = {'volume_syringe_1':[0,self.widget_psd.syringe_size], \
                  'volume_syringe_2':[0,self.widget_psd.syringe_size], \
                  'volume_syringe_3':[0,self.widget_psd.syringe_size], \
                  'volume_syringe_4':[0,self.widget_psd.syringe_size],\
                  'resevoir_volumn':[0,self.widget_psd.resevoir_volumn_total],\
                  'waste_volumn':[0,self.widget_psd.waste_volumn_total],\
                  'volume_of_electrolyte_in_cell':[0,self.widget_psd.cell_volume_in_total]}
        for each in limits:
            value = getattr(self.widget_psd,each)
            if value<limits[each][0]:
                setattr(self.widget_psd,each,limits[each][0])
                self.stop_all_motion()
                logging.getLogger().exception('\nError due to {} out of limits: '.format(each))
                self.tabWidget.setCurrentIndex(2) 
                # self.timer_check_limit.stop()
                break
            elif value>limits[each][1]:
                setattr(self.widget_psd,each,limits[each][1])
                self.stop_all_motion()
                logging.getLogger().exception('\nError due to {} out of limits: '.format(each))
                self.tabWidget.setCurrentIndex(2) 
                # self.timer_check_limit.stop()
                break
    
    def stop_timer_normal_mode(self):
        self.timer_update_normal_mode.stop()

    def show_or_hide_cam_settings(self):
        if self.show_cam_settings:
            self.groupBox_camview.setVisible(True)
        else:
            self.groupBox_camview.setVisible(False)
        self.show_cam_settings = not self.show_cam_settings

    #save a snapshot of webcam
    def catch_frame(self):
        if self.timer_webcam.isActive():
            frame_path = os.path.join(script_path,'cam_frame{}.png'.format(self.frame_number))
            cv2.imwrite(frame_path, self.image)
            self.frame_number+=1
            self.statusbar.showMessage('Cam Image is saved at {}!'.format(frame_path))
        else:
            pass

    def stop_all_timers(self):
        for timer in self.timers:
            if timer.isActive():
                timer.stop()

    def check_any_timer(func):
        @functools.wraps(func)
        def wrapper_func(self, *args, **kwargs):
            for timer in self.timers:
                if timer.isActive():
                    logging.getLogger().exception('Error: some timer is running now. Stop it before you can make this move!')
                    self.tabWidget.setCurrentIndex(2)
                    return
            return func(self, *args, **kwargs)
        return wrapper_func

    def check_any_timer_except_exchange(func):
        @functools.wraps(func)
        def wrapper_func(self, *args, **kwargs):
            for timer in self.timers_partial:
                if timer.isActive():
                    logging.getLogger().exception('Error: some timer is running now. Stop it before you can make this move!')
                    self.tabWidget.setCurrentIndex(2)
                    return
            return func(self, *args, **kwargs)
        return wrapper_func

    def init_start(self):
        if self.comboBox_exchange_mode.currentText() == 'Continuous':
            self.init_start_advance()
        elif self.comboBox_exchange_mode.currentText() == 'Intermittent':
            self.init_start_simple()

    @check_any_timer
    def init_start_advance(self):
        self.textBrowser_error_msg.setText('')
        #check the cell volume first
        if self.widget_psd.volume_of_electrolyte_in_cell < 0.1:
            logging.getLogger().exception('Error: Not enough electrolyte in cell. Please fill some solution in the cell first!')
            self.tabWidget.setCurrentIndex(2) 
        else:
            if self.check_connection_for_advanced_auto_refilling():
                self.advanced_exchange_operation.start_premotion_timer()

    @check_any_timer
    def init_start_simple(self):
        self.textBrowser_error_msg.setText('')
        if self.widget_psd.volume_of_electrolyte_in_cell < 0.1:
            logging.getLogger().exception('Error: Not enough electrolyte in cell. Please fill some solution in the cell first!')
            self.tabWidget.setCurrentIndex(2) 
        else:
            self.simple_exchange_operation.start_premotion_timer()

    def start_exchange(self):
        if self.comboBox_exchange_mode.currentText() == 'Continuous':
            self.start_exchange_advance(not self.checkBox_auto.isChecked())
        elif self.comboBox_exchange_mode.currentText() == 'Intermittent':
            self.start_exchange_simple(not self.checkBox_auto.isChecked())

    @check_any_timer
    def start_exchange_advance(self, onetime):
        self.textBrowser_error_msg.setText('')
        self.advanced_exchange_operation.start_motion_timer(onetime)

    @check_any_timer
    def start_exchange_simple(self, onetime):
        self.textBrowser_error_msg.setText('')
        self.simple_exchange_operation.start_motion_timer(onetime)
        #self.advanced_exchange_operation.start_motion_timer(onetime)

    def init_stop_simple(self):
        self.stop_all_timers()

    def check_connection_for_advanced_auto_refilling(self):
        #the connections have to be like this, otherwise its not gonna work in this mode
        _setting = {'S1_left':'resevoir',
                    'S1_up':'waste',
                    'S1_right':'cell_inlet',
                    'S2_left':'resevoir',
                    'S2_up':'waste',
                    'S2_right':'cell_inlet',
                    'S3_left':'cell_outlet',
                    'S3_up':'waste',
                    'S3_right':'not_used',
                    'S4_left':'cell_outlet',
                    'S4_up':'waste',
                    'S4_right':'not_used',
                    }
        for each in _setting:
            if self.pump_settings[each]!=_setting[each]:
                logging.getLogger().exception('Connections error: something is not properly set up in your valve port connection for auto_refilling purpose\n{} must be connected to {} rather than {}'.format(each,_setting[each], self.pump_settings[each]))
                self.tabWidget.setCurrentIndex(2) 
                return False
        return True

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
        self.textBrowser_error_msg.setText('')
        self.widget_psd.operation_mode = 'init_mode'
        #which one is the syringe to pull electrolyte from cell
        self.widget_psd.actived_pulling_syringe_init_mode = int(self.comboBox_pulling_syringe_init_mode.currentText())
        #which one is the syringe to push electrolyte to cell
        self.widget_psd.actived_pushing_syringe_init_mode = int(self.comboBox_pushing_syringe_init_mode.currentText())
        self.widget_psd.mvp_channel = int(self.comboBox_pushing_syringe_init_mode.currentText())
        self.widget_psd.mvp_connected_valve = 'S{}'.format(self.widget_psd.mvp_channel)
        self.widget_psd.actived_syringe_motion_init_mode = 'fill'
        self.widget_psd.connect_valve_port[self.widget_psd.actived_pulling_syringe_init_mode] = 'left'
        self.widget_psd.connect_valve_port[self.widget_psd.actived_pushing_syringe_init_mode] = 'right'
        self.widget_psd.update()

    def update_to_normal_mode(self, syringe_no):
        self.textBrowser_error_msg.setText('')
        #radioButton_widget.setChecked(True)
        self.widget_psd.actived_syringe_normal_mode = syringe_no
        self.widget_psd.operation_mode = 'normal_mode'
        valve_position = eval('self.comboBox_valve_port_{}.currentText()'.format(syringe_no))
        self.widget_psd.connect_valve_port[self.widget_psd.actived_syringe_normal_mode] = valve_position
        key_for_pump_setting = 'S{}_{}'.format(syringe_no,valve_position)
        key_for_mvp = 'S{}_mvp'.format(syringe_no)
        '''
        #update mvp channel if connecting to cell_inlet
        if self.pump_settings[key_for_pump_setting]=='cell_inlet':
            self.widget_psd.mvp_channel = int(self.pump_settings[key_for_mvp].rsplit('_')[1])
            self.widget_psd.mvp_connected_valve = 'S{}'.format(self.widget_psd.mvp_channel)
        '''
        #update the valve connection based on the info in pump settings
        #eval("self.comboBox_valve_connection_{}.setCurrentText('{}')".format(syringe_no,self.pump_settings[key_for_pump_setting]))
        #self.widget_psd.actived_syringe_valve_connection = eval('self.comboBox_valve_connection_{}.currentText()'.format(syringe_no))
        self.widget_psd.actived_syringe_valve_connection = self.pump_settings[key_for_pump_setting]
        self.widget_psd.volume_normal_mode = eval('self.doubleSpinBox_stroke_factor_{}.value()'.format(syringe_no))*self.widget_psd.syringe_size
        self.widget_psd.update()

    @check_any_timer
    def update_mvp_connection(self, syringe_no):
        self.textBrowser_error_msg.setText('')
        self.connected_mvp_channel = self.pump_settings['S{}_mvp'.format(syringe_no)]
        self.widget_psd.mvp_channel = syringe_no
        self.widget_psd.mvp_connected_valve = 'S{}'.format(syringe_no)
        self.widget_psd.update()

    def add_solution_to_cell(self, amount):
        self.spinBox_speed_init_mode.setValue(int(self.spinBox_speed.value()))
        self.spinBox_volume_init_mode.setValue(int(amount))
        self.fill_init_mode()

    def remove_solution_from_cell(self, amount):
        self.spinBox_speed_init_mode.setValue(int(self.spinBox_speed.value()))
        self.spinBox_volume_init_mode.setValue(int(amount))
        self.dispense_init_mode()

    @check_any_timer_except_exchange
    def fill_init_mode(self,kwargs = None):
        self.textBrowser_error_msg.setText('')
        if self.timer_update.isActive() or self.timer_update_simple.isActive():
            self.advanced_exchange_operation.extra_amount_fill = True
            self.advanced_exchange_operation.fill_or_dispense_extra_amount = self.advanced_exchange_operation.settings['extra_amount_handle']()/1000
            self.timer_extra_amount.start(1000)
        else:
            self.widget_psd.actived_syringe_motion_init_mode = 'fill'
            self.stop_all_timers()
            self.init_operation.start_exchange_timer()

    @check_any_timer_except_exchange
    def dispense_init_mode(self, kwargs = None):
        self.textBrowser_error_msg.setText('')
        if self.timer_update.isActive() or self.timer_update_simple.isActive():
            self.advanced_exchange_operation.extra_amount_fill = False
            self.advanced_exchange_operation.fill_or_dispense_extra_amount = self.advanced_exchange_operation.settings['extra_amount_handle']()/1000
            self.timer_extra_amount.start(1000)
        else:
            self.widget_psd.actived_syringe_motion_init_mode = 'dispense'
            self.stop_all_timers()
            self.init_operation.start_exchange_timer()

    @check_any_timer
    def fill_syringe(self,syringe_no):
        self.textBrowser_error_msg.setText('')
        if self.pump_settings['S{}_mvp'.format(syringe_no)] != 'not_used':
            exec('self.pushButton_connect_mvp_syringe_{}.click()'.format(syringe_no))
        self.widget_psd.actived_syringe_motion_normal_mode = 'fill'
        exec('self.widget_psd.filling_status_syringe_{} = True'.format(syringe_no))
        self.normal_operation.syringe_index = syringe_no
        self.normal_operation.start_timer_motion()

    @check_any_timer
    def dispense_syringe(self,syringe_no):
        self.textBrowser_error_msg.setText('')
        if self.pump_settings['S{}_mvp'.format(syringe_no)] != 'not_used':
            exec('self.pushButton_connect_mvp_syringe_{}.click()'.format(syringe_no))
        self.widget_psd.actived_syringe_motion_normal_mode = 'dispense'
        exec('self.widget_psd.filling_status_syringe_{} = False'.format(syringe_no))
        #radioButton_widget.setChecked(True)
        self.stop_all_timers()
        self.normal_operation.syringe_index = syringe_no
        self.normal_operation.start_timer_motion()

    #reset the volume of resevoir and waste bottom
    @check_any_timer
    def reset_exchange(self, kwargs = 1):
        self.textBrowser_error_msg.setText('')
        self.widget_psd.waste_volumn = 0
        self.widget_psd.resevoir_volumn = self.widget_psd.resevoir_volumn_total
        self.widget_psd.update()

    #stop auto_refilling mode
    def stop(self):
        self.stop_all_timers()

    def update_speed(self):
        self.widget_psd.speed = float(self.doubleSpinBox.value())

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
