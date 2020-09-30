# -*- coding: utf-8 -*-
"""
Created on Wed Aug  5 18:49:04 2020

@author: Timo
"""

import serial
from serial.tools import list_ports
import queue
import multiprocessing as mp
import multiprocessing.connection
from multiprocessing.pool import ExceptionWithTraceback
import logging
import warnings
import time
import traceback
import binascii
import codecs
import sys
import numpy as np
import atexit
import functools
import itertools
from collections import OrderedDict

class DeviceError(Exception):
    """
    
    """
    
    deviceErrorsFull = {-1 : 'No device answer',
                    0 : 'No error',
                    1 : 'Initialization error – occurs when the device fails to initialize.',
                    2 : 'Invalid command – occurs when an unrecognized command is used.',
                    3 : 'Invalid operand – occurs when and invalid parameter is given with a command.',
                    4 : 'Invalid command sequence – occurs when the command communication protocol is incorrect.',
                    6 : 'EEPROM failure – occurs when the EEPROM is faulty.',
                    7 : 'Device not initialized – occurs when the device fails to initialize.',
                    9 : 'Syringe overload – occurs when the syringe encounters excessive back pressure.',
                    10 : 'Valve overload – occurs when the valve drive encounters excessive back pressure.',
                    11 : 'Syringe move not allowed – when the valve is in the bypass or throughput position, syringe move commands are not allowed.',
                    15 : 'Device is busy – occurs when the command buffer is full.'} 

    deviceErrors = {-1 : 'No device answer',
                        0 : 'No error',
                        1 : 'Initialization error',
                        2 : 'Invalid command',
                        3 : 'Invalid operand',
                        4 : 'Invalid command sequence',
                        6 : 'EEPROM failure',
                        7 : 'Device not initialized',
                        9 : 'Syringe overload',
                        10 : 'Valve overload',
                        11 : 'Syringe move not allowed',
                        15 : 'Device is busy'} 
    
    def __init__(self,statusbyte,*args,**keyargs):
        self.busy, self.errorcode = DeviceError.decodeStatusbyte(statusbyte)
        args += ("busy: %s" % self.busy,)
        if 'deviceId' in keyargs:
            self.deviceId = keyargs.pop('deviceId',None)
            args += ("device: %s" % self.deviceId,)
        if 'rawcommand' in keyargs:
            self.rawcommand = keyargs.pop('rawcommand',None)
            args += ("command: %s" % self.rawcommand,)
        if keyargs.pop('short',False):
            super(DeviceError, self).__init__(DeviceError.deviceErrors[self.errorcode],*args)
        else:
            super(DeviceError, self).__init__(DeviceError.deviceErrorsFull[self.errorcode],*args)
            
    @staticmethod
    def isBusyStatus(statusbyte):
        return bool(statusbyte & int('20',16))

    @staticmethod    
    def decodeStatusbyte(status):
        if status == -1:
            return False, -1
        busy = DeviceError.isBusyStatus(status)
        errorcode = status & int('0f',16)
        return busy, errorcode


