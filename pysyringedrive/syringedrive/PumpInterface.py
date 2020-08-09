# -*- coding: utf-8 -*-
"""
Created on Thu Jul 16 17:20:04 2020

@author: Timo
"""

import serial
from serial.tools import list_ports
import multiprocessing as mp
#import multiprocessing.connection
import logging
import codecs
import sys
import numpy as np
import atexit
from collections import OrderedDict 
from . import CommunicationServer as cms
from .CommunicationServer import CommunicationServer, DeviceError, DataReciever


valveType = {
    0 : '3-way 120 degree Y valve',
    1 : '4-way 90 degree T valve',
    2 : '3-way 90 degree distribution valve',
    3 : '8-way 45 degree valve',
    4 : '4-way 90 degree valve',
    5 : 'Reserved',
    6 : '6-way 45 degree valve'
    }


valveType_inv = dict(map(reversed, valveType.items()))

valveType_f = lambda n : valveType[n]


# TODO: add other aliases
            

class PumpController(object):
    """
    multiprocessing-safe interface for the communication 
    with Hamilton PSD4 pumps and MVP valves via RS-485 protocol
    """
    def __init__(self,**portsettings):
        """

        Parameters
        ----------
        **portsettings : dict with the settings of the used serial port
            port : Device name
            baudrate : Baud rate such as 9600 or 38400 etc.
                Default is 38400.
                
            Other settings as used in serial.Serial.__init__ can be overwritten,
            However, the default should work with PSD and MVP devices.
            

        """

        self.__comServer = mp.Process()
        self.__killComProcessEvent = mp.Event()
        self.portsettings = portsettings
        atexit.register(self.stopServer)
        self.reinitialize()
        
    def deviceIds(self):
        status = np.array(self.statusbytes[:])
        return np.nonzero(status >= 0)[0] + 1
    
    def deviceStatus(self,deviceId=-1):
        if deviceId == -1:
            status = np.array(self.statusbytes[:])
            ids = np.nonzero(status >= 0)[0] + 1
            availablestatus = status[ids-1]
            statusdict = OrderedDict()
            for sb, devid in zip(availablestatus,ids):
                statusdict[devid] = DeviceError(sb,short=True)
            return statusdict
        else:
            sb = self.statusbytes[deviceId-1]
            return DeviceError(sb,short=True)
            
    def statusAllIds(self):
        status = np.array(self.statusbytes[:])
        ids = np.arange(status.size) + 1
        statusdict = OrderedDict()
        for sb, devid in zip(status,ids):
            statusdict[devid] = DeviceError(sb,short=True)
        return statusdict
    
    def waitForDeviceIdle(self,deviceId,timeout=None):
        """
        Faster response than polling deviceStatus(id).busy

        Parameters
        ----------
        deviceId : TYPE
            DESCRIPTION.
        timeout : TYPE, optional
            DESCRIPTION. The default is None.

        Returns
        -------
        TYPE
            DESCRIPTION.

        """
        return self.idle[deviceId-1].wait(timeout)
        
        
    def syringePumpIds(self):
        ids = self.deviceIds()
        stroke = np.array(self.syringePos[:])[ids-1]
        return ids[np.nonzero(stroke >= 0)]
    
    def valvePositionerIds(self):
        ids = self.deviceIds()
        stroke = np.array(self.syringePos[:])[ids-1]
        return ids[np.nonzero(stroke < 0)]
    
    def getSettings(self,deviceId,wait=True,timeout=0.3):
        recv = self.getFirmware(deviceId,False)
        recv.appendReciever(self.getValveType(deviceId,False))
        recv.appendReciever(self.getValvePosition(deviceId,False))
        
        if self.syringePos[deviceId-1] < 0: # valve positioner
            recv.data['type'] = 'MVP'
        else:
            recv.appendReciever(self.getStartVelocity(deviceId,False))
            recv.appendReciever(self.getMaximumVelocity(deviceId,False))
            recv.appendReciever(self.getStopVelocity(deviceId,False))
            recv.appendReciever(self.getReturnSteps(deviceId,False))
            recv.data['type'] = 'PSD'
        if wait:
            recv(timeout)
        return recv
        
    def getValvePosition(self,deviceId,wait=True,timeout=0.25):
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), b'?24000')
        recv = DataReciever(pipe,'valve position',cms.deviceAnswerToNumber,False)
        if wait:
            recv(timeout)
        return recv
            
    def getValveType(self,deviceId,wait=True,timeout=0.25):
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), b'?21000')
        recv = DataReciever(pipe,'valve type',cms.deviceAnswerToNumber,False)
        if wait:
            recv(timeout)
        return recv
        
    def getFirmware(self,deviceId,wait=True,timeout=0.25):
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), b'&')
        recv = DataReciever(pipe,'firmware',codecs.decode,False)
        if wait:
            recv(timeout)
        return recv
        
    def getStartVelocity(self,deviceId,wait=True,timeout=0.25):
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), b'?1')
        recv = DataReciever(pipe,'start velocity',cms.deviceAnswerToNumber,False)
        if wait:
            recv(timeout)
        return recv

    def getMaximumVelocity(self,deviceId,wait=True,timeout=0.25):
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), b'?2')
        recv = DataReciever(pipe,'maximum velocity',cms.deviceAnswerToNumber,False)
        if wait:
            recv(timeout)
        return recv
        
    def getStopVelocity(self,deviceId,wait=True,timeout=0.25):
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), b'?3')
        recv = DataReciever(pipe,'stop velocity',cms.deviceAnswerToNumber,False)
        if wait:
            recv(timeout)
        return recv
        
    def getReturnSteps(self,deviceId,wait=True,timeout=0.25):
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), b'?12')
        recv = DataReciever(pipe,'return steps',cms.deviceAnswerToNumber,False)
        if wait:
            recv(timeout)
        return recv
    
    def getSyringePos(self,deviceId):
        return self.syringePos[deviceId-1]
    
    def setSettings(self,deviceId,settingsdict,wait=True,timeout=0.25):
        """
        Send settings to a device.
        
        (This could be optimized by combining the commands into a single 
         command string, but for now this is probably fine. - 
         takes maybe 0.4 s in total.)

        Parameters
        ----------
        deviceId : TYPE
            DESCRIPTION.
        settingsdict : TYPE
            DESCRIPTION.
        wait : TYPE, optional
            DESCRIPTION. The default is True.
        timeout : TYPE, optional
            DESCRIPTION. The default is 0.2.

        Returns
        -------
        recv : TYPE
            DESCRIPTION.

        """
        recievers = []
        if 'valve type' in settingsdict:
            recievers.append(self.setValveType(deviceId,settingsdict['valve type'] ,False))
        if 'start velocity' in settingsdict:
            recievers.append(self.setStartVelocity(deviceId,settingsdict['start velocity'] ,False))
        if 'maximum velocity' in settingsdict:
            recievers.append(self.setMaximumVelocity(deviceId,settingsdict['maximum velocity'] ,False))
        if 'stop velocity' in settingsdict:
            recievers.append(self.setStopVelocity(deviceId,settingsdict['stop velocity'] ,False))
        if 'return steps' in settingsdict:
            recievers.append(self.setReturnSteps(deviceId,settingsdict['return steps'] ,False))
        if 'acceleration' in settingsdict:
            recievers.append(self.setAcceleration(deviceId,settingsdict['acceleration'] ,False))
            
        recv = recievers.pop(0)
        [recv.appendReciever(r) for r in recievers]
        if wait:
            recv(timeout)
        return recv
            
    def setValveType(self,deviceId,vtype ,wait=True,timeout=0.25):
        if isinstance(vtype, str):
            vtype = valveType_inv[vtype]
        vtype += 21000
        cmd = "h%sR" % int(vtype)
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'))
        recv = DataReciever(pipe,'valve type',lambda x : x,False)
        if wait:
            recv(timeout)
        return recv
    
    def setStartVelocity(self,deviceId,velocity ,wait=True,timeout=0.25):
        if not 50 <= velocity <= 800:
            raise ValueError("Start velocity v has to be in the range 50 <= v <= 800 motor steps/s, is : %s" % velocity)
        cmd = "v%sR" % int(velocity)
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'))
        recv = DataReciever(pipe,'start velocity',lambda x : x,False)
        if wait:
            recv(timeout)
        return recv    
    
    def setMaximumVelocity(self,deviceId,velocity ,wait=True,timeout=0.25):
        if not 2 <= velocity <= 3400:
            raise ValueError("Maximum velocity V has to be in the range 2 <= V <= 3400 motor steps/s, is : %s" % velocity)
        cmd = "V%sR" % int(velocity)
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'))
        recv = DataReciever(pipe,'maximum velocity',lambda x : x,False)
        if wait:
            recv(timeout)
        return recv
    
    def setStopVelocity(self,deviceId,velocity ,wait=True,timeout=0.25):
        if not 50 <= velocity <= 1700:
            raise ValueError("Stop velocity c has to be in the range 50 <= c <= 1700 motor steps/s, is : %s" % velocity)
        cmd = "c%sR" % int(velocity)
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'))
        recv = DataReciever(pipe,'stop velocity',lambda x : x,False)
        if wait:
            recv(timeout)
        return recv    
    
    def setReturnSteps(self,deviceId,steps ,wait=True,timeout=0.25):
        if not 0 <= steps <= 6400:
            raise ValueError("Return steps K has to be in the range 0 <= K <= 6400 motor steps, is : %s" % steps)
        cmd = "K%sR" % int(steps)
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'))
        recv = DataReciever(pipe,'return steps',lambda x : x,False)
        if wait:
            recv(timeout)
        return recv
    
    def setAcceleration(self,deviceId,acceleration ,wait=True,timeout=0.25):
        """
        Sets the acceleration of the syringe.
        The actual acceleration is mapped to an acceleration code,
        which is between 1 and 20, 
        where 1 corresponds to 2500 steps/s^2 and 20 to 50000 steps/s^2
        
        The code is evaluated using: acceleration // 2500.
        
        Parameters
        ----------
        deviceId : int
            hardware device id. Must be a PSD device id.
        acceleration : int
            syringe acceleration in steps/s^2. Must be between 2500 and 50000
        wait : bool, optional
            Indicates to wait for device answer. The default is True.
        timeout : float, optional
            Wait timeout in s. Blocks for the specified time or until a device
            answer is recieved. An error will be raised if no answer
            was recieved. The default is 0.2.

        Raises
        ------
        ValueError
            Raised if not 2500 <= acceleration <= 50000 motor steps/s^2

        Returns
        -------
        recv : DataReciever
            Data reciever handle. 
            To get the response from the device, call recv(timeout), where 
            timeout is the connection timeout to the comm server.
            If wait was not set, this can raise DeviceErrors. 

        """
        if not 2500 <= acceleration <= 50000:
            raise ValueError("Acceleration L has to be in the range 2500 <= L <= 50000 motor steps/s^2, is : %s" % acceleration)
        cmd = "L%sR" % int(acceleration // 2500)
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'))
        recv = DataReciever(pipe,'acceleration',lambda x : x,False)
        if wait:
            recv(timeout)
        return recv
    
    def terminateMovement(self, deviceId=None ):
        cmd = "T"
        if deviceId is None: # broadcast to all devices
            pipe = self._tansmitCommand(int('5f',16), cmd.encode('ascii'),True)
        else:
            pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'),True)
        recv = DataReciever(pipe,'terminate buffer',lambda x : x,False)
        recv(0.5)
        return recv
    
    def initializeValve(self, deviceId=None ,wait=True,timeout=0.25):
        cmd = "h20000"
        if deviceId is None:
            pipe = self._tansmitCommand(int('5f',16), cmd.encode('ascii'),True)
        else:
            pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'),True)
        recv = DataReciever(pipe,'valve init',lambda x : x,False)
        if wait:
            recv(timeout)
        return recv
    
    def initializeSyringe(self,deviceId,output,speed,backoff,wait=True,timeout=0.25):
        if not 1 <= output <= 8:
            raise ValueError("Possible valve positions are 1 <= output <= 8, is : %s" % output)
        if not 1 <= speed <= 40:
            raise ValueError("Valid speed codes are 1(fast) <= speed <= 40(slow), is : %s" % speed)
        if not 0 <= backoff <= 12800:
            raise ValueError("back-off steps k has to be in the range 0 <= k <= 12800, is : %s" % backoff)
        output += 26000
        speed += 10000
        cmd = "k%sh%sh%sR" % (int(backoff),int(output),int(speed))
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'))
        recv = DataReciever(pipe,'syringe init',lambda x : x,False)
        if wait:
            recv(timeout)
        return recv
    
    def moveValve(self,deviceId,position,wait=True,timeout=0.25):
        if not 1 <= position <= 8:
            raise ValueError("Possible valve positions are 1 <= position <= 8, is : %s" % position)
        position += 26000
        cmd = "h%sR" % int(position)
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'))
        recv = DataReciever(pipe,'valve move',lambda x : x,True)
        if wait:
            recv(timeout)
        return recv
    
    def moveSyringe(self,deviceId,stroke,velocity=-1,valvePos=-1,wait=True,timeout=0.25):
        """
        Moves the plunger of the syringe to an absolute position in microsteps.
        
        Prior to the plunger movement, a movement of the valve of the 
        PSD device into a new position can be performed by setting valvePos
        to the desired position.
        

        Parameters
        ----------
        deviceId : int
            hardware device id. Must be a PSD device id.
        stroke : int
            Desired position of the syringe plunger in microsteps. 
            Must be in between 0 and 192000.
        velocity : int, optional
            Maximum velocity of the plunger move in motorsteps/s. 
            Will retain the last set value if velocity is set to -1.
            Has to be in the range 2 <= V <= 3400 motor steps/s. 
            The default is -1.
        valvePos : int, optional
            Will optionally move the valve to this position prior to the
            plunger move. 
            The valve will not move if set to -1.
            The default is -1.
        wait : bool, optional
            Indicates to wait for device answer. The default is True.
        timeout : float, optional
            Wait timeout in s. Blocks for the specified time or until a device
            answer is recieved. An error will be raised if no answer
            was recieved. The default is 0.25.

        Raises
        ------
        ValueError
            DESCRIPTION.

        Returns
        -------
        recv : DataReciever
            Data reciever handle. 
            To get the response from the device, call recv(timeout), where 
            timeout is the connection timeout to the comm server.
            If wait was not set, this can raise DeviceErrors. 

        """
        if not 0 <= stroke <= 192000:
            raise ValueError("Possible syringe positions are 0 <= stroke <= 192000, is : %s" % stroke)
        cmd = ""
        if velocity >= 0:
            if not 2 <= velocity <= 3400:
                raise ValueError("Maximum velocity V has to be in the range 2 <= V <= 3400 motor steps/s, is : %s" % velocity)
            cmd += "V%s" % int(velocity)
        if valvePos >= 0:
            if not 1 <= valvePos <= 8:
                raise ValueError("Possible valve positions are 1 <= valvePos <= 8, is : %s" % valvePos)
            valvePos += 26000
            cmd += "h%s" % int(valvePos)

        cmd += "A%sR" % int(stroke)
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'))
        recv = DataReciever(pipe,'syringe move',lambda x : x,True)
        if wait:
            recv(timeout)
        return recv
    
    def dispense(self,deviceId,microsteps,velocity=-1,valvePos=-1,wait=True,timeout=0.25):
        """
        Relative dispense: Moves the plunger of the syringe microsteps up.
        
        Prior to the plunger movement, a movement of the valve of the 
        PSD device into a new position can be performed by setting valvePos
        to the desired position.
        

        Parameters
        ----------
        deviceId : int
            hardware device id. Must be a PSD device id.
        microsteps : int
            Desired dispense microsteps.
            The maximum dispense microsteps are stored in self.syringePos,
            i.e. the stroke cannot be below 0.
            Must be in between 0 and 192000.
        velocity : int, optional
            Maximum velocity of the plunger move in motorsteps/s. 
            Will retain the last set value if velocity is set to -1.
            Has to be in the range 2 <= V <= 3400 motor steps/s. 
            The default is -1.
        valvePos : int, optional
            Will optionally move the valve to this position prior to the
            plunger move. 
            The valve will not move if set to -1.
            The default is -1.
        wait : bool, optional
            Indicates to wait for device answer. The default is True.
        timeout : float, optional
            Wait timeout in s. Blocks for the specified time or until a device
            answer is recieved. An error will be raised if no answer
            was recieved. The default is 0.25.

        Raises
        ------
        ValueError
            DESCRIPTION.

        Returns
        -------
        recv : DataReciever
            Data reciever handle. 
            To get the response from the device, call recv(timeout), where 
            timeout is the connection timeout to the comm server.
            If wait was not set, this can raise DeviceErrors. 

        """
        if not 0 <= microsteps <= 192000:
            raise ValueError("Possible syringe positions are 0 <= stroke <= 192000, is : %s" % microsteps)
        cmd = ""
        if velocity >= 0:
            if not 2 <= velocity <= 3400:
                raise ValueError("Maximum velocity V has to be in the range 2 <= V <= 3400 motor steps/s, is : %s" % velocity)
            cmd += "V%s" % int(velocity)
        if valvePos >= 0:
            if not 1 <= valvePos <= 8:
                raise ValueError("Possible valve positions are 1 <= valvePos <= 8, is : %s" % valvePos)
            valvePos += 26000
            cmd += "h%s" % int(valvePos)

        cmd += "D%sR" % int(microsteps)
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'))
        recv = DataReciever(pipe,'dispense',lambda x : x,True)
        if wait:
            recv(timeout)
        return recv
        
    def pickup(self,deviceId,microsteps,velocity=-1,valvePos=-1,wait=True,timeout=0.25):
        """
        Relative Pickup: Moves the plunger of the syringe microsteps down.
        
        Prior to the plunger movement, a movement of the valve of the 
        PSD device into a new position can be performed by setting valvePos
        to the desired position.
        

        Parameters
        ----------
        deviceId : int
            hardware device id. Must be a PSD device id.
        microsteps : int
            Desired pickup microsteps.
            The maximum pickup microsteps are stored in self.syringePos,
            i.e. the stroke cannot be below 0.
            Must be in between 0 and 192000.
        velocity : int, optional
            Maximum velocity of the plunger move in motorsteps/s. 
            Will retain the last set value if velocity is set to -1.
            Has to be in the range 2 <= V <= 3400 motor steps/s. 
            The default is -1.
        valvePos : int, optional
            Will optionally move the valve to this position prior to the
            plunger move. 
            The valve will not move if set to -1.
            The default is -1.
        wait : bool, optional
            Indicates to wait for device answer. The default is True.
        timeout : float, optional
            Wait timeout in s. Blocks for the specified time or until a device
            answer is recieved. An error will be raised if no answer
            was recieved. The default is 0.25.

        Raises
        ------
        ValueError
            DESCRIPTION.

        Returns
        -------
        recv : DataReciever
            Data reciever handle. 
            To get the response from the device, call recv(timeout), where 
            timeout is the connection timeout to the comm server.
            If wait was not set, this can raise DeviceErrors. 

        """
        if not 0 <= microsteps <= 192000:
            raise ValueError("Possible syringe positions are 0 <= stroke <= 192000, is : %s" % microsteps)
        cmd = ""
        if velocity >= 0:
            if not 2 <= velocity <= 3400:
                raise ValueError("Maximum velocity V has to be in the range 2 <= V <= 3400 motor steps/s, is : %s" % velocity)
            cmd += "V%s" % int(velocity)
        if valvePos >= 0:
            if not 1 <= valvePos <= 8:
                raise ValueError("Possible valve positions are 1 <= valvePos <= 8, is : %s" % valvePos)
            valvePos += 26000
            cmd += "h%s" % int(valvePos)

        cmd += "P%sR" % int(microsteps)
        pipe = self._tansmitCommand(cms.deviceIdToAddress(deviceId), cmd.encode('ascii'))
        recv = DataReciever(pipe,'pickup',lambda x : x,True)
        if wait:
            recv(timeout)
        return recv
    
    def refill(self,deviceId,velocity,valveToReservoir,wait=True,timeout=0.25):
        """
        Completely refills a syringe from the valve position valveToReservoir
        with the velocity velocity.
        
        Prior to the plunger movement, the valve position will be changed
        to valveToReservoir.
        

        Parameters
        ----------
        deviceId : int
            hardware device id. Must be a PSD device id.
        velocity : int
            Maximum velocity of the plunger move in motorsteps/s. 
            Has to be in the range 2 <= V <= 3400 motor steps/s.
            Will retain the last set value if velocity is set to -1.
        valveToReservoir : int
            Will move the valve to this position prior to the
            plunger move.
            The valve will not move if set to -1.
        wait : bool, optional
            Indicates to wait for device answer. The default is True.
        timeout : float, optional
            Wait timeout in s. Blocks for the specified time or until a device
            answer is recieved. An error will be raised if no answer
            was recieved. The default is 0.25.

        Raises
        ------
        ValueError
            DESCRIPTION.

        Returns
        -------
        recv : DataReciever
            Data reciever handle. 
            To get the response from the device, call recv(timeout), where 
            timeout is the connection timeout to the comm server.
            If wait was not set, this can raise DeviceErrors. 

        """
        return self.moveSyringe(deviceId,192000,velocity,valveToReservoir,wait,timeout)
    
    def drain(self,deviceId,velocity,valveToWaste,wait=True,timeout=0.25):
        """
        Empties a syringe into the valve position valveToWaste
        with the velocity velocity.
        
        Prior to the plunger movement, the valve position will be changed
        to valveToWaste.
        

        Parameters
        ----------
        deviceId : int
            hardware device id. Must be a PSD device id.
        velocity : int
            Maximum velocity of the plunger move in motorsteps/s. 
            Has to be in the range 2 <= V <= 3400 motor steps/s.
            Will retain the last set value if velocity is set to -1.
        valveToWaste : int
            Will move the valve to this position prior to the
            plunger move.
            The valve will not move if set to -1.
        wait : bool, optional
            Indicates to wait for device answer. The default is True.
        timeout : float, optional
            Wait timeout in s. Blocks for the specified time or until a device
            answer is recieved. An error will be raised if no answer
            was recieved. The default is 0.25.

        Raises
        ------
        ValueError
            DESCRIPTION.

        Returns
        -------
        recv : DataReciever
            Data reciever handle. 
            To get the response from the device, call recv(timeout), where 
            timeout is the connection timeout to the comm server.
            If wait was not set, this can raise DeviceErrors. 

        """
        return self.moveSyringe(deviceId,0,velocity,valveToWaste,wait,timeout)    
        
    def waitServerReady(self,timeout=5):
        """        
        Blocks until the server process is ready or timeout has passed. 
        This takes a few seconds.

        After initialization, this should be called to wait for the startup
        of the server process to be completed. Commands will only be 
        executed after the server is ready.
        
        Parameters
        ----------
        timeout : float, optional
            wait time until the block is released if the process is still not
            ready. The default is 5.

        Returns
        -------
        bool
        indicates whether the server is ready.

        """
        return self.idle[-1].wait(timeout)        
        
    def _tansmitCommand(self,address,cmd,priority=False):
        """
        low level interface with the communication server.
        
        Enqueues the transmission of a command cmd to device(s)
        with the address address. The transmission will be executed 
        by the server process.
        
        After transmission of the command, a dict with the reponse of the 
        device and possible errors is accesible through the returned Connection
        
        Can raise the queue.Full exception.
        
        Example:
            controller = PumpController(port='COM1')
            controller.waitServerReady()
            
            pipe = controller._tansmitCommand(int('31',16), b'?')
            
            message, isbusy, errorcode = waitForAnswer(pipe,5) # wait for results to arrive, timeout: 5s


        Parameters
        ----------
        address : int
            Address of the device. See the device manual for all possible 
            addresses
        cmd : bytes
            command to send. See the device manual for all possible 
            commands.
        priority : bool, optional
            whether command should be enqueued into the priority or the 
            default command queue. Priority commands will be send prior to any
            default command. The default is False.

        Returns
        -------
        reciever : Connection
            

        """
        reciever, sender = mp.Pipe(False)
        if priority:
            self.priorityQueue.put((sender,address,cmd),True,0.1)
        else:
            self.commandQueue.put((sender,address,cmd),True,0.1)
        
        return reciever
            
        
    def reinitialize(self, wait=False):
        """
        Restarts the communication server.
        During startup, the server performs a device scan and updates the 
        device id list.
        
        You can explicitly wait for the server startup using the command
        waitServerReady.
        After initialization, waitServerReady should be called to wait 
        for the startup of the server process to be completed. Commands will 
        only be executed after the server is ready.

        Parameters
        ----------
        wait : bool, optional
            whether to wait until the server startup is complete. 
            The default is False.

        Raises
        ------
        Exception
            Related to communication with the server.

        Returns
        -------
        None.

        """
        if self.__comServer.is_alive():
            mp.get_logger().warn("Reinitialisation: Communication Process is still alive! Trying to gently shut down the process...")
            #warnings.warn("Reinitialisation: Communication Process is still alive! Trying to gently shut down the process...")
            self.__killComProcessEvent.set()
            self.__comServer.join(2)
            if self.__comServer.is_alive():
                mp.get_logger().warn("Reinitialisation: Communication Process not responding! killing the process...")
                #warnings.warn("Reinitialisation: Communication Process is still alive! killing the process...")
                self.__comServer.kill()
                self.__comServer.join(10)
                if self.__comServer.is_alive():
                    raise Exception("Cannot kill comm process")
        
        self.__killComProcessEvent.clear()
        
        self.serialinstance = serial.Serial()
        self.serialinstance.baudrate = self.portsettings.get('baudrate',38400)
        self.serialinstance.port = self.portsettings.get('port','COM3')
        self.serialinstance.bytesize = self.portsettings.get('bytesize',8)
        self.serialinstance.parity = self.portsettings.get('parity',serial.PARITY_NONE)
        self.serialinstance.stopbits = self.portsettings.get('stopbits',1)
        self.serialinstance.xonxoff = self.portsettings.get('xonxoff',False)
        self.serialinstance.rtscts = self.portsettings.get('rtscts',False)
        self.serialinstance.dsrdtr = self.portsettings.get('dsrdtr',False)
        self.serialinstance.timeout = self.portsettings.get('timeout',0.05)
        
        self.commandQueue = mp.Queue(100)
        self.priorityQueue = mp.Queue(100)
        
        self.statusbytes = mp.Array('i', np.full(16,-1))
        self.syringePos = mp.Array('i', np.full(16,-1))
        self.idle = [mp.Event() for i in range(17)] # last one is set after startup of the server
        
        self.__comServer = CommunicationServer(self.serialinstance,self.commandQueue,
                                                 self.priorityQueue, self.__killComProcessEvent,
                                                 self.statusbytes,self.syringePos, self.idle)
        
        self.__comServer.start()
        mp.get_logger().info("Server process on serial port %s started" % self.serialinstance.port)
        if wait:
            self.waitServerReady()
        
    
    def stopServer(self):
        self.__killComProcessEvent.set()
        
    def serverAlive(self):
        return self.__comServer.is_alive()
        
    def __repr__(self):
        rep = "PumpController: server process alive: %s\n" % self.__comServer.is_alive()
        rep += "Available devices: %s" % self.deviceIds()
        return rep
        



        
if __name__ == '__main__':
    logger = mp.log_to_stderr()
    logger.setLevel(logging.INFO)
    
    p = PumpController(port='COM4')
    p.waitServerReady()
    
