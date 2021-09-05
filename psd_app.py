from PyQt5 import QtCore
from PyQt5.QtWidgets import QCheckBox, QRadioButton, QDialog, QTableWidgetItem, QHeaderView, QAbstractItemView, QInputDialog, QDialog,QShortcut
from PyQt5.QtCore import Qt, QTimer, QDeadlineTimer, QEventLoop, QThread
from PyQt5.QtGui import QTransform, QFont, QBrush, QColor, QIcon, QImage, QPixmap
from pyqtgraph.Qt import QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PyQt5 import uic, QtWidgets
#The following three lines are necessary as a detoure to the incompatibiltiy of Qt5 APP showing in Mac Big Sur OS
#This solution seems non-sense, since the matplotlib is not used in the app.
#But if these lines are removed, the app GUI is not gonna pop up.
#This situation may change in the future.
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("TkAgg")
import qdarkstyle
import sys,os
import cv2
import logging
import time
from datetime import datetime
import functools
import subprocess
import threading
from pymongo import MongoClient
try:
    from . import locate_path
except:
    import locate_path
from operationmode.operations import initOperationMode, normalOperationMode, advancedRefillingOperationMode, simpleRefillingOperationMode, fillCellOperationMode, cleanOperationMode
script_path = locate_path.module_path_locator()
# sys.path.append(os.path.join(script_path, 'pysyringedrive'))
# from syringedrive.PumpInterface import PumpController
# from syringedrive.device import PSD4_smooth, Valve, ExchangePair

class MessageExchanger(QtCore.QObject):
    exec_cmd = QtCore.pyqtSignal(str)
    #update_response = QtCore.pyqtSignal(bool)
    def __init__(self, parent_object):
        super(MessageExchanger, self).__init__()
        self.database = parent_object.database
        self.parent = parent_object

    def exchange_info(self):
        if self.parent.main_client_cloud:
            self._update_device_info_to_cloud(self.exec_cmd)
        else:
            self._update_device_info_from_cloud()

    def _update_device_info_to_cloud(self, sig_exec_cmd):
        #main client update device info to mongo cloud
        #never end unless terminating the main_gui program
        while True:
            if not self.parent.listen:
                self.parent.lineEdit_listen_status.setText('Listening is terminated!')
                return
            time.sleep(0.05)
            self.database.device_info.update_one({'client_id':self.parent.lineEdit_current_client.text()},{"$set": {"S1_vol":str(self.parent.widget_psd.volume_syringe_1)}})
            self.database.device_info.update_one({'client_id':self.parent.lineEdit_current_client.text()},{"$set": {'valve_pos':str(self.parent.widget_psd.connect_valve_port)}})
            self.database.device_info.update_one({'client_id':self.parent.lineEdit_current_client.text()},{"$set": {'S2_vol': str(self.parent.widget_psd.volume_syringe_2)}})
            self.database.device_info.update_one({'client_id':self.parent.lineEdit_current_client.text()},{"$set": {"S3_vol":str(self.parent.widget_psd.volume_syringe_3)}})
            self.database.device_info.update_one({'client_id':self.parent.lineEdit_current_client.text()},{"$set": {"S4_vol":str(self.parent.widget_psd.volume_syringe_4)}})
            self.database.device_info.update_one({'client_id':self.parent.lineEdit_current_client.text()},{"$set": {"cell_vol":str(self.parent.widget_psd.volume_of_electrolyte_in_cell)}})
            self.database.device_info.update_one({'client_id':self.parent.lineEdit_current_client.text()},{"$set": {'mvp_valve': str(self.parent.widget_psd.mvp_channel)}})
            self.database.device_info.update_one({'client_id':self.parent.lineEdit_current_client.text()},{"$set": {'resevoir_vol': str(self.parent.widget_psd.resevoir_volumn)}})
            self.database.device_info.update_one({'client_id':self.parent.lineEdit_current_client.text()},{"$set": {'waste_vol': str(self.parent.widget_psd.waste_volumn)}})
            self.database.device_info.update_one({'client_id':self.parent.lineEdit_current_client.text()},{"$set": {'connect_status': str(self.parent.widget_psd.connect_status)}})
            self.database.device_info.update_one({'client_id':self.parent.lineEdit_current_client.text()},{"$set": {'operation_mode': self.parent.widget_psd.operation_mode}})
            #cmds
            target = self.database.cmd_info.find_one({'client_id':self.parent.lineEdit_paired_client.text()})
            if target == None:
                pass
            else:
                if target['cmd'] != '':
                    sig_exec_cmd.emit(target['cmd'])

    def _update_device_info_from_cloud(self):
        #pulling device info from mongo cloud
        #never end unless terminating the main_gui program
        while True:
            #time.sleep(0.01)
            if not self.parent.listen:
                self.parent.lineEdit_listen_status.setText('Listening is terminated!')
                return
            device_info = self.database.device_info.find_one()
            self.parent.widget_psd.volume_syringe_1 = float(device_info['S1_vol'])
            self.parent.widget_psd.volume_syringe_2 = float(device_info['S2_vol'])
            self.parent.widget_psd.volume_syringe_3 = float(device_info['S3_vol'])
            self.parent.widget_psd.volume_syringe_4 = float(device_info['S4_vol'])
            self.parent.widget_psd.volume_of_electrolyte_in_cell = float(device_info['cell_vol'])
            self.parent.widget_psd.connect_valve_port = eval(device_info['valve_pos'])
            self.parent.widget_psd.connect_status = eval(device_info['connect_status'])
            self.parent.widget_psd.mvp_channel = int(device_info['mvp_valve'])
            self.parent.widget_psd.resevoir_volumn = float(device_info['resevoir_vol'])
            self.parent.widget_psd.waste_volumn = float(device_info['waste_vol'])
            self.parent.widget_psd.operation_mode = device_info['operation_mode']
            self.parent.widget_psd.update()

def error_pop_up(msg_text = 'error', window_title = ['Error','Information','Warning'][0]):
    msg = QMessageBox()
    if window_title == 'Error':
        msg.setIcon(QMessageBox.Critical)
    elif window_title == 'Warning':
        msg.setIcon(QMessageBox.Warning)
    else:
        msg.setIcon(QMessageBox.Information)

    msg.setText(msg_text)
    # msg.setInformativeText('More information')
    msg.setWindowTitle(window_title)
    msg.exec_()

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

class StartServerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        # Load the dialog's GUI
        uic.loadUi(os.path.join(script_path,"start_mongo_server.ui"), self)
        self.pushButton_start.clicked.connect(self.setup_mongo_client_cloud)

    def setup_mongo_client_cloud(self):
        if (self.lineEdit_database_name.text()!='') and (self.lineEdit_client_id.text()!='') and (self.lineEdit_paired_client_id.text()!=''):
            self.parent.lineEdit_database_name.setText(self.lineEdit_database_name.text())
            self.parent.lineEdit_current_client.setText(self.lineEdit_client_id.text())
            self.parent.lineEdit_paired_client.setText(self.lineEdit_paired_client_id.text())
            main_client = self.checkBox_main_client.isChecked()
            if main_client:
                self.parent.lineEdit_main_client.setText(self.lineEdit_client_id.text())
            else:
                self.parent.lineEdit_main_client.setText(self.lineEdit_paired_client_id.text())
            self.parent.login_name = self.lineEdit_login.text()
            self.parent.password = self.lineEdit_pass.text()
            error_pop_up('Success setting up MongoDB clients. Now you can go back to main GUI and connect the Pymongo cloud!','Information')
        else:
            error_pop_up('Failure: some fields are not filled!','Error')


class StartPumpClientDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        # Load the dialog's GUI
        uic.loadUi(os.path.join(script_path,"start_pump_client.ui"), self)
        self.pushButton_open.clicked.connect(self.open_file)
        self.pushButton_update.clicked.connect(self.update_file)
        self.pushButton_load.clicked.connect(self.load_file)
        self.pushButton_init_s1.clicked.connect(lambda:self.initialize_device(1,'syringe'))
        self.pushButton_init_s2.clicked.connect(lambda:self.initialize_device(2,'syringe'))
        self.pushButton_init_s3.clicked.connect(lambda:self.initialize_device(3,'syringe'))
        self.pushButton_init_s4.clicked.connect(lambda:self.initialize_device(4,'syringe'))
        self.pushButton_init_mvp.clicked.connect(lambda:self.initialize_device(None,'mvp'))
        self.pushButton_init_all.clicked.connect(lambda:self.initialize_all_device([1,2,3,4,None],['syringe']*4+['mvp']))
        self.pushButton_create_client.clicked.connect(self.create_client_without_config)
        self.pushButton_server_cmd.clicked.connect(self.generate_server_cmd)
        # self.pushButton_load_without_config.clicked.connect(self.load_file_without_config)

    def open_file(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", "","config file (*.yml);;config Files (*.txt)", options=options)
        if fileName:
            with open(fileName,'r') as f:
                self.textEdit_config.setPlainText(f.read())
            self.lineEdit_config_path.setText(fileName)
        else:
            pass

    def update_file(self):
        if self.textEdit_config.toPlainText()!='':
            with open(self.lineEdit_config_path.text(),'w') as f:
                f.write(self.textEdit_config.toPlainText())
    
    def load_file(self):
        self.parent.create_pump_client(config_file = self.lineEdit_config_path.text(), device_name = 'exp/ec/pump1', config_use = True)
        self.parent.timer_syn_server_and_gui.start(100)

    def load_file_without_config(self):
        self.parent.create_pump_client(config_file = self.lineEdit_config_path.text(), device_name = self.lineEdit_device_name.text(), config_use = False)

    def generate_server_cmd(self):
        if len(self.lineEdit_config_path.text())==0:
            return
        import yaml
        data = yaml.safe_load(open(self.lineEdit_config_path.text(),'r'))
        bashCommand = "PumpServer {} -ORBendPoint giop:tcp::{} -nodb -dlist {}".format(data['server']['name'], data['server']['port'], data['server']['tangoname'])
        self.lineEdit_server_cmd.setText(bashCommand)

    def create_client_without_config(self):
        cmd = '{}:{}{}#dbase=no'.format(self.lineEdit_ip.text(),self.lineEdit_port.text(),self.lineEdit_device_name.text())
        try:
            self.parent.client = psd.connect(cmd)
            self.parent.init_server_devices()
            self.parent.set_up_operations()
            self.parent.timer_syn_server_and_gui.start(100)
        except Exception as e:
            error_pop_up('Fail to start start client.'+'\n{}'.format(str(e)),'Error')

    def initialize_device(self, device_id, device_type):
        if device_type == 'syringe':
            valve = getattr(self,'comboBox_val_s{}'.format(device_id)).currentText()
            syringe = getattr(self.parent,'syringe_server_S{}'.format(device_id))
            syringe.initSyringe(valve, 200)
            # exec("self.parent.widget_psd.connect_status[device_id] = syringe.status['syringe'].__str__()")
            connect_status = self.parent.widget_psd.connect_status
            connect_status[device_id] = syringe.status['syringe'].__str__()
            # print(connect_status)
            self.parent.syn_server_and_gui_init(attrs = {'connect_status':connect_status})
            getattr(self,'lineEdit_status_s{}'.format(device_id)).setText(syringe.status['syringe'].__str__())
        elif device_type == 'mvp':
            self.parent.mvp_valve_server.initValve()
            self.parent.mvp_valve_server.join()
            self.lineEdit_status_mvp.setText(self.parent.mvp_valve_server.status['valve'].__str__())
            self.parent.pushButton_connect_mvp_syringe_1.click()
        else:
            pass
        self.parent.widget_psd.update()

    def initialize_all_device(self,device_ids, device_types):
        for device_id, device_type in zip(device_ids, device_types):
            self.initialize_device(device_id, device_type)

class MyMainWindow(QMainWindow):
    def __init__(self, parent = None):
        super(MyMainWindow, self).__init__(parent)
        #load GUI ui file made by qt designer
        ui_path = os.path.join(script_path,'psd_gui.ui')
        uic.loadUi(ui_path,self)
        self.connected_mvp_channel = None #like 'channel_1'
        self.fill_speed_syringe = 500 # global speed for filling syringe in ul/s
        self.client = None
        self.demo = True
        self.main_client_cloud = None
        self.listen = False
        self.msg_exchange_thread = QtCore.QThread()
        self.login_name = ''
        self.password = ''

        self.pump_settings = {}
        self.pushButton_apply_settings.clicked.connect(self.apply_pump_settings)
        self.apply_pump_settings()
        ##
        self.cam_frame_path = os.path.join(script_path,'images')
        self.widget_terminal.update_name_space('psd_widget',self.widget_psd)
        self.widget_terminal.update_name_space('main_gui',self)

        self.image = None
        self.frame_number = 0
        self.pushButton_catch_frame.clicked.connect(self.catch_frame)

        self.under_exchange = False

        self.actionfillSyringe.triggered.connect(self.fill_specified_syringe)
        self.actioninitTubeLine.triggered.connect(self.open_refill_dialog)
        self.actioninitExchange.triggered.connect(self.init_start)
        self.pushButton_exchange.setIcon(QtGui.QIcon(os.path.join(script_path,'icons','exchange.png')))
        self.pushButton_exchange.setIconSize(QtCore.QSize(50,50))
        self.pushButton_exchange.clicked.connect(self.start_exchange)
        self.actionExchange.triggered.connect(self.start_exchange)

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

        self.actionStartPumpClient.triggered.connect(self.start_pump_client_dialog)
        self.actionStartServer.triggered.connect(self.start_server_dialog)
        self.pushButton_connect_cloud.clicked.connect(self.start_mongo_client_cloud)
        self.pushButton_listen.clicked.connect(self.start_listening_cloud)
        self.pushButton_stop_listen.clicked.connect(self.stop_listening_cloud)

        self.actionStop_all_motions.triggered.connect(self.stop_all_motion)
        self.shortcut_stop = QShortcut(QtGui.QKeySequence("Ctrl+C"), self)
        self.shortcut_stop.activated.connect(self.stop_all_motion)
        self.actionReset_resevoir_and_waste_volume.triggered.connect(self.reset_exchange)
        self.doubleSpinBox.valueChanged.connect(self.update_speed)
        self.update_speed()
        self.label_cam.setScaledContents(True)

        #reset cell volume as wish
        self.actionReset_Cell_Vol.triggered.connect(self.reset_cell_vol)
        #cleaner dialog pop up
        self.actioncleaner.triggered.connect(self.onCleanerClicked)

        self.actionshowSettingFrame.triggered.connect(self.display_setting_frame)
        self.actionhideSettingFrame.triggered.connect(self.hide_setting_frame)

        #fill the button with icon
        self.pushButton_fill_init_mode.setIcon(QtGui.QIcon(os.path.join(script_path,'icons','big_drop.png')))
        self.pushButton_fill_init_mode.setIconSize(QtCore.QSize(50,50))
        self.pushButton_fill_init_mode.clicked.connect(self.dispense_init_mode)
        self.actionPuffMeniscus.triggered.connect(self.dispense_init_mode)

        self.pushButton_dispense_init_mode.setIcon(QtGui.QIcon(os.path.join(script_path,'icons','small_drop.png')))
        self.pushButton_dispense_init_mode.setIconSize(QtCore.QSize(50,50)) 
        self.pushButton_dispense_init_mode.clicked.connect(self.pickup_init_mode)
        self.actionShrinkMeniscus.triggered.connect(self.pickup_init_mode)

        self.pushButton_start_webcam.clicked.connect(self.start_webcam)
        self.pushButton_stop_webcam.clicked.connect(self.stop_webcam)

        self.pushButton_load_config.clicked.connect(self.load_setting_table)
        self.pushButton_save_config.clicked.connect(self.save_setting_table)

        #timer to check whether or not the server devices are busy
        #if not busy, stop the init mode and resume the simple exchange mode
        #used to perform droplet adjustment during simple exchange mode
        self.timer_check_device_busy = QTimer(self)
        self.timer_check_device_busy.timeout.connect(self.check_server_devices_busy_init_mode_to_simple_mode)

        ##timmer to syn gui meta status to client config
        self.timer_syn_server_and_gui = QTimer(self)
        # self.timer_syn_server_and_gui.timeout.connect(self.syn_server_and_gui)

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
        self.timer_prepressure_S1 = QTimer(self)
        self.timer_prepressure_S2 = QTimer(self)
        self.timer_droplet_adjustment_S1 = QTimer(self)
        self.timer_droplet_adjustment_S2 = QTimer(self)
        self.timer_droplet_adjustment_S3 = QTimer(self)
        self.timer_droplet_adjustment_S4 = QTimer(self)
        self.timer_droplet_adjustment_on_the_fly = QTimer(self)
        self.timer_droplet_adjustment_on_the_fly.timeout.connect(self.check_elapsed_time)
        self.deadlinetimer_droplet_adjustment_on_the_fly = QDeadlineTimer()
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

        self.timers = [self.timer_prepressure_S1, self.timer_prepressure_S2, self.timer_droplet_adjustment_S1, self.timer_droplet_adjustment_S2, self.timer_droplet_adjustment_S3, self.timer_droplet_adjustment_S4, self.timer_update_simple, self.timer_update_simple_pre, self.timer_update_fill_half_mode,  self.timer_update,self.timer_update_normal_mode, self.timer_update_init_mode, self.timer_update_fill_cell, self.timer_clean_S1, self.timer_clean_S2, self.timer_clean_S3, self.timer_clean_S4]
        self.timers_partial = [self.timer_update_simple_pre, self.timer_update_fill_half_mode, self.timer_update_normal_mode, self.timer_update_init_mode]

        self.syn_valve_pos()

    def syn_server_and_gui_init(self,attrs):
        if self.client == None:
            return
        config = self.client.configuration
        for key, value in attrs.items():
            config['psd_widget'][key] = value
        self.client.configuration = config

    def syn_server_and_gui(self):
        running = False
        for each_timer in self.timers:
            if each_timer.isActive():
                running = True
                break
        if running:#update gui info in the server config
            gui_info = {
                        'cell_vol':str(round(self.widget_psd.volume_of_electrolyte_in_cell,3)),
                        'mvp_valve': self.widget_psd.mvp_channel,
                        'resevoir_vol': str(round(self.widget_psd.resevoir_volumn,3)),
                        'waste_vol': str(round(self.widget_psd.waste_volumn,3)),
                        'operation_mode': self.widget_psd.operation_mode,
                        'connect_status':self.widget_psd.connect_status,
                        'filling_status':{1:self.widget_psd.filling_status_syringe_1,
                                          2:self.widget_psd.filling_status_syringe_2,
                                          3:self.widget_psd.filling_status_syringe_3,
                                          4:self.widget_psd.filling_status_syringe_4},
                        'resume_advance_exchange':self.advanced_exchange_operation.resume
                        }
            self.syn_server_and_gui_init(gui_info)
        else:#pull gui info from server config
            configuration = self.client.configuration['psd_widget']
            self.widget_psd.volume_syringe_1 = float(self.server_devices['syringe'][1].volume/1000)
            self.widget_psd.volume_syringe_2 = float(self.server_devices['syringe'][2].volume/1000)
            self.widget_psd.volume_syringe_3 = float(self.server_devices['syringe'][3].volume/1000)
            self.widget_psd.volume_syringe_4 = float(self.server_devices['syringe'][4].volume/1000)
            self.widget_psd.connect_valve_port = {1:self.server_devices['syringe'][1].valve,2:self.server_devices['syringe'][2].valve,3:self.server_devices['syringe'][3].valve,4:self.server_devices['syringe'][4].valve}
            self.widget_psd.volume_of_electrolyte_in_cell = float(configuration.get('cell_vol',0))
            self.widget_psd.mvp_channel = configuration.get('mvp_valve',1)
            self.widget_psd.resevoir_volumn = float(configuration.get('resevoir_vol',250))
            self.widget_psd.waste_volumn = float(configuration.get('waste_vol',0))
            self.widget_psd.operation_mode = configuration.get('operation_mode','not_ready_mode')
            self.widget_psd.connect_status = configuration.get('connect_status',{1:'disconnected',2:'disconnected',3:'disconnected',4:'disconnected', 'mvp': 'disconnected'})
            self.widget_psd.filling_status_syringe_1 = configuration.get('filling_status')[1]
            self.widget_psd.filling_status_syringe_2 = configuration.get('filling_status')[2]
            self.widget_psd.filling_status_syringe_3 = configuration.get('filling_status')[3]
            self.widget_psd.filling_status_syringe_4 = configuration.get('filling_status')[4]
            self.advanced_exchange_operation.resume = configuration.get('resume_advance_exchange')
            self.widget_psd.update()

    def start_mongo_client_cloud(self):
        if self.lineEdit_database_name.text()=='':
            return
        try:
            self.mongo_client = MongoClient(f"mongodb+srv://{self.login_name}:{self.password}@cluster0.sjw9m.mongodb.net/<dbname>?retryWrites=true&w=majority")
            self.database = self.mongo_client[self.lineEdit_database_name.text()]
            self.database.client_info.delete_one({'client_id':self.lineEdit_current_client.text()})
            if self.lineEdit_current_client.text()==self.lineEdit_main_client.text():
                self.main_client_cloud = True
                self.database.device_info.drop()
            else:
                self.main_client_cloud = False
                self.database.cmd_info.drop()
            self.database.client_info.insert_one({'client_id':self.lineEdit_current_client.text(),
                                    'main_client':self.lineEdit_main_client.text()==self.lineEdit_current_client.text(),
                                    'paired_client_id':self.lineEdit_paired_client.text()
                                    })
            self.init_mongo_DB()
            error_pop_up('Success connection to MongoDB atlas cloud!','Information')
        except Exception as e:
            error_pop_up('Fail to start mongo client.'+'\n{}'.format(str(e)),'Error')

    def init_mongo_DB(self):
        if self.main_client_cloud:
            self.send_cmd_remotely = False
            device_info = {
                           'client_id':self.lineEdit_current_client.text(),
                           'S1_vol': str(self.widget_psd.volume_syringe_1),
                           'valve_pos':str(self.widget_psd.connect_valve_port),
                           'S2_vol': str(self.widget_psd.volume_syringe_2),
                           'S3_vol': str(self.widget_psd.volume_syringe_3),
                           'S4_vol': str(self.widget_psd.volume_syringe_4),
                           'cell_vol':str(self.widget_psd.volume_of_electrolyte_in_cell),
                           'mvp_valve': str(self.widget_psd.mvp_channel),
                           'resevoir_vol': str(self.widget_psd.resevoir_volumn),
                           'waste_vol': str(self.widget_psd.waste_volumn),
                           'operation_mode': self.widget_psd.operation_mode,
                           'connect_status':str(self.widget_psd.connect_status)}
            self.database.device_info.delete_one({'client_id':self.lineEdit_current_client.text()})
            self.database.device_info.insert_one(device_info)
            self.database.response_info.delete_one({'client_id':self.lineEdit_current_client.text()})
            self.database.response_info.insert_one({'response':'','client_id':self.lineEdit_current_client.text()})
            try:
                self.database.cmd_info.delete_one({'client_id':self.lineEdit_paired_client.text()})
            except:
                pass
            self.database.cmd_info.insert_one({'cmd':'','client_id':self.lineEdit_paired_client.text()})
        else:
            #self.timer_renew_device_info_gui.start(100)
            self.send_cmd_remotely = True
            try:
                self.database.cmd_info.delete_one({'client_id':self.lineEdit_current_client.text()})
            except:
                pass
            self.database.cmd_info.insert_one({'cmd':'','client_id':self.lineEdit_current_client.text()})
        self.msg_exchange = MessageExchanger(self)
        self.msg_exchange.moveToThread(self.msg_exchange_thread)
        self.msg_exchange_thread.started.connect(self.msg_exchange.exchange_info)
        self.msg_exchange.exec_cmd.connect(self._exec_cmd)

    @QtCore.pyqtSlot(str)
    def _exec_cmd(self, cmd_string):
        now = datetime.now().strftime("%H:%M:%S")
        try:
            self.textEdit_response.setPlainText('{}:cmd [{}] requested by client: {}'.format(now,cmd_string,self.lineEdit_paired_client.text()))
            exec(cmd_string)
            self.database.response_info.update_one({'client_id':self.lineEdit_current_client.text()},{"$set": {"response":'{}:Success to execute cmd: {} from {}'.format(now,cmd_string,self.lineEdit_paired_client.text())}})
        except Exception as e:
            self.textEdit_response.setPlainText('{}:cmd [{}] requested by {}'.format(now,cmd_string,self.lineEdit_paired_client.text()))
            self.database.response_info.update_one({'client_id':self.lineEdit_current_client.text()},{"$set": {"response":'{}:{}'.format(now,str(e))}})
        # finally:
        self.database.cmd_info.update_one({'client_id':self.lineEdit_paired_client.text()},{"$set": {"cmd":''}})
            #self.exec_cmd_from_cloud()

    #update response string from main client
    def _update_response(self):
        try:
            self.textEdit_response.setPlainText(self.database.response_info.find_one({'client_id':self.lineEdit_paired_client.text()})['response'])
        except:
            pass

    def start_listening_cloud(self):
        self.listen = True
        self.lineEdit_listen_status.setText('Listening now!')
        self.msg_exchange_thread.start()
        if not self.main_client_cloud:
            self.timer_update_response = QTimer(self)
            self.timer_update_response.timeout.connect(self._update_response)
            self.timer_update_response.start(500)

    def stop_listening_cloud(self):
        self.listen = False
        self.msg_exchange_thread.terminate()
        if not self.main_client_cloud:
            try:
                self.timer_update_response.stop()
            except:
                print('Cannot stop timer:{}!'.format('timer_update_response'))

    def send_cmd_to_cloud(self, cmd_string):
        self.database.cmd_info.update_one({'client_id':self.lineEdit_current_client.text()},{"$set": {"cmd":cmd_string}})

    def exec_cmd_from_cloud(self):
        target = self.database.cmd_info.find_one({'client_id':self.lineEdit_paired_client.text()})
        if target == None:
            pass
        if target['cmd'] != '':
            try:
                exec(target['cmd'])
                self.database.response_info.update_one({'client_id':self.lineEdit_current_client.text()},{"$set": {"response":'Success to execute cmd: {}'.format(cmd_string)}})
                self.textEdit_response.setPlainText('Success to execute cmd: {}'.format(target['cmd']))
            except Exception as e:
                self.database.response_info.update_one({'client_id':self.lineEdit_current_client.text()},{"$set": {"response":str(e)}})
                self.textEdit_response.setPlainText(str(e))
            else:
                self.database.cmd_info.update_one({'client_id':self.lineEdit_current_client.text()},{"$set": {"cmd":''}})
        else:
            pass

    def make_cmd_list_during_exchange(self):
        cmd_list = [
                    'self.doubleSpinBox.setValue({})'.format(self.doubleSpinBox.value()),
                    'self.doubleSpinBox_exchange_amount.setValue({})'.format(self.doubleSpinBox_exchange_amount.value()),
                    'self.spinBox_speed.setValue({})'.format(self.spinBox_speed.value()),
                    "self.lineEdit_default_speed.setText('{}')".format(self.lineEdit_default_speed.text()),
                    "self.comboBox_exchange_mode.setCurrentText('{}')".format(self.comboBox_exchange_mode.currentText()),
                    'self.spinBox_amount.setValue({})'.format(self.spinBox_amount.value()),
                    'self.doubleSpinBox_prepresure_vol.setValue({})'.format(self.doubleSpinBox_prepresure_vol.value()),
                    'self.doubleSpinBox_prepressure_rate.setValue({})'.format(self.doubleSpinBox_prepressure_rate.value()),
                    'self.doubleSpinBox_leftover_vol.setValue({})'.format(self.doubleSpinBox_leftover_vol.value()),
                    'self.checkBox_auto.setChecked({})'.format(self.checkBox_auto.isChecked())
                    ]
        #self.send_cmd_to_cloud('\n'.join(cmd_list))
        return cmd_list


    def update_valve_on_GUI(self,syringe_num = 1, valve_pos = None):
        if valve_pos not in ['up', 'left', 'right']:
            return
        comboBox_name = 'comboBox_valve_port_{}'.format(syringe_num)
        combo = getattr(self, comboBox_name)
        if combo.currentText() == valve_pos:
            return
        else:
            combo.setCurrentText(valve_pos)

    def hide_setting_frame(self):
        '''
        size = self.frame_2.size()
        self.frame_2.setVisible(False)
        self.frame.resize(size)
        '''
        self.tabWidget_settings.hide()

    def display_setting_frame(self):
        # self.frame_2.setVisible(True)
        self.tabWidget_settings.show()

    def start_pump_client_dialog(self):
        dlg = StartPumpClientDialog(self)
        dlg.exec()

    def start_server_dialog(self):
        dlg = StartServerDialog(self)
        dlg.exec()

    def run_server(self, instance_name, port, device_name, tango_db = False):
        bashCommand = "PumpServer {} -ORBendPoint giop:tcp::{} -nodb -dlist {}".format(instance_name, port, device_name)
        bashCommand_db = "PumpServer {}".format(instance_name)
        if tango_db:
            try:
                process = subprocess.Popen(bashCommand_db.split(), stdout=subprocess.PIPE)
                output, error = process.communicate()
                error_pop_up('\n'.join([str(output),str(error)]), ['Information','Error'][int(error=='')])
            except Exception as e:
                error_pop_up('Fail to start start server.'+'\n{}'.format(str(e)),'Error')
        else:
            try:
                process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
                output, error = process.communicate()
                error_pop_up('\n'.join([str(output),str(error)]), ['Information','Error'][int(error=='')])
            except Exception as e:
                error_pop_up('Fail to start start server.'+'\n{}'.format(str(e)),'Error')

    def create_pump_client(self, config_file = None, device_name = None, config_use = True):
        if config_use:
            assert config_file!=None, 'Specify config file first!'
            try:
                self.client = psd.fromFile(config_file)
                self.client.readConfigfile(config_file)
                self.init_server_devices()
                self.set_up_operations()
            except Exception as e:
                error_pop_up('Fail to start start client.'+'\n{}'.format(str(e)),'Error')
        else:
            assert device_name!=None, 'Specify device_name first!'
            try:
                self.client = psd.connect(device_name)
                self.init_server_devices()
                self.set_up_operations()
            except Exception as e:
                error_pop_up('Fail to start start client.'+'\n{}'.format(str(e)),'Error')

    def syn_valve_pos(self):
        #syn T valve position between widget_psd and the GUI comboBOx
        for each_key in self.widget_psd.connect_valve_port:
            exec(f"self.comboBox_valve_port_{each_key}.setCurrentText('{self.widget_psd.connect_valve_port[each_key]}')")

    def init_server_devices(self):
        if self.demo:
            self.server_devices = {'syringe': {1:None,2:None, 3:None, 4:None},\
                                'T_valve': {1:None,2:None,3:None,4:None},\
                                'mvp_valve': None,\
                                'exchange_pair':{'S1_S4':None, 'S2_S3':None},
                                'server':None}
        else:
            #self.psd_server = PumpController()
            self.syringe_server_S1 = self.client.getSyringe(4)#PSD4_smooth(self.psd_server,1, 12500)
            self.syringe_server_S2 = self.client.getSyringe(2)#PSD4_smooth(self.psd_server,3, 12500)
            self.syringe_server_S3 = self.client.getSyringe(3)#PSD4_smooth(self.psd_server,4, 12500)
            self.syringe_server_S4 = self.client.getSyringe(1)#PSD4_smooth(self.psd_server,2, 12500)

            self.valve_server_S1 = self.syringe_server_S1
            self.valve_server_S2 = self.syringe_server_S2
            self.valve_server_S3 = self.syringe_server_S3
            self.valve_server_S4 = self.syringe_server_S4
            self.set_valve_pos_alias(valve_devices = [self.valve_server_S1,self.valve_server_S2,self.valve_server_S3,self.valve_server_S4])
            # [each.initSyringe(2,200) for each in [self.valve_server_S1,self.valve_server_S2,self.valve_server_S3,self.valve_server_S4]]
            # for i in range(1,5):
                # exec("self.widget_psd.connect_status[i] = self.syringe_server_S{}.status['syringe'].__str__()".format(i))
            self.widget_psd.update()
            self.mvp_valve_server = self.client.getValve(5)
            # self.mvp_valve_server.initValve()

            self.exchange_pair_S2_and_S4 = self.client.operations['Exchanger 1']
            self.exchange_pair_S1_and_S3 = self.client.operations['Exchanger 2']

            self.server_devices = {'syringe': {1:self.syringe_server_S1,2:self.syringe_server_S2, 3:self.syringe_server_S3, 4:self.syringe_server_S4},\
                                'T_valve': {1:self.valve_server_S1,2:self.valve_server_S2,3:self.valve_server_S3,4:self.valve_server_S4},\
                                'mvp_valve': self.mvp_valve_server,\
                                'exchange_pair':{'S1_S3':self.exchange_pair_S1_and_S3, 'S2_S4':self.exchange_pair_S2_and_S4},
                                'client':self.client
                                  }
        self.widget_terminal.update_name_space('server_devices',self.server_devices)

    def set_under_exchange_to_false(self):
        self.under_exchange = False

    def set_up_operations(self):
        #pushing electrolyte to cell or pulling it out (miniscus size adjustment)
        self.init_operation = initOperationMode(self.server_devices, self.widget_psd,self.textBrowser_error_msg, None, self.timer_update_init_mode, 100, self.pump_settings, \
                                                settings = {'pull_syringe_handle':self.get_pulling_syringe_init_mode,
                                                            'push_syringe_handle':self.get_pushing_syringe_init_mode,
                                                            'vol_handle':self.spinBox_amount.value,
                                                            'speed_handle':self.spinBox_speed.value}, demo = self.demo)

        #operation of single syringe pump in reasonable way (e.g. NOT reasonable: you are not allowed to withdraw electrolyte from waste)
        self.normal_operation = normalOperationMode(self.server_devices, self.widget_psd,self.textBrowser_error_msg, None, self.timer_update_normal_mode, 100, self.pump_settings, \
                                                settings = {'syringe_handle':self.get_syringe_index_handle_normal_mode,
                                                            'valve_position_handle':self.get_valve_position_handle_normal_mode,
                                                            'valve_connection_handle':self.get_valve_connection_handle_normal_mode,
                                                            'vol_handle':self.get_vol_handle_normal_mode,
                                                            'speed_handle':self.get_speed_handle_normal_mode}, demo = self.demo)
        #automatically exchange mode (two pairs of pumps alternate to fill the cell)
        self.advanced_exchange_operation = advancedRefillingOperationMode(self.server_devices, self.widget_psd, self.textBrowser_error_msg, self.timer_update_fill_half_mode, self.timer_update, 100, self.pump_settings, \
                                                settings = {'premotion_speed_handle':self.get_default_filling_speed,
                                                            'total_exchange_amount_handle':lambda:self.doubleSpinBox_exchange_amount.value()/1000,
                                                            'exchange_speed_handle':lambda:self.doubleSpinBox.value()/1000,
                                                            'pre_pressure_volume_handle':lambda:self.doubleSpinBox_prepresure_vol.value()/1000.,
                                                            'pre_pressure_speed_handle':lambda:self.doubleSpinBox_prepressure_rate.value()/1000.,
                                                            'leftover_volume_handle':lambda:self.doubleSpinBox_leftover_vol.value()/1000.,
                                                            'refill_speed_handle':self.get_default_filling_speed,
                                                            'time_record_handle':self.display_exchange_time,
                                                            'volume_record_handle':self.display_exchange_volume,
                                                            'extra_amount_timer':self.timer_extra_amount,
                                                            'extra_amount_handle':self.spinBox_amount.value,
                                                            'extra_amount_speed_handle':self.spinBox_speed.value,
                                                            'timer_prepressure_S1':self.timer_prepressure_S1,
                                                            'timer_prepressure_S2':self.timer_prepressure_S2,
                                                            'timer_droplet_adjustment_S1':self.timer_droplet_adjustment_S1,
                                                            'timer_droplet_adjustment_S2':self.timer_droplet_adjustment_S2,
                                                            'timer_droplet_adjustment_S3':self.timer_droplet_adjustment_S3,
                                                            'timer_droplet_adjustment_S4':self.timer_droplet_adjustment_S4,
                                                            'valve_handle': self.update_valve_on_GUI,
                                                            'set_under_exchange_to_false': self.set_under_exchange_to_false,
                                                            }, demo = self.demo)

        #only one pair of pumps responsible for electrolyte eschange (will automatically refill the syringe once empty)
        self.simple_exchange_operation = simpleRefillingOperationMode(self.server_devices, self.widget_psd,self.textBrowser_error_msg, self.timer_update_simple_pre, self.timer_update_simple, 100, self.pump_settings, \
                                                settings = {'pull_syringe_handle':self.get_pulling_syringe_simple_exchange_mode,
                                                            'total_exchange_amount_handle':lambda:self.doubleSpinBox_exchange_amount.value()/1000,
                                                            'pre_pressure_volume_handle':lambda:self.doubleSpinBox_prepresure_vol.value()/1000.,
                                                            'pre_pressure_speed_handle':lambda:self.doubleSpinBox_prepressure_rate.value()/1000.,
                                                            'leftover_volume_handle':lambda:self.doubleSpinBox_leftover_vol.value()/1000.,
                                                            'push_syringe_handle':self.get_pushing_syringe_simple_exchange_mode,
                                                            'refill_speed_handle':self.get_default_filling_speed,
                                                            'volume_record_handle':self.display_exchange_volume,
                                                            'timer_prepressure':QTimer(self),
                                                            'valve_handle': self.update_valve_on_GUI,
                                                            'set_under_exchange_to_false': self.set_under_exchange_to_false,
                                                            'exchange_speed_handle':lambda:self.doubleSpinBox.value()/1000}, demo = self.demo)

        #fill the tubing line (to waste then to cell for specified cycles)
        self.fill_cell_operation = fillCellOperationMode(self.server_devices, self.widget_psd,self.textBrowser_error_msg, None, self.timer_update_fill_cell, 100, self.pump_settings, \
                                                settings = {'push_syringe_handle':self.get_pushing_syringe_fill_cell_mode,
                                                            'refill_speed_handle':self.get_refill_speed_fill_cell_mode,
                                                            'refill_times_handle':self.get_refill_times_fill_cell_mode,
                                                            'waste_disposal_vol_handle':self.get_vol_to_waste_fill_cell_mode,
                                                            'waste_disposal_speed_handle':self.get_disposal_speed_fill_cell_mode,
                                                            'cell_dispense_vol_handle':self.get_vol_to_cell_fill_cell_mode},
                                                            demo = self.demo)

        #the following four modes are for cleaning purpose for each pump
        self.clean_operation_S1 = cleanOperationMode(self.server_devices, self.widget_psd,self.textBrowser_error_msg, None, self.timer_clean_S1, 100, self.pump_settings, \
                                                settings = {'syringe_handle':lambda:1,
                                                            'refill_speed_handle':lambda:self.get_refill_speed_clean_mode(1),
                                                            'refill_times_handle':lambda:self.get_refill_times_clean_mode(1),
                                                            'holding_time_handle':lambda:self.get_holding_time_clean_mode(1),
                                                            'inlet_port_handle':lambda:self.get_inlet_port_clean_mode(1),
                                                            'outlet_port_handle':lambda:self.get_outlet_port_clean_mode(1)}, demo = self.demo)

        self.clean_operation_S2 = cleanOperationMode(self.server_devices, self.widget_psd,self.textBrowser_error_msg, None, self.timer_clean_S2, 100, self.pump_settings, \
                                                settings = {'syringe_handle':lambda:2,
                                                            'refill_speed_handle':lambda:self.get_refill_speed_clean_mode(2),
                                                            'refill_times_handle':lambda:self.get_refill_times_clean_mode(2),
                                                            'holding_time_handle':lambda:self.get_holding_time_clean_mode(2),
                                                            'inlet_port_handle':lambda:self.get_inlet_port_clean_mode(2),
                                                            'outlet_port_handle':lambda:self.get_outlet_port_clean_mode(2)}, demo = self.demo)

        self.clean_operation_S3 = cleanOperationMode(self.server_devices, self.widget_psd,self.textBrowser_error_msg, None, self.timer_clean_S3, 100, self.pump_settings, \
                                                settings = {'syringe_handle':lambda:3,
                                                            'refill_speed_handle':lambda:self.get_refill_speed_clean_mode(3),
                                                            'refill_times_handle':lambda:self.get_refill_times_clean_mode(3),
                                                            'holding_time_handle':lambda:self.get_holding_time_clean_mode(3),
                                                            'inlet_port_handle':lambda:self.get_inlet_port_clean_mode(3),
                                                            'outlet_port_handle':lambda:self.get_outlet_port_clean_mode(3)}, demo = self.demo)

        self.clean_operation_S4 = cleanOperationMode(self.server_devices, self.widget_psd,self.textBrowser_error_msg, None, self.timer_clean_S4, 100, self.pump_settings, \
                                                settings = {'syringe_handle':lambda:4,
                                                            'refill_speed_handle':lambda:self.get_refill_speed_clean_mode(4),
                                                            'refill_times_handle':lambda:self.get_refill_times_clean_mode(4),
                                                            'holding_time_handle':lambda:self.get_holding_time_clean_mode(4),
                                                            'inlet_port_handle':lambda:self.get_inlet_port_clean_mode(4),
                                                            'outlet_port_handle':lambda:self.get_outlet_port_clean_mode(4)}, demo = self.demo)
    def get_default_filling_speed(self):
        return float(self.lineEdit_default_speed.text())/1000

    def fill_specified_syringe(self):
        syringe, done = QInputDialog.getInt(self, 'Pick the syringe', 'Enter the syringe_index (integer from 1 to 4):',value = 1)
        if not done:
            error_pop_up('Error in getting syringe index from pop-up dialog!')
        else:
            if syringe not in [1,2,3,4]:
                error_pop_up('Invalid syringe index, must be an integer from 1 to 4!')
            else:
                cmd_list = [
                            f'self.doubleSpinBox_speed_normal_mode_{syringe}.setValue({float(self.lineEdit_default_speed.text())})',
                            f'self.doubleSpinBox_stroke_factor_{syringe}.setValue(12500)',
                            f"self.comboBox_valve_port_{syringe}.setCurrentText('left')",
                            f'self.pushButton_fill_syringe_{syringe}.click()'
                           ]

                if self.main_client_cloud!=None:
                    if not self.main_client_cloud:
                        self.send_cmd_to_cloud('\n'.join(cmd_list))
                    else:
                        for each in cmd_list:
                            exec(each)
                else:
                    for each in cmd_list:
                        exec(each)

    #set the alias for three T valve channel, double check the correctness of the mapping relationship
    def set_valve_pos_alias(self, valve_devices):
        for each in valve_devices:
            each.setValvePosName(1,'left')
            each.setValvePosName(2,'up')
            each.setValvePosName(3,'right')

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
        volume, done = QInputDialog.getInt(self, 'Reset the cell volume', 'Enter the cell volume (ul) you want to set to:',value = 100)
        if not done:
            error_pop_up('Error in setting the cell volume!')
        else:
            self.syn_server_and_gui_init(attrs = {'cell_vol':volume/1000})
            self.widget_psd.volume_of_electrolyte_in_cell = volume/1000
            self.widget_psd.update()

    def onCleanerClicked(self):
        dlg = Cleaner(self)
        dlg.exec()

    def display_exchange_time(self):
        pass
    
    def empty_func(self):
        pass

    def display_exchange_volume(self, vol):
        self.statusbar.clearMessage()
        self.statusbar.showMessage('Exchange vol: {} ul'.format(vol))

    def get_pushing_syringe_fill_cell_mode(self):
        syringe = self.widget_psd.actived_syringe_fill_cell_mode
        if syringe not in [1,2,3,4]:
            error_pop_up('Error: The syringe index {} is wrongly set, please reset the syringe index from [1,2,3,4]!'.format(syringe))
        else:
            for each in self.pump_settings:
                #The syringe must connect to the cell_inlet in the setting table
                if (self.pump_settings[each]=='cell_inlet') and ('S{}'.format(syringe) in each):
                    return syringe
            error_pop_up('Error: The selected syringe is not supposed to pushing solution to cell, but used as waste syringe. Pick a different syringe!')

    def get_refill_speed_fill_cell_mode(self):
        speed = self.widget_psd.refill_speed_fill_cell_mode
        if speed<0:
            speed = 0
        return speed

    def get_disposal_speed_fill_cell_mode(self):
        speed = self.widget_psd.disposal_speed_fill_cell_mode
        if speed<0:
            speed = 0
        return speed

    def get_vol_to_cell_fill_cell_mode(self):
        return self.widget_psd.vol_to_cell_fill_cell_mode

    def get_vol_to_waste_fill_cell_mode(self):
        return self.widget_psd.vol_to_waste_fill_cell_mode

    def get_refill_times_fill_cell_mode(self):
        times = int(self.widget_psd.refill_times_fill_cell_mode)
        if times<0:
            times = 0
        return times

    def get_pulling_syringe_init_mode(self):
        return self.get_pulling_syringe_simple_exchange_mode()

    def get_pushing_syringe_init_mode(self):
        return self.get_pushing_syringe_simple_exchange_mode()

    def get_pulling_syringe_simple_exchange_mode(self):
        if self.widget_psd.mvp_channel not in [1,2]:
            error_pop_up('MVP not in the right position, should be either 1 or 2!','error')
            return None 
        else:
            return {1:3,2:4}[self.widget_psd.mvp_channel]

    def get_pushing_syringe_simple_exchange_mode(self):
        if self.widget_psd.mvp_channel not in [1,2]:
            error_pop_up('MVP not in the right position, should be either 1 or 2!','error')
            return None
        else:
            return self.widget_psd.mvp_channel 

    def update_cell_volume(self):
        self.widget_psd.cell_volume_in_total = self.spinBox_cell_volume.value()

    def get_syringe_index_handle_normal_mode(self):
        radioButtons = [getattr(self, 'radioButton_syringe_{}'.format(i)) for i in range(1,16) if hasattr(self, 'radioButton_syringe_{}'.format(i))]
        for i in range(0,len(radioButtons)):
            if radioButtons[i].isChecked():
                return int(i+1)
        error_pop_up('No radioButton has been clicked! Click one button to activate normal mode!')

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
        #self.

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
                error_pop_up('\nError due to {} out of limits: within {} but now {}'.format(each,self.widget_psd,each,limits[each],value))
                self.tabWidget.setCurrentIndex(2) 
                # self.timer_check_limit.stop()
                break
            elif value>limits[each][1]:
                setattr(self.widget_psd,each,limits[each][1])
                self.stop_all_motion()
                error_pop_up('\nError due to {} out of limits: within {} but now {}'.format(each,self.widget_psd,each,limits[each],value))
                # logging.getLogger().exception('\nError due to {} out of limits: '.format(each))
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
        self.advanced_exchange_operation.resume = True
        for timer in self.timers:
            if timer.isActive():
                timer.stop()

    def check_any_timer(func):
        @functools.wraps(func)
        def wrapper_func(self, *args, **kwargs):
            for timer in self.timers:
                if timer.isActive():
                    error_pop_up('Error: some timer is running now. Stop it before you can make this move!')
                    self.tabWidget.setCurrentIndex(2)
                    return
            return func(self, *args, **kwargs)
        return wrapper_func

    def check_any_timer_except_exchange(func):
        @functools.wraps(func)
        def wrapper_func(self, *args, **kwargs):
            for timer in self.timers_partial:
                if timer.isActive():
                    error_pop_up('Error: some timer is running now. Stop it before you can make this move!')
                    self.tabWidget.setCurrentIndex(2)
                    return
            return func(self, *args, **kwargs)
        return wrapper_func

    def init_start(self):
        if self.comboBox_exchange_mode.currentText() == 'Continuous':
            # self.init_start_advance()
            # self.advanced_exchange_operation.resume = False
            if self.main_client_cloud!=None:
                if not self.main_client_cloud:
                    cmd_list_widget = self.make_cmd_list_during_exchange()
                    self.send_cmd_to_cloud('\n'.join(cmd_list_widget + ['self.init_start_advance()','self.advanced_exchange_operation.resume = False']))
                else:
                    self.init_start_advance()
                    self.advanced_exchange_operation.resume = False
            else:
                self.init_start_advance()
                self.advanced_exchange_operation.resume = False

        elif self.comboBox_exchange_mode.currentText() == 'Intermittent':
            #self.init_start_simple()
            if self.main_client_cloud!=None:
                if not self.main_client_cloud:
                    cmd_list_widget = self.make_cmd_list_during_exchange()
                    self.send_cmd_to_cloud('\n'.join(cmd_list_widget + ['self.init_start_simple()']))
                else:
                    self.init_start_simple()
            else:
                self.init_start_simple()

    # @check_any_timer
    def init_start_advance(self):
        self.textBrowser_error_msg.setText('')
        #check the cell volume first
        if self.widget_psd.volume_of_electrolyte_in_cell < 0.1:
            error_pop_up('Error: Not enough electrolyte in cell. Please fill some solution in the cell first!')
            self.tabWidget.setCurrentIndex(1) 
        else:
            if self.check_connection_for_advanced_auto_refilling():
                self.advanced_exchange_operation.start_premotion_timer()

    # @check_any_timer
    def init_start_simple(self):
        self.textBrowser_error_msg.setText('')
        if self.widget_psd.volume_of_electrolyte_in_cell < 0.1:
            error_pop_up('Error: Not enough electrolyte in cell. Please fill some solution in the cell first!')
            self.tabWidget.setCurrentIndex(2) 
        else:
            self.simple_exchange_operation.start_premotion_timer()

    def open_refill_dialog(self):
        dlg = RefillCellSetup(self)
        dlg.exec()

    # @check_any_timer
    def start_fill_cell(self,kwargs =1):
        self.fill_cell_operation.start_timer_motion()

    def start_exchange(self):
        # self.init_start()
        self.under_exchange = True
        if self.comboBox_exchange_mode.currentText() == 'Continuous':
            if self.main_client_cloud!=None:
                if not self.main_client_cloud:
                    cmd_list_widget = self.make_cmd_list_during_exchange()
                    self.send_cmd_to_cloud('\n'.join(cmd_list_widget+['self.start_exchange_advance(not self.checkBox_auto.isChecked())']))
                else:
                    self.start_exchange_advance(not self.checkBox_auto.isChecked())
            else:
                self.start_exchange_advance(not self.checkBox_auto.isChecked())
        elif self.comboBox_exchange_mode.currentText() == 'Intermittent':
            if self.main_client_cloud!=None:
                if not self.main_client_cloud:
                    cmd_list_widget = self.make_cmd_list_during_exchange()
                    self.send_cmd_to_cloud('\n'.join(cmd_list_widget+['self.start_exchange_simple(not self.checkBox_auto.isChecked())']))
                else:
                    self.start_exchange_simple(not self.checkBox_auto.isChecked())
            else:
                self.start_exchange_simple(not self.checkBox_auto.isChecked())

    # @check_any_timer
    def start_exchange_advance(self, onetime):
        self.textBrowser_error_msg.setText('')
        #self.advanced_exchange_operation.resume = True
        self.advanced_exchange_operation.start_motion_timer(onetime)
        self.widget_psd.operation_mode = 'autorefilling_mode'

    # @check_any_timer
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
                error_pop_up('Connections error: something is not properly set up in your valve port connection for auto_refilling purpose\n{} must be connected to {} rather than {}'.format(each,_setting[each], self.pump_settings[each]))
                self.tabWidget.setCurrentIndex(1) 
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
        # self.cap = cv2.VideoCapture(int(self.lineEdit_camera_index.text()),cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            error_pop_up('\nOpenCV: camera failed to properly initialize! \nOpenCV: out device of bound: {}'.format(int(self.lineEdit_camera_index.text())))
            self.tabWidget.setCurrentIndex(1) 
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
        def _action():
            self.under_exchange = False
            for each in self.timers:
                if each==self.timer_update and each.isActive():
                    self.advanced_exchange_operation.resume = True
                    self.syn_server_and_gui_init(attrs = {'resume_advance_exchange':True})
                else:
                    pass
                try:
                    each.stop()
                except:
                    pass
            if not self.demo:
                self.client.stop()
                for i in range(1,5):
                    self.widget_psd.connect_status[i] = 'ready'
                    # setattr(self.widget_psd,'volume_syringe_{}'.format(i),round(self.server_devices['syringe'][i].volume,1))
                self.syn_server_and_gui_init(attrs = {'connect_status':{1:'ready',2:'ready',3:'ready',4:'ready','mvp':self.widget_psd.connect_status['mvp']}})
                self.widget_psd.update()
        if self.main_client_cloud!=None:
            if not self.main_client_cloud:
                self.send_cmd_to_cloud('self.stop_all_motion()')
            else:
                _action()
        else:
            _action()

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
        self.widget_psd.actived_syringe_normal_mode = syringe_no
        if self.under_exchange:
            pass
        else:
            self.widget_psd.operation_mode = 'normal_mode'
            valve_position = eval('self.comboBox_valve_port_{}.currentText()'.format(syringe_no))
            temp_valve_port = self.widget_psd.connect_valve_port
            temp_valve_port.update({syringe_no:valve_position})
            self.syn_server_and_gui_init(attrs = {'operation_mode':'normal_mode','valve_pos':temp_valve_port})
            self.widget_psd.connect_valve_port[self.widget_psd.actived_syringe_normal_mode] = valve_position
            key_for_pump_setting = 'S{}_{}'.format(syringe_no,valve_position)
            if not self.demo:
                exec("self.valve_server_S{}.valve = '{}'".format(syringe_no, valve_position))
                exec('self.valve_server_S{}.join()'.format(syringe_no))
            self.widget_psd.actived_syringe_valve_connection = self.pump_settings[key_for_pump_setting]
            self.widget_psd.update()

    # @check_any_timer
    def update_mvp_connection(self, syringe_no):
        self.textBrowser_error_msg.setText('')
        self.connected_mvp_channel = self.pump_settings['S{}_mvp'.format(syringe_no)]
        self.syn_server_and_gui_init(attrs = {'mvp_valve':syringe_no})
        self.widget_psd.mvp_channel = syringe_no
        self.widget_psd.mvp_connected_valve = 'S{}'.format(syringe_no)
        if not self.demo:
            self.mvp_valve_server.moveValve(syringe_no)
            self.mvp_valve_server.join()
        self.widget_psd.update()

    def add_solution_to_cell(self, amount):
        self.spinBox_speed_init_mode.setValue(int(self.spinBox_speed.value()))
        self.spinBox_volume_init_mode.setValue(int(amount))
        self.pickup_init_mode()

    def remove_solution_from_cell(self, amount):
        self.spinBox_speed_init_mode.setValue(int(self.spinBox_speed.value()))
        self.spinBox_volume_init_mode.setValue(int(amount))
        self.dispense_init_mode()

    @check_any_timer_except_exchange
    def pickup_init_mode(self,kwargs = None):
        self.textBrowser_error_msg.setText('')
        if self.timer_update.isActive():
            label = 'S{}_S{}'.format(*self.widget_psd.get_exchange_syringes_advance_exchange_mode())
            timeout = self.spinBox_amount.value()/self.spinBox_speed.value()*1000
            self.server_devices['exchange_pair'][label].pullSyr.rate = self.server_devices['exchange_pair'][label].rate + self.spinBox_speed.value()
            self.timer_droplet_adjustment_on_the_fly.start(10)
            self.deadlinetimer_droplet_adjustment_on_the_fly.setRemainingTime(timeout)
            # self.server_devices['exchange_pair'][label].decreaseVolume(volume = self.spinBox_amount.value(), rate = self.spinBox_speed.value())
        elif self.timer_update_simple.isActive():#if simple exchange mode actived
            pull_syringe_index = int(self.simple_exchange_operation.settings['pull_syringe_handle']())
            push_syringe_index = int(self.simple_exchange_operation.settings['push_syringe_handle']())
            label = f"S{push_syringe_index}_S{pull_syringe_index}"
            timeout = self.spinBox_amount.value()/self.spinBox_speed.value()*1000
            self.server_devices['exchange_pair'][label].pullSyr.rate = self.server_devices['exchange_pair'][label].rate + self.spinBox_speed.value()
            self.timer_droplet_adjustment_on_the_fly.start(10)
            self.deadlinetimer_droplet_adjustment_on_the_fly.setRemainingTime(timeout)
            # self.server_devices['exchange_pair'][label].decreaseVolume(volume = self.spinBox_amount.value(), rate = self.spinBox_speed.value())
        else:
            self.server_devices['client'].stop()
            self.stop_all_timers()
            self.widget_psd.actived_syringe_motion_init_mode = 'fill'
            self.init_operation.start_exchange_timer()

    def check_server_devices_busy_init_mode_to_simple_mode(self):
        #If any device is busy, then the device busy state is True
        this_timer = self.timer_check_device_busy
        connect_timer = self.init_operation.timer_motion
        post_action = lambda:self.simple_exchange_operation.start_motion_timer(not self.checkBox_auto.isChecked())
        busy = False
        for each in list(self.server_devices['syringe'].values()) + [self.server_devices['mvp_valve']]:
            if each.busy:
                busy = True
                break
        if not busy:
            this_timer.stop()
            connect_timer.stop()
            self.server_devices['client'].stop()
            post_action()

    @check_any_timer_except_exchange
    def dispense_init_mode(self, kwargs = None):
        self.textBrowser_error_msg.setText('')
        #puff droplet during advanced exchange
        if self.timer_update.isActive():
            label = 'S{}_S{}'.format(*self.widget_psd.get_exchange_syringes_advance_exchange_mode())
            timeout = self.spinBox_amount.value()/self.spinBox_speed.value()*1000
            self.server_devices['exchange_pair'][label].pushSyr.rate = self.server_devices['exchange_pair'][label].rate + self.spinBox_speed.value()
            self.timer_droplet_adjustment_on_the_fly.start(10)
            self.deadlinetimer_droplet_adjustment_on_the_fly.setRemainingTime(timeout)
            #self.server_devices['exchange_pair'][label].increaseVolume(volume = self.spinBox_amount.value(), rate = self.spinBox_speed.value())
        elif self.timer_update_simple.isActive():#if simple exchange mode actived
            pull_syringe_index = int(self.simple_exchange_operation.settings['pull_syringe_handle']())
            push_syringe_index = int(self.simple_exchange_operation.settings['push_syringe_handle']())
            label = f"S{push_syringe_index}_S{pull_syringe_index}"
            timeout = self.spinBox_amount.value()/self.spinBox_speed.value()*1000
            self.server_devices['exchange_pair'][label].pushSyr.rate = self.server_devices['exchange_pair'][label].rate + self.spinBox_speed.value()
            self.timer_droplet_adjustment_on_the_fly.start(10)
            self.deadlinetimer_droplet_adjustment_on_the_fly.setRemainingTime(timeout)
            # self.server_devices['exchange_pair'][label].increaseVolume(volume = self.spinBox_amount.value(), rate = self.spinBox_speed.value())
            '''
            self.stop_all_timers()
            self.server_devices['client'].stop()
            self.simple_exchange_operation.set_status_to_ready()
            time.sleep(0.1)
            self.widget_psd.actived_syringe_motion_init_mode = 'dispense'
            self.init_operation.start_exchange_timer()
            self.timer_check_device_busy.start(50)
            '''
        else:
            self.widget_psd.actived_syringe_motion_init_mode = 'dispense'
            self.stop_all_timers()
            self.server_devices['client'].stop()
            self.init_operation.start_exchange_timer()

    def check_elapsed_time(self):
        if self.deadlinetimer_droplet_adjustment_on_the_fly.hasExpired():
            #advance exchange mode
            if self.timer_update.isActive():
                label = 'S{}_S{}'.format(*self.widget_psd.get_exchange_syringes_advance_exchange_mode()) 
                self.server_devices['exchange_pair'][label].pullSyr.rate = self.server_devices['exchange_pair'][label].rate
                self.server_devices['exchange_pair'][label].pushSyr.rate = self.server_devices['exchange_pair'][label].rate
            elif self.timer_update_simple.isActive():#if simple exchange mode actived
                pull_syringe_index = int(self.simple_exchange_operation.settings['pull_syringe_handle']())
                push_syringe_index = int(self.simple_exchange_operation.settings['push_syringe_handle']())
                label = f"S{push_syringe_index}_S{pull_syringe_index}"
                self.server_devices['exchange_pair'][label].pullSyr.rate = self.server_devices['exchange_pair'][label].rate
                self.server_devices['exchange_pair'][label].pushSyr.rate = self.server_devices['exchange_pair'][label].rate
            self.timer_droplet_adjustment_on_the_fly.stop()

    def make_cmd_list_normal_mode(self, syringe_no):
        speed_wid_str = f'doubleSpinBox_speed_normal_mode_{syringe_no}'
        vol_wid_str = f'doubleSpinBox_stroke_factor_{syringe_no}'
        valve_wid_str = f'comboBox_valve_port_{syringe_no}'
        speed = getattr(self, speed_wid_str).value()
        vol = getattr(self, vol_wid_str).value()
        valve = getattr(self, valve_wid_str).currentText()
        cmd_list = ['self.'+speed_wid_str+f'.setValue({speed})',
                  'self.'+vol_wid_str+f'.setValue({vol})',
                  'self.'+valve_wid_str+f".setCurrentText('{valve}')"]
        return cmd_list

    # @check_any_timer
    def _fill_syringe(self, syringe_no):
        if self.pump_settings['S{}_mvp'.format(syringe_no)] != 'not_used':
            exec('self.pushButton_connect_mvp_syringe_{}.click()'.format(syringe_no))
        self.widget_psd.actived_syringe_motion_normal_mode = 'fill'
        exec('self.widget_psd.filling_status_syringe_{} = True'.format(syringe_no))
        self.normal_operation.syringe_index = syringe_no
        self.normal_operation.start_timer_motion()

    def fill_syringe(self,syringe_no):
        self.textBrowser_error_msg.setText('')
        if self.main_client_cloud!=None:
            if not self.main_client_cloud:
                self.send_cmd_to_cloud('\n'.join(self.make_cmd_list_normal_mode(syringe_no)+[f'self._fill_syringe({syringe_no})']))
            else:
                self._fill_syringe(syringe_no)
        else:
            self._fill_syringe(syringe_no)

    # @check_any_timer
    def _dispense_syringe(self, syringe_no):
        self.textBrowser_error_msg.setText('')
        if self.pump_settings['S{}_mvp'.format(syringe_no)] != 'not_used':
            exec('self.pushButton_connect_mvp_syringe_{}.click()'.format(syringe_no))
        self.widget_psd.actived_syringe_motion_normal_mode = 'dispense'
        exec('self.widget_psd.filling_status_syringe_{} = False'.format(syringe_no))
        #radioButton_widget.setChecked(True)
        self.stop_all_timers()
        self.normal_operation.syringe_index = syringe_no
        self.normal_operation.start_timer_motion()

    #@check_any_timer
    def dispense_syringe(self,syringe_no):
        if self.main_client_cloud!=None:
            if not self.main_client_cloud:
                self.send_cmd_to_cloud('\n'.join(self.make_cmd_list_normal_mode(syringe_no)+[f'self._dispense_syringe({syringe_no})']))
            else:
                self._dispense_syringe(syringe_no)
        else:
            self._dispense_syringe(syringe_no)

    # @check_any_timer
    def reset_exchange(self,kwargs = 1):
        dlg = ResetResevoirWaste(self)
        dlg.exec()

    # @check_any_timer
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
        uic.loadUi(os.path.join(script_path,"config_pump_dialog.ui"), self)

class RefillCellSetup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        # Load the dialog's GUI
        uic.loadUi(os.path.join(script_path,"refill_cell_dialog2.ui"), self)
        self.buttonBox.accepted.connect(self.start_refill)

    def start_refill(self):
        syringe_index = int(self.lineEdit_syringe_index.text())
        refill_times = int(self.lineEdit_refill_times.text())
        refill_speed = float(self.lineEdit_refill_speed.text())/1000
        disposal_speed = float(self.lineEdit_waste_disposal_speed.text())/1000
        vol_to_cell = float(self.lineEdit_vol_cell_dispense.text())/1000
        vol_to_waste = float(self.lineEdit_vol_waste_disposal.text())/1000
        if self.parent.main_client_cloud!=None:
            if not self.parent.main_client_cloud:
                cmd_list = ['self.widget_psd.actived_syringe_fill_cell_mode = {}'.format(syringe_index),
                            'self.widget_psd.refill_times_fill_cell_mode = {}'.format(refill_times*2),
                            'self.widget_psd.refill_speed_fill_cell_mode = {}'.format(refill_speed),
                            'self.widget_psd.disposal_speed_fill_cell_mode = {}'.format(disposal_speed),
                            'self.widget_psd.vol_to_cell_fill_cell_mode = {}'.format(vol_to_cell),
                            'self.widget_psd.vol_to_waste_fill_cell_mode = {}'.format(vol_to_waste),
                            'self.start_fill_cell()'
                            ]
                self.parent.send_cmd_to_cloud('\n'.join(cmd_list))
            else:
                assert syringe_index in [1,2,3,4], 'Warning: The syringe index is not set right. It should be integer from 1 to 4!'
                assert type(refill_times)==int and refill_times>=1, 'Warning: The refill is not set right. It should be integer >1!'
                self.parent.widget_psd.actived_syringe_fill_cell_mode = syringe_index
                self.parent.widget_psd.refill_times_fill_cell_mode = refill_times*2 # in the script, one stroke filled or emptied is counted as one time, so need to mult by 2
                self.parent.widget_psd.refill_speed_fill_cell_mode = refill_speed
                self.parent.widget_psd.disposal_speed_fill_cell_mode = disposal_speed
                self.parent.widget_psd.vol_to_cell_fill_cell_mode = vol_to_cell
                self.parent.widget_psd.vol_to_waste_fill_cell_mode = vol_to_waste
                self.parent.start_fill_cell()
        else:
            assert syringe_index in [1,2,3,4], 'Warning: The syringe index is not set right. It should be integer from 1 to 4!'
            assert type(refill_times)==int and refill_times>=1, 'Warning: The refill is not set right. It should be integer >1!'
            self.parent.widget_psd.actived_syringe_fill_cell_mode = syringe_index
            self.parent.widget_psd.refill_times_fill_cell_mode = refill_times*2 # in the script, one stroke filled or emptied is counted as one time, so need to mult by 2
            self.parent.widget_psd.refill_speed_fill_cell_mode = refill_speed
            self.parent.widget_psd.disposal_speed_fill_cell_mode = disposal_speed
            self.parent.widget_psd.vol_to_cell_fill_cell_mode = vol_to_cell
            self.parent.widget_psd.vol_to_waste_fill_cell_mode = vol_to_waste
            self.parent.start_fill_cell()

class Cleaner(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        # Load the dialog's GUI
        uic.loadUi(os.path.join(script_path,"cleaner_dialog.ui"), self)
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
        if not self.parent.demo:
            self.parent.client.stop()
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
        uic.loadUi(os.path.join(script_path,"reset_resevoir_waste_dialog.ui"), self)
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
    if sys.argv[-1] == 'demo':
        myWin.demo = True
        myWin.init_server_devices()
        myWin.set_up_operations()
    else:
        myWin.demo = False
        import psdrive as psd
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    myWin.show()
    sys.exit(app.exec_())
