import numpy as np
from PyQt5.QtCore import QTimer
import logging
import time
import threading


#valve postion mapping between GUI and server side, key is GUI and value is based on server
VALVE_POSITION_T = {'left':1,'up':2, 'right':3}

#syringe pump id mapping between GUI and server side, key is from GUI and value is based on server
DEVICE_ID_MAP = {1:1, 2:2, 3:3, 4:4}

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
        """using the error reporting dialog or via email to <%s>.\n"""%\
        ("crqiu2@gmail.com")
        self.textBrowser_error_msg.clear()
        cursor = self.textBrowser_error_msg.textCursor()
        cursor.insertHtml('''<p><span style="color: red;">{} <br></span>'''.format(" "))
        self.textBrowser_error_msg.setText(notice + '\n' +separator+'\n'+error_msg)


class baseOperationMode(object):
    def __init__(self, psd_server,psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings):
        self.switch_success_pump_server = True
        self.server_ready = False
        self.server_devices = psd_server
        self.server_data_receiver = []
        self.psd_widget = psd_widget
        self.error_widget = error_widget
        self.timer_premotion = timer_premotion
        self.timer_motion = timer_motion
        self.timeout = timeout
        self.pump_settings = pump_settings
        self.settings = settings
        self.exchange_amount_already = 0
        self.total_exchange_amount = 0
        #set redirection of error message to embeted text browser widget
        logTextBox = QTextEditLogger(error_widget)
        # You can format what is printed to text box
        logTextBox.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(logTextBox)
        # You can control the logging level
        logging.getLogger().setLevel(logging.DEBUG)

    #TODO by Timo
    #update the syringe volumes from server to GUI
    #syringe are indexed from left to righ as 1, 2, 3 and 4, respectively in the GUI
    def syn_server_to_gui(self):
        for index in [1,2,3,4]:
            try:
                #impliment this func in the PumpInterface to get the volume (in ml) of solution in syringe with id of index
                vol_temp = self.psd_server.getSyringeVol(deviceId = index)
                setattr(self.psd_widget,'volume_syringe_{}'.format(index),vol_temp)
            except:
                pass
        self.psd_widget.update()

    def check_settings(self):
        #check the setttins for the specific motion
        return

    def init_pre_motion(self):
        #you need to define the syringes under consideration, define the valve positions, the range of syringe volume
        return

    def pre_motion(self, index):
        #loop through the registered syringes
        return

    def init_motion(self):
        #registered the syringe for exchange, and set the valve position to initial positions
        pass

    def exchange_motion(self):
        #loop through the registered syringes for exchange, the argument of continual_exchange should be set to True to apply the syringe motion
        pass

    def get_status(self,index):
        print(self.settings['syringe{}_status'.format(index)])

    def set_status(self,index, status):
        self.settings['syringe{}_status'.format(index)] = status

    def single_syringe_motion(self,index, speed_tag = 'speed', continual_exchange = True, use_limits_for_exchange = True, demo = True):
        if demo:
            self.single_syringe_motion_demo(index, speed_tag, continual_exchange, use_limits_for_exchange)
        else:
            self.single_syringe_motion_server(index, continual_exchange, use_limits_for_exchange)

    def stop_all_devices(self):
        #stop 
        self.server_devices['client'].stop()

    def single_syringe_motion_server(self, index, continual_exchange = True, use_limits_for_exchange = True):
        #move the syringe under the physical limit, and update the volum of the part (cell, resevior or waste) which it is connection to.
        #index: index (eg 1 or 2 or 3) for syringe
        #direction_sign: either 1(filling syringe) or -1(dispense syringe)
        type_ = 'syringe'
        #speed = self.settings.get(speed_tag)
        #the name of syringe defined in the psd_widget
        #looks like volume_syringe_1, volume_syringe_2
        type_name_in_widget = 'volume_{}_{}'.format(type_,str(index))
        direction_sign = [-1,1][int(getattr(self.psd_widget,'filling_status_syringe_{}'.format(index)))]
        if type_name_in_widget == None:
            logging.getLogger().exception('Error: The key {} is not set in the settings'.format(type_+str(index)))
            return
        
        ##send cmd to server only once at the begginning##
        #cmd string sent in the premotion
        '''
        if send_cmd_to_server:
            if direction_sign == -1:
                self.server_devices['syringe'][index].drain(rate = speed*10*1000) #speed in ml per 100 ms, converted to ul per s
            elif direction_sign == 1:
                self.server_devices['syringe'][index].fill(rate = speed*10*1000) #speed in ml per 100 ms, converted to ul per s
        '''

        value_before_motion = getattr(self.psd_widget, type_name_in_widget)
        #value_after_motion = value_before_motion + speed*direction_sign
        value_after_motion = self.server_devices['syringe'][index].volume/1000 # get volume from server, convert to value in ml

        '''
        if continual_exchange:
            checked_value = self.check_limits(value_after_motion, type_)
        else:
            #you need to specify the range of volume of this syringe, eg syringe_1_min, syringe_1_max
            checked_value = self.check_limits(value_after_motion, type_, min_vol = self.settings[type_+'_'+str(index)+'_min'], max_vol = self.settings[type_+'_'+str(index)+'_max'])
        '''

        #corrected speed considering the possible overshootting in syringe motion
        #this speed will be taken to update the volume of the part the syringe is connecting to right now
        #speed_new = speed - checked_value

        valve_position = self.psd_widget.connect_valve_port[int(index)]
        connection = self.pump_settings['S{}_{}'.format(index, valve_position)]
        #checked_value_connection_part = {}

        if direction_sign == -1:#the syringe dispensing solution
            if connection not in ['waste', 'cell_inlet']:
                logging.getLogger().exception('Pump setting Error:YOU ARE ONLY allowed to dispense solution to WASTE or CELL_INLET')
                try:
                    self.timer_motion.stop()
                except:
                    self.timer_premotion.stop()
                else:
                    self.server_devices['client'].stop()

            elif connection == 'waste':
                #checked_value_connection_part = {'type':'waste', 'checked_value':self.check_limits(self.psd_widget.waste_volumn+speed_new, 'waste')}
                self.psd_widget.waste_volumn = self.psd_widget.waste_volumn - (value_after_motion - value_before_motion)
            elif connection == 'cell_inlet':
                #checked_value_connection_part = {'type':'cell', 'checked_value':self.check_limits(self.psd_widget.volume_of_electrolyte_in_cell+speed_new, 'cell')}
                self.psd_widget.volume_of_electrolyte_in_cell = self.psd_widget.volume_of_electrolyte_in_cell - (value_after_motion - value_before_motion)
                self.exchange_amount_already = self.exchange_amount_already - (value_after_motion - value_before_motion)
        elif direction_sign == 1:
            if connection not in ['resevoir', 'cell_outlet', 'not_used']:
                logging.getLogger().exception('Pump setting Error:YOU ARE ONLY allowed to withdraw solution from RESEVOIR or CELL_OUTLET')
                try:
                    self.timer_motion.stop()
                except:
                    self.timer_premotion.stop()
                else:
                    self.server_devices['client'].stop()
            elif connection == 'resevoir':
                # checked_value_connection_part = {'type':'resevoir', 'checked_value':self.check_limits(self.psd_widget.resevoir_volumn-speed_new, 'resevoir')}
                # self.psd_widget.resevoir_volumn = self.psd_widget.resevoir_volumn - (speed_new - checked_value_connection_part['checked_value'])
                resevoir_volumn = getattr(self.psd_widget, 'resevoir_volumn_S{}'.format(index))
                #checked_value_connection_part = {'type':'resevoir', 'checked_value':self.check_limits(resevoir_volumn-speed_new, 'resevoir')}
                self.psd_widget.resevoir_volumn = resevoir_volumn - (value_after_motion - value_before_motion)
                setattr(self.psd_widget, 'resevoir_volumn_S{}'.format(index), self.psd_widget.resevoir_volumn)
                self.psd_widget.label_resevoir = self.pump_settings['S{}_solution'.format(index)]
            elif connection == 'cell_outlet':
                #checked_value_connection_part = {'type':'cell', 'checked_value':self.check_limits(self.psd_widget.volume_of_electrolyte_in_cell-speed_new, 'cell')}
                self.psd_widget.volume_of_electrolyte_in_cell = self.psd_widget.volume_of_electrolyte_in_cell - (value_after_motion - value_before_motion)
            elif connection == 'not_used':#if not used, just sucking from air, nothing need to be updated
                # checked_value_connection_part = {'type':'not_used','checked_value':0}
                pass
        #speed_syringe = speed_new
        setattr(self.psd_widget, type_name_in_widget, value_after_motion)
        if not self.server_devices['syringe'][index].busy:
            self.set_status(index,'ready')
            if self.psd_widget.connect_status[index] != 'ready':
                self.psd_widget.connect_status[index] = 'ready'
        else:
            self.set_status(index,'moving')
            if self.psd_widget.connect_status[index] != 'moving':
                self.psd_widget.connect_status[index] = 'moving'
        '''
        if continual_exchange:
            if abs(getattr(self.psd_widget, type_name_in_widget) - self.psd_widget.syringe_size)<0.0000001:
                self.set_status(index,'ready')
            elif abs(getattr(self.psd_widget, type_name_in_widget))<0.0000001:
                self.set_status(index,'ready')
        else:
            if not self.server_devices['syringe'][index].busy:
                self.set_status(index,'ready')
            else:
                self.set_status(index,'moving')
        '''

        #if limits reached, then stop devices and stop GUI timer
        if (self.psd_widget.resevoir_volumn<0) or (self.psd_widget.waste_volumn>self.psd_widget.waste_volumn_total) or (self.psd_widget.volume_of_electrolyte_in_cell> self.psd_widget.cell_volume_in_total):
            self.stop_all_devices()
            if self.timer_motion.isActive():
                # print(checked_value_connection_part)
                self.timer_motion.stop()
            if self.timer_premotion!= None:
                if self.timer_premotion.isActive():
                    self.timer_premotion.stop()
        self.psd_widget.update()

    def single_syringe_motion_demo(self, index, speed_tag = 'speed', continual_exchange = True, use_limits_for_exchange = True):
        #move the syringe under the physical limit, and update the volum of the part (cell, resevior or waste) which it is connection to.
        #index: index (eg 1 or 2 or 3) for syringe
        #direction_sign: either 1(filling syringe) or -1(dispense syringe)
        type_ = 'syringe'
        speed = self.settings.get(speed_tag)
        #the name of syringe defined in the psd_widget
        #looks like volume_syringe_1, volume_syringe_2
        type_name_in_widget = 'volume_{}_{}'.format(type_,str(index))
        direction_sign = [-1,1][int(getattr(self.psd_widget,'filling_status_syringe_{}'.format(index)))]
        if type_name_in_widget == None:
            logging.getLogger().exception('Error: The key {} is not set in the settings'.format(type_+str(index)))
            return

        value_before_motion = getattr(self.psd_widget, type_name_in_widget)
        value_after_motion = value_before_motion + speed*direction_sign
        if continual_exchange:
            if use_limits_for_exchange:
                checked_value = self.check_limits(value_after_motion, type_)
            else:
                checked_value = self.check_limits(value_after_motion, type_, min_vol = self.settings[type_+'_'+str(index)+'_min'], max_vol = self.settings[type_+'_'+str(index)+'_max'])
        else:
            #you need to specify the range of volume of this syringe, eg syringe_1_min, syringe_1_max
            checked_value = self.check_limits(value_after_motion, type_, min_vol = self.settings[type_+'_'+str(index)+'_min'], max_vol = self.settings[type_+'_'+str(index)+'_max'])

        #corrected speed considering the possible overshootting in syringe motion
        #this speed will be taken to update the volume of the part the syringe is connecting to right now
        speed_new = speed - checked_value

        valve_position = self.psd_widget.connect_valve_port[int(index)]
        connection = self.pump_settings['S{}_{}'.format(index, valve_position)]
        checked_value_connection_part = {}

        if direction_sign == -1:#the syringe dispensing solution
            if connection not in ['waste', 'cell_inlet']:
                logging.getLogger().exception('Pump setting Error:YOU ARE ONLY allowed to dispense solution to WASTE or CELL_INLET')
            elif connection == 'waste':
                checked_value_connection_part = {'type':'waste', 'checked_value':self.check_limits(self.psd_widget.waste_volumn+speed_new, 'waste')}
                self.psd_widget.waste_volumn = self.psd_widget.waste_volumn + speed_new - checked_value_connection_part['checked_value']
            elif connection == 'cell_inlet':
                checked_value_connection_part = {'type':'cell', 'checked_value':self.check_limits(self.psd_widget.volume_of_electrolyte_in_cell+speed_new, 'cell')}
                self.psd_widget.volume_of_electrolyte_in_cell = self.psd_widget.volume_of_electrolyte_in_cell + speed_new  - checked_value_connection_part['checked_value']
                self.exchange_amount_already = self.exchange_amount_already + speed_new  - checked_value_connection_part['checked_value']
        elif direction_sign == 1:
            if connection not in ['resevoir', 'cell_outlet', 'not_used']:
                logging.getLogger().exception('Pump setting Error:YOU ARE ONLY allowed to withdraw solution from RESEVOIR or CELL_OUTLET')
            elif connection == 'resevoir':
                # checked_value_connection_part = {'type':'resevoir', 'checked_value':self.check_limits(self.psd_widget.resevoir_volumn-speed_new, 'resevoir')}
                # self.psd_widget.resevoir_volumn = self.psd_widget.resevoir_volumn - (speed_new - checked_value_connection_part['checked_value'])
                resevoir_volumn = getattr(self.psd_widget, 'resevoir_volumn_S{}'.format(index))
                checked_value_connection_part = {'type':'resevoir', 'checked_value':self.check_limits(resevoir_volumn-speed_new, 'resevoir')}
                self.psd_widget.resevoir_volumn = resevoir_volumn - (speed_new - checked_value_connection_part['checked_value'])
                setattr(self.psd_widget, 'resevoir_volumn_S{}'.format(index), self.psd_widget.resevoir_volumn)
                self.psd_widget.label_resevoir = self.pump_settings['S{}_solution'.format(index)]
            elif connection == 'cell_outlet':
                checked_value_connection_part = {'type':'cell', 'checked_value':self.check_limits(self.psd_widget.volume_of_electrolyte_in_cell-speed_new, 'cell')}
                self.psd_widget.volume_of_electrolyte_in_cell = self.psd_widget.volume_of_electrolyte_in_cell - (speed_new - checked_value_connection_part['checked_value'])
            elif connection == 'not_used':#if not used, just sucking from air, nothing need to be updated
                checked_value_connection_part = {'type':'not_used','checked_value':0}
        speed_syringe = speed_new
        if len(checked_value_connection_part)!=0:
            if abs(checked_value_connection_part['checked_value'])<10**-6: # do normally the volume update if True
                speed_syringe = speed_new
                setattr(self.psd_widget, type_name_in_widget, value_before_motion + direction_sign*speed_syringe)
            else:#overshooting in cell, resevior or waste. You should stop the timer then.
                speed_syringe = speed_new - checked_value_connection_part['checked_value']
                #update the syringe volume according to this speed
                setattr(self.psd_widget, type_name_in_widget, value_before_motion + direction_sign*speed_syringe)
                if self.timer_motion.isActive():
                    # print(checked_value_connection_part)
                    self.timer_motion.stop()
                if self.timer_premotion!= None:
                    if self.timer_premotion.isActive():
                        self.timer_premotion.stop()
        if continual_exchange:
            if use_limits_for_exchange:
                if abs(getattr(self.psd_widget, type_name_in_widget) - self.psd_widget.syringe_size)<0.0000001:
                    self.set_status(index,'ready')
                elif abs(getattr(self.psd_widget, type_name_in_widget))<0.0000001:
                    self.set_status(index,'ready')
            else:
                if checked_value > 0:
                    self.set_status(index,'ready')
                else:
                    self.set_status(index,'moving')
        else:
            if checked_value > 0:
                self.set_status(index,'ready')
            else:
                self.set_status(index,'moving')
        self.psd_widget.update()

    def check_limits(self, current_value, type_, min_vol = None, max_vol = None):
        #return the speed correction value (>=0)
        #0: no speed correction
        #>0: the practical speed should be smaller by the value
        volume_min, volume_max = 0, 0
        if type_ == 'resevoir':
            if max_vol == None:
                volume_max = self.psd_widget.resevoir_volumn_total
            else:
                volume_max = max_vol
        elif type_ == 'waste':
            if max_vol == None:
                volume_max = self.psd_widget.waste_volumn_total
            else:
                volume_max = max_vol
        elif type_ == 'cell':
            if max_vol == None:
                volume_max = self.psd_widget.cell_volume_in_total
            else:
                volume_max = max_vol
        elif type_ == 'syringe':
            if max_vol == None:
                volume_max = self.psd_widget.syringe_size
            else:
                volume_max = max_vol
        else:
            logging.getLogger().exception('Unknown type of object for limit checking: It should be one of {} but got {}'.format('resevoir, cell, syringe, waste',type_))
            return
        if min_vol==None:
            volume_min = 0
        else:
            volume_min = min_vol
        if volume_max >= current_value >= volume_min:
            return 0
        else:
            if current_value > volume_max:
                return current_value - volume_max
            elif current_value < volume_min:
                return volume_min - current_value

    #mode dependent, should be overloaded in each subclass mode if needed
    def check_synchronization(self, index_list):
        pass

    def simulated_data_receiver(self):
        return True

    def turn_valve_from_server(self, index, position):
        self.server_devices['T_valve'][index].valve = position
        self.server_devices['T_valve'][index].join()

    def turn_valve(self, index, to_position = None):
        if to_position in ['up','left','right']:
            if index in self.psd_widget.connect_valve_port:
                self.psd_widget.connect_valve_port[index] = to_position
                if not self.demo:
                    self.turn_valve_from_server(index, to_position)
            else:
                logging.getLogger().exception('The syringe index {} is not registered.'.format(index))
        elif to_position == None:#switch the vale to the other possible position
            possible_valve_positions = self.settings['possible_connection_valves_syringe_{}'.format(index)]
            if possible_valve_positions!=None:
                if len(possible_valve_positions)!=2:
                    logging.getLogger().exception('Valve turning error: During exchange, there must be only two possible valve positions for each syringe!')
                else:
                    if index in self.psd_widget.connect_valve_port:
                        current_valve_position = self.psd_widget.connect_valve_port[index]
                        #note 0-->-1, 1-->0, in both cases the index-1 will be refering to the other one in a two member index list
                        self.psd_widget.connect_valve_port[index] = possible_valve_positions[possible_valve_positions.index(current_valve_position)-1]
                        if not self.demo:
                            self.turn_valve_from_server(index, possible_valve_positions[possible_valve_positions.index(current_valve_position)-1])
                    else:
                        logging.getLogger().exception('The syringe index {} is not registered.'.format(index))
            else:
                logging.getLogger().exception('Valve turning error: possible_connection_valves_syringe_{} is not the member of settings'.format(index))