class DataReciever(object):

    def __init__(self,pipes,names,dataconverters=None,raiseDeviceErrors=True):
        if hasattr(pipes,"recv") and hasattr(pipes,"poll"): #ugly check, whether this is a Connection; this has to be done this way due to python 2 vs 3 isues
            self.isScalar = True
        else:
            self.isScalar = False
        self.pipes = pipes
        self.names = names
        self.dataavailable = False
        self.data = OrderedDict()

        if self.isScalar:
            self.dataconverters = dataconverters if dataconverters is not None else lambda x : x
            self.raiseDeviceErrors = raiseDeviceErrors
        else:
            self.dataconverters = dataconverters if dataconverters is not None else [lambda x : x for i in range(len(self.pipes))]
            if isinstance(raiseDeviceErrors,bool):
                self.raiseDeviceErrors = [raiseDeviceErrors for i in range(len(self.pipes))]
            else:
                self.raiseDeviceErrors = raiseDeviceErrors
                
                
    def __repr__(self):
        if self.dataavailable:
            return "DataReciever: transmission complete\ndata:\n%s" % self.data
        else:
            return "DataReciever: Data not yet available:\n%s\nCall DataReciever() to check for the data" % self.names
        
    def __call__(self,timeout=0.2):
        if self.dataavailable:
            return self.data
        else:
            if self.isScalar:
                try:
                    msg, err = DataReciever.waitForAnswer(self.pipes,timeout,self.raiseDeviceErrors)
                except Exception as e:
                    self.dataavailable = True
                    self.data = "Error during transmission:\n%s" % e
                    raise
                self.errors = err
                self.busy = err.busy
                self.data = self.dataconverters(msg)
                self.dataavailable = True
                del self.pipes
                return self.data
            else:
                self.errors = []
                self.busy = []
                for p, name, conv, raising in zip(self.pipes, self.names, self.dataconverters ,self.raiseDeviceErrors):
                    try:
                        msg, err = DataReciever.waitForAnswer(p,timeout,raising)
                    except Exception as e:
                        [p.close() for p in self.pipes]
                        self.dataavailable = True
                        self.data = "Error during transmission:\n%s" % e
                        raise
                    self.errors.append(err)
                    self.busy.append(err.busy)
                    self.data[name] = conv(msg)
                del self.pipes
                self.dataavailable = True
                return self.data
            
    def appendReciever(self,other):
        assert self.dataavailable == False # in future versions, we could also handle the other two cases
        assert other.dataavailable == False
        if self.isScalar:
            self.dataconverters = [self.dataconverters]
            self.pipes = [self.pipes]
            self.names = [self.names]
            self.raiseDeviceErrors = [self.raiseDeviceErrors]
            
        if other.isScalar:
            other.dataconverters = [other.dataconverters]
            other.pipes = [other.pipes]
            other.names = [other.names]
            other.raiseDeviceErrors = [other.raiseDeviceErrors]
            
        self.dataconverters += other.dataconverters
        self.pipes += other.pipes
        self.names += other.names
        self.raiseDeviceErrors += other.raiseDeviceErrors
        self.isScalar = False
    
    @staticmethod
    def waitForAnswer(pipe_connection,timeout=0.15,raiseDeviceErrors=True):
        """
        
    
        Parameters
        ----------
        pipe_connection : TYPE
            DESCRIPTION.
        raiseDeviceErrors : TYPE, optional
            Raise all device errors. if False: Only raises invalid command errors.
            The default is True.
        timeout : TYPE, optional
            timeout in s for server answer. The default is 0.15.
    
        Raises
        ------
        Exception
            DESCRIPTION.
        DeviceError
            DESCRIPTION.
        data
            DESCRIPTION.
    
        Returns
        -------
        TYPE
            DESCRIPTION.
        isbusy : TYPE
            DESCRIPTION.
        errorcode : TYPE
            DESCRIPTION.
    
        """
        if not pipe_connection.poll(timeout):
            raise Exception("Connection timeout to server process, Is the server ready?")
        else:
            data = pipe_connection.recv()
            if data['success']:
                if data['status'] is not None:
                    err = DeviceError(data['status'])
                    if err.errorcode != 0:
                        if raiseDeviceErrors or 1 < err.errorcode < 5:
                            raise err
                else:
                    err = DeviceError(-1) #no response, i.e. broadcast
                return data['message'], err
            else:            
                raise data['error'] #server error


