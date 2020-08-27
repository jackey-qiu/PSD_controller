import numpy as np
from PyQt5.QtCore import QTimer
import logging
import time

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
    def __init__(self, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings):
        self.switch_success_pump_server = True
        self.server_ready = False
        self.psd_widget = psd_widget
        self.error_widget = error_widget
        self.timer_premotion = timer_premotion
        self.timer_motion = timer_motion
        self.timeout = timeout
        self.pump_settings = pump_settings
        self.settings = settings
        #set redirection of error message to embeted text browser widget
        logTextBox = QTextEditLogger(error_widget)
        # You can format what is printed to text box
        logTextBox.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(logTextBox)
        # You can control the logging level
        logging.getLogger().setLevel(logging.DEBUG)

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

    def single_syringe_motion(self, index, speed_tag = 'speed', continual_exchange = True):
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
            checked_value = self.check_limits(value_after_motion, type_)
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
            if abs(getattr(self.psd_widget, type_name_in_widget) - self.psd_widget.syringe_size)<0.0000001:
                self.set_status(index,'ready')
            elif abs(getattr(self.psd_widget, type_name_in_widget))<0.0000001:
                self.set_status(index,'ready')
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

    def turn_valve(self, index, to_position = None):
        if to_position in ['up','left','right']:
            if index in self.psd_widget.connect_valve_port:
                self.psd_widget.connect_valve_port[index] = to_position
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
                    else:
                        logging.getLogger().exception('The syringe index {} is not registered.'.format(index))
            else:
                logging.getLogger().exception('Valve turning error: possible_connection_valves_syringe_{} is not the member of settings'.format(index))

class simpleRefillingOperationMode(baseOperationMode):
    def __init__(self, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings):
        super().__init__(psd_widget, error_widget, timer_premotion, timer_motion,timeout, pump_settings, settings)
        self.operation_mode = 'simple_exchange_mode'
        self.onetime = False
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
        for each in ['pull_syringe_handle','push_syringe_handle','refill_speed_handle','exchange_speed_handle']:
            if each not in self.settings:
                missed.append(each)
        if len(missed)>0:
            logging.getLogger().exception('Missing the following keys in the Init mode settings:{}'.format(','.join(missed)))

    def init_premotion(self):
        pull_syringe_index = int(self.settings['pull_syringe_handle']())
        push_syringe_index = int(self.settings['push_syringe_handle']())
        refill_speed = float(self.settings['refill_speed_handle']())/(1000/self.timeout) #timeout in ms
        exchange_speed = float(self.settings['exchange_speed_handle']())/(1000/self.timeout) #timeout in ms
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
        #TODO: send cmd to server to turn valve to the right position. Program should suspend until the valve are turned sucessfully. 
        #Also update the speed in syringe instance, which should be refill_speed here

    def start_premotion_timer(self):
        self.init_premotion()
        #TODO (Before timer started!): send cmd to server to apply motions of the related syringes. Under exchange mode, cmd should be broadcasted instead of send one by one to allow synchronization.
        #Program continues upon all syringes starting to move.
        self.timer_premotion.start(100)

    def premotion(self):
        if self.check_synchronization():
            if self.timer_premotion.isActive():
                self.timer_premotion.stop()
                #self.init_motion()
                #TODO (Before timer starts!!): send cmd to server to apply motions of the related syringes. Under exchange mode, cmd should be broadcasted instead of send one by one to allow synchronization.
                #Now you should set the speed in syringe instances to exchange speed. Program continues upon all syringes starting to move.
                #self.timer_motion.start(100)
        else:
            for i in [int(self.settings['pull_syringe_handle']()),int(self.settings['push_syringe_handle']())]:
                self.single_syringe_motion(i, speed_tag = 'refill_speed', continual_exchange = True)

    def start_motion_timer(self,onetime):
        self.onetime = onetime
        self.init_motion()
        self.timer_motion.start(100)

    def init_motion(self):
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
        #TODO: send cmd to server to turn valve (including MVP valve) to the right position. Program should suspend until the valve are turned sucessfully.

    def exchange_motion(self):
        if self.check_synchronization():
            if not self.server_ready:
                pass
            else:
                if self.onetime:
                    self.timer_motion.stop()
                    return
                #TODO: switch status (valve positions, speed, and dispense/fill volume) in pump server side for next cycle. Update the switch_success_pump_server
                self.switch_success_pump_server = True
                if self.switch_success_pump_server:
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
                        self.single_syringe_motion(i, speed_tag = speed_tag, continual_exchange = True)
                else:
                    pass#if not ready, GUI update will be suspended!
        else:
            exchange_tag = self.check_refill_or_exchange()
            # print('I am here now. The exchange tag is {}'.format(exchange_tag))
            if exchange_tag:
                speed_tag = 'exchange_speed'
            else:
                speed_tag = 'refill_speed'
            for i in [int(self.settings['pull_syringe_handle']()),int(self.settings['push_syringe_handle']())]:
                self.single_syringe_motion(i, speed_tag = speed_tag, continual_exchange = True)

    def check_synchronization(self):
        for i in [int(self.settings['pull_syringe_handle']()),int(self.settings['push_syringe_handle']())]:
            if self.settings['syringe{}_status'.format(i)]!='ready':
                return False
        #TODO: check if all related syringes are busy (give the value to the server_ready). If so set server_ready to False, else set it to True
        self.server_ready = True
        if self.server_ready:
            #TODO: switch status (valve positions, speed, and dispense/fill volume) for next cycle.
            #return True
            pass
        return True

    def check_refill_or_exchange(self):
        index_pushing = int(self.settings['push_syringe_handle']())
        if self.pump_settings['S{}_{}'.format(index_pushing, self.psd_widget.connect_valve_port[index_pushing])] == 'cell_inlet':
            return True#if under exchange state
        else:
            return False#if under refilling state

    def switch_state_during_exchange(self, syringe_index_list):
        for syringe_index in syringe_index_list:
            self.turn_valve(syringe_index)
            setattr(self.psd_widget, 'filling_status_syringe_{}'.format(syringe_index), not getattr(self.psd_widget, 'filling_status_syringe_{}'.format(syringe_index)))

    def set_status_to_moving(self):
        for i in [int(self.settings['pull_syringe_handle']()),int(self.settings['push_syringe_handle']())]:
            self.settings['syringe{}_status'.format(i)] = 'moving'