class simpleRefillingOperationMode(baseOperationMode):
    def __init__(self, psd_server, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings, demo):
        super().__init__(psd_server, psd_widget, error_widget, timer_premotion, timer_motion,timeout, pump_settings, settings)
        self.demo = demo
        self.operation_mode = 'simple_exchange_mode'
        self.onetime = False
        self.timer_begin = False
        self.timer_motion.timeout.connect(self.exchange_motion)
        self.timer_premotion.timeout.connect(self.premotion)
        self.check_settings()

    def append_valve_info(self, index, pushing_syringe = True):
        if pushing_syringe:
            directions = ['left', 'right']
        else:
            directions = ['left', 'up']
        self.settings['possible_connection_valves_syringe_{}'.format(index)] = directions

    def check_settings(self):
        missed = []
        for each in ['pull_syringe_handle','push_syringe_handle','refill_speed_handle','exchange_speed_handle','total_exchange_amount_handle']:
            if each not in self.settings:
                missed.append(each)
        if len(missed)>0:
            logging.getLogger().exception('Missing the following keys in the Init mode settings:{}'.format(','.join(missed)))

    def init_premotion(self):
        pull_syringe_index = int(self.settings['pull_syringe_handle']())
        push_syringe_index = int(self.settings['push_syringe_handle']())
        refill_speed = float(self.settings['refill_speed_handle']())/(1000/self.timeout) #timeout in ms
        exchange_speed = float(self.settings['exchange_speed_handle']())/(1000/self.timeout) #timeout in ms
        self.total_exchange_amount = float(self.settings['total_exchange_amount_handle']())
        self.settings['refill_speed'] = refill_speed
        self.settings['exchange_speed'] = exchange_speed
        self.psd_widget.operation_mode = 'simple_exchange_mode'
        #which one is the syringe to push electrolyte to cell
        self.psd_widget.actived_left_syringe_simple_exchange_mode = int(push_syringe_index)
        #which one is the syringe to pull electrolyte from cell
        self.psd_widget.actived_right_syringe_simple_exchange_mode = int(pull_syringe_index)
        exec('self.psd_widget.filling_status_syringe_{} = True'.format(push_syringe_index)) # refill the pushing syringe
        exec('self.psd_widget.filling_status_syringe_{} = False'.format(pull_syringe_index)) # empty the pulling syringe
        self.settings['syringe{}_status'.format(push_syringe_index)] ='moving'
        self.settings['syringe{}_status'.format(pull_syringe_index)] ='moving'
        self.turn_valve(pull_syringe_index, 'up')
        self.turn_valve(push_syringe_index, 'left')
        self.append_valve_info(pull_syringe_index, pushing_syringe = False)
        self.append_valve_info(push_syringe_index, pushing_syringe = True)
        if not self.demo:
            while True:
                if not self.server_devices['T_valve'][pull_syringe_index].busy:
                    self.server_devices['syringe'][pull_syringe_index].fill(rate = refill_speed*10*1000)
                else:
                    break
                if not self.server_devices['T_valve'][push_syringe_index].busy:
                    self.server_devices['syringe'][push_syringe_index].drain(rate = refill_speed*10*1000)
                else:
                    break

    def start_premotion_timer(self):
        self.init_premotion()
        if not self.demo:
            while True:
                if self.check_server_devices_busy():
                    #logging.getLogger().exception('Server devices are busy, waiting now: {} seconds have elapsed!'.format(round(time.time()-t0,1)))
                    #time.sleep(0.5)
                    break
                else:
                    pass
        self.timer_premotion.start(100)
        self.timer_beginning = True

    def premotion(self):
        # for i in [int(self.settings['pull_syringe_handle']()),int(self.settings['push_syringe_handle']())]:
            # self.single_syringe_motion(i, speed_tag = 'refill_speed', continual_exchange = True, demo = self.demo)
        # return
        if self.check_synchronization_premotion():
            if self.timer_premotion.isActive():
                self.timer_premotion.stop()
                # self.start_motion_timer()
                #self.init_motion()
                #TODO (Before timer starts!!): send cmd to server to apply motions of the related syringes. Under exchange mode, cmd should be broadcasted instead of send one by one to allow synchronization.
                #Now you should set the speed in syringe instances to exchange speed. Program continues upon all syringes starting to move.
                #self.timer_motion.start(100)
        else:
            for i in [int(self.settings['pull_syringe_handle']()),int(self.settings['push_syringe_handle']())]:
                self.single_syringe_motion(i, speed_tag = 'refill_speed', continual_exchange = True, demo = self.demo)
            # if self.timer_beginning:
                # self.timer_beginning = False

    def start_motion_timer(self,onetime):
        self.onetime = onetime
        self.init_motion()
        self.timer_motion.start(100)
        self.timer_begin = False

    def init_motion(self):
        self.total_exchange_amount = float(self.settings['total_exchange_amount_handle']())
        pull_syringe_index = int(self.settings['pull_syringe_handle']())
        push_syringe_index = int(self.settings['push_syringe_handle']())
        exec('self.psd_widget.filling_status_syringe_{} = False'.format(push_syringe_index)) 
        exec('self.psd_widget.filling_status_syringe_{} = True'.format(pull_syringe_index)) 
        self.settings['syringe{}_status'.format(push_syringe_index)] ='moving'
        self.settings['syringe{}_status'.format(pull_syringe_index)] ='moving'
        self.turn_valve(pull_syringe_index, 'left')
        self.turn_valve(push_syringe_index, 'right')
        #set mvp channel
        self.psd_widget.mvp_channel = int(self.pump_settings['S{}_mvp'.format(push_syringe_index)].rsplit('_')[1])
        self.psd_widget.mvp_connected_valve = 'S{}_right'.format(push_syringe_index)
        #set mvp channel from server side
        if not self.demo:
            self.server_devices['mvp_valve'].valve = self.psd_widget.mvp_channel
        #waiting for the server devices(valves) to be ready
            while True:
                if not self.check_server_devices_busy():
                    #logging.getLogger().exception('Server devices are busy, waiting now: {} seconds have elapsed!'.format(round(time.time()-t0,1)))
                    #time.sleep(0.5)
                    break
                else:
                    pass
            #launch electrolyte exchange
            # at the beginning, S1 and S4 are connected to resevoir and waste, respectively
            # while, S2 and S3 are connected to cell for exchangeing
            if f'S{push_syringe_index}_S{pull_syringe_index}' not in ['S1_S4','S2_S3']:
                logging.getLogger().exception(f'Syringe pair S{push_syringe_index}_S{pull_syringe_index} not implemented! Please use combo of S1_S4 or S1_S3!')
                return
            else:
                self.server_devices['exchange_pair']['S{push_syringe_index}_S{pull_syringe_index}'](rate = float(self.settings['exchange_speed_handle']())*1000)


    def exchange_motion(self):
        if self.check_synchronization():
            if self.onetime:
                self.timer_motion.stop()
                return
            #TODO: switch status (valve positions, speed, and dispense/fill volume) in pump server side for next cycle. Update the switch_success_pump_server
            #self.switch_success_pump_server = True
            
            #TODO: send cmd to server to apply motions of the related syringes. Under exchange mode, cmd should be broadcasted instead of send one by one to allow synchronization.
            #Program continues upon all syringes starting to move.
            self.switch_state_during_exchange(syringe_index_list = [self.psd_widget.actived_left_syringe_simple_exchange_mode,self.psd_widget.actived_right_syringe_simple_exchange_mode])
            self.set_status_to_moving()
            exchange_tag = self.check_refill_or_exchange()
            if exchange_tag:
                speed_tag = 'exchange_speed'
            else:
                speed_tag = 'refill_speed'
            for i in [int(self.settings['pull_syringe_handle']()),int(self.settings['push_syringe_handle']())]:
                self.single_syringe_motion(i, speed_tag = speed_tag, continual_exchange = True, demo = self.demo)
        else:
            exchange_tag = self.check_refill_or_exchange()
            if exchange_tag:
                speed_tag = 'exchange_speed'
            else:
                speed_tag = 'refill_speed'
            for i in [int(self.settings['pull_syringe_handle']()),int(self.settings['push_syringe_handle']())]:
                self.single_syringe_motion(i, speed_tag = speed_tag, continual_exchange = True, demo = self.demo)

    def check_server_devices_ready(self):
        #TODO by Timo
        '''
        if len(self.server_data_receiver)==0:
            self.server_ready = Fasle
            return

        for each in self.server_data_receiver:
            if each.busy:#is this right check?
                self.server_ready = False
                return
        self.server_ready = True
        '''
        return True

    def check_synchronization_premotion(self):
        for i in [int(self.settings['pull_syringe_handle']()),int(self.settings['push_syringe_handle']())]:
            if self.settings['syringe{}_status'.format(i)]!='ready':
                return False
        return True

    def check_synchronization(self):
        gui_ready, server_ready = False, False
        for i in [int(self.settings['pull_syringe_handle']()),int(self.settings['push_syringe_handle']())]:
            if self.settings['syringe{}_status'.format(i)]=='ready':
                gui_ready = True
        if self.exchange_amount_already>=self.total_exchange_amount:
            self.timer_motion.stop()
            gui_ready = True
        '''
        if not self.demo:
            server_ready = self.check_server_devices_ready()
        else:
            server_ready = True
        '''
        return gui_ready

    def check_refill_or_exchange(self):
        index_pushing = int(self.settings['push_syringe_handle']())
        if self.pump_settings['S{}_{}'.format(index_pushing, self.psd_widget.connect_valve_port[index_pushing])] == 'cell_inlet':
            return True#if under exchange state
        else:
            return False#if under refilling state

    def switch_state_during_exchange(self, syringe_index_list):
        assert len(syringe_index_list)==2, 'Error during switching: Provide only two syringe index prease. But you have {}'.format(len(syringe_index_list))
        push_syringe_index, pull_syringe_index = syringe_index_list
        for syringe_index in syringe_index_list:
            self.turn_valve(syringe_index)
            setattr(self.psd_widget, 'filling_status_syringe_{}'.format(syringe_index), not getattr(self.psd_widget, 'filling_status_syringe_{}'.format(syringe_index)))
        if not self.demo:
            while True:
                if not self.check_server_devices_busy():
                    break
            self.server_devices['exchange_pair']['S{push_syringe_index}_S{pull_syringe_index}'].swap()
            if getattr(self.psd_widget, 'filling_status_syringe_{}'.format(push_syringe_index)):
                self.server_devices['exchange_pair']['S{push_syringe_index}_S{pull_syringe_index}'](rate = float(self.settings['exchange_speed_handle']())*1000)
            else:
                self.server_devices['exchange_pair']['S{push_syringe_index}_S{pull_syringe_index}'](rate = float(self.settings['refill_speed_handle']())*1000)
           #if the syringe start moving
            while True:
                if self.check_server_devices_busy():
                    break

    def set_status_to_moving(self):
        for i in [int(self.settings['pull_syringe_handle']()),int(self.settings['push_syringe_handle']())]:
            self.settings['syringe{}_status'.format(i)] = 'moving'

