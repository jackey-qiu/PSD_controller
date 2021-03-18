# -*- coding: utf-8 -*-
###############################################################################
# Copyright (c) 2020 Timo Fuchs, Olaf Magnussen all rights reserved
#
# This software was developed during the PhD work of Timo Fuchs,
# within the group of Olaf Magnussen. Usage within the group is hereby granted.
###############################################################################

__author__ = "Timo Fuchs"
__copyright__ = "Copyright 2020, Timo Fuchs, Olaf Magnussen all rights reserved"
__credits__ = []
__license__ = "all rights reserved"
__version__ = "1.0.0"
__maintainer__ = "Timo Fuchs"
__email__ = "fuchs@physik.uni-kiel.de"

import tango
from tango import DevState, GreenMode, AttrQuality, AttrWriteType, DispLevel, DebugIt, EventType
from tango.server import Device, command, attribute, device_property, run
import time
import queue
import concurrent.futures
import threading
from dataclasses import dataclass, field
from typing import Callable
import serial
from serial.tools import list_ports
import numpy as np
from .DeviceStatus import StatusByte
import traceback


@dataclass(order=True)
class PrioritizedTask:
    priority: int
    task: Callable = field(compare=False)
    future: concurrent.futures.Future = field(compare=False, init=False)

    def __post_init__(self):
        self.future = concurrent.futures.Future()

    def __call__(self):
        if self.future.done():
            return self.future.result()
        if self.future.set_running_or_notify_cancel():
            try:
                result = self.task()
                self.future.set_result(result)
            except Exception as e:
                self.future.set_exception(e)
        else:
            self.future.set_exception(concurrent.futures.CancelledError())

    def cancel(self):
        self.future.set_exception(
            concurrent.futures.CancelledError("Cancelled extenally"))


