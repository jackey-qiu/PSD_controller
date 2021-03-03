from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QBrush, QFont, QPen
from PyQt5.QtCore import Qt, QTimer
import sys
import numpy as np
import time

class syringe_widget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        #number of total channels in MVP
        self.number_of_channel_mvp = 5
        #mvp valve position, integer larger than 1
        self.mvp_channel = 1
        #The mvp valve position to the currently activated syringe
        self.syringe_mvp_cell_inlet_channel = 1
        #mvp connected valve: S1_right
        self.mvp_connected_valve = 'S1_right'
        #label of resevoir
        self.label_resevoir = 'Resevoir'
        #syringe info in clean_mode, keys are syringe index
        self.syringe_info_clean_mode = {1:{'refill_speed':0,'refill_times':5,'holding_time':0,'inlet_port':'left','outlet_pot':'up'},
                                        2:{'refill_speed':0,'refill_times':5,'holding_time':0,'inlet_port':'left','outlet_pot':'up'},
                                        3:{'refill_speed':0,'refill_times':5,'holding_time':0,'inlet_port':'left','outlet_pot':'up'},
                                        4:{'refill_speed':0,'refill_times':5,'holding_time':0,'inlet_port':'left','outlet_pot':'up'}}
        #volume of solution in each syringe
        self.volume_syringe_1 = 0
        self.volume_syringe_2 = 0
        self.volume_syringe_3 = 0
        self.volume_syringe_4 = 0
        #motion type for each syringe
        #True: pulling; False: Pushing
        self.filling_status_syringe_1 = True
        self.filling_status_syringe_2 = False
        self.filling_status_syringe_3 = True
        self.filling_status_syringe_4 = False
        #size of syringe
        self.syringe_size = 12.5
        #leftover volumn in resevoir
        self.resevoir_volumn = 250 #in mL
        #volumn size of resevoir bottle
        self.resevoir_volumn_total = 250 #in ml
        #volumn size of waste bottle
        self.waste_volumn_total = 250 #in ml
        #current volumn in the waste bottle
        self.waste_volumn = 0 # in mL
        #speed for auto_refilling mode
        self.speed = 0 # in mL/s
        #speed for single_mode
        self.speed_normal_mode = 0
        #volume for single mode
        self.volume_normal_mode = 0
        #default speed for fill_all and empty_all mode
        self.speed_by_default = 1
        #ref length for drawing syringe
        self.ref_unit = 15
        self.line_style = 1
        #either init_mode, auto_refilling mode or normal_mode
        self.operation_mode = 'not_ready_mode'
        #3-channel T valve position (either left, right or up)
        self.connect_valve_port = {1:'up',2:'up',3:'up',4:'up'}
        #connected status
        self.connect_status = {1:'disconnected',2:'disconnected',3:'disconnected',4:'disconnected', 'mvp': 'disconnected'}
        #The actived syringe index(only one) for operating in refill cell mode
        self.actived_syringe_fill_cell_mode = 1
        #either fill or dispense
        self.actived_syringe_motion_fill_cell_mode = 'fill'
        #refill speed for cell in fill_cell mode
        self.refill_speed_fill_cell_mode =0.1#in ml per second
        #disposal speed to waste in fill_cell mode
        self.disposal_speed_fill_cell_mode =0.1#in ml per second
        #vol filled to cell in each cycle in fill_cell mode
        self.vol_to_cell_fill_cell_mode = 0
        #vol filled to waste in each cycle in fill_cell mode
        self.vol_to_waste_fill_cell_mode = 0
        #refill times
        self.refill_times_fill_cell_mode =10
        #the actived syringe index(only one) for operating in normal mode
        self.actived_syringe_normal_mode = 1
        #status in normal mode: fill or dispense
        self.actived_syringe_motion_normal_mode = 'fill'
        #valve connection in normal mode: cell_inlet(outlet) or resevoir or waste or not_used
        self.actived_syringe_valve_connection = 'not_used'
        #the actived syringe index (two) for operating in init_mode
        self.actived_pulling_syringe_init_mode = 3
        self.actived_pushing_syringe_init_mode = 2
        #status: fill or dispense
        self.actived_syringe_motion_init_mode = 'fill'
        #speed set for motion in init_mode
        self.speed_init_mode = 0
        #volume left to be fill(or)dispense
        self.volume_init_mode = 0
        #the actived syringe index (two) for operating in simple_mode
        self.actived_left_syringe_simple_exchange_mode = 3
        self.actived_right_syringe_simple_exchange_mode = 2
        #volume of solution in cell
        self.volume_of_electrolyte_in_cell = 0
        #max vol in cell
        self.cell_volume_in_total = 500000000
        #the height in the drawing of resevior/waste bottle
        self.bottom_height_total = 150

    #get the index of syringe for refilling (connecting to resevoir) and dispensing (connecting to waste) in advance exchange mode
    def get_refill_syringes_advance_exchange_mode(self):
        index_list = []
        for ix, direction in self.connect_valve_port.items():
            if self.pump_settings['S{}_{}'.format(ix,direction)] in ['waste', 'resevoir']:
                index_list.append(ix)
        return index_list

    def get_exchange_syringes_advance_exchange_mode(self):
        index_list = []
        for ix, direction in self.connect_valve_port.items():
            if self.pump_settings['S{}_{}'.format(ix,direction)] in ['cell_inlet', 'cell_outlet']:
                index_list.append(ix)
        return index_list
        #index_list = self.get_refill_syringes_advance_exchange_mode()
        #return [each for each in self.connect_valve_port if each not in index_list]

    def get_actived_pulling_syringe_init_mode(self):
        for ix, direction in self.connect_valve_port.items():
            if self.pump_settings['S{}_{}'.format(ix,direction)] == 'cell_outlet':
                self.actived_pulling_syringe_init_mode = ix
                return ix
        return None

    def get_actived_pushing_syringe_init_mode(self):
        for ix, direction in self.connect_valve_port.items():
            if self.pump_settings['S{}_{}'.format(ix,direction)] == 'cell_inlet':
                self.actived_pushing_syringe_init_mode = ix
                return ix
        return None

    def get_syringe_mvp_cell_inlet_channel(self):
        line_index = [1,2,3,4]
        if self.operation_mode == 'simple_exchange_mode':
            line_index = [self.actived_left_syringe_simple_exchange_mode,self.actived_right_syringe_simple_exchange_mode]
        elif self.operation_mode == 'init_mode':
            line_index = [self.actived_pulling_syringe_init_mode,self.actived_pushing_syringe_init_mode]
        elif self.operation_mode == 'normal_mode':
            line_index = [self.actived_syringe_normal_mode]
        elif self.operation_mode == 'fill_cell_mode':
            line_index = [self.actived_syringe_fill_cell_mode]
        for i in line_index:
            valve_pos = self.connect_valve_port[i]
            key = 'S{}_{}'.format(i, valve_pos)
            connection = self.pump_settings[key]
            if connection == 'cell_inlet':
                self.syringe_mvp_cell_inlet_channel = i
                return i
        else:#if no syringe is connected to cell inlet, just set this to 1, which doesnot hurt.
            self.syringe_mvp_cell_inlet_channel = 1
            return 1

    #you can have multiple resevoir bottles but only one waste bottle
    def set_resevoir_volumes(self):
        for each in self.pump_settings:
            if self.pump_settings[each] == 'resevoir':
                tag = each.rsplit('_')[0]#looks like S1, S2
                setattr(self,'resevoir_volumn_{}'.format(tag),self.pump_settings['{}_volume'.format(tag)])
        self.resevoir_volumn = self.resevoir_volumn_S1

    def get_syringe_index_mvp_connection(self):
        return int(''.join(self.mvp_connected_valve.rsplit('_')[0][1:]))

    def initUI(self):
        self.setGeometry(300, 300, 350, 400)
        self.setWindowTitle('Colours')
        self.show()

    def _get_directions(self, part = 'cell_inlet'):
        mapping = {'cell_inlet': 'left',
                   'cell_outlet': 'right',
                   'resevoir': 'up',
                   'waste': 'up'}
        return mapping[part]

    def paintEvent(self, e):
        qp = QPainter()
        qp.begin(self)
        # self.draw_syringe(qp)
        inter_syringe_width = self.width()/self.ref_unit/6 * 0.8
        left_bound_rects_1 = 6
        left_bound_rects_2 = left_bound_rects_1 + inter_syringe_width
        left_bound_rects_4 = self.width()/self.ref_unit - 18
        left_bound_rects_3 = left_bound_rects_4 - inter_syringe_width
        left_bound_cell = (left_bound_rects_3 +left_bound_rects_2)/2 + 3
        left_bound_resevoir = 1
        left_bound_waste = left_bound_rects_4 + 10

        line_styles = [Qt.DashDotDotLine,Qt.DashLine]
        rects_1 = self.draw_syringe(qp,'volume_syringe_1',[6*0 + left_bound_rects_1,5+2],[250,0,0],label =['S1', self.pump_settings['S1_solution']],volume = self.syringe_size)
        rects_2 = self.draw_syringe(qp,'volume_syringe_2',[12*0 + left_bound_rects_2,5+2],[100,100,0],label = ['S2', self.pump_settings['S2_solution']], volume = self.syringe_size)
        rects_3 = self.draw_syringe(qp,'volume_syringe_3',[20*0 + left_bound_rects_3,5+2],[0,200,0], label = ['S3', self.pump_settings['S3_solution']], volume = self.syringe_size)
        rects_4 = self.draw_syringe(qp,'volume_syringe_4',[26*0 + left_bound_rects_4,5+2],[0,100,250],label=['S4', self.pump_settings['S4_solution']],volume = self.syringe_size)

        self.draw_valve(qp,rects_1[1],connect_port=self.connect_valve_port[1])
        self.draw_valve(qp,rects_2[1],connect_port=self.connect_valve_port[2])
        self.draw_valve(qp,rects_3[1],connect_port=self.connect_valve_port[3])
        self.draw_valve(qp,rects_4[1],connect_port=self.connect_valve_port[4])

        self.draw_radio_signal(qp,[rects_1[8][0]-6,rects_1[8][1]+90],msg=self.connect_status[1])
        self.draw_radio_signal(qp,[rects_2[8][0]-6,rects_2[8][1]+90],msg=self.connect_status[2])
        self.draw_radio_signal(qp,[rects_3[8][0]-6,rects_3[8][1]+90],msg=self.connect_status[3])
        self.draw_radio_signal(qp,[rects_4[8][0]-6,rects_4[8][1]+90],msg=self.connect_status[4])
        # if self.operation_mode in ['auto_refilling','init_mode']:
        #Not showing the cell in the clean_mode
        if not self.operation_mode == 'clean_mode':
            self.draw_cell(qp,offset=[(19.5*0 + left_bound_cell)*self.ref_unit,(1.3)*self.ref_unit])
        rects_resevoir = self.draw_bottle(qp, fill_height = self.resevoir_volumn/self.resevoir_volumn_total*self.bottom_height_total, offset = [1*0+ left_bound_resevoir,8+2],volume=self.resevoir_volumn_total,label = self.label_resevoir)
        rects_waste = self.draw_bottle(qp, fill_height = self.waste_volumn/self.waste_volumn_total*self.bottom_height_total, offset = [36*0 + left_bound_waste,8+2], volume = self.waste_volumn_total,label = 'Waste')
        # self.draw_mvp_valve(qp,[rects_waste[0][0]+150, rects_waste[0][1]-150, 50, 50],connected_channel = self.mvp_channel)
        mvp_connect_coord_channel, mvp_connect_coord_cell = self.draw_mvp_valve(qp,[self.cell_rect[0] - (50 - self.cell_rect[2])/2, self.cell_rect[1]+20, 50, 50],connected_channel = self.mvp_channel, syringe_connected_channel = self.get_syringe_mvp_cell_inlet_channel())
        mvp_connect_rect_channel = list(mvp_connect_coord_channel- np.array([1,1])) + [2,2]
        mvp_connect_rect_cell = list(mvp_connect_coord_cell- np.array([1,1])) + [2,2]
        pen = QPen([Qt.red,Qt.blue][0], 2, line_styles[int(self.line_style==1)])
        qp.setPen(pen)
        #rects map
        rects_map = {'cell_inlet':mvp_connect_rect_channel,
                     'cell_outlet':mvp_connect_rect_cell,
                     'resevoir':rects_resevoir[0],
                     'waste':rects_waste[0],
                     'left':2,
                     'up':0,
                     'right':3}

        height_map = {'waste':80,
                      'resevoir':120,
                      'cell_inlet':0,
                      'cell_outlet':0}

        extension_map = {'left':5,
                         'right':5,
                         'up':0}

        lines = []
        line_index = [1,2,3,4]
        if self.operation_mode == 'simple_exchange_mode':
            line_index = [self.actived_left_syringe_simple_exchange_mode,self.actived_right_syringe_simple_exchange_mode]
        elif self.operation_mode == 'init_mode':
            line_index = [self.actived_pulling_syringe_init_mode,self.actived_pushing_syringe_init_mode]
        elif self.operation_mode == 'normal_mode':
            line_index = [self.actived_syringe_normal_mode]
        elif self.operation_mode == 'fill_cell_mode':
            line_index = [self.actived_syringe_fill_cell_mode]
        elif self.operation_mode == 'not_ready_mode':
            line_index = []
        for i in line_index:
            valve_pos = self.connect_valve_port[i]
            key = 'S{}_{}'.format(i, valve_pos)
            connection = self.pump_settings[key]
            if connection in ['resevoir', 'waste', 'cell_inlet', 'cell_outlet']:
                connection_direction = self._get_directions(connection)
                connection_rect = rects_map[connection]
                rect = eval('rects_{}[{}]'.format(i,rects_map[valve_pos]))
                rect_direction = valve_pos
                height = height_map[connection]
                if self.operation_mode == 'normal_mode' and connection == 'waste':
                    height = 40
                ext1 = extension_map[rect_direction]
                ext2 = extension_map[connection_direction]
                lines.append(self.cal_line_coords(rect, connection_rect,rect_direction, connection_direction, ext1, ext2, height))
        pen = QPen([Qt.red,Qt.blue][0], 2, line_styles[int(self.line_style==1)])
        qp.setPen(pen)
        for i in range(len(lines)):
            each_line = lines[i]
            for ii in range(len(each_line)-1):
                qp.drawLine(*(each_line[ii]+each_line[ii+1]))
        self.line_style=self.line_style*-1
        
        qp.end()

    def cal_ref_pos(self,width,hight,x_ref,y_ref,width_ref,hight_ref,align = 'left',offset = 0):
        if align == 'left':
            return [x_ref - width-offset, y_ref+hight_ref/2-hight/2]
        elif align == 'right':
            return [x_ref + width_ref+offset, y_ref+hight_ref/2-hight/2]
        elif align == 'up':
            return [x_ref+width_ref/2-width/2, y_ref-hight-offset]
        elif align == 'down':
            return [x_ref+width_ref/2-width/2,y_ref+hight_ref+offset]

    def cal_line_coords(self,rect1,rect2,align1,align2,extend1,extend2,height):
        def _left(rect1,extend1):
            start_pos = [rect1[0],rect1[1]+rect1[3]/2]
            start_pos_next =[rect1[0]-extend1,rect1[1]+rect1[3]/2] 
            return start_pos,start_pos_next 
        def _right(rect1,extend1):
            start_pos = [rect1[0]+rect1[2],rect1[1]+rect1[3]/2]
            start_pos_next = [rect1[0]+rect1[2]+extend1,rect1[1]+rect1[3]/2]
            return start_pos,start_pos_next 
        def _up(rect1,extend1):
            start_pos = [rect1[0]+rect1[2]/2,rect1[1]]
            start_pos_next = [rect1[0]+rect1[2]/2,rect1[1]-extend1] 
            return start_pos,start_pos_next 
        def _down(rect1,extend1):
            start_pos = [rect1[0]+rect1[2]/2,rect1[1]+rect1[3]]
            start_pos_next = [rect1[0]+rect1[2]/2,rect1[1]+rect1[3]+extend1] 
            return start_pos,start_pos_next 

        if [align1,align2]==['left','left']:
            start_pos = [rect1[0],rect1[1]+rect1[3]/2]
            end_pos = [rect2[0],rect2[1]+rect2[3]/2]
            start_pos_next = [rect1[0]-extend1,rect1[1]+rect1[3]/2]
            end_pos_next = [rect2[0]-extend2,rect2[1]+rect2[3]/2]
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['right','right']: 
            start_pos = [rect1[0]+rect1[2],rect1[1]+rect1[3]/2]
            end_pos = [rect2[0]+rect2[2],rect2[1]+rect2[3]/2]
            start_pos_next = [rect1[0]+rect1[2]+extend1,rect1[1]+rect1[3]/2]
            end_pos_next = [rect2[0]+rect2[2]+extend2,rect2[1]+rect2[3]/2]
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['up','up']: 
            start_pos = [rect1[0]+rect1[2]/2,rect1[1]]
            end_pos = [rect2[0]+rect2[2]/2,rect2[1]]
            start_pos_next = [rect1[0]+rect1[2]/2,rect1[1]-extend1]
            end_pos_next = [rect2[0]+rect2[2]/2,rect2[1]-extend2]
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['down','down']: 
            start_pos = [rect1[0]+rect1[2]/2,rect1[1]+rect1[3]]
            end_pos = [rect2[0]+rect2[2]/2,rect2[1]+rect2[3]]
            start_pos_next = [rect1[0]+rect1[2]/2,rect1[1]+rect1[3]+extend1]
            end_pos_next = [rect2[0]+rect2[2]/2,rect2[1]+rect2[3]+extend2]
            ref_height = max([start_pos_next[1],end_pos_next[1]])+height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['left','right']: 
            start_pos,start_pos_next = _left(rect1,extend1)
            end_pos,end_pos_next = _right(rect2,extend2)
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['right','left']:
            start_pos,start_pos_next = _right(rect1,extend1)
            end_pos,end_pos_next = _left(rect2,extend2)
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['up','down']: 
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['down','up']:
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['left','up']: 
            start_pos,start_pos_next = _left(rect1,extend1)
            end_pos,end_pos_next = _up(rect2,extend2)
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['up','left']:
            start_pos,start_pos_next = _up(rect1,extend1)
            end_pos,end_pos_next = _left(rect2,extend2)
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['left','down']: 
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['down','left']:
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['right','up']: 
            start_pos,start_pos_next = _right(rect1,extend1)
            end_pos,end_pos_next = _up(rect2,extend2)
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['up','right']:
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['right','down']: 
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]
        elif [align1,align2]==['down','right']:
            ref_height = min([start_pos_next[1],end_pos_next[1]])-height
            top_left_pos = [start_pos_next[0],ref_height]
            top_right_pos = [end_pos_next[0],ref_height]
            return [start_pos,start_pos_next,top_left_pos,top_right_pos,end_pos_next,end_pos]

    def draw_cell(self,qp,l1=80,l2=20,offset = [0,0]):
        path = QPainterPath()
        x,y = offset
        path.moveTo(*offset)
        path.lineTo(x+l1,y)
        path.lineTo(x+l1-(l1-l2)/2,y+(l1-l2)/2)
        path.lineTo(x+l1-(l1-l2)/2-l2,y+(l1-l2)/2)
        path.lineTo(x,y)
        path.addRect(x+l1-(l1-l2)/2-l2,y+(l1-l2)/2,l2,l2)
        qp.setPen(QPen(QColor(79, 106, 25), 1, Qt.SolidLine,
                            Qt.FlatCap, Qt.MiterJoin))
        qp.setBrush(QColor(122, 163, 39))
        qp.drawPath(path)
        self.cell_rect = [x+l1-(l1-l2)/2-l2,y+(l1-l2)/2,l2,l2]
        qp.drawText(self.cell_rect[0]-15-18,self.cell_rect[1]-35,"cell vol:{:7.1f} ul".format(self.volume_of_electrolyte_in_cell*1000))
        return [x+l1-(l1-l2)/2-l2,y+(l1-l2)/2,l2,l2]

    def draw_radio_signal(self,qp,pos,dim=[40,40],start_angle=50,num_arcs = 0,vertical_spacing =10, msg='error'):
        color = 'green'
        if msg == 'error':
            color = 'red'
        qp.setPen(QPen(getattr(Qt,color), 2, Qt.SolidLine))
        for i in range(num_arcs):
            current_pos = [pos[0]+i*vertical_spacing/2,pos[1]+i*vertical_spacing/2]
            # current_pos = pos
            current_dim = [dim[0]-i*vertical_spacing]*2
            if i==num_arcs-1:
                if color=='red':
                    qp.setBrush(QColor(200,0,0))
                elif color =='blue':
                    qp.setBrush(QColor(0,0,200))
                qp.setPen(QPen(getattr(Qt,color), 0, Qt.SolidLine))
                qp.drawEllipse(current_pos[0],current_pos[1],current_dim[0],current_dim[1])
            else:
                qp.drawArc(current_pos[0],current_pos[1],current_dim[0],current_dim[1],30*16,120*16)
        color = 'white'
        if msg in ['ready','No error']:
            color = 'green'
        elif msg in ['moving']:
            color = 'magenta'
        elif msg in ['disconnected']:
            color = 'red'
        qp.setPen(QPen(getattr(Qt,color), 2, Qt.SolidLine))
        qp.setFont(QFont('Decorative', 12))
        offset = [-15,2][int(msg=='error')]
        qp.drawText(pos[0]+offset,pos[1]+vertical_spacing*num_arcs-10,msg)

    def draw_bottle(self,qp,top_width = 80,top_height = 4, bottom_width = 90, fill_height =20, offset = [0,0],color = [0,0,250],label='resevoir',volume=250):
        bottom_height_total = self.bottom_height_total
        rec1_pos = [self.ref_unit*offset[0],self.ref_unit*offset[1]]
        rec1_dim = [bottom_width,top_height*4]
        rec2_dim = [top_width,top_height]
        rec3_dim = [top_width,top_height]
        rec4_dim = [top_width,top_height]
        rec5_dim = [bottom_width,bottom_height_total-fill_height]
        rec6_dim = [bottom_width,fill_height]
        rec2_pos = self.cal_ref_pos(rec2_dim[0],rec2_dim[1],rec1_pos[0],rec1_pos[1],rec1_dim[0],rec1_dim[1],'down',0)
        rec3_pos = self.cal_ref_pos(rec3_dim[0],rec3_dim[1],rec2_pos[0],rec2_pos[1],rec2_dim[0],rec2_dim[1],'down',0)
        rec4_pos = self.cal_ref_pos(rec4_dim[0],rec4_dim[1],rec3_pos[0],rec3_pos[1],rec3_dim[0],rec3_dim[1],'down',0)
        rec5_pos = self.cal_ref_pos(rec5_dim[0],rec5_dim[1],rec4_pos[0],rec4_pos[1],rec4_dim[0],rec4_dim[1],'down',0)
        rec6_pos = self.cal_ref_pos(rec6_dim[0],rec6_dim[1],rec5_pos[0],rec5_pos[1],rec5_dim[0],rec5_dim[1],'down',0)

        qp.setBrush(QColor(250, 250, 250))
        qp.setPen(QPen(QColor(100, 100, 100), 1, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        qp.drawRect(*(rec1_pos+rec1_dim))
        qp.drawRect(*(rec2_pos+rec2_dim))
        qp.drawRect(*(rec3_pos+rec3_dim))
        qp.drawRect(*(rec4_pos+rec4_dim))
        qp.drawRect(*(rec5_pos+rec5_dim))
        # qp.setBrush(QColor(0, 0, 250))
        qp.setBrush(QColor(*color))
        qp.drawRect(*(rec6_pos+rec6_dim))
        qp.setBrush(QColor(250, 250, 250))
        # qp.drawRect(*(rec10_pos+rec10_dim))
        qp.setPen(QPen(QColor(200, 200, 200), 1, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        qp.setFont(QFont('Decorative', 12))
        qp.drawText(rec6_pos[0],rec6_pos[1]+rec6_dim[1]+50,"{}:{:6.2f} ml".format(label,volume/bottom_height_total*fill_height))
        if label!='Waste':
            qp.drawText(rec6_pos[0],rec6_pos[1]+rec6_dim[1]+30,"Resevoir")
        rects = []
        for i in range(1,6):
            rect_pos = eval('rec{}_pos'.format(i))
            rect_dim = eval('rec{}_dim'.format(i))
            rects.append(rect_pos+rect_dim)
        qp.setPen(QPen(QColor(10, 10, 10), 1, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        # self.draw_markers(qp,rec5_pos+[bottom_width,bottom_height_total],'left',volume,[50,100,150,200],False)
        markers = [int(volume/5)*(i+1) for i in range(4)]
        self.draw_markers(qp,rec5_pos+[bottom_width,bottom_height_total],'left',volume,markers,False)
        return rects

    def draw_valve(self,qp, dim, connect_port = 'left'):
        coord_left = [dim[0],dim[1]+dim[3]/2]
        coord_right =[dim[0]+dim[2],dim[1]+dim[3]/2] 
        coord_top = [dim[0]+dim[2]/2,dim[1]]
        coord_bottom = [dim[0]+dim[2]/2,dim[1]+dim[3]]
        coord_center = [dim[0]+dim[2]/2,dim[1]+dim[3]/2]
        qp.setPen(QPen(Qt.green,  4, Qt.SolidLine))
        qp.drawEllipse(*dim)
        qp.setPen(QPen(Qt.red,  4, Qt.SolidLine))
        if connect_port == 'left':
            qp.drawLine(*(coord_left+coord_center))
        elif connect_port == 'right':
            qp.drawLine(*(coord_right+coord_center))
        elif connect_port == 'up':
            qp.drawLine(*(coord_top+coord_center))
        qp.drawLine(*(coord_bottom+coord_center))

    def draw_mvp_valve(self,qp, dim, connected_channel = 3, syringe_connected_channel =3):
        coord_center = [dim[0]+dim[2]/2,dim[1]+dim[3]/2]
        qp.setPen(QPen(Qt.blue,  2, Qt.SolidLine))
        # qp.drawRect(*dim)
        return_coord_channel = None
        return_coord_cell = None
        if self.operation_mode !='clean_mode':
            qp.drawEllipse(*dim)
            qp.setPen(QPen(Qt.blue,  1, Qt.SolidLine))
            qp.drawEllipse(*(coord_center+[2,2]))
        qp.setPen(QPen(Qt.blue,  4, Qt.SolidLine))
        for i in range(self.number_of_channel_mvp):
            if i in [0, connected_channel]:
                qp.setPen(QPen(Qt.red, 2, Qt.SolidLine))
            else:
                qp.setPen(QPen(Qt.black, 2, Qt.DotLine))
            rot_ang = np.pi*2/self.number_of_channel_mvp*i
            coord_tmp = list(np.array(coord_center) - np.array([dim[2]/2*np.sin(rot_ang),dim[2]/2*np.cos(rot_ang)]))
            if i == 0:
                coord_tmp = list(coord_tmp - np.array([0,8]))
                return_coord_cell = coord_tmp
            if i == syringe_connected_channel:
                return_coord_channel = coord_tmp
            if self.operation_mode !='clean_mode':
                qp.drawLine(*(coord_tmp+coord_center))
        qp.setFont(QFont('Decorative', 12))
        qp.setPen(QPen(Qt.red,  4, Qt.SolidLine))
        if self.operation_mode !='clean_mode':
            # qp.drawText(dim[0],dim[1]+80,"{}-->MVP".format(self.mvp_connected_valve))
            qp.drawText(dim[0],dim[1]+80,"S{}-->MVP".format(self.mvp_channel))
        return return_coord_channel, return_coord_cell

    def draw_markers(self,qp,rect,which_side = 'left',total_volume_in_ml = 12.5, marker_pos_in_ml = [2,4,6,8,10,12], inverse = True):
        if which_side in ['left','right']:
            marker_length = rect[2]*0.1
        else:
            marker_length = rect[3]*0.1
        marker_pos_in_pix = []
        for each in marker_pos_in_ml:
            if inverse:
                marker_pos_in_pix.append([rect[0],(each/total_volume_in_ml)*rect[3]+rect[1],rect[0]+marker_length,(each/total_volume_in_ml)*rect[3]+rect[1]])
            else:
                marker_pos_in_pix.append([rect[0],((total_volume_in_ml - each)/total_volume_in_ml)*rect[3]+rect[1],rect[0]+marker_length,((total_volume_in_ml - each)/total_volume_in_ml)*rect[3]+rect[1]])
        for each in marker_pos_in_pix:
            qp.drawLine(*each)
            qp.drawText(each[2],each[3],"{} ml".format(marker_pos_in_ml[marker_pos_in_pix.index(each)]))

    def draw_syringe(self,qp,vol_tag = 'volume',origin_offset = [0,0],color = [0,0,250],label = 'S1',volume = 12.5):
        ref_unit = self.ref_unit
        col = QColor(0, 0, 0)
        col.setNamedColor('#d4d4d4')
        qp.setPen(col)
        qp.setBrush(QColor(100, 0, 0))
        # print(self.volume)

        #top small
        #[width,height] of ten rectangles
        rec1_dim = [ref_unit,ref_unit]
        rec2_dim = [ref_unit*3,ref_unit*3]
        rec3_dim = [ref_unit,ref_unit]
        rec4_dim = [ref_unit,ref_unit]
        rec5_dim = [ref_unit,ref_unit]
        rec6_dim = [ref_unit*4,ref_unit*getattr(self,vol_tag)/12.5*8]
        rec7_dim = [ref_unit*4,ref_unit*(8.5-getattr(self,vol_tag)/12.5*8)]
        rec8_dim = [ref_unit*4,ref_unit*0.5]
        #rec9_dim = [ref_unit*0.5,ref_unit*9]
        rec9_dim = [ref_unit*1,ref_unit*0.5]

        rec1_pos = [5*ref_unit+origin_offset[0]*ref_unit, ref_unit+origin_offset[1]*ref_unit]
        rec2_pos = self.cal_ref_pos(rec2_dim[0],rec2_dim[1],rec1_pos[0],rec1_pos[1],rec1_dim[0],rec1_dim[1],'down',0)
        rec3_pos = self.cal_ref_pos(rec3_dim[0],rec3_dim[1],rec2_pos[0],rec2_pos[1],rec2_dim[0],rec2_dim[1],'left',0)
        rec4_pos = self.cal_ref_pos(rec4_dim[0],rec4_dim[1],rec2_pos[0],rec2_pos[1],rec2_dim[0],rec2_dim[1],'right',0)
        rec5_pos = self.cal_ref_pos(rec5_dim[0],rec5_dim[1],rec2_pos[0],rec2_pos[1],rec2_dim[0],rec2_dim[1],'down',0)
        rec6_pos = self.cal_ref_pos(rec6_dim[0],rec6_dim[1],rec5_pos[0],rec5_pos[1],rec5_dim[0],rec5_dim[1],'down',0)
        rec7_pos = self.cal_ref_pos(rec7_dim[0],rec7_dim[1],rec6_pos[0],rec6_pos[1],rec6_dim[0],rec6_dim[1],'down',0)
        rec8_pos = self.cal_ref_pos(rec8_dim[0],rec8_dim[1],rec7_pos[0],rec7_pos[1],rec7_dim[0],rec7_dim[1],'up',-rec8_dim[1])
        # rec9_pos = self.cal_ref_pos(rec9_dim[0],rec9_dim[1],rec8_pos[0],rec8_pos[1],rec8_dim[0],rec8_dim[1],'down',0)
        # rec10_pos = self.cal_ref_pos(rec10_dim[0],rec10_dim[1],rec9_pos[0],rec9_pos[1],rec9_dim[0],rec9_dim[1],'down',0)
        rec9_pos = self.cal_ref_pos(rec9_dim[0],rec9_dim[1],rec7_pos[0],rec7_pos[1],rec7_dim[0],rec7_dim[1],'down',0)

        rec_tube = rec6_pos+[ref_unit*4,ref_unit*8]

        # print(rec7_pos+rec7_dim)
        qp.drawRect(*(rec1_pos+rec1_dim))
        qp.drawRect(*(rec2_pos+rec2_dim))
        qp.drawRect(*(rec3_pos+rec3_dim))
        qp.drawRect(*(rec4_pos+rec4_dim))
        qp.drawRect(*(rec5_pos+rec5_dim))
        # qp.setBrush(QColor(0, 0, 250))
        qp.setBrush(QColor(*color))
        qp.drawRect(*(rec6_pos+rec6_dim))
        qp.setBrush(QColor(250, 250, 250))
        qp.drawRect(*(rec7_pos+rec7_dim))
        qp.setBrush(QColor(150, 150, 150))
        qp.drawRect(*(rec8_pos+rec8_dim))
        qp.setBrush(QColor(50, 50, 50))
        qp.drawRect(*(rec9_pos+rec9_dim))
        # qp.drawRect(*(rec10_pos+rec10_dim))
        qp.setFont(QFont("Arial", 12))
        qp.setPen(QPen(QColor(250, 250, 250), 1, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        qp.drawText(rec8_pos[0],rec9_pos[1]+40,label[1])
        # qp.drawText(rec8_pos[0],rec9_pos[1]+60,"{}:{:6.2f} ml".format(label[0],getattr(self,vol_tag)))
        qp.drawText(rec8_pos[0],rec9_pos[1]+60,"{}:{:7.1f} ul".format(label[0],getattr(self,vol_tag)*1000))
        rects = []
        for i in range(1,10):
            rect_pos = eval('rec{}_pos'.format(i))
            rect_dim = eval('rec{}_dim'.format(i))
            rects.append(rect_pos+rect_dim)
        qp.setPen(QPen(QColor(0, 0, 0), 1, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        qp.setFont(QFont("Arial", 12))
        self.draw_markers(qp,rec_tube)
        qp.setFont(QFont("Arial", 15, QFont.Bold))
        return rects

    def drawRectangles(self, qp):
        col = QColor(0, 0, 0)
        col.setNamedColor('#d4d4d4')
        qp.setPen(col)

        qp.setBrush(QColor(200, 0, 0))
        qp.drawRect(20, 15, 90, 60)

        qp.setBrush(QColor(255, 80, 0, 160))
        qp.drawRect(30, 15+60, 70, 60)

        qp.setBrush(QColor(25, 0, 90, 200))
        qp.drawRect(20, 15+120, 90, 60)

    def drawText(self, event, qp):
        qp.setPen(QColor(168, 34, 3))
        qp.setFont(QFont('Decorative', 10))
        qp.drawText(event.rect(), Qt.AlignCenter, self.text)