class advancedRefillingOperationMode(baseOperationMode):
    def __init__(self, psd_server, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings, demo):
        super().__init__(psd_server, psd_widget, error_widget, timer_premotion, timer_motion,timeout, pump_settings, settings)
        self.demo = demo
        self.resume = False
        self.operation_mode = 'autorefilling_mode'
        self.onetime = False
        self.timer_beginning = False
        self.timer_premotion.timeout.connect(self.premotion)
        self.timer_motion.timeout.connect(self.start_motion)
        self.check_settings()
        self.append_valve_info()
        self.waste_volume_t0 = 0
        self.exchange_t0 = 0
        self.fill_or_dispense_extra_amount = 0 
        self.extra_amount_fill = True
        self.thread_fill_or_dispense_extra_amount = threading.Thread(target=self.start_extra_amount_server, args=(), daemon = True)

    def append_valve_info(self):
        self.settings['possible_connection_valves_syringe_1'] = ['left', 'right']
        self.settings['possible_connection_valves_syringe_2'] = ['left', 'right']
        self.settings['possible_connection_valves_syringe_3'] = ['left', 'up']
        self.settings['possible_connection_valves_syringe_4'] = ['left', 'up']

    def check_settings(self):
        missed = []
        for each in ['premotion_speed_handle','exchange_speed_handle', 'refill_speed_handle','total_exchange_amount_handle', 'time_record_handle', 'volume_record_handle', 'extra_amount_timer', 'extra_amount_handle', 'extra_amount_speed_handle']:
            if each not in self.settings:
                missed.append(each)
        if len(missed)>0:
            logging.getLogger().exception('Missing the following keys in this autorefilling_mode settings:{}'.format(','.join(missed)))

    def init_premotion(self):
        self.psd_widget.operation_mode = 'pre_auto_refilling'
        speed = float(self.settings['premotion_speed_handle']())/(1000/self.timeout)
        self.total_exchange_amount = float(self.settings['total_exchange_amount_handle']())
        self.exchange_amount_already = 0
        self.settings['speed'] = speed

        for i in [1,2,3,4]:
            if i in [1,2]:
                self.turn_valve(i,'left')
                setattr(self.psd_widget, 'filling_status_syringe_{}'.format(i), True)
                self.settings['syringe_{}_min'.format(i)] = getattr(self.psd_widget,'volume_syringe_{}'.format(i))
                self.settings['syringe_{}_max'.format(i)] = self.psd_widget.syringe_size
                if not self.demo:
                    while True:
                        if not self.server_devices['syringe'][i].busy:
                            self.server_devices['syringe'][i].fill(rate = speed*10*1000)
                            break
                        else:
                            pass
                    #self.server_devices['syringe'][i].fill(1,speed*10*1000)
            else:
                self.turn_valve(i,'up')
                setattr(self.psd_widget, 'filling_status_syringe_{}'.format(i), False)
                self.settings['syringe_{}_min'.format(i)] = 0
                self.settings['syringe_{}_max'.format(i)] = getattr(self.psd_widget,'volume_syringe_{}'.format(i))
                if not self.demo:
                    while True:
                        if not self.server_devices['syringe'][i].busy:
                            self.server_devices['syringe'][i].drain(rate = speed*10*1000)
                            break
                        else:
                            pass
            self.settings['syringe{}_status'.format(i)] ='moving'

    def start_premotion_timer(self):
        self.init_premotion()
        #t0 = time.time()
        #waiting for the server devices(valves) to be ready
        '''
        if not self.demo:
            while True:
                if self.check_server_devices_busy():
                    #logging.getLogger().exception('Server devices are busy, waiting now: {} seconds have elapsed!'.format(round(time.time()-t0,1)))
                    #time.sleep(0.5)
                    break
                else:
                    pass
        '''
        self.timer_premotion.start(100)

    def start_motion_timer(self, onetime = False):
        if not self.resume:
            self.onetime = onetime
            self.init_motion()
            #self.timer_beginning = False
            self.timer_motion.start(100)
        else:
            self.init_motion_resume()
            #self.timer_beginning = False
            self.timer_motion.start(100) 

    def premotion(self):
        if self.check_synchronization_premotion():
            if self.timer_premotion.isActive():
                self.timer_premotion.stop()
                #self.init_motion()
                #self.timer_motion.start(100)
                self.exchange_t0 = time.time()
                self.waste_volume_t0 = self.psd_widget.waste_volumn
        else:
            for i in range(1,5):
                self.single_syringe_motion(i, speed_tag = 'speed', continual_exchange = False, demo = self.demo)
            if self.timer_beginning:
                self.timer_beginning = False

    def init_motion_resume(self):
        if not self.demo:
            '''
            while True:
                if not self.check_server_devices_busy():
                    break
                else:
                    pass
            '''
            #launch electrolyte exchange
            # at the beginning, S1 and S3 are connected to resevoir and waste, respectively
            # while, S2 and S4 are connected to cell for exchangeing
            #set status to moving
            for i in range(1,5):
                self.settings['syringe{}_status'.format(i)] ='moving'
            if 1 in self.psd_widget.get_exchange_syringes_advance_exchange_mode():
                self.server_devices['exchange_pair']['S1_S3'].exchange(volume = self.server_devices['exchange_pair']['S1_S3'].exchangeableVolume,rate = float(self.settings['exchange_speed_handle']())*1000)
                self.server_devices['exchange_pair']['S2_S4'].exchange(volume = self.server_devices['exchange_pair']['S2_S4'].exchangeableVolume,rate = float(self.settings['refill_speed_handle']())*1000)
            else:
                self.server_devices['exchange_pair']['S1_S3'].exchange(volume = self.server_devices['exchange_pair']['S1_S3'].exchangeableVolume,rate = float(self.settings['refill_speed_handle']())*1000)
                self.server_devices['exchange_pair']['S2_S4'].exchange(volume = self.server_devices['exchange_pair']['S2_S4'].exchangeableVolume,rate = float(self.settings['exchange_speed_handle']())*1000)


    def init_motion(self):
        self.psd_widget.operation_mode = 'auto_refilling'
        speed = float(self.settings['exchange_speed_handle']())/(1000/self.timeout)
        self.total_exchange_amount = float(self.settings['total_exchange_amount_handle']())
        # self.total_exchange_amount = float(self.settings['exchange_speed_handle']())/(1000/self.timeout)
        self.exchange_amount_already = 0
        self.settings['exchange_speed'] = speed
        refill_speed = float(self.settings['premotion_speed_handle']())/(1000/self.timeout)
        self.settings['refill_speed'] = refill_speed

        #syringe_1 to syringe_4
        self.turn_valve(1,'left')
        setattr(self.psd_widget, 'filling_status_syringe_{}'.format(1), True)
        self.settings['syringe{}_status'.format(1)] ='moving'

        self.turn_valve(2,'right')
        setattr(self.psd_widget, 'filling_status_syringe_{}'.format(2), False)
        self.settings['syringe{}_status'.format(2)] ='moving'
        #set mvp channel
        self.psd_widget.mvp_channel = int(self.pump_settings['S{}_mvp'.format(2)].rsplit('_')[1])
        self.psd_widget.mvp_connected_valve = 'S2_right'
        #set mvp channel from server side
        if not self.demo:
            self.server_devices['mvp_valve'].moveValve(self.psd_widget.mvp_channel)
            self.server_devices['mvp_valve'].join()

        self.turn_valve(3,'up')
        setattr(self.psd_widget, 'filling_status_syringe_{}'.format(3), False)
        self.settings['syringe{}_status'.format(3)] ='moving'

        self.turn_valve(4,'left')
        setattr(self.psd_widget, 'filling_status_syringe_{}'.format(4), True)
        self.settings['syringe{}_status'.format(4)] ='moving'

        #waiting for the server devices(valves) to be ready
        
        if not self.demo:
            '''
            while True:
                if not self.check_server_devices_busy():
                    break
                else:
                    pass
            '''
            #launch electrolyte exchange
            # at the beginning, S1 and S3 are connected to resevoir and waste, respectively
            # while, S2 and S4 are connected to cell for exchangeing
            self.server_devices['exchange_pair']['S1_S3'].exchange(volume = self.server_devices['exchange_pair']['S1_S3'].exchangeableVolume,rate = float(self.settings['refill_speed_handle']())*1000)
            self.server_devices['exchange_pair']['S2_S4'].exchange(volume = self.server_devices['exchange_pair']['S2_S4'].exchangeableVolume,rate = float(self.settings['exchange_speed_handle']())*1000)

    def check_server_devices_busy(self):
        #If any device is busy, then return True
        for each in list(self.server_devices['syringe'].values()) + [self.server_devices['mvp_valve']]:
            if each.busy:
                return True
        return False

    def check_server_devices_ready(self):
        #one of the exchanging syringe stop moving, then return True
        pass

    def switch_state_during_exchange(self, syringe_index_list):
        for syringe_index in syringe_index_list:
            self.turn_valve(syringe_index)
            '''
            if not self.demo:
                while True:
                    if not self.check_server_devices_busy():
                        break 
            '''
            setattr(self.psd_widget, 'filling_status_syringe_{}'.format(syringe_index), not getattr(self.psd_widget, 'filling_status_syringe_{}'.format(syringe_index)))
            if self.pump_settings['S{}_{}'.format(syringe_index, self.psd_widget.connect_valve_port[syringe_index])] == 'cell_inlet':
                print('switch mvp now!')
                self.psd_widget.mvp_connected_valve = 'S{}_{}'.format(syringe_index, self.psd_widget.connect_valve_port[syringe_index])
                self.psd_widget.mvp_channel = int(self.pump_settings['S{}_mvp'.format(syringe_index)].rsplit('_')[1])
                if not self.demo:  
                    '''          
                    while True:
                        if not self.check_server_devices_busy():
                            break 
                    '''
                    self.server_devices['mvp_valve'].moveValve(self.psd_widget.mvp_channel)
                    self.server_devices['mvp_valve'].join()
        '''
        while True:
            if not self.check_server_devices_busy():
                break
            else:
                pass
        '''
        if not self.demo:
            #make sure the mvp vale is switched succesfully
            '''
            while True:
                if not self.check_server_devices_busy():
                    break
            '''
            self.server_devices['exchange_pair']['S1_S3'].swap()
            self.server_devices['exchange_pair']['S2_S4'].swap()
            if self.psd_widget.filling_status_syringe_1: #if pushing for S1, it is connected to cell for exchange
                self.server_devices['exchange_pair']['S1_S3'].exchange(volume = self.server_devices['exchange_pair']['S1_S3'].exchangeableVolume,rate = float(self.settings['refill_speed_handle']())*1000)
                self.server_devices['exchange_pair']['S2_S4'].exchange(volume = self.server_devices['exchange_pair']['S2_S4'].exchangeableVolume,rate = float(self.settings['exchange_speed_handle']())*1000)
            else:
                self.server_devices['exchange_pair']['S1_S3'].exchange(volume = self.server_devices['exchange_pair']['S1_S3'].exchangeableVolume,rate = float(self.settings['exchange_speed_handle']())*1000)
                self.server_devices['exchange_pair']['S2_S4'].exchange(volume = self.server_devices['exchange_pair']['S2_S4'].exchangeableVolume,rate = float(self.settings['refill_speed_handle']())*1000)
            #if the syringe start moving
            #self.server_devices['exchange_pair']['S1_S3'].join()
            #self.server_devices['exchange_pair']['S2_S4'].join()
            while True:
                if self.check_server_devices_busy():
                    break
        
    #set addup_speed when clicking fill or dispense during exchange
    def set_addup_speed(self, overshoot = 0):
        self.settings['addup_speed'] = self.settings['exchange_speed'] + self.settings['extra_amount_speed_handle']()/1000/(1000/self.timeout)*[-1,1][int(self.extra_amount_fill)] - overshoot

    def update_extra_amount(self):
        self.fill_or_dispense_extra_amount = self.fill_or_dispense_extra_amount - self.settings['extra_amount_speed_handle']()/1000/(1000/self.timeout)
        if self.fill_or_dispense_extra_amount < 0:
            self.settings['extra_amount_timer'].stop()
            return abs(self.fill_or_dispense_extra_amount)
        else:
            return 0

    def _pair_key(self):
        for syringe_index in [1,2,3,4]:
            if self.pump_settings['S{}_{}'.format(syringe_index, self.psd_widget.connect_valve_port[syringe_index])] == 'cell_inlet':
                if syringe_index in [1,3]:
                    return 'S1_S3'
                else:
                    return 'S2_S4'

    def _volume(self):
        return self.settings['total_exchange_amount_handle']()*1000

    def _rate(self):
        return self.settings['exchange_speed_handle']()*1000

    def _increase_or_decrease_check(self):
        return self.extra_amount_fill

    def start_extra_amount_server(self):
        pair_key = self._pair_key()
        volume = self._volume()
        rate = self._rate()
        if self._increase_or_decrease_check():
            self.psd_server['exchange_pair'][pair_key].increaseVolume(volume, rate)
        else:
            self.psd_server['exchange_pair'][pair_key].decreaseVolume(volume, rate)

    def start_thread(self):
        if self.thread_fill_or_dispense_extra_amount.is_alive():
            #self.thread_fill_or_dispense_extra_amount.start()
            pass
        else:
            self.thread_fill_or_dispense_extra_amount = threading.Thread(target=self.start_extra_amount_server, args=(), daemon = True)
            self.thread_fill_or_dispense_extra_amount.start()

    def _syringe_motions(self, index = [1,2,3,4],overshoot_amount = 0):
        for i in index:
            if self.settings['extra_amount_timer'].isActive():
                if i == self.psd_widget.get_syringe_index_mvp_connection():
                    self.set_addup_speed(overshoot_amount)
                    self.single_syringe_motion(i, speed_tag = 'addup_speed', continual_exchange = True, demo = self.demo)
                else:
                    if i in self.psd_widget.get_refill_syringes_advance_exchange_mode():
                        self.single_syringe_motion(i, speed_tag = 'refill_speed', continual_exchange = True, demo = self.demo)
                    else:
                        self.single_syringe_motion(i, speed_tag = 'exchange_speed', continual_exchange = True, demo = self.demo)
            else:
                if i in self.psd_widget.get_refill_syringes_advance_exchange_mode():
                    self.single_syringe_motion(i, speed_tag = 'refill_speed', continual_exchange = True, demo = self.demo)
                else:
                    self.single_syringe_motion(i, speed_tag = 'exchange_speed', continual_exchange = True, demo = self.demo)

    def start_motion(self):
        self.settings['volume_record_handle'](round(self.exchange_amount_already*1000,0))
        overshoot_amount = 0
        ready = self.check_synchronization()
        # print('Ready or not:',ready)
        if ready:
            if not self.timer_motion.isActive():
                return
            if self.onetime:
                self.timer_motion.stop()
                return
            '''
            if not self.demo:
                if not self.check_server_devices_ready():
                    return
            '''
            self.switch_state_during_exchange(syringe_index_list = [1, 2, 3, 4])
            self.set_status_to_moving()
            if self.settings['extra_amount_timer'].isActive():
                overshoot_amount = self.update_extra_amount()
                if not self.demo:
                    self.start_thread()
            self._syringe_motions(index = range(1,5), overshoot_amount = overshoot_amount)
        else:
            if self.settings['extra_amount_timer'].isActive():
                overshoot_amount = self.update_extra_amount()
                if not self.demo:
                    self.start_thread()
            self._syringe_motions(index = range(1,5), overshoot_amount = overshoot_amount)

    def check_synchronization(self):
        #whichever is ready, the valve positions of all syringes will switch over
        gui_ready = False
        # print('Exchange syringe no:',self.psd_widget.get_exchange_syringes_advance_exchange_mode())
        # for i in self.psd_widget.get_exchange_syringes_advance_exchange_mode():
            # print(i, self.settings['syringe{}_status'.format(i)])
        for i in self.psd_widget.get_exchange_syringes_advance_exchange_mode():
            if self.settings['syringe{}_status'.format(i)]=='ready':
                gui_ready = True
                break
        if self.exchange_amount_already>=self.total_exchange_amount:
            self.timer_motion.stop()
            gui_ready = True
        '''    
        if not self.demo:
            server_ready = self.check_server_devices_ready()
        else:
            server_ready = True
        '''
        return gui_ready

    def check_synchronization_premotion(self):
        #whichever is ready, the valve positions of all syringes will switch over
        gui_ready = True
        for i in [1,2,3,4]:
            if self.settings['syringe{}_status'.format(i)]!='ready':
                gui_ready = False
                break
        '''    
        if not self.demo:
            server_ready = self.check_server_devices_ready()
        else:
            server_ready = True
        '''    
        return gui_ready

    def set_status_to_moving(self):
        for i in [1,2,3,4]:
            self.settings['syringe{}_status'.format(i)] = 'moving'