class CommunicationServer(mp.Process):
    """
    handles the low-level communication with the serial interface.
    all communication from other code should be done via the PumpController
    
    the PumpController provides a high-level interface to enqueue commands in
    the cammand queue of the server.
    
    Each server handles the communication with one serial port. 
    
    
    """
    
    def __init__(self, serialinstance, commandQueue, priorityQueue, stopevent,statusbytes,syringePos,valvePos,idlearray):
        self.serialinstance = serialinstance
        self.commandQueue = commandQueue
        self.priorityQueue = priorityQueue
        self.stopevent = stopevent
        self.statusbytes = statusbytes
        self.idlearray = idlearray
        self.syringePos = syringePos
        self.valvePos = valvePos
        self.retries = 1 # maximum number of retries until the communication will be considered as failed
        self.__sequence = np.zeros(16,dtype=np.int)
        self.__availableDeviceId = []
        self.__deviceType = [] #0 for MVP; 1 for syringe pump;
        super(CommunicationServer, self).__init__()
        
    def run(self):
        self.serialinstance.open()
        self.scanDevices()
        mp.get_logger().info("Ready to accept requests.")
        self.idlearray[-1].set()
        currentDeviceIndex = 0
        deviceNumber = len(self.__availableDeviceId)
        try:
            
            # main loop
            while not self.stopevent.is_set():

                if not self.priorityQueue.empty():
                    ret = dict()
                    ret['status'] = ''
                    ret['message'] = ''
                    pipe ,address,cmd = self.priorityQueue.get(False)
                    try:
                        status, msg = self._sendCmd(address, cmd)
                        ret['status'] = status
                        ret['message'] = msg
                    except Exception as e:
                        ret['success'] = False
                        ret['error'] = ExceptionWithTraceback(e,e.__traceback__) #RemoteException(e, traceback.format_exc())
                        try:
                            pipe.send(ret)
                        except Exception:
                            pass
                        continue
                    ret['success'] = True
                    try:
                        pipe.send(ret)
                    except Exception:
                        pass
                    continue
                
                if not self.commandQueue.empty():
                    ret = dict()
                    ret['status'] = ''
                    ret['message'] = ''
                    pipe ,address,cmd = self.commandQueue.get(False)
                    try:
                        status, msg = self._sendCmd(address, cmd)
                        ret['status'] = status
                        ret['message'] = msg
                    except Exception as e:
                        ret['success'] = False
                        ret['error'] = ExceptionWithTraceback(e,e.__traceback__)
                        try:
                            pipe.send(ret)
                        except Exception:
                            pass
                        continue
                    ret['success'] = True
                    try:
                        pipe.send(ret)
                    except Exception:
                        pass
                    continue
                
                if deviceNumber > 0:
                    self._updateStatus(self.__availableDeviceId[currentDeviceIndex], self.__deviceType[currentDeviceIndex])
                    currentDeviceIndex += 1
                    if currentDeviceIndex > deviceNumber:
                        currentDeviceIndex = 0

                
        except Exception:
            traceback.print_exc()
        self.serialinstance.close()
        
    def scanDevices(self):
        try:
            self._sendCmd(int('5f',16),b'h30001R') # enable h-commands for all devices
        except Exception as e:
            mp.get_logger().info("Communication error; error: %s" % (e))
            
        mp.get_logger().warn("Start scanning devices...")
        for i in range(1,17): # maximum 16 devices, iterate over deviceIds
            try:
                status, firmware = self._sendCmd(deviceIdToAddress(i), b'&')
            except Exception as e:
                mp.get_logger().info("No device with id %s; error: %s" % (i,e))
                continue
            
            self.__availableDeviceId.append(i)
            
            self.statusbytes[i-1] = status
            if DeviceError.isBusyStatus(status):
                self.idlearray[i-1].clear()
            else:
                self.idlearray[i-1].set()
            
            try:
                status, msg = self._sendCmd(deviceIdToAddress(i), b'?')
            except Exception as e:
                mp.get_logger().info("Communication error with id %s; error: %s" % (i,e))
                self.__deviceType.append(-1)
                continue
            
            if status[0] & int('0f',16) == 0: # no device errorcode -> syringe pump
                self.syringePos[i-1] = deviceAnswerToNumber(msg)
                self.__deviceType.append(1)
                mp.get_logger().info("Found syringe pump device with id %s: %s" % (i,firmware))
            else:
                self.__deviceType.append(0)
                mp.get_logger().info("Found valve positioner device with id %s: %s" % (i,firmware))
            
            self._updateStatus(self.__availableDeviceId[-1], self.__deviceType[-1])

        mp.get_logger().warn("Available devices: %s" % (self.__availableDeviceId))
    
    
    def _updateStatus(self,deviceId,devicetype):
        if devicetype == 1: # syringe pump
            try:
                status, msg = self._sendCmd(deviceIdToAddress(deviceId), b'?')
                self.syringePos[deviceId-1] = deviceAnswerToNumber(msg)
                
                status, msg = self._sendCmd(deviceIdToAddress(deviceId), b'?24000')
                self.valvePos[deviceId-1] = deviceAnswerToNumber(msg)
                
            except Exception as e:
                mp.get_logger().info("Communication error with id %s; error: %s" % (deviceId,e))
        elif devicetype == 0: # MVP
            try:
                status, msg = self._sendCmd(deviceIdToAddress(deviceId), b'?24000')
                self.valvePos[deviceId-1] = deviceAnswerToNumber(msg)
                
            except Exception as e:
                mp.get_logger().info("Communication error with id %s; error: %s" % (deviceId,e))
                
        else:
            mp.get_logger().info("Unknown device with id %s, type is %s" % (deviceId,self.__deviceType))
            try:
                status, msg = self._sendCmd(deviceIdToAddress(deviceId), b'Q')
            except Exception as e:
                mp.get_logger().info("Communication error with id %s; error: %s" % (deviceId,e))
        
        
    def _sendCmd(self,address,cmd):
        """
        sends a command to an address and recieves the answer.
        There will be no answer after a broadcast command.
        This should never be called from a different process
        than the Server process

        Parameters
        ----------
        address : unsigned int8 
            i.e. smaller than 255, see the manual for further details 
        cmd : bytes
            command string.

        Returns
        -------
        (statusbyte, datastring) 
        
        None,None if address is a broadcast

        """
        error = ''
        self.serialinstance.reset_input_buffer()

        broadcast = isBroadcast(address)
        
        if not broadcast:
            deviceId = addressToDeviceId(address)
            seq = self.__sequence[deviceId-1]
            self.__sequence[deviceId-1] += 1
            if self.__sequence[deviceId-1] > 7:
                self.__sequence[deviceId-1] = 1
        else:
            seq = int(1)
            
        for retry in range(self.retries+1):
            
            sequencebyte = seq | int('30',16)
            if retry > 0:
                sequencebyte = sequencebyte | int('08',16)
                mp.get_logger().info("Retry to send command %s to address %s, first error message: %s" % (cmd,str(hex(address)),error))
            
            commandarray = np.concatenate(([int('02',16)], [address], [sequencebyte], np.frombuffer(cmd,dtype=np.uint8), [int('03',16)]))
            commandarray = commandarray.astype(np.uint8)
            checksum = calculateChecksum(commandarray)
            fullcommand = np.concatenate((commandarray,checksum)).astype(np.uint8)
            
            self.serialinstance.write(fullcommand.tobytes())
            
            if not broadcast:
                message = self.serialinstance.read_until(b'\x03')
                checksum_response = self.serialinstance.read(1)
                if message == b'':
                    error = "connection timeout"
                    continue
                
                messageArray = np.frombuffer(message,dtype=np.uint8)
                checksum_calc = calculateChecksum(messageArray).tobytes()
                if checksum_response != checksum_calc:
                    error = "checksum mismatch"
                    continue
                
                status = messageArray[2]
                self.statusbytes[deviceId-1] = status
                if DeviceError.isBusyStatus(status):
                    self.idlearray[deviceId-1].clear()
                else:
                    self.idlearray[deviceId-1].set()
                message = messageArray[3:-1]
                return status,message
            else:
                return None,None
        
        mp.get_logger().warn("No answer from address %s after sending %s; reason: %s" % (str(hex(address)), fullcommand.tobytes(),error))
        
        raise ConnectionError("No answer from address %s after sending %s : %s" % (str(hex(address)),fullcommand.tobytes(),error))
        
        
         
def isBroadcast(address):
    assert address < 255
    return not ((address & int('f0',16)) == int('30',16) or address == int('40',16))

def deviceIdToAddress(deviceId):
    return deviceId + int('30',16)
        
def addressToDeviceId(address):
    deviceId = (address & int('0f',16))
    if deviceId == 0:
        deviceId = 16
    return deviceId
        
def deviceAnswerToNumber(array):
    array = array.astype(np.uint8)
    arr_bytes = array.tobytes()
    return int(arr_bytes)
    
def calculateChecksum(command):
    """
    Calcualtes the checksum

    Parameters
    ----------
    command : np.array, uint8
        DESCRIPTION.

    Returns
    -------
    checksum : np.array, uint8
        DESCRIPTION.

    """
    command = command.astype(np.uint8)
    b = np.unpackbits(command.reshape((1,command.size)).T,axis=1).sum(axis=0)
    checksum = np.packbits(b % 2)
    return checksum
