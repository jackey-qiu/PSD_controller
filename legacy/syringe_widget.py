from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QBrush, QFont, QPen
from PyQt5.QtCore import Qt, QTimer
import sys
import time

class syringe_widget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        #volume of solution in each syringe
        self.volume_syringe_1 = 0
        self.volume_syringe_2 = 0
        self.volume_syringe_3 = 0
        self.volume_syringe_4 = 0
        #motion type for each syringe
        #True: pushing; False: Pulling
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
        self.speed_by_default = 0.
        #ref length for drawing syringe
        self.ref_unit = 20
        self.line_style = 1
        #either init_mode, auto_refilling mode or normal_mode
        self.operation_mode = 'init_mode'
        #3-channel T valve position (either left, right or up)
        self.connect_valve_port = {1:'left',2:'right',3:'up',4:'up'}
        #connected status
        self.connect_status = {1:'connected',2:'connected',3:'connected',4:'connected'}
        #the actived syringe index(only one) for operating in normal mode
        self.actived_syringe_normal_mode = 1
        #status: fill or dispense
        self.actived_syringe_motion_normal_mode = 'fill'
        #the actived syringe index (two) for operating in init_mode
        self.actived_pulling_syringe_init_mode = 3
        self.actived_pushing_syringe_init_mode = 2
        #status: fill or dispense
        self.actived_syringe_motion_init_mode = 'fill'
        #speed set for motion in init_mode
        self.speed_init_mode = 0
        #volume left to be fill(or)dispense
        self.volume_init_mode = 0
        #volume of solution in cell
        self.volume_of_electrolyte_in_cell = 0

    def initUI(self):
        self.setGeometry(300, 300, 350, 400)
        self.setWindowTitle('Colours')
        self.show()

    def paintEvent(self, e):
        qp = QPainter()
        qp.begin(self)
        # self.draw_syringe(qp)
        line_styles = [Qt.DashDotDotLine,Qt.DashLine]
        rects_1 = self.draw_syringe(qp,'volume_syringe_1',[6,5],[250,0,0],label ='S1',volume = self.syringe_size)
        rects_2 = self.draw_syringe(qp,'volume_syringe_2',[12,5],[100,100,0],label = 'S2', volume = self.syringe_size)
        rects_3 = self.draw_syringe(qp,'volume_syringe_3',[20,5],[0,200,0], label = 'S3', volume = self.syringe_size)
        rects_4 = self.draw_syringe(qp,'volume_syringe_4',[26,5],[0,100,250],label='S4',volume = self.syringe_size)
        if self.operation_mode == 'auto_refilling':
            self.draw_valve(qp,rects_1[1],connect_port=['left','right'][int(not self.filling_status_syringe_1)])
            self.connect_valve_port[1] = ['left','right'][int(not self.filling_status_syringe_1)]
            self.draw_valve(qp,rects_2[1],connect_port=['left','right'][int(not self.filling_status_syringe_2)])
            self.connect_valve_port[2] = ['left','right'][int(not self.filling_status_syringe_2)]
            self.draw_valve(qp,rects_3[1],connect_port=['left','up'][int(not self.filling_status_syringe_3)])
            self.connect_valve_port[3] = ['left','right'][int(not self.filling_status_syringe_3)]
            self.draw_valve(qp,rects_4[1],connect_port=['left','up'][int(not self.filling_status_syringe_4)])
            self.connect_valve_port[4] = ['left','right'][int(not self.filling_status_syringe_4)]
        elif self.operation_mode == 'pre_auto_refilling':
            self.draw_valve(qp,rects_1[1],connect_port=['up','left'][int(self.filling_status_syringe_1)])
            self.connect_valve_port[1] = ['up','left'][int(self.filling_status_syringe_1)]
            self.draw_valve(qp,rects_2[1],connect_port=['up','left'][int(self.filling_status_syringe_2)])
            self.connect_valve_port[2] = ['up','left'][int(self.filling_status_syringe_2)]
            self.draw_valve(qp,rects_3[1],connect_port=['up','left'][int(self.filling_status_syringe_3)])
            self.connect_valve_port[3] = ['up','left'][int(self.filling_status_syringe_3)]
            self.draw_valve(qp,rects_4[1],connect_port=['up','left'][int(self.filling_status_syringe_4)])
            self.connect_valve_port[4] = ['up','left'][int(self.filling_status_syringe_4)]        
        elif self.operation_mode == 'normal_mode':
            self.draw_valve(qp,rects_1[1],connect_port=self.connect_valve_port[1])
            self.draw_valve(qp,rects_2[1],connect_port=self.connect_valve_port[2])
            self.draw_valve(qp,rects_3[1],connect_port=self.connect_valve_port[3])
            self.draw_valve(qp,rects_4[1],connect_port=self.connect_valve_port[4])
        elif self.operation_mode == 'init_mode':
            self.draw_valve(qp,rects_1[1],connect_port=self.connect_valve_port[1])
            self.draw_valve(qp,rects_2[1],connect_port=self.connect_valve_port[2])
            self.draw_valve(qp,rects_3[1],connect_port=self.connect_valve_port[3])
            self.draw_valve(qp,rects_4[1],connect_port=self.connect_valve_port[4])
        elif self.operation_mode == 'empty_all_mode':
            self.draw_valve(qp,rects_1[1],connect_port='up')
            self.connect_valve_port[1] = 'up'
            self.draw_valve(qp,rects_2[1],connect_port='up')
            self.connect_valve_port[2] = 'up'
            self.draw_valve(qp,rects_3[1],connect_port='up')
            self.connect_valve_port[3] = 'up'
            self.draw_valve(qp,rects_4[1],connect_port='up')
            self.connect_valve_port[4] = 'up'
        elif self.operation_mode == 'fill_all_mode':
            self.draw_valve(qp,rects_1[1],connect_port='left')
            self.connect_valve_port[1] = 'left'
            self.draw_valve(qp,rects_2[1],connect_port='left')
            self.connect_valve_port[2] = 'left'
            self.draw_valve(qp,rects_3[1],connect_port='left')
            self.connect_valve_port[3] = 'left'
            self.draw_valve(qp,rects_4[1],connect_port='left')
            self.connect_valve_port[4] = 'left'

        self.draw_radio_signal(qp,[rects_1[8][0]-6,rects_1[8][1]+90],color=['red','blue'][int(self.connect_status[1]=='connected')])
        self.draw_radio_signal(qp,[rects_2[8][0]-6,rects_2[8][1]+90],color=['red','blue'][int(self.connect_status[2]=='connected')])
        self.draw_radio_signal(qp,[rects_3[8][0]-6,rects_3[8][1]+90],color=['red','blue'][int(self.connect_status[3]=='connected')])
        self.draw_radio_signal(qp,[rects_4[8][0]-6,rects_4[8][1]+90],color=['red','blue'][int(self.connect_status[4]=='connected')])
        if self.operation_mode in ['auto_refilling','init_mode']:
            self.draw_cell(qp,offset=[(19.5)*self.ref_unit,(1.3)*self.ref_unit])
        rects_resevoir = self.draw_bottle(qp, fill_height = self.resevoir_volumn/250*200, offset = [1,8],volume=self.resevoir_volumn_total,label = 'Resevoir')
        rects_waste = self.draw_bottle(qp, fill_height = self.waste_volumn/250*200, offset = [36,8], volume = self.waste_volumn_total,label = 'Waste')
        pen = QPen([Qt.red,Qt.blue][0], 2, line_styles[int(self.line_style==1)])
        qp.setPen(pen)
        if self.operation_mode=='auto_refilling':
            lines1 = self.cal_line_coords(rects_1[2],rects_resevoir[0],'left','up',5,0,110)
            lines2 = self.cal_line_coords(rects_1[0],rects_waste[0],'up','up',0,0,80)
            lines3 = self.cal_line_coords(rects_1[3],self.cell_rect,'right','left',5,5,0)
            lines4 = self.cal_line_coords(rects_2[3],self.cell_rect,'right','left',5,5,0)
            lines5 = self.cal_line_coords(self.cell_rect,rects_4[2],'right','left',5,5,0)
            lines6 = self.cal_line_coords(self.cell_rect,rects_3[2],'right','left',5,5,0)
            lines7 = self.cal_line_coords(rects_2[0],rects_waste[0],'up','up',0,0,80)
            lines8 = self.cal_line_coords(rects_3[0],rects_waste[0],'up','up',0,0,80)
            lines9 = self.cal_line_coords(rects_4[0],rects_waste[0],'up','up',0,0,80)
            lines10 = self.cal_line_coords(rects_2[2],rects_resevoir[0],'left','up',5,0,120)
            lines = [lines1,lines2,lines3,lines4,lines5,lines6,lines7,lines8,lines9,lines10]
            operations = [self.filling_status_syringe_1,False,not self.filling_status_syringe_1,not self.filling_status_syringe_2,self.filling_status_syringe_4,self.filling_status_syringe_3,False,not self.filling_status_syringe_3,not self.filling_status_syringe_4,self.filling_status_syringe_2]
            for i in range(len(lines)):
                each_line = lines[i]
                operation = operations[i]
                if operation:
                    pen = QPen([Qt.red,Qt.blue][0], 2, line_styles[int(self.line_style==1)])
                    qp.setPen(pen)
                    for ii in range(len(each_line)-1):
                        qp.drawLine(*(each_line[ii]+each_line[ii+1]))
                else:
                    pass
        elif self.operation_mode=='init_mode':
            rects_map_table = {1:rects_1,2:rects_2,3:rects_3,4:rects_4}
            rects_push = rects_map_table[self.actived_pushing_syringe_init_mode]
            rects_pull = rects_map_table[self.actived_pulling_syringe_init_mode]
            lines1 = self.cal_line_coords(rects_push[3],self.cell_rect,'right','left',5,5,0)
            lines2 = self.cal_line_coords(rects_pull[2],self.cell_rect,'left','right',5,5,0)
            lines = [lines1,lines2]
            for i in range(len(lines)):
                each_line = lines[i]
                pen = QPen([Qt.red,Qt.blue][0], 2, line_styles[int(self.line_style==1)])
                qp.setPen(pen)
                for ii in range(len(each_line)-1):
                    qp.drawLine(*(each_line[ii]+each_line[ii+1]))
        elif self.operation_mode == 'normal_mode':
            rects_actived_syringe = eval('rects_{}'.format(self.actived_syringe_normal_mode))
            if self.actived_syringe_motion_normal_mode == 'fill':
                rect_connected = rects_resevoir[0]
            elif self.actived_syringe_motion_normal_mode == 'dispense':
                rect_connected = rects_waste[0]
            rect_index = {'left':2,'right':3,'up':0}[self.connect_valve_port[self.actived_syringe_normal_mode]]
            lines = self.cal_line_coords(rects_actived_syringe[rect_index],rect_connected,self.connect_valve_port[self.actived_syringe_normal_mode],'up',5,5,110)
            pen = QPen([Qt.red,Qt.blue][0], 2, line_styles[int(self.line_style==1)])
            qp.setPen(pen)
            for ii in range(len(lines)-1):
                qp.drawLine(*(lines[ii]+lines[ii+1]))
        elif self.operation_mode == 'pre_auto_refilling':
            if self.filling_status_syringe_1:
                lines1 = self.cal_line_coords(rects_1[2],rects_resevoir[0],'left','up',5,0,140)
            else:
                lines1 = self.cal_line_coords(rects_1[0],rects_waste[0],'up','up',0,0,110)
            if self.filling_status_syringe_2:
                lines2 = self.cal_line_coords(rects_2[2],rects_resevoir[0],'left','up',5,0,140)
            else:
                lines2 = self.cal_line_coords(rects_2[0],rects_waste[0],'up','up',0,0,110)
            if self.filling_status_syringe_3:
                lines3 = self.cal_line_coords(rects_3[2],rects_resevoir[0],'left','up',5,0,140)
            else:
                lines3 = self.cal_line_coords(rects_3[0],rects_waste[0],'up','up',0,0,110)
            if self.filling_status_syringe_4:
                lines4 = self.cal_line_coords(rects_4[2],rects_resevoir[0],'left','up',5,0,140)
            else:
                lines4 = self.cal_line_coords(rects_4[0],rects_waste[0],'up','up',0,0,110)
            lines = [lines1,lines2,lines3,lines4]
            for i in range(len(lines)):
                each_line = lines[i]
                pen = QPen([Qt.red,Qt.blue][0], 2, line_styles[int(self.line_style==1)])
                qp.setPen(pen)
                for ii in range(len(each_line)-1):
                    qp.drawLine(*(each_line[ii]+each_line[ii+1]))
        elif self.operation_mode == 'empty_all_mode':
            lines1 = self.cal_line_coords(rects_1[0],rects_waste[0],'up','up',0,0,100)
            lines2 = self.cal_line_coords(rects_2[0],rects_waste[0],'up','up',0,0,100)
            lines3 = self.cal_line_coords(rects_3[0],rects_waste[0],'up','up',0,0,100)
            lines4 = self.cal_line_coords(rects_4[0],rects_waste[0],'up','up',0,0,100)
            lines = [lines1,lines2,lines3,lines4]
            for i in range(len(lines)):
                each_line = lines[i]
                pen = QPen([Qt.red,Qt.blue][0], 2, line_styles[int(self.line_style==1)])
                qp.setPen(pen)
                for ii in range(len(each_line)-1):
                    qp.drawLine(*(each_line[ii]+each_line[ii+1]))
        elif self.operation_mode == 'fill_all_mode':
            lines1 = self.cal_line_coords(rects_1[2],rects_resevoir[0],'left','up',5,0,140)
            lines2 = self.cal_line_coords(rects_2[2],rects_resevoir[0],'left','up',5,0,140)
            lines3 = self.cal_line_coords(rects_3[2],rects_resevoir[0],'left','up',5,0,140)
            lines4 = self.cal_line_coords(rects_4[2],rects_resevoir[0],'left','up',5,0,140)
            lines = [lines1,lines2,lines3,lines4]
            for i in range(len(lines)):
                each_line = lines[i]
                pen = QPen([Qt.red,Qt.blue][0], 2, line_styles[int(self.line_style==1)])
                qp.setPen(pen)
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
        qp.drawText(self.cell_rect[0]-15-18,self.cell_rect[1]-40,"cell vol:{} ml".format(round(self.volume_of_electrolyte_in_cell,3)))
        return [x+l1-(l1-l2)/2-l2,y+(l1-l2)/2,l2,l2]

    def draw_radio_signal(self,qp,pos,dim=[40,40],start_angle=50,num_arcs = 4,vertical_spacing =10, color='red'):
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
        offset = [-15,2][int(color=='red')]
        qp.drawText(pos[0]+offset,pos[1]+vertical_spacing*num_arcs+8,['connected','error'][int(color=='red')])

    def draw_bottle(self,qp,top_width = 100,top_height = 4, bottom_width = 120, bottom_height_total = 200, fill_height =20, offset = [0,0],color = [0,0,250],label='resevoir',volume=250):
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
        qp.setPen(QPen(QColor(100, 100, 100), 1, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        qp.drawText(rec6_pos[0],rec6_pos[1]+rec6_dim[1]+60,"{}:{:6.2f} ml".format(label,volume/bottom_height_total*fill_height))
        rects = []
        for i in range(1,6):
            rect_pos = eval('rec{}_pos'.format(i))
            rect_dim = eval('rec{}_dim'.format(i))
            rects.append(rect_pos+rect_dim)
        qp.setPen(QPen(QColor(10, 10, 10), 1, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        self.draw_markers(qp,rec5_pos+[bottom_width,bottom_height_total],'left',volume,[50,100,150,200],False)
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
        qp.setFont(QFont("Arial", 15, QFont.Bold))
        qp.setPen(QPen(QColor(50, 50, 50), 1, Qt.SolidLine, Qt.FlatCap, Qt.MiterJoin))
        qp.drawText(rec8_pos[0],rec9_pos[1]+60,"{}:{:6.2f} ml".format(label,getattr(self,vol_tag)))
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