class cleanOperationMode(baseOperationMode):
    def __init__(self, psd_server, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings, demo):
        super().__init__(psd_server, psd_widget, error_widget, timer_premotion, timer_motion,timeout, pump_settings, settings)
        self.demo = demo
        self.operation_mode = 'clean_mode'
        self.timer_motion.timeout.connect(self.start_motion)
        self.syringe_index = None
        self.refill_times_already = 0
        self.check_settings()

    def check_settings(self):
        missed = []
        for each in ['syringe_handle','inlet_port_handle','outlet_port_handle','refill_speed_handle','refill_times_handle','holding_time_handle']:
            if each not in self.settings:
                missed.append(each)
        if len(missed)>0:
            logging.getLogger().exception('Missing the following keys in this clean_mode settings:{}'.format(','.join(missed)))

    def init_motion(self):
        #syringe index
        syringe = self.settings['syringe_handle']()
        self.syringe_index = syringe
        self.psd_widget.operation_mode = 'clean_mode'
        self.psd_widget.actived_syringe_fill_cell_mode = syringe
        if getattr(self.psd_widget,'volume_syringe_{}'.format(syringe))<self.psd_widget.syringe_size:
            self.turn_valve(syringe,self.settings['inlet_port_handle']())
            setattr(self.psd_widget,'filling_status_syringe_{}'.format(syringe),True)
        elif getattr(self.psd_widget,'volume_syringe_{}'.format(syringe))==self.psd_widget.syringe_size:
            self.turn_valve(syringe, self.settings['outlet_port_handle']())
            setattr(self.psd_widget,'filling_status_syringe_{}'.format(syringe),False)
        self.psd_widget.refill_speed_fill_cell_mode = self.settings['refill_speed_handle']()
        self.psd_widget.refill_times_fill_cell_mode = self.settings['refill_times_handle']()

        #append info in settings
        self.settings['speed'] = self.settings['refill_speed_handle']()/(1000/self.timeout)
        self.settings['syringe{}_status'.format(syringe)] ='moving'
        self.settings['syringe_{}_min'.format(syringe)] =  0
        self.settings['syringe_{}_max'.format(syringe)] = self.psd_widget.syringe_size
        self.settings['possible_connection_valves_syringe_{}'.format(syringe)] = [self.settings['inlet_port_handle'](),self.settings['outlet_port_handle']()]
        self.psd_widget.update()

        if not self.demo:
            while True:
                if not self.server_devices['T_valve'][syringe].busy:
                    if getattr(self.psd_widget,'filling_status_syringe_{}'.format(syringe)):
                        self.server_devices['syringe'][syringe].fill(rate = self.settings['speed']*10*1000)
                    else:
                        self.server_devices['syringe'][syringe].drain(rate = self.settings['speed']*10*1000)

    def start_timer_motion(self,kwargs = 1):
        self.refill_times_already = 0
        self.init_motion()
        self.timer_motion.start(100)

    def check_synchronization(self):
        return self.settings['syringe'+str(self.syringe_index)+'_status']=='ready'

    def switch_state_during_exchange(self):
        #turn valve
        self.turn_valve(self.syringe_index)
        #switch filling status
        setattr(self.psd_widget,'filling_status_syringe_{}'.format(self.syringe_index),not getattr(self.psd_widget,'filling_status_syringe_{}'.format(self.syringe_index)))
        #switch motion state
        self.settings['syringe'+str(self.syringe_index)+'_status'] = 'moving'
        if not self.demo:
            while True:
                if not self.server_devices['T_valve'][self.syringe_index].busy:
                    if getattr(self.psd_widget,'filling_status_syringe_{}'.format(self.syringe_index)):
                        self.server_devices['syringe'][self.syringe_index].fill(rate = self.settings['speed']*10*1000)
                    else:
                        self.server_devices['syringe'][self.syringe_index].drain(rate = self.settings['speed']*10*1000)

    def start_motion(self):
        ready = self.check_synchronization()
        if ready:
            self.refill_times_already = self.refill_times_already + 1
            if self.refill_times_already == self.settings['refill_times_handle']():
                if self.timer_motion.isActive():
                    self.timer_motion.stop()
            else:#switch status
                self.switch_state_during_exchange()
                self.single_syringe_motion(self.syringe_index, speed_tag = 'speed', continual_exchange = True)
                self.psd_widget.update()
        else:
            self.single_syringe_motion(self.syringe_index, speed_tag = 'speed', continual_exchange = True)

