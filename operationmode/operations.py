import numpy as np
from PyQt5.QtCore import QTimer

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

class initOperationMode(baseOperationMode):
    def __init__(self, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings):
        super().__init__(psd_widget, error_widget, timer_premotion, timer_motion, pump_settings, settings)
        self.check_settings()
        self.operation_mode = 'init_mode'

    def check_settings(self):
        missed = []
        for each in ['pull_syringe_handle','push_syringe_handle','push_vol_handle','speed_handle','init_mode']:
            if each not in self.settings:
                missed.append(each)
        if len(missed)>0:
            logging.getLogger().exception('Missing the following keys in the Init mode settings:{}'.format(','.join(missed)))

    def init_motion(self):
        pull_syringe_index = int(self.settings['pull_syringe_handle']())
        push_syringe_index = int(self.settings['push_syringe_handle']())
        vol = self.settings['push_vol_handle']()/1000 # in uL in GUI
        speed = float(self.settings['speed_handle']())/1000/(1000/timeout) #timeout in ms
        self.psd_widget.operation_mode = 'init_mode'
        #which one is the syringe to pull electrolyte from cell
        self.psd_widget.actived_pulling_syringe_init_mode = int(pull_syringe_index)
        #which one is the syringe to push electrolyte to cell
        self.psd_widget.actived_pushing_syringe_init_mode = int(push_syringe_index)
        #self.psd_widget.actived_syringe_motion_init_mode = 'fill'
        exec('self.filling_status_syringe_{}=True'.format(pull_syringe_index))
        exec('self.filling_status_syringe_{}=False'.format(push_syringe_index))
        self.settings['syringe_{}_min'.format(pull_syringe_index)] = getattr(self.psd_widget,'volume_syringe_{}'.format(pull_syringe_index))
        self.settings['syringe_{}_max'.format(pull_syringe_index)] = getattr(self.psd_widget,'volume_syringe_{}'.format(pull_syringe_index)) + vol
        self.settings['syringe_{}_max'.format(push_syringe_index)] = getattr(self.psd_widget,'volume_syringe_{}'.format(push_syringe_index))
        self.settings['syringe_{}_min'.format(push_syringe_index)] = getattr(self.psd_widget,'volume_syringe_{}'.format(push_syringe_index)) - vol
        self.settings['speed'] = speed
        self.psd_widget.connect_valve_port[pull_syringe_index] = 'left'
        self.psd_widget.connect_valve_port[push_syringe_index] = 'right'
        self.psd_widget.update()

    def exchange_motion(self,index):
        self.single_syringe_motion(index, speed_tag = 'speed', continual_exchange = False)
        if getattr(self, 'syringe'+str(index)+'_status')=='ready':
            if self.timer_motion.isActive():
                self.timer_motion.stop()
        else:
            pass


class baseOperationMode(object):
    def __init__(self, psd_widget, error_widget, timer_premotion, timer_motion, timeout, pump_settings, settings):
        self.psd_widget = psd_widget
        self.error_widget = error_widget
        self.timer_premotion = timer_premotion
        self.timer_motion = timer_motion
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

    def single_syringe_motion(self, index, speed_tag = 'speed', continual_exchange = True):
        #move the syringe under the physical limit, and update the volum of the part (cell, resevior or waste) which it is connection to.
        #index: index (eg 1 or 2 or 3) for syringe
        #direction_sign: either 1(filling syringe) or -1(dispense syringe)
        type_ = 'syringe'
        speed_name_in_widget = self.settings.get(speed_tag)
        if speed_name_in_widget == None:
            logging.getLogger().exception('Error: The speed is not set in the settings')
            return
        else:
            speed = getattr(self.psd_widget, speed_name_in_widget)
        #the name of syringe defined in the psd_widget
        #looks like volume_syringe_1, volume_syringe_2
        type_name_in_widget = self.settings.get(type_+str(index))
        direction_sign = [-1,1][int(getattr(self.psd_widget,'filling_status_syringe_{}'.format(index)))]
        if type_name_in_widget == None:
            logging.getLogger().exception('Error: The key {} is not set in the settings'.format(type_+str(index)))
            return
        value_before_motion = getattr(self.psd_widget, type_name_in_widget)
        #if direction_sign not in [1, -1]:
        #    logging.getLogger().exception('Error: The value of direction_sign could only be either 1 or -1, but not others')
        #    return
        value_after_motion = value_before_motion + speed*direction_sign
        if continual_exchange:
            checked_value = self.check_limits(value_after_motion, type_)
        else:
            #you need to specify the range of volume of this syringe, eg syringe_1_min, syringe_1_max
            checked_value = self.check_limits(value_after_motion, type_, min_vol = getattr(self, type_+str(index)+'_min'), max_vol = getattr(self, type_+str(index)+'_max'))

        if (not continual_exchange) and (checked_value > 0):
            setattr(self, type_+str(index)+'_status', 'ready')

        #corrected speed considering the possible overshootting in syringe motion
        #this speed will be taken to update the volume of the part the syringe connecting to right now
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
            if connection not in ['resevoir', 'cell_outlet']:
                logging.getLogger().exception('Pump setting Error:YOU ARE ONLY allowed to withdraw solution from RESEVOIR or CELL_OUTLET')
            elif connection == 'resevoir':
                checked_value_connection_part = {'type':'resevoir', 'checked_value':self.check_limits(self.psd_widget.resevoir_volumn-speed_new, 'resevoir')}
                self.psd_widget.resevoir_volumn = self.psd_widget.resevoir_volumn - (speed_new - checked_value_connection_part['checked_value'])
            elif connection == 'cell_outlet':
                checked_value_connection_part = {'type':'cell', 'checked_value':self.check_limits(self.psd_widget.volume_of_electrolyte_in_cell-speed_new, 'cell')}
                self.psd_widget.volume_of_electrolyte_in_cell = self.psd_widget.volume_of_electrolyte_in_cell - (speed_new - checked_value_connection_part['checked_value'])

        speed_syringe = speed_new
        if len(checked_value_connection_part)!=0:
            if checked_value_connection_part['checked_value']==0: # do normally the volume update if True
                speed_syringe = speed_new
                setattr(self.psd_widget, type_name_in_widget, value_before_motion + direction_sign*speed_syringe)
            else:#overshooting in cell, resevior or waste. You should stop the timer then.
                speed_syringe = speed_new - checked_value_connection_part['checked_value']
                #update the syringe volume according to this speed
                setattr(self.psd_widget, type_name_in_widget, value_before_motion + direction_sign*speed_syringe)
                if self.timer_motion.isActive():
                    self.timer_motion.stop()
                if self.timer_premotion.isActive():
                    elf.timer_premotion.stop()
        if getattr(self.psd_widget, type_name_in_widget) == self.psd_widget.syringe_size:
            setattr(self, type_+str(index)+'_status', 'ready')
        elif getattr(self.psd_widget, type_name_in_widget) == 0:
            setattr(self, type_+str(index)+'_status', 'ready')
        else:
            setattr(self, type_+str(index)+'_status', 'moving')

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

    #mode dependent
    def check_synchronization(self, index_list):
        pass

    def turn_valve(self, index, to_position = None):
        if to_position in ['up','left','right']:
            if index in self.psd_widget.connect_valve_port:
                self.psd_widget.connect_valve_port[index] = to_position
            else:
                logging.getLogger().exception('The syringe index {} is not registered.'.format(index))
        elif to_position == None:#switch the vale to the other possible position
            possible_valve_positions = get(self.settings, 'possible_connection_valves_syringe_{}'.format(index))
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
                





