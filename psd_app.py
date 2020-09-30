from PyQt5 import QtCore
from PyQt5.QtWidgets import QCheckBox, QRadioButton, QTableWidgetItem, QHeaderView, QAbstractItemView, QInputDialog, QDialog,QShortcut
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
from operationmode.operations import initOperationMode, normalOperationMode, advancedRefillingOperationMode, simpleRefillingOperationMode, fillCellOperationMode, cleanOperationMode
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
        ui_path = os.path.join(script_path,'psd_gui_beta2.ui')
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

        self.pushButton_fill_cell.setIcon(QtGui.QIcon(os.path.join(script_path,'icons','refill1.png')))
        self.pushButton_fill_cell.setIconSize(QtCore.QSize(60,60))
        self.pushButton_fill_cell.clicked.connect(self.open_refill_dialog)

        self.pushButton_start.setIcon(QtGui.QIcon(os.path.join(script_path,'icons','refill.png')))
        self.pushButton_start.setIconSize(QtCore.QSize(60,60))
        self.pushButton_start.clicked.connect(self.init_start)

        self.pushButton_stop.clicked.connect(self.stop)

        self.pushButton_exchange.setIcon(QtGui.QIcon(os.path.join(script_path,'icons','exchange.png')))
        self.pushButton_exchange.setIconSize(QtCore.QSize(60,60))
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

        self.actionCalibrate_pump_system.triggered.connect(self.config_pump_system)

        self.actionStop_all_motions.triggered.connect(self.stop_all_motion)
        self.shortcut_stop = QShortcut(QtGui.QKeySequence("Ctrl+C"), self)
        self.shortcut_stop.activated.connect(self.stop_all_motion)
        self.actionReset_resevoir_and_waste_volume.triggered.connect(self.reset_exchange)
        self.doubleSpinBox.valueChanged.connect(self.update_speed)
        self.update_speed()
        self.label_cam.setScaledContents(True)

        #reset cell volume to 0
        self.actionReset_Cell_Vol.triggered.connect(self.reset_cell_vol)
        #cleaner dialog pop up
        self.actioncleaner.triggered.connect(self.onCleanerClicked)

        #fill the button with icon
        self.pushButton_fill_init_mode.setIcon(QtGui.QIcon(os.path.join(script_path,'icons','big_drop.png')))
        self.pushButton_fill_init_mode.setIconSize(QtCore.QSize(50,50))
        self.pushButton_fill_init_mode.clicked.connect(self.fill_init_mode)

        self.pushButton_dispense_init_mode.setIcon(QtGui.QIcon(os.path.join(script_path,'icons','small_drop.png')))
        self.pushButton_dispense_init_mode.setIconSize(QtCore.QSize(50,50)) 
        self.pushButton_dispense_init_mode.clicked.connect(self.dispense_init_mode)

        self.pushButton_start_webcam.clicked.connect(self.start_webcam)
        self.pushButton_stop_webcam.clicked.connect(self.stop_webcam)

        self.pushButton_load_config.clicked.connect(self.load_setting_table)
        self.pushButton_save_config.clicked.connect(self.save_setting_table)

        ###set timmers###
        #webcam timer
        self.timer_webcam = QTimer(self)
        self.timer_webcam.timeout.connect(self.viewCam)

        #timers in clean_mode
        self.timer_clean_S1 = QTimer(self)
        self.timer_clean_S2 = QTimer(self)
        self.timer_clean_S3 = QTimer(self)
        self.timer_clean_S4 = QTimer(self)

        #timer to check limits
        self.timer_check_limit = QTimer(self)
        self.timer_check_limit.timeout.connect(self.check_limit)
        self.timer_check_limit.start(10)

        #timer for refill_cell mode
        self.timer_update_fill_cell = QTimer(self)

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

        self.timers = [self.timer_update_simple, self.timer_update_simple_pre, self.timer_update_fill_half_mode,  self.timer_update,self.timer_update_normal_mode, self.timer_update_init_mode, self.timer_update_fill_cell]
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
                                                settings = {'premotion_speed_handle':lambda:self.doubleSpinBox_premotion_speed.value()/1000,
                                                            'exchange_speed_handle':lambda:self.doubleSpinBox.value()/1000,
                                                            'time_record_handle':self.display_exchange_time,
                                                            'volume_record_handle':self.display_exchange_volume,
                                                            'extra_amount_timer':self.timer_extra_amount,
                                                            'extra_amount_handle':self.spinBox_amount.value,
                                                            'extra_amount_speed_handle':self.spinBox_speed.value})

        self.simple_exchange_operation = simpleRefillingOperationMode(self.widget_psd,self.textBrowser_error_msg, self.timer_update_simple_pre, self.timer_update_simple, 100, self.pump_settings, \
                                                settings = {'pull_syringe_handle':self.get_pulling_syringe_simple_exchange_mode,
                                                            'push_syringe_handle':self.get_pushing_syringe_simple_exchange_mode,
                                                            'refill_speed_handle':lambda:self.doubleSpinBox_premotion_speed.value()/1000,
                                                            'exchange_speed_handle':lambda:self.doubleSpinBox.value()/1000})

        self.fill_cell_operation = fillCellOperationMode(self.widget_psd,self.textBrowser_error_msg, None, self.timer_update_fill_cell, 100, self.pump_settings, \
                                                settings = {'push_syringe_handle':self.get_pushing_syringe_fill_cell_mode,
                                                            'refill_speed_handle':self.get_refill_speed_fill_cell_mode,
                                                            'refill_times_handle':self.get_refill_times_fill_cell_mode})

        self.clean_operation_S1 = cleanOperationMode(self.widget_psd,self.textBrowser_error_msg, None, self.timer_clean_S1, 100, self.pump_settings, \
                                                settings = {'syringe_handle':lambda:1,
                                                            'refill_speed_handle':lambda:self.get_refill_speed_clean_mode(1),
                                                            'refill_times_handle':lambda:self.get_refill_times_clean_mode(1),
                                                            'holding_time_handle':lambda:self.get_holding_time_clean_mode(1),
                                                            'inlet_port_handle':lambda:self.get_inlet_port_clean_mode(1),
                                                            'outlet_port_handle':lambda:self.get_outlet_port_clean_mode(1)})

        self.clean_operation_S2 = cleanOperationMode(self.widget_psd,self.textBrowser_error_msg, None, self.timer_clean_S2, 100, self.pump_settings, \
                                                settings = {'syringe_handle':lambda:2,
                                                            'refill_speed_handle':lambda:self.get_refill_speed_clean_mode(2),
                                                            'refill_times_handle':lambda:self.get_refill_times_clean_mode(2),
                                                            'holding_time_handle':lambda:self.get_holding_time_clean_mode(2),
                                                            'inlet_port_handle':lambda:self.get_inlet_port_clean_mode(2),
                                                            'outlet_port_handle':lambda:self.get_outlet_port_clean_mode(2)})

        self.clean_operation_S3 = cleanOperationMode(self.widget_psd,self.textBrowser_error_msg, None, self.timer_clean_S3, 100, self.pump_settings, \
                                                settings = {'syringe_handle':lambda:3,
                                                            'refill_speed_handle':lambda:self.get_refill_speed_clean_mode(3),
                                                            'refill_times_handle':lambda:self.get_refill_times_clean_mode(3),
                                                            'holding_time_handle':lambda:self.get_holding_time_clean_mode(3),
                                                            'inlet_port_handle':lambda:self.get_inlet_port_clean_mode(3),
                                                            'outlet_port_handle':lambda:self.get_outlet_port_clean_mode(3)})

        self.clean_operation_S4 = cleanOperationMode(self.widget_psd,self.textBrowser_error_msg, None, self.timer_clean_S4, 100, self.pump_settings, \
                                                settings = {'syringe_handle':lambda:4,
                                                            'refill_speed_handle':lambda:self.get_refill_speed_clean_mode(4),
                                                            'refill_times_handle':lambda:self.get_refill_times_clean_mode(4),
                                                            'holding_time_handle':lambda:self.get_holding_time_clean_mode(4),
                                                            'inlet_port_handle':lambda:self.get_inlet_port_clean_mode(4),
                                                            'outlet_port_handle':lambda:self.get_outlet_port_clean_mode(4)})

    #handles in clean mode
    def get_refill_speed_clean_mode(self,index):
        return self.widget_psd.syringe_info_clean_mode[index]['refill_speed']

    def get_refill_times_clean_mode(self,index):
        return self.widget_psd.syringe_info_clean_mode[index]['refill_times']

    def get_holding_time_clean_mode(self,index):
        return self.widget_psd.syringe_info_clean_mode[index]['holding_time']

    def get_inlet_port_clean_mode(self,index):
        return self.widget_psd.syringe_info_clean_mode[index]['inlet_port']

    def get_outlet_port_clean_mode(self,index):
        return self.widget_psd.syringe_info_clean_mode[index]['outlet_port']

    def load_setting_table(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", "","All Files (*);;Setting Files (*.ini)", options=options)
        name_mapping = {1:'comboBox_S{}_left',2:'comboBox_S{}_left',3:'comboBox_S{}_right',4:'comboBox_S{}_mvp',5:'lineEdit_sol_{}',6:'lineEdit_vol_{}'}
        if fileName:
            with open(fileName,'r') as f:
                lines = f.readlines()
                for i in range(1,len(lines)+1):
                    items = lines[i-1].rstrip().rsplit(',')
                    for j in range(1,len(items)+1):
                        if j<=6:
                            handle = getattr(self,name_mapping[j].format(i))
                            try:
                                current_index = handle.findText(items[j-1])
                                if current_index!=-1:
                                    handle.setCurrentIndex(current_index)
                            except:
                                handle.setText(items[j-1])

    def save_setting_table(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getSaveFileName(self,"QFileDialog.getSaveFileName()","","config file (*.ini);Text Files (*.txt);all files(*.*)", options=options)
        name_mapping = {1:'comboBox_S{}_left',2:'comboBox_S{}_left',3:'comboBox_S{}_right',4:'comboBox_S{}_mvp',5:'lineEdit_sol_{}',6:'lineEdit_vol_{}'}
        if fileName:
            with open(fileName,'w') as f:
                for i in range(1,5):
                    items = []
                    for j in range(1,7):
                        handle = getattr(self,name_mapping[j].format(i))
                        try:
                            items.append(handle.currentText())
                        except:
                            items.append(handle.text()) 
                    #items.append('\n')
                    if i==4:
                        f.write(','.join(items))
                    else:
                        f.write(','.join(items)+'\n')

    def reset_cell_vol(self):
        self.widget_psd.volume_of_electrolyte_in_cell = 0
        self.widget_psd.update()

    def onCleanerClicked(self):
        dlg = Cleaner(self)
        dlg.exec()

    #def 

    def display_exchange_time(self):
        pass
    
    def empty_func(self):
        pass

    def display_exchange_volume(self, vol):
        self.statusbar.clearMessage()
        self.statusbar.showMessage('Exchange vol: {} ml'.format(vol))

    def get_pushing_syringe_fill_cell_mode(self):
        syringe = self.widget_psd.actived_syringe_fill_cell_mode
        if syringe not in [1,2,3,4]:
            logging.getLogger().exception('Error: The syringe index {} is wrongly set, please reset the syringe index from [1,2,3,4]!'.format(syringe))
        else:
            for each in self.pump_settings:
                #The syringe must connect to the cell_inlet in the setting table
                if (self.pump_settings[each]=='cell_inlet') and ('S{}'.format(syringe) in each):
                    return syringe
            logging.getLogger().exception('Error: The selected syringe is not supposed to pushing solution to cell, but used as waste syringe. Pick a different syringe!')

    def get_refill_speed_fill_cell_mode(self):
        speed = self.widget_psd.refill_speed_fill_cell_mode
        if speed<0:
            speed = 0
        return speed

    def get_refill_times_fill_cell_mode(self):
        times = int(self.widget_psd.refill_times_fill_cell_mode)
        if times<0:
            times = 0
        return times

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

    def open_refill_dialog(self):
        dlg = RefillCellSetup(self)
        dlg.exec()

    @check_any_timer
    def start_fill_cell(self,kwargs =1):
        self.fill_cell_operation.start_timer_motion()

    def start_exchange(self):
        # self.init_start()
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
        # self.widget_psd.volume_normal_mode = eval('self.doubleSpinBox_stroke_factor_{}.value()'.format(syringe_no))*self.widget_psd.syringe_size
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
    '''
    @check_any_timer
    def reset_exchange(self, kwargs = 1):
        self.textBrowser_error_msg.setText('')
        self.widget_psd.waste_volumn = 0
        self.widget_psd.resevoir_volumn = self.widget_psd.resevoir_volumn_total
        self.widget_psd.update()
    '''

    @check_any_timer
    def reset_exchange(self,kwargs = 1):
        dlg = ResetResevoirWaste(self)
        dlg.exec()

    @check_any_timer
    def config_pump_system(self,kwargs = 1):
        dlg = ConfigPumpSystem(self)
        dlg.exec()

    #stop auto_refilling mode
    def stop(self):
        self.stop_all_timers()

    def update_speed(self):
        self.widget_psd.speed = float(self.doubleSpinBox.value())/1000

class ConfigPumpSystem(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Load the dialog's GUI
        uic.loadUi("config_pump_dialog.ui", self)

class RefillCellSetup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        # Load the dialog's GUI
        uic.loadUi("refill_cell_dialog.ui", self)
        self.buttonBox.accepted.connect(self.start_refill)

    def start_refill(self):
        syringe_index = int(self.lineEdit_syringe_index.text())
        refill_times = int(self.lineEdit_refill_times.text())
        refill_speed = float(self.lineEdit_refill_speed.text())/1000
        assert syringe_index in [1,2,3,4], 'Warning: The syringe index is not set right. It should be integer from 1 to 4!'
        assert type(refill_times)==int and refill_times>=1, 'Warning: The refill is not set right. It should be integer >1!'
        self.parent.widget_psd.actived_syringe_fill_cell_mode = syringe_index
        self.parent.widget_psd.refill_times_fill_cell_mode = refill_times*2 # in the script, one stroke filled or emptied is counted as one time, so need to mult by 2
        self.parent.widget_psd.refill_speed_fill_cell_mode = refill_speed
        self.parent.start_fill_cell()

class Cleaner(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        # Load the dialog's GUI
        uic.loadUi("cleaner_dialog.ui", self)
        self.pushButton_start_syringe_1.clicked.connect(lambda:self.start_motion(1))
        self.pushButton_start_syringe_2.clicked.connect(lambda:self.start_motion(2))
        self.pushButton_start_syringe_3.clicked.connect(lambda:self.start_motion(3))
        self.pushButton_start_syringe_4.clicked.connect(lambda:self.start_motion(4))

        self.pushButton_stop_syringe_1.clicked.connect(lambda:self.stop_motion(1))
        self.pushButton_stop_syringe_2.clicked.connect(lambda:self.stop_motion(2))
        self.pushButton_stop_syringe_3.clicked.connect(lambda:self.stop_motion(3))
        self.pushButton_stop_syringe_4.clicked.connect(lambda:self.stop_motion(4))
        self.pushButton_start_all.clicked.connect(lambda:self.start_all([1,2,3,4]))
        self.pushButton_stop_all.clicked.connect(lambda:self.stop_all([1,2,3,4]))

    def start_all(self,index_list = [1,2,3,4]):
        for index in index_list:
            self.start_motion(index)

    def stop_all(self,index_list = [1,2,3,4]):
        for index in index_list:
            self.stop_motion(index)

    def start_motion(self,index):
        self._set_info(index)
        getattr(self.parent, 'clean_operation_S{}'.format(index)).start_timer_motion()

    def stop_motion(self,index):
        timer = getattr(self.parent, 'clean_operation_S{}'.format(index)).timer_motion
        if timer.isActive():
            timer.stop()

    def _set_info(self,index):
        speed = self.parent.widget_psd.syringe_size/getattr(self,'spinBox_speed_syringe_{}'.format(index)).value()
        time = getattr(self,'spinBox_hold_time_syringe_{}'.format(index)).value()
        cycle = int(getattr(self,'spinBox_cycles_syringe_{}'.format(index)).value())
        inlet = getattr(self,'comboBox_inlet_port_syringe_{}'.format(index)).currentText()
        outlet = getattr(self,'comboBox_outlet_port_syringe_{}'.format(index)).currentText()
        self.parent.widget_psd.syringe_info_clean_mode[index]['refill_speed'] = speed
        self.parent.widget_psd.syringe_info_clean_mode[index]['refill_times'] = cycle*2
        self.parent.widget_psd.syringe_info_clean_mode[index]['holding_time'] = time
        self.parent.widget_psd.syringe_info_clean_mode[index]['inlet_port'] = inlet
        self.parent.widget_psd.syringe_info_clean_mode[index]['outlet_port'] = outlet

class ResetResevoirWaste(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        # Load the dialog's GUI
        uic.loadUi("reset_resevoir_waste_dialog.ui", self)
        # print(self.__dir__())
        self.get_info_from_parent()
        self.pushButton_apply.clicked.connect(self.apply)
        
    def get_info_from_parent(self):
        for i in range(1,5):
            tag = 'S{}_volume'.format(i)
            tag2 = 'S{}_solution'.format(i)
            if self.parent.pump_settings[tag2] == 'waste':
                getattr(self,tag).setText('None')
            else:
                getattr(self,tag).setText(str(self.parent.pump_settings[tag]))
            getattr(self,tag2).setText(str(self.parent.pump_settings[tag2]))
            self.lineEdit_max_vol.setText(str(self.parent.widget_psd.resevoir_volumn_total))
    
    def apply(self):
        for i in range(1,5):
            tag = 'S{}_volume'.format(i)
            tag2 = 'S{}_solution'.format(i)
            if self.parent.pump_settings[tag2] == 'waste':
                pass
            else:
                self.parent.pump_settings[tag] = eval(getattr(self,tag).text())
            self.parent.pump_settings[tag2]= getattr(self,tag2).text()
        self.parent.widget_psd.pump_settings = self.parent.pump_settings
        self.parent.widget_psd.set_resevoir_volumes()
        self.parent.widget_psd.waste_volumn = eval(self.lineEdit_waste_vol.text())
        self.parent.widget_psd.update()

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