class fillCellOperationMode(baseOperationMode):
    def __init__(self, psd_server, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings, demo):
        super().__init__(psd_server, psd_widget, error_widget, timer_premotion, timer_motion,timeout, pump_settings, settings)
        self.demo = demo
        self.operation_mode = 'fill_cell_mode'
        self.timer_motion.timeout.connect(self.start_motion)
        self.syringe_index = None
        self.refill_times_already = 0
        self.check_settings()

    def check_settings(self):
        missed = []
        for each in ['push_syringe_handle','refill_speed_handle','refill_times_handle','waste_disposal_vol_handle','waste_disposal_speed_handle','cell_dispense_vol_handle']:
            if each not in self.settings:
                missed.append(each)
        if len(missed)>0:
            logging.getLogger().exception('Missing the following keys in this refill_cell_mode settings:{}'.format(','.join(missed)))

    def init_motion(self):
        #syringe index
        self.check_settings()
        syringe = self.settings['push_syringe_handle']()
        self.syringe_index = syringe
        self.psd_widget.operation_mode = 'fill_cell_mode'
        self.psd_widget.actived_syringe_fill_cell_mode = syringe
        #in this mode, the syringe is always pushing
        setattr(self.psd_widget,'filling_status_syringe_{}'.format(syringe),False)

        #start with connecting to waste
        self.turn_valve(syringe,'up')
        #self.psd_widget.connect_valve_port[syringe] = 'up'

        '''
        if self.pump_settings['S{}_{}'.format(syringe, self.psd_widget.connect_valve_port[syringe])] == 'cell_inlet':
            self.psd_widget.mvp_connected_valve = 'S{}_{}'.format(syringe, self.psd_widget.connect_valve_port[syringe])
            self.psd_widget.mvp_channel = int(self.pump_settings['S{}_mvp'.format(syringe)].rsplit('_')[1])
        '''
        self.psd_widget.refill_speed_fill_cell_mode = self.settings['refill_speed_handle']()
        self.psd_widget.disposal_speed_fill_cell_mode = self.settings['waste_disposal_speed_handle']()
        self.psd_widget.refill_times_fill_cell_mode = self.settings['refill_times_handle']()

        #append info in settings
        self.settings['cell_speed'] = self.settings['refill_speed_handle']()/(1000/self.timeout)
        self.settings['waste_speed'] = self.settings['waste_disposal_speed_handle']()/(1000/self.timeout)
        self.settings['vol_to_waste'] = self.settings['waste_disposal_vol_handle']()#in ml
        self.settings['vol_to_cell'] = self.settings['cell_dispense_vol_handle']()#in ml
        self.settings['syringe{}_status'.format(syringe)] ='moving'
        self.settings['syringe_{}_max'.format(syringe)] =  eval('self.psd_widget.volume_syringe_{}'.format(syringe))
        self.settings['syringe_{}_min'.format(syringe)] = max([0,eval('self.psd_widget.volume_syringe_{}'.format(syringe))-self.settings['vol_to_waste']])
        self.settings['possible_connection_valves_syringe_{}'.format(syringe)] = ['up','right']
        self.psd_widget.update()
        if not self.demo:
            while True:
                if not self.server_devices['T_valve'][syringe].busy:
                    self.server_devices['syringe'][syringe].dispense(volume = self.settings['vol_to_waste']*1000, rate = self.settings['waste_speed']*10*1000)
                    break
                else:
                    pass

    def start_timer_motion(self,kwargs = 1):
        self.refill_times_already = 0
        self.init_motion()
        self.timer_motion.start(100)

    def check_synchronization(self):
        gui_ready = self.settings['syringe'+str(self.syringe_index)+'_status']=='ready'
        return gui_ready

    def switch_state_during_exchange(self):
        #turn valve
        self.turn_valve(self.syringe_index)
        vol_dispense, speed_dispense = 0, 0
        if self.psd_widget.connect_valve_port[self.syringe_index] == 'up':#waste
            vol_dispense = self.settings['vol_to_waste']*1000
            speed_dispense = self.settings['waste_speed']*10*1000
            self.settings['syringe_{}_max'.format(self.syringe_index)] =  eval('self.psd_widget.volume_syringe_{}'.format(self.syringe_index))
            self.settings['syringe_{}_min'.format(self.syringe_index)] = max([0,eval('self.psd_widget.volume_syringe_{}'.format(self.syringe_index))-self.settings['vol_to_waste']])
        elif self.psd_widget.connect_valve_port[self.syringe_index] == 'right':#cell
            vol_dispense = self.settings['vol_to_cell']*1000
            speed_dispense = self.settings['cell_speed']*10*1000
            self.settings['syringe_{}_max'.format(self.syringe_index)] =  eval('self.psd_widget.volume_syringe_{}'.format(self.syringe_index))
            self.settings['syringe_{}_min'.format(self.syringe_index)] = max([0,eval('self.psd_widget.volume_syringe_{}'.format(self.syringe_index))-self.settings['vol_to_cell']])

        #switch motion state
        self.settings['syringe'+str(self.syringe_index)+'_status'] = 'moving'
        #switch to the right mvp channel 
        if self.pump_settings['S{}_{}'.format(self.syringe_index, self.psd_widget.connect_valve_port[self.syringe_index])] == 'cell_inlet':
            #print('switch mvp now!')
            self.psd_widget.mvp_connected_valve = 'S{}_{}'.format(self.syringe_index, self.psd_widget.connect_valve_port[self.syringe_index])
            self.psd_widget.mvp_channel = int(self.pump_settings['S{}_mvp'.format(self.syringe_index)].rsplit('_')[1])
        if not self.demo:
            self.server_devices['mvp_valve'].moveValve(self.psd_widget.mvp_channel)
            while True:
                if (not self.server_devices['T_valve'][self.syringe_index].busy) and (not self.server_devices['mvp_valve'].busy):
                    self.server_devices['syringe'][self.syringe_index].dispense(volume = vol_dispense, rate = speed_dispense)
                    break
                else:
                    pass
        return True

    def start_motion(self):
        gui_ready = self.check_synchronization()
        if gui_ready:
            self.refill_times_already = self.refill_times_already + 1
            if self.refill_times_already == self.settings['refill_times_handle']():
                if self.timer_motion.isActive():
                    self.timer_motion.stop()
            else:#switch status
                self.switch_state_during_exchange()
                speed_tag = 'waste_speed'
                if self.psd_widget.connect_valve_port[self.syringe_index] == 'right':
                    speed_tag = 'cell_speed'
                self.single_syringe_motion(self.syringe_index, speed_tag = speed_tag, continual_exchange = False, use_limits_for_exchange = False, demo = self.demo)
                self.psd_widget.update()
        else:
            speed_tag = 'waste_speed'
            if self.psd_widget.connect_valve_port[self.syringe_index] == 'right':
                speed_tag = 'cell_speed'
            self.single_syringe_motion(self.syringe_index, speed_tag = speed_tag, continual_exchange = False, use_limits_for_exchange = False, demo = self.demo)