class PumpServer(Device):
    green_mode = GreenMode.Gevent

    baudrate = device_property(dtype=int, default_value=38400)
    bytesize = device_property(dtype=int, default_value=8)
    parity = device_property(dtype=str, default_value=serial.PARITY_NONE)
    stopbits = device_property(dtype=int, default_value=1)
    xonxoff = device_property(dtype=bool, default_value=False)
    rtscts = device_property(dtype=bool, default_value=False)
    dsrdtr = device_property(dtype=bool, default_value=False)
    timeout = device_property(dtype=float, default_value=0.05)
    retries = device_property(dtype=int, default_value=1)
    writeTimeout = device_property(dtype=float, default_value=1)
    # port = device_property(dtype=str, default_value='')

    def __init__(self, *args, **keyargs):
        self.taskqueue = queue.PriorityQueue()
        self.workerthread = threading.Thread()
        self.stopevent = threading.Event()
        self.serialinstance = serial.Serial()
        super().__init__(*args, **keyargs)

    def init_device(self):
        super().init_device()

        if self.workerthread.is_alive():
            self.stopevent.set()

        self._config = b''

        # self.serialinstance = serial.Serial()
        self._port = ''
        self.count = 0
        self.__sequence = np.zeros(16, dtype=np.int)

        self.__availableDeviceId = np.array([])

        self._statusbytes = np.full(16, 255, dtype=np.uint8)
        self._syringePos = np.full(16, -1, dtype=np.int)
        self._valvePos = np.full(16, -1, dtype=np.int)

        self._syringeStatus = np.full(16, 512, dtype=np.int)
        self._valveStatus = np.full(16, 512, dtype=np.int)

        # 0 for MVP; 1 for syringe pump;
        self._deviceType = np.full(16, -1, dtype=np.int)

        self.set_state(DevState.OFF)
        self.set_status("serial port controlling thread not running")

    @attribute(dtype=bool, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ)
    def isConnected(self):
        return self.workerthread.is_alive()

    @attribute(dtype=str, display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ)
    def port(self):
        return self._port

    @attribute(dtype=(str,), display_level=DispLevel.OPERATOR,
               access=AttrWriteType.READ, max_dim_x=100)
    def listPorts(self):
        return [p.device for p in list_ports.comports()]

    @command(dtype_in=int,dtype_out=(str,))
    def scanPortsForDeviceId(self, deviceId):
        if self.workerthread.is_alive() or self.serialinstance.isOpen():
            raise Exception("Server is already connected to a port. Please disconnect first")
            
        hwaddress = deviceIdToAddress(deviceId)
        founddev = []
        for dev_pr in list_ports.comports():
            dev = dev_pr.device
            print("Scan port %s" % dev)
            self.serialinstance = serial.Serial()
            self.serialinstance.baudrate = self.baudrate
            self.serialinstance.port = dev
            self.serialinstance.bytesize = self.bytesize
            self.serialinstance.parity = self.parity
            self.serialinstance.stopbits = self.stopbits
            self.serialinstance.xonxoff = self.xonxoff
            self.serialinstance.rtscts = self.rtscts
            self.serialinstance.dsrdtr = self.dsrdtr
            self.serialinstance.timeout = self.timeout
            self.serialinstance.write_timeout = self.writeTimeout
            try:
                # to test that the port exists; error in the thread would be hard
                # to debug!
                self.serialinstance.open()
            except serial.SerialException as e:
                print("Cannot open serial port %s :\n%s" % (dev,e))
                if self.serialinstance.isOpen():
                    self.serialinstance.close()
                continue
            except Exception as e:
                if self.serialinstance.isOpen():
                    self.serialinstance.close()
                print("Unexpected exception while opening serial port %s :\n%s" % (dev,e))
                continue
            try:
                status, firmware = self._sendCmd(hwaddress, b'&')
                self.serialinstance.close()
                print("Found device with firmware %s" % firmware.tobytes())
                founddev.append(dev)
            except serial.SerialException as e:
                if self.serialinstance.isOpen():
                    self.serialinstance.close()
                print("Cannot reopen serial port %s :\n%s" % (dev,e))
            except Exception as e:
                if self.serialinstance.isOpen():
                    self.serialinstance.close()
                print("Search without success for device with id %s on serial port %s :\n%s" % (deviceId,dev,e))
        return founddev
        
    @command(dtype_in=str)
    def connectPort(self, port=''):
        if port != '':
            self._port = port
        self.restartThread()
        self.scanDevices(10)

    @command
    def disconnectPort(self):
        self.stopevent.set()

    @attribute(dtype=(np.uint8,), access=AttrWriteType.READ, display_level=DispLevel.OPERATOR,
               max_dim_x=16)
    def statusbytes(self):
        return self._statusbytes

    @attribute(dtype=(np.int,), access=AttrWriteType.READ, display_level=DispLevel.OPERATOR,
               max_dim_x=16)
    def syringePos(self):
        return self._syringePos

    @attribute(dtype=(np.int,), access=AttrWriteType.READ, display_level=DispLevel.OPERATOR,
               max_dim_x=16)
    def syringeStatus(self):
        return self._syringeStatus

    @attribute(dtype=(np.int,), access=AttrWriteType.READ, display_level=DispLevel.OPERATOR,
               max_dim_x=16)
    def valveStatus(self):
        return self._valveStatus

    @attribute(dtype=(np.int,), access=AttrWriteType.READ, display_level=DispLevel.OPERATOR,
               max_dim_x=16)
    def valvePos(self):
        return self._valvePos

    @attribute(dtype=(np.int,), access=AttrWriteType.READ, display_level=DispLevel.OPERATOR,
               max_dim_x=16)
    def deviceType(self):
        return self._deviceType

    @attribute(dtype=str, label="global configuration of devices in YAML format", access=AttrWriteType.READ_WRITE)
    def configuration(self):
        return self._config

    @configuration.write
    def configuration(self, config):
        self._config = config

    @command(dtype_in=int)
    def terminateMovement(self, address=0):
        if not int('30', 16) < address < int('60', 16):
            address = int('5f', 16)

        def task():
            return self._sendCmd(address, b'T')
        status, msg = self.execInThread(task, True, 0)
        err = StatusByte(status, address=address)
        err.raiseIfError()

    @command(dtype_in=int)
    def stopCommandBuffer(self, address=0):
        if not int('30', 16) < address < int('60', 16):
            address = int('5f', 16)

        def task():
            return self._sendCmd(address, b't')
        status, msg = self.execInThread(task, True, 0)
        err = StatusByte(status, address=address)
        err.raiseIfError()

    # dtype_in: array int with: [priority,address,moveCmd,command]
    # out:
    @command(dtype_in=(np.uint8,), dtype_out=(np.uint8,))
    def sendCommand(self, cmd):
        """


        Parameters
        ----------
        cmd : ndarray(int) with: [priority,address,moveCmd,command]
            DESCRIPTION.

        Returns
        -------
        ndarray(int) msg
            msg[0] : statusbyte
            msg[1:] : device answer

        """
        priority = cmd[0]
        address = cmd[1]
        moveCmd = bool(cmd[2])
        command = cmd[3:]
        if moveCmd and not isBroadcast(address):
            deviceId = addressToDeviceId(address)

            def task():
                status, msg = self._sendCmd(address, command)
                status = status & ~int('20', 16)  # force status busy
                self._statusbytes[deviceId - 1] = status
                return status, msg
        elif moveCmd and isBroadcast(address):
            def task():
                deviceids = np.array(
                    list(
                        deviceIdLookup[address]),
                    dtype=np.int)
                availableids = np.intersect1d(
                    deviceids, self.__availableDeviceId)
                status, msg = self._sendCmd(address, command)
                status = status & ~int('20', 16)  # force status busy
                self._statusbytes[availableids - 1] = status
                return status, msg

        else:
            def task():
                return self._sendCmd(address, command)
        status, msg = self.execInThread(task, True, priority)
        if msg is not None:
            return np.concatenate([[status], msg]).astype(np.uint8)
        else:
            return np.array([status], dtype=np.uint8)

    # this would be great as decorator, but is not yet impemented in python 3.7
    def execInThread(self, taskfun: Callable, wait=True,
                     priority: int = 1000, timeout=None):
        if not self.workerthread.is_alive():
            raise Exception(
                "Serial port controlling thread not running. Did you connect to a port?")
        task = PrioritizedTask(priority, taskfun)
        self.taskqueue.put(task)
        if wait:
            return task.future.result(timeout)

    def main_thread_loop(self):
        # with tango.EnsureOmniThread():  # not working, wait for future release
        try:
            self.serialinstance.open()
            self.set_state(DevState.RUNNING)
            self.set_status("Device startup")
        except Exception:
            self.set_state(DevState.FAULT)
            raise

        currentDeviceIndex = 0
        tstart = time.time()
        while not self.stopevent.is_set():
            try:
                task = self.taskqueue.get_nowait()
                self.set_state(DevState.RUNNING)
                self.set_status("Sending commands")
                task()
                self.taskqueue.task_done()
                continue
            except queue.Empty:
                pass

            if self.get_state() != DevState.FAULT:
                self.set_state(DevState.ON)
                self.set_status(
                    "Command buffer empty, ready to accept requests.")

            if len(self.__availableDeviceId) > 0:
                if currentDeviceIndex >= len(self.__availableDeviceId):
                    currentDeviceIndex = 0
                    # uncomment to print updaterate
                    # print(time.time() - tstart)
                    tstart = time.time()

                devid = self.__availableDeviceId[currentDeviceIndex]

                if StatusByte.isBusyStatus(
                        self._statusbytes[self.__availableDeviceId - 1]):  # any busy??
                    if not StatusByte.isBusyStatus(
                            self._statusbytes[devid - 1]):  # current index not busy, so skip this one
                        currentDeviceIndex += 1
                        continue

                try:
                    self.__updateStatus(devid, self._deviceType[devid - 1])
                except Exception as e:
                    self.set_state(DevState.FAULT)
                    # traceback.print_exc()
                    self.set_status("Error during status update: %s" % str(e))

                currentDeviceIndex += 1

            else:
                time.sleep(0.01)  # no device detected, so just idle

        self.serialinstance.close()
        self.set_state(DevState.OFF)
        self.set_status("serial port controlling thread not running")

    @command
    def scanDevices(self, timeout=None):
        """
        Scan for devices on the bus
        long running command, so will return before execution finished

        device.state() will be set to DevState.RUNNING during execution of
        the command. This can be used to detect when the command finishes.

        Raises
        ------
        exception
            DESCRIPTION.

        Returns
        -------
        None.

        """
        self.set_state(DevState.RUNNING)
        self.set_status("Sending commands")

        def taskfun():
            # enable h-commands for all devices
            self._sendCmd(int('5f', 16), b'h30001R')
            # self.__availableDeviceId.clear()
            self._deviceType[:] = -1
            self._syringePos[:] = -1
            self._syringeStatus[:] = 512
            self._valveStatus[:] = 512
            __availDev = []
            for i in range(
                    1, 17):  # maximum 16 devices, iterate over deviceIds
                try:
                    status, firmware = self._sendCmd(
                        deviceIdToAddress(i), b'&')
                    print("Found device with firmware %s" % firmware.tobytes())
                except Exception:
                    # ("No device with id %s; error: %s" % (i,e))
                    self._deviceType[i - 1] = -1
                    continue

                __availDev.append(i)
                #self._statusbytes[i-1] = status

                try:
                    status, msg = self._sendCmd(deviceIdToAddress(i), b'?')
                except Exception:  # this should not happen, as a device is already detected, so raise exception!
                    self._deviceType[i - 1] = -1
                    print(
                        "ScanDevices: Unexpected error during transmission: device answered, but now not anymore!")
                    continue

                if status & int(
                        '0f', 16) == 0:  # no device errorcode -> syringe pump
                    self._syringePos[i - 1] = deviceAnswerToNumber(msg)
                    self._deviceType[i - 1] = 1

                    print(
                        "Identified syringe pump device with id %s: %s" %
                        (i, firmware.tobytes()))
                else:
                    self._deviceType[i - 1] = 0
                    print(
                        "Identified valve positioner device with id %s: %s" %
                        (i, firmware.tobytes()))
                    #mp.get_logger().info("Found valve positioner device with id %s: %s" % (i,firmware))
                try:
                    self.__updateStatus(
                        __availDev[-1], self._deviceType[i - 1], True)
                except Exception:  # this should not happen, as a device is already detected, so raise exception!
                    self._deviceType[i - 1] = -1
                    print(
                        "ScanDevices: Unexpected error during transmission: device answered, but now not anymore!")
                    continue
            self.__availableDeviceId = np.array(__availDev, dtype=np.int)
            # self.push_data_ready_event("deviceType")
            #self.deviceNumber = len(self.__availableDeviceId)

        self.execInThread(taskfun, False, 1000, timeout)

        #mp.get_logger().warn("Available devices: %s" % (self.__availableDeviceId))

    @command
    def restartThread(self):
        """
        Restarts the communication thread and opens the serial port.

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

        # kill thread, if running
        if self.workerthread.is_alive():
            self.stopevent.set()
            self.workerthread.join(1)
        self.set_state(DevState.OFF)
        self.set_status("serial port controlling thread not running")
        self.stopevent.clear()

        # cleanup tasks
        while not self.taskqueue.empty():
            try:
                self.taskqueue.get_nowait().cancel()
                self.taskqueue.task_done()
            except queue.Empty:
                break

        self.serialinstance = serial.Serial()
        self.serialinstance.baudrate = self.baudrate
        self.serialinstance.port = self._port
        self.serialinstance.bytesize = self.bytesize
        self.serialinstance.parity = self.parity
        self.serialinstance.stopbits = self.stopbits
        self.serialinstance.xonxoff = self.xonxoff
        self.serialinstance.rtscts = self.rtscts
        self.serialinstance.dsrdtr = self.dsrdtr
        self.serialinstance.timeout = self.timeout
        self.serialinstance.write_timeout = self.writeTimeout
        try:
            # to test that the port exists; error in the thread would be hard
            # to debug!
            self.serialinstance.open()
            self.serialinstance.close()
        except serial.SerialException:
            print(traceback.print_exc())
            raise
        except Exception as e:
            print("Unexpected exception while opening serial port :\n%s" % e)
            raise
        self.workerthread = threading.Thread(target=self.main_thread_loop)
        self.workerthread.daemon = True
        self.workerthread.start()

    def _sendCmd(self, address, cmd):
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

        broadcast = isBroadcast(address)

        if not broadcast:
            deviceId = addressToDeviceId(address)
            seq = self.__sequence[deviceId - 1]
            self.__sequence[deviceId - 1] += 1
            if self.__sequence[deviceId - 1] > 7:
                self.__sequence[deviceId - 1] = 1
        else:
            seq = int(1)

        for retry in range(self.retries + 1):
            self.serialinstance.reset_input_buffer()
            self.serialinstance.reset_output_buffer()
            sequencebyte = seq | int('30', 16)
            if retry > 0:
                sequencebyte = sequencebyte | int('08', 16)
                print("retry sending command")

            commandarray = np.concatenate(([int('02', 16)], [address], [
                                          sequencebyte], np.frombuffer(cmd, dtype=np.uint8), [int('03', 16)]))
            commandarray = commandarray.astype(np.uint8)
            checksum = calculateChecksum(commandarray)
            fullcommand = np.concatenate(
                (commandarray, checksum)).astype(
                np.uint8)
            self.serialinstance.write(fullcommand.tobytes())
            if not broadcast:

                message = self.serialinstance.read_until(b'\x03')
                if message == b'':
                    error = "connection timeout"
                    continue

                if not message.endswith(b'\x03'):
                    error = "Unexpected response: message should end with 0x03, got: %s" % message
                    continue

                msgstart = message.find(b'\x02')
                if msgstart < 0:
                    error = "Unexpected response: cannot find start symbol 0x02, got: %s" % message
                    continue

                message = message[msgstart:]

                timeout_s = self.serialinstance.timeout
                self.serialinstance.timeout = timeout_s / 2  # to speed up scanning
                checksum_response = self.serialinstance.read(1)
                self.serialinstance.timeout = timeout_s

                messageArray = np.frombuffer(message, dtype=np.uint8)
                checksum_calc = calculateChecksum(messageArray).tobytes()
                if checksum_response != checksum_calc:
                    error = "checksum mismatch: %s is not equal to calculated %s, message : %s" % (
                        checksum_response.hex(), checksum_calc.hex(), message)
                    continue

                status = messageArray[2]
                # self._statusbytes[deviceId-1] = status # this does not work!,
                # hardware bug???
                message = messageArray[3:-1]
                return status, message
            else:
                return 255, None
        self._statusbytes[deviceId - 1] = 255
        raise ConnectionError(
            "No answer from address %s after sending %s : %s" %
            (str(address), fullcommand.tobytes(), error))

    def __updateStatus(self, deviceId, devicetype, full=False):
        """
        only to be called by communication thread


        Parameters
        ----------
        deviceId : TYPE
            DESCRIPTION.
        devicetype : TYPE
            DESCRIPTION.
        full: bool, default: False
            indicate to force a full status update

        Returns
        -------
        status : TYPE
            DESCRIPTION.

        """
        stat = None
        try:
            address = deviceIdToAddress(deviceId)

            stat, msg = self._sendCmd(address, b'Q')
            status = stat
            self._statusbytes[deviceId - 1] = status
            busy = StatusByte.isBusyStatus(status)

            if busy and not full:  # only fast update of most important parameters
                if devicetype == 1:  # syringe pump
                    stat, msg = self._sendCmd(address, b'?')
                    try:
                        self._syringePos[deviceId -
                                         1] = deviceAnswerToNumber(msg)
                        # there is an transient error after power loss, where
                        # the status byte responds with "no error", but no syringe
                        # position is send. A time delay before sending the next
                        # command seems to solve the issue.
                        # might be the boot time of the pumps
                    except Exception:
                        time.sleep(0.2)
                        stat, msg = self._sendCmd(address, b'?')  # retry
                        self._syringePos[deviceId -
                                         1] = deviceAnswerToNumber(msg)

                elif devicetype == 0:  # MVP
                    pass

            else:  # idle or full update forced, so do full status update
                if devicetype == 1:  # syringe pump
                    stat, msg = self._sendCmd(address, b'?')
                    try:
                        self._syringePos[deviceId -
                                         1] = deviceAnswerToNumber(msg)
                        # there is an transient error after power loss, where
                        # the status byte responds with "no error", but no syringe
                        # position is send. A time delay before sending the next
                        # command seems to solve the issue.
                        # might be the boot time of the pumps
                    except Exception:
                        time.sleep(0.2)
                        stat, msg = self._sendCmd(address, b'?')  # retry
                        self._syringePos[deviceId -
                                         1] = deviceAnswerToNumber(msg)

                    # first extended command, so check if h commands are
                    # enabled
                    stat, msg = self._sendCmd(address, b'?24000')
                    if StatusByte(stat).errorcode != 0:
                        stat, msg = self._sendCmd(
                            address, b'h30001R')  # enable h-command
                        stat, msg = self._sendCmd(address, b'?24000')  # retry
                    self._valvePos[deviceId - 1] = deviceAnswerToNumber(msg)

                    stat, msg = self._sendCmd(address, b'?10000')
                    self._syringeStatus[deviceId -
                                        1] = deviceAnswerToNumber(msg)

                    stat, msg = self._sendCmd(address, b'?20000')
                    self._valveStatus[deviceId - 1] = deviceAnswerToNumber(msg)

                elif devicetype == 0:  # MVP
                    # first extended command, so check if h commands are
                    # enabled
                    stat, msg = self._sendCmd(address, b'?24000')

                    if StatusByte(stat).errorcode != 0:
                        stat, msg = self._sendCmd(
                            address, b'h30001R')  # enable h-command
                        stat, msg = self._sendCmd(address, b'?24000')  # retry
                    self._valvePos[deviceId - 1] = deviceAnswerToNumber(msg)
                    stat, msg = self._sendCmd(address, b'?20000')
                    self._valveStatus[deviceId - 1] = deviceAnswerToNumber(msg)
        except Exception as e:
            if stat is not None:
                e.args += (StatusByte(stat),)
            raise

        return status


def isBroadcast(address):
    assert address < 255
    return not ((address & int('f0', 16)) == int(
        '30', 16) or address == int('40', 16))


deviceIdLookup = {
    int('41', 16): frozenset([1, 2]),
    int('43', 16): frozenset([3, 4]),
    int('45', 16): frozenset([5, 6]),
    int('47', 16): frozenset([7, 8]),
    int('49', 16): frozenset([9, 10]),
    int('4b', 16): frozenset([11, 12]),
    int('4d', 16): frozenset([13, 14]),
    int('4f', 16): frozenset([15, 16]),

    int('51', 16): frozenset([1, 2, 3, 4]),
    int('55', 16): frozenset([5, 6, 7, 8]),
    int('59', 16): frozenset([9, 10, 11, 12]),
    int('5d', 16): frozenset([13, 14, 15, 16]),

    int('5f', 16): frozenset(range(1, 17))
}

addressLookup = {v: k for k, v in deviceIdLookup.items()}


def deviceIdToAddress(deviceId):
    return deviceId + int('30', 16)


def addressToDeviceId(address):
    deviceId = (address & int('0f', 16))
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
    b = np.unpackbits(command.reshape((1, command.size)).T, axis=1).sum(axis=0)
    checksum = np.packbits(b % 2)
    return checksum


def main():
    run((PumpServer,))


# python .\test_server.py test1 -ORBendPoint giop:tcp::50005 -nodb -dlist id31/eh1/test1
# python .\PumpServer.py pump1 -ORBendPoint giop:tcp::50005 -nodb -dlist exp/ec/pump1
# devname: 'localhost:50005/exp/ec/pump1#dbase=no'
if __name__ == '__main__':
    main()