class advancedRefillingOperationMode(baseOperationMode):
    def __init__(self, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings):
        super().__init__(psd_widget, error_widget, timer_premotion, timer_motion,timeout, pump_settings, settings)
        self.operation_mode = 'autorefilling_mode'
        self.onetime = False
        self.timer_premotion.timeout.connect(self.premotion)
        self.timer_motion.timeout.connect(self.start_motion)
        self.check_settings()
        self.append_valve_info()
        self.waste_volume_t0 = 0
        self.exchange_t0 = 0
        self.fill_or_dispense_extra_amount = 0 
        self.extra_amount_fill = True

    def append_valve_info(self):
        self.settings['possible_connection_valves_syringe_1'] = ['left', 'right']
        self.settings['possible_connection_valves_syringe_2'] = ['left', 'right']
        self.settings['possible_connection_valves_syringe_3'] = ['left', 'up']
        self.settings['possible_connection_valves_syringe_4'] = ['left', 'up']

    def check_settings(self):
        missed = []
        for each in ['premotion_speed_handle','exchange_speed_handle', 'time_record_handle', 'volume_record_handle', 'extra_amount_timer', 'extra_amount_handle', 'extra_amount_speed_handle']:
            if each not in self.settings:
                missed.append(each)
        if len(missed)>0:
            logging.getLogger().exception('Missing the following keys in this autorefilling_mode settings:{}'.format(','.join(missed)))

    def init_premotion(self):
        self.psd_widget.operation_mode = 'pre_auto_refilling'
        speed = float(self.settings['premotion_speed_handle']())/(1000/self.timeout)
        self.settings['speed'] = speed

        def _get_plunge_position(syringe_index):
            vol = getattr(self.psd_widget,'volume_syringe_{}'.format(syringe_index))
            if vol >= self.psd_widget.syringe_size/2:
                return True
            else:
                return False

        #syringe_1 to syringe_4
        for i in [1,2,3,4]:
            if _get_plunge_position(i):
                self.turn_valve(i,'up')
                setattr(self.psd_widget, 'filling_status_syringe_{}'.format(i), False)
                self.settings['syringe_{}_min'.format(i)] = self.psd_widget.syringe_size/2
                self.settings['syringe_{}_max'.format(i)] = getattr(self.psd_widget,'volume_syringe_{}'.format(i))
            else:
                if i in [1,2]:
                    self.turn_valve(i,'left')
                else:
                    self.turn_valve(i,'right')
                setattr(self.psd_widget, 'filling_status_syringe_{}'.format(i), True)
                self.settings['syringe_{}_min'.format(i)] = getattr(self.psd_widget,'volume_syringe_{}'.format(i))
                self.settings['syringe_{}_max'.format(i)] = self.psd_widget.syringe_size/2
            self.settings['syringe{}_status'.format(i)] ='moving'

    def start_premotion_timer(self):
        self.init_premotion()
        self.timer_premotion.start(100)

    def start_motion_timer(self, onetime = False):
        self.onetime = onetime
        self.init_motion()
        self.timer_motion.start(100)

    def premotion(self):
        if self.check_synchronization():
            if self.timer_premotion.isActive():
                self.timer_premotion.stop()
                #self.init_motion()
                #self.timer_motion.start(100)
                self.exchange_t0 = time.time()
                self.waste_volume_t0 = self.psd_widget.waste_volumn
        else:
            for i in range(1,5):
                self.single_syringe_motion(i, speed_tag = 'speed', continual_exchange = False)

    def init_motion(self):
        self.psd_widget.operation_mode = 'auto_refilling'
        speed = float(self.settings['exchange_speed_handle']())/(1000/self.timeout)
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

        self.turn_valve(3,'left')
        setattr(self.psd_widget, 'filling_status_syringe_{}'.format(3), True)
        self.settings['syringe{}_status'.format(3)] ='moving'

        self.turn_valve(4,'up')
        setattr(self.psd_widget, 'filling_status_syringe_{}'.format(4), False)
        self.settings['syringe{}_status'.format(4)] ='moving'

    def switch_state_during_exchange(self, syringe_index_list):
        for syringe_index in syringe_index_list:
            self.turn_valve(syringe_index)
            setattr(self.psd_widget, 'filling_status_syringe_{}'.format(syringe_index), not getattr(self.psd_widget, 'filling_status_syringe_{}'.format(syringe_index)))
            if self.pump_settings['S{}_{}'.format(syringe_index, self.psd_widget.connect_valve_port[syringe_index])] == 'cell_inlet':
                print('switch mvp now!')
                self.psd_widget.mvp_connected_valve = 'S{}_{}'.format(syringe_index, self.psd_widget.connect_valve_port[syringe_index])
                self.psd_widget.mvp_channel = int(self.pump_settings['S{}_mvp'.format(syringe_index)].rsplit('_')[1])

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

    def start_motion(self):
        # self.settings['time_record_handle'](int(time.time()-self.exchange_t0))
        self.settings['volume_record_handle'](round(self.psd_widget.waste_volumn-self.waste_volume_t0,3))
        if self.check_synchronization():
            self.switch_state_during_exchange(syringe_index_list = [1, 2, 3, 4])
            self.set_status_to_moving()
            if self.onetime:
                self.timer_motion.stop()
                return
            if self.settings['extra_amount_timer'].isActive():
                overshoot_amount = self.update_extra_amount()
            for i in range(1,5):
                if self.settings['extra_amount_timer'].isActive():
                    if i == self.psd_widget.get_syringe_index_mvp_connection():
                        self.set_addup_speed(overshoot_amount)
                        self.single_syringe_motion(i, speed_tag = 'addup_speed', continual_exchange = True)
                    else:
                        if i in self.psd_widget.get_refill_syringes_advance_exchange_mode():
                            self.single_syringe_motion(i, speed_tag = 'refill_speed', continual_exchange = True)
                        else:
                            self.single_syringe_motion(i, speed_tag = 'exchange_speed', continual_exchange = True)
                else:
                    if i in self.psd_widget.get_refill_syringes_advance_exchange_mode():
                        self.single_syringe_motion(i, speed_tag = 'refill_speed', continual_exchange = True)
                    else:
                        self.single_syringe_motion(i, speed_tag = 'exchange_speed', continual_exchange = True)
        else:
            if self.settings['extra_amount_timer'].isActive():
                overshoot_amount = self.update_extra_amount()
            for i in range(1,5):
                if self.settings['extra_amount_timer'].isActive():
                    if i == self.psd_widget.get_syringe_index_mvp_connection():
                        self.set_addup_speed(overshoot_amount)
                        self.single_syringe_motion(i, speed_tag = 'addup_speed', continual_exchange = True)
                    else:
                        if i in self.psd_widget.get_refill_syringes_advance_exchange_mode():
                            self.single_syringe_motion(i, speed_tag = 'refill_speed', continual_exchange = True)
                        else:
                            self.single_syringe_motion(i, speed_tag = 'exchange_speed', continual_exchange = True)
                else:
                    if i in self.psd_widget.get_refill_syringes_advance_exchange_mode():
                        self.single_syringe_motion(i, speed_tag = 'refill_speed', continual_exchange = True)
                    else:
                        self.single_syringe_motion(i, speed_tag = 'exchange_speed', continual_exchange = True)

    def check_synchronization(self):
        '''
        if not self.settings['extra_amount_timer'].isActive():
            for i in [1,2,3,4]:
                if self.settings['syringe{}_status'.format(i)]!='ready':
                    return False
            return True
        else:
            for i in self.psd_widget.get_exchange_syringes_advance_exchange_mode():
                if self.settings['syringe{}_status'.format(i)]=='ready':
                    return True
            for i in [1,2,3,4]:
                if self.settings['syringe{}_status'.format(i)]=='ready':
                    self.timer_motion.stop()
                    self.settings['extra_amount_timer'].stop()
                    break
        '''
        #whichever is ready, the valve positions of all syringes will switch over
        for i in self.psd_widget.get_exchange_syringes_advance_exchange_mode():
            if self.settings['syringe{}_status'.format(i)]=='ready':
                return True 
        return False

    def set_status_to_moving(self):
        for i in [1,2,3,4]:
            self.settings['syringe{}_status'.format(i)] = 'moving'