class normalOperationMode(baseOperationMode):
    def __init__(self, psd_server, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings, demo):
        super().__init__(psd_server, psd_widget, error_widget, timer_premotion, timer_motion,timeout, pump_settings, settings)
        self.demo = demo
        self.operation_mode = 'normal_mode'
        self.timer_motion.timeout.connect(self.start_motion)
        self.syringe_index = None
        self.check_settings()

    def check_settings(self):
        missed = []
        for each in ['syringe_handle','valve_position_handle','valve_connection_handle', 'vol_handle','speed_handle']:
            if each not in self.settings:
                missed.append(each)
        if len(missed)>0:
            logging.getLogger().exception('Missing the following keys in this normal_mode settings:{}'.format(','.join(missed)))

    def init_motion(self):
        #syringe_index = int(self.settings['syringe_handle']())
        syringe_index = self.syringe_index
        valve_position = self.settings['valve_position_handle'](syringe_index)
        valve_connection = self.settings['valve_connection_handle'](syringe_index)
        # vol = float(self.settings['vol_handle'](syringe_index))*self.psd_widget.syringe_size #note the vol in GUI is in stroke unit
        # speed = float(self.settings['speed_handle'](syringe_index))/(1000/self.timeout)
        vol = float(self.settings['vol_handle'](syringe_index))/1000 #note the vol in GUI is in uL unit
        speed = float(self.settings['speed_handle'](syringe_index))/1000/(1000/self.timeout) #note the vol in GUI is in uL unit

        #set widget variables
        self.psd_widget.operation_mode = 'normal_mode'
        self.turn_valve(syringe_index, valve_position)
        self.psd_widget.actived_syringe_normal_mode = syringe_index
        self.psd_widget.actived_syringe_valve_connection = valve_connection
        self.psd_widget.speed_normal_mode = speed
        self.psd_widget.volume_normal_mode = vol

        #append info in settings
        self.settings['speed'] = speed
        self.settings['syringe{}_status'.format(syringe_index)] ='moving'
        self.settings['syringe_{}_min'.format(syringe_index)] = max([getattr(self.psd_widget,'volume_syringe_{}'.format(syringe_index)) - vol, 0])
        self.settings['syringe_{}_max'.format(syringe_index)] = min([getattr(self.psd_widget,'volume_syringe_{}'.format(syringe_index)) + vol, self.psd_widget.syringe_size])

        if not self.demo:
            self.server_devices['mvp_valve'].moveValve(self.psd_widget.mvp_channel)
            #waiting for the server devices(valves) to be ready
            while True:
                if not self.server_devices['mvp_valve'].busy:
                    break
                else:
                    pass
            while True:
                if not self.server_devices['T_valve'][syringe_index].busy:
                    if eval('self.psd_widget.filling_status_syringe_{}'.format(syringe_index)):#if true then pushing the syringe
                        try:
                            self.server_devices['syringe'][syringe_index].pickup(volume= vol*1000, rate = speed*10*1000)
                        except ValueError:
                            self.server_devices['syringe'][syringe_index].fill(rate = speed*10*1000)
                    else:
                        try:
                            self.server_devices['syringe'][syringe_index].dispense(volume= vol*1000, rate = speed*10*1000)
                        except ValueError:
                            self.server_devices['syringe'][syringe_index].drain(rate = speed*10*1000)
                    break
                else:
                    pass

        self.psd_widget.update()

    def start_timer_motion(self):
        self.init_motion()
        self.timer_motion.start(100)

    def start_motion(self):
        if self.settings['syringe'+str(self.syringe_index)+'_status']=='ready':
            if self.timer_motion.isActive():
                self.timer_motion.stop()
        else:
            self.single_syringe_motion(self.syringe_index, speed_tag = 'speed', continual_exchange = False, demo = self.demo)