class normalOperationMode(baseOperationMode):
    def __init__(self, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings):
        super().__init__(psd_widget, error_widget, timer_premotion, timer_motion,timeout, pump_settings, settings)
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
        vol = float(self.settings['vol_handle'](syringe_index))*self.psd_widget.syringe_size #note the vol in GUI is in stroke unit
        speed = float(self.settings['speed_handle'](syringe_index))/(1000/self.timeout)

        #set widget variables
        self.psd_widget.operation_mode = 'normal_mode'
        self.psd_widget.connect_valve_port[syringe_index] = valve_position
        self.psd_widget.actived_syringe_normal_mode = syringe_index
        self.psd_widget.actived_syringe_valve_connection = valve_connection
        self.psd_widget.speed_normal_mode = speed
        self.psd_widget.volume_normal_mode = vol

        #append info in settings
        self.settings['speed'] = speed
        self.settings['syringe{}_status'.format(syringe_index)] ='moving'
        self.settings['syringe_{}_min'.format(syringe_index)] = max([getattr(self.psd_widget,'volume_syringe_{}'.format(syringe_index)) - vol, 0])
        self.settings['syringe_{}_max'.format(syringe_index)] = min([getattr(self.psd_widget,'volume_syringe_{}'.format(syringe_index)) + vol, self.psd_widget.syringe_size])

        self.psd_widget.update()

    def start_timer_motion(self):
        self.init_motion()
        self.timer_motion.start(100)

    def start_motion(self):
        if self.settings['syringe'+str(self.syringe_index)+'_status']=='ready':
            if self.timer_motion.isActive():
                self.timer_motion.stop()
        else:
            self.single_syringe_motion(self.syringe_index, speed_tag = 'speed', continual_exchange = False)

class initOperationMode(baseOperationMode):
    def __init__(self, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings):
        super().__init__(psd_widget, error_widget, timer_premotion, timer_motion,timeout, pump_settings, settings)
        self.operation_mode = 'init_mode'
        self.timer_motion.timeout.connect(self.exchange_motion)
        self.check_settings()
        self.init_motion()

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
        self.psd_widget.connect_valve_port[pull_syringe_index] = 'left'
        self.psd_widget.connect_valve_port[push_syringe_index] = 'right'
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
        self.single_syringe_motion(index, speed_tag = 'speed', continual_exchange = False)