class initOperationMode(baseOperationMode):
    def __init__(self, psd_server, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings, demo):
        super().__init__(psd_server, psd_widget, error_widget, timer_premotion, timer_motion,timeout, pump_settings, settings)
        self.demo = demo
        self.operation_mode = 'init_mode'
        self.timer_motion.timeout.connect(self.exchange_motion)
        self.check_settings()
        # self.init_motion()

    def check_settings(self):
        missed = []
        for each in ['pull_syringe_handle','push_syringe_handle','vol_handle','speed_handle']:
            if each not in self.settings:
                missed.append(each)
        if len(missed)>0:
            logging.getLogger().exception('Missing the following keys in the Init mode settings:{}'.format(','.join(missed)))

    def init_motion(self):
        pull_syringe_index = int(self.settings['pull_syringe_handle']())
        push_syringe_index = int(self.settings['push_syringe_handle']())
        vol = self.settings['vol_handle']()/1000 # in uL in GUI
        speed = float(self.settings['speed_handle']())/1000/(1000/self.timeout) #timeout in ms
        self.psd_widget.operation_mode = 'init_mode'
        #which one is the syringe to pull electrolyte from cell
        self.psd_widget.actived_pulling_syringe_init_mode = int(pull_syringe_index)
        #which one is the syringe to push electrolyte to cell
        self.psd_widget.actived_pushing_syringe_init_mode = int(push_syringe_index)
        exec('self.psd_widget.filling_status_syringe_{}=True'.format(pull_syringe_index))
        exec('self.psd_widget.filling_status_syringe_{}=False'.format(push_syringe_index))
        self.settings['syringe{}_status'.format(pull_syringe_index)] ='moving'
        self.settings['syringe{}_status'.format(push_syringe_index)] ='moving'
        self.settings['syringe_{}_min'.format(pull_syringe_index)] = getattr(self.psd_widget,'volume_syringe_{}'.format(pull_syringe_index))
        self.settings['syringe_{}_max'.format(pull_syringe_index)] = getattr(self.psd_widget,'volume_syringe_{}'.format(pull_syringe_index)) + vol
        self.settings['syringe_{}_max'.format(push_syringe_index)] = getattr(self.psd_widget,'volume_syringe_{}'.format(push_syringe_index))
        self.settings['syringe_{}_min'.format(push_syringe_index)] = getattr(self.psd_widget,'volume_syringe_{}'.format(push_syringe_index)) - vol
        self.settings['speed'] = speed
        #self.psd_widget.connect_valve_port[pull_syringe_index] = 'left'
        #self.psd_widget.connect_valve_port[push_syringe_index] = 'right'
        self.turn_valve(pull_syringe_index, 'left')
        self.turn_valve(push_syringe_index, 'right')
        if not self.demo:
            while True:
                if not self.check_server_devices_busy():
                    if self.psd_widget.actived_syringe_motion_init_mode == 'fill':
                        index = self.psd_widget.actived_pushing_syringe_init_mode
                        self.server_devices['syringe'][index].dispense(volume= vol*1000, rate = speed*10*1000)
                    elif self.psd_widget.actived_syringe_motion_init_mode == 'dispense':
                        index = self.psd_widget.actived_pulling_syringe_init_mode
                        self.server_devices['syringe'][index].pickup(volume= vol*1000, rate = speed*10*1000)
                    break
            while True:
                if self.check_server_devices_busy():
                    break 
                else:
                    pass
        self.psd_widget.update()

    def start_exchange_timer(self):
        self.init_motion()
        self.timer_motion.start(100)

    def exchange_motion(self):
        if self.psd_widget.actived_syringe_motion_init_mode == 'fill':
            index = self.psd_widget.actived_pushing_syringe_init_mode
        elif self.psd_widget.actived_syringe_motion_init_mode == 'dispense':
            index = self.psd_widget.actived_pulling_syringe_init_mode

        if self.settings['syringe'+str(index)+'_status']=='ready':
            if self.timer_motion.isActive():
                self.timer_motion.stop()
        else:
            pass
        self.single_syringe_motion(index, speed_tag = 'speed', continual_exchange = False, demo = self.demo)





