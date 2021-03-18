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

import multiprocessing as mp
import gzip
import traceback
import time
import logging
import codecs
import sys
import numpy as np
import atexit
from collections import OrderedDict
import yaml
from typing import Type

from . import device
from . import operations
from .device import Valve, Syringe, PSD4_smooth

from .PumpServer import PrioritizedTask, deviceIdToAddress, deviceAnswerToNumber

from .DeviceStatus import StatusByte, ValveStatus, SyringeStatus

import tango

valveType = {
    0: '3-way 120 degree Y valve',
    1: '4-way 90 degree T valve',
    2: '3-way 90 degree distribution valve',
    3: '8-way 45 degree valve',
    4: '4-way 90 degree valve',
    5: 'Reserved',
    6: '6-way 45 degree valve'
}


valveType_inv = dict(map(reversed, valveType.items()))


def valveType_f(n): return valveType[n]


# TODO: add other aliases


class PumpClient(object):
    """Public client interface for the communication
    with Hamilton PSD4 pumps and MVP4 valves on a RS-485 bus.

    This interface is used to configure devices amd to access multiple devices
    on the bus simultaneously.

    The communication will be carried out using a tango device server using the
    :class:`tango.DeviceProxy` ``_device`` of the
    :class:`~psdrive.PumpServer.PumpServer`.
    Direct access to the server is not recommended.

    There are 3 ways to create a PumpClient:

    #. direct instantiation with the Tango device server name ``devname``:

        .. code-block:: python

            import psdrive as psd
            client = psd.PumpClient(devname)

        This will create an unconfigured PumpClient. Also the server will not
        be configured.

    #. Creating a PumpClient with configuration file ``config.yml`` and\
    configuring the server:

        .. code-block:: python

            import psdrive as psd
            client = psd.fromFile("config.yml")

        This will create and configure the PumpClient and configures the device
        server if necessary. If the server is already configured, it will
        connect to the server and fetch the configuration from the server.
        See also :meth:`PumpClient.fromFile`

    #. Connecting to a configured Tango device server ``devname``:

        .. code-block:: python

            import psdrive as psd
            client = psd.connect(devname)

        will connect to the server and fetch the configuration from the server.

    """

    defaultTimeout = 0.5

    def __init__(self, *args, **keyargs):
        """
        :param args: from :class:`tango.DeviceProxy`. At least\
        ``dev_name`` is required.
        """

        self._device = tango.DeviceProxy(*args, **keyargs)
        """The Tango :class:`tango.DeviceProxy`.
        """
        self._device.set_green_mode(tango.GreenMode.Gevent)
        self.__syringes = {}
        self.__valves = {}
        """Holds configured classes from operations.py
        """
        self.operations = {}

    @classmethod
    def fromFile(cls, filename: str):
        """Creates a :class:`~psdrive.PumpInterface.PumpClient` from the\
        configuration file and configures the device server if necessary.

        Will raise errors if the configuration is invalid or if devices have
        not been found on the bus.

        :param filename: Path to the configuration file. See TODO for\
        further details.
        :type filename: str
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        :return: The new client.
        :rtype: :class:`~psdrive.PumpInterface.PumpClient`
        """

        with open(filename, 'r') as f:
            config = yaml.safe_load(f)

        server = config['server']
        if not server['database']:
            name = "%s:%s/%s#dbase=no" % (server['host'], server['port'], server['tangoname'])
        else:
            name = server['tangoname']

        client = cls(name)
        client._device.ping()  # check whether server is alive

        deviceconfig = client.configuration  # fetch remote config

        if client.isPortConnected and deviceconfig is not None:
            # server already configured, so use remote config
            client.fetchConfig()
            return client
        else:
            try:
                client.connectPort(server['serialport'])  # server scans for devices
                client.waitForServerIdle(10)
            except Exception:
                print("Warning: Could not connect to serial port %s:" % server['serialport'])
                traceback.print_exc()
                return client
            client.configure(config)
            return client

    @property
    def configuration(self):
        """Wrapper to store and load a configuration :class:`dict` on the
        device server.

        The dict will be stored on the server as a YAML file. Make sure that
        the dict can be converted to a YAML string.

        .. note::
            Will not update the configuration of the devices.
            Use :meth:`~PumpClient.configure` for this instead.

        :getter: Returns the config :class:`dict` on the device server.
        :setter: Saves the config as a YAML file on the the server.
        :raises ~tango.DevError: if the communication with the device server fails
        """
        return yaml.safe_load(self._device.configuration)

    @configuration.setter
    def configuration(self, config: dict):
        self._device.configuration = yaml.safe_dump(config)

    def fetchConfig(self):
        """Uses the configuration stored on the device server to
        create the device proxies.

        Will not update the device configuration since the devices should 
        already be configured.

        :raises ~tango.DevError: if the communication with the device server fails
        """
        config = self.configuration
        devices = config.get('devices', None)
        if devices is not None:

            for devid in devices:
                if devid not in self.deviceIds():
                    raise Exception("Device %i was not detected on the device bus" %
                          devid)
                devconfig = devices[devid]
                if devconfig['type'] == 'PSD':
                    klass = getattr(device, devconfig['class'])
                    syr = self.getSyringe(devid, klass, devconfig['syringevolume'],
                                          name=devconfig['name'])
                    syr.config = devconfig
                elif devconfig['type'] == 'MVP':
                    klass = getattr(device, devconfig['class'])
                    vlve = self.getValve(devid, klass, name=devconfig['name'])
                    vlve.config = devconfig

        op_section = config.get('operations', None)
        if op_section is not None:

            for op in op_section:
                klass = getattr(operations, op)
                klass_section = op_section[op]
                for name in klass_section:
                    args = klass_section[name]['args']
                    args = [self._parseDeviceStr(s) for s in args]
                    oper = klass(*args, name=name)
                    oper.configure(klass_section[name])
                    self.operations[name] = oper

    def _parseDeviceStr(self, devstr: str):
        if devstr.startswith("Syringe"):
            try:
                return self.getSyringe(int(devstr[len("Syringe"):]))
            except Exception:
                # no device no
                return self.getSyringe(devstr[len("Syringe"):].strip())
        elif devstr.startswith("Valve"):
            try:
                return self.getValve(int(devstr[len("Valve"):]))
            except Exception:
                # no device no
                return self.getValve(devstr[len("Valve"):].strip())
        else:
            raise Exception("Class %s not found in devices or not implemented"
                            % devstr)

    def readConfigfile(self, filename: str):
        """Reconfigures client and server with the configuration stored in the 
        file.

        :param filename: Path to the configuration file. See TODO for\
        further details.
        :type filename: str
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        with open(filename, 'r') as f:
            config = yaml.safe_load(f)
        self.configure(config)

    def configure(self, config: dict = None):
        """Configures the devices on the bus and sets up the device proxies,\
        which you can access with\
        :meth:`~psdrive.PumpInterface.PumpClient.getSyringe` or\
        :meth:`~psdrive.PumpInterface.PumpClient.getValve`.

        If ``config`` is ``None`` (the default), this will fetch the config
        from the device server and reconfigure from this configuration.

        :param config: Configuration of the devices. Should be a dict with a\
        ``devices`` section, where the device config is stored.
        :type config: dict
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        if config is None:
            config = self.configuration

        devices = config.get('devices', None)
        if devices is not None:

            for devid in devices:
                if devid not in self.deviceIds():
                    print("Warning: Device %i was not detected on the device bus" %
                          devid)
                    continue
                devconfig = devices[devid]
                if devconfig['type'] == 'PSD':
                    klass = getattr(device, devconfig['class'])
                    syr = self.getSyringe(devid, klass, devconfig['syringevolume'],
                                          name=devconfig['name'])
                    syr.config = devconfig
                    syr.reconfigure()
                elif devconfig['type'] == 'MVP':
                    klass = getattr(device, devconfig['class'])
                    vlve = self.getValve(devid, klass, name=devconfig['name'])
                    vlve.config = devconfig
                    vlve.reconfigure()

        op_section = config.get('operations', None)
        if op_section is not None:

            for op in op_section:
                klass = getattr(operations, op)
                klass_section = op_section[op]
                for name in klass_section:
                    args = klass_section[name]['args']
                    args = [self._parseDeviceStr(s) for s in args]
                    oper = klass(*args, name=name)
                    oper.configure(klass_section[name])
                    self.operations[name] = oper

        self.configuration = config

    def listPorts(self):
        """Returns the available serial ports on the device server.

        :raises ~tango.DevError: if the communication with the device server fails.
        :return: The list of serial port names.
        :rtype: list of str
        """
        return self._device.listPorts
    
    def scanPortsForId(self, deviceId: int):
        """Scans for a particular device id on all serial ports. 

        :raises ~tango.DevError: if the communication with the device server fails.
        :return: A list of serial port names with an existing device with id\
        ``deviceId``.
        :rtype: list of str
        """
        self._device.set_timeout_millis(30000)
        devlist = self._device.scanPortsForDeviceId(deviceId)
        self._device.set_timeout_millis(3000)
        return devlist
        

    def connectPort(self, port: str):
        """Instructs the device server to connect to the specified serial port.

        The server will subsequently start scanning for devices on the serial
        bus. Device status information is only vaild after the
        :attr:`~psdrive.PumpInterface.PumpClient.state` has changed from
        :attr:`~tango.DevState.RUNNING` to a different state (Should be
        :attr:`~tango.DevState.ON` if the scan was succcessful).

        :param port: The name of the serial port.
        :type port: str
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        """
        self._device.connectPort(port)

    def disconnectPort(self):
        """Instructs the device server to disconnect from the serial port and
        to release the hardware.

        The :attr:`~psdrive.PumpInterface.PumpClient.state` will change to
        :data:`~tango.DevState.OFF`

        :raises ~tango.DevError: if the communication with the device server\
            fails
        """
        self._device.disconnectPort()

    @property
    def isPortConnected(self):
        """Indicates whether the device server is connected to a serial port.
        """
        return self._device.isConnected

    @property
    def state(self):
        """Reports the current device server status.

        Possible states are:

        - :data:`~tango.DevState.ON`: Server thread is running on a serial\
            port, no commands in the command buffer.
        - :data:`~tango.DevState.OFF`: Server thread not running. Serial port\
            disconnected.
        - :data:`~tango.DevState.FAULT`: Unexpected error in the server. See\
            :attr:`~psdrive.PumpInterface.PumpClient.status` for more details.
        - :data:`~tango.DevState.RUNNING`: Commands are beeing transmitted\
            over the serial bus.

        :type: :class:`~tango.DevState`
        :raises ~tango.DevError: if the communication with the device server\
            fails
        """
        return self._device.state()

    @property
    def status(self):
        """A string describing the current device server status.

        :type: str
        :raises ~tango.DevError: if the communication with the device server\
            fails
        """
        return self._device.status()

    def scanDevices(self):
        """Instructs the device server to scan for devices on the serial bus.

        Waits until the scan has completed (this will take a few seconds).

        :return: dict with available device ids and their status.
        :rtype: OrderedDict of the form { dev_id: StatusByte }
        :raises ~tango.DevError: if the communication with the device server\
            fails
        """
        self._device.scanDevices()
        self.waitForServerIdle(10)
        return self.statusAllIds()

    def stop(self, deviceId: int = None, address: int = None):
        """Sends a command to devices to stop any movement.

        The default will send this command to all devices.

        You can provide either deviceId or an hardware address.
        The address can be used to send broadcast commands to multiple devices.

        Usage:

        >>> client.stop() #stop all devices.

        >>> client.stop(deviceId=1) # will stop any movement of device ``1``.

        >>> client.stop(address=int('41',16)) # will stop any movement\
of devices ``1`` and ``2``.

        :raises ~tango.DevError: if the communication with the device server\
            fails
        """
        if deviceId is None and address is None:
            self._device.terminateMovement(0)
        elif address is not None:
            self._device.terminateMovement(address)
        elif deviceId is not None:
            self._device.terminateMovement(deviceIdToAddress(deviceId))

    def pauseBufferedCommands(self, deviceId: int = None, address: int = None):
        """Sends a command to devices to stop after execution of the last\
        command.

        The default will send this command to all devices.

        You can provide either deviceId or an hardware address.
        The address can be used to send broadcast commands to multiple devices.

        Has the same usage as :meth:`~psdrive.PumpInterface.PumpClient.stop`.

        :raises ~tango.DevError: if the communication with the device server\
            fails
        """
        if deviceId is None and address is None:
            self._device.stopCommandBuffer(0)
        elif address is not None:
            self._device.stopCommandBuffer(address)
        elif deviceId is not None:
            self._device.stopCommandBuffer(deviceIdToAddress(deviceId))

    def serialCommandToId(self, deviceId: int, command: bytes, move: bool, **keyargs):
        """Converts a deviceId to the corresponding address and calls\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand`\
        with this address.

        See: :meth:`~psdrive.PumpInterface.PumpClient.serialCommand`
        for further details.

        :return: The device answer as future-like or bytes
        :rtype: :class:`bytes` or future-like, which exposes the methods of\
        :class:`concurrent.futures.Future`
        """
        address = deviceIdToAddress(deviceId)
        return self.serialCommand(address, command, move, **keyargs)

    def serialCommand(self, address: int, command: bytes, move: bool, **keyargs):
        """Sends a command over the serial bus.

        The command will first be enqueued in the taskqueue of the
        deviceserver. You can assign the commmand a priority.
        Lower prioritiy number will be send first.

        Allows synchronous or asynchronous communication via gevent module
        Set wait=False to enable asynchronous communication.

        It is possible to concatenate multiple commands using the ``send`` and
        ``enqueue`` keyargs, which are implememted in most functions. Here an
        example how to send the device configuration ``config`` together with
        the initialization command (Similarly to the implementation in
        :meth:`~psdrive.device.Syringe.initSyringe`):

        .. code-block:: python

            cmd = client.initializeSyringe(
                deviceId, valveId, speed, backoff, enqueue=True, send=False)
            cmd += client.setSettings(config, enqueue=False, send=False)
            client.serialCommandToId(deviceId, cmd.encode('latin-1'), True)


        :param int address: hardware address to which the command will be send
        :param bytes command: command string to send.
        :param bool move: please indicate whether this command will intiate\
        a movement
        :param dict optional keyargs:\
            - wait: bool, default: True
                indicates whether to use synchronous or asynchronous
                communication, i.e. waits for result or returns future-like
                :class:`concurrent.futures.Future`.

            - timeout: float : gevent Timeout for asynchronous calls
                (wait=False). defaults to :attr:`~PumpClient.defaultTimeout`.

            - converter: :data:`~typing.Callable`, optional
                to convert the device message prior returning the result

            - priority: int8, optional
                Assigns a priority to the command. The default is 255.

            - send: bool, defaults to True,
                Indicate whether to send the command. If set to False,
                will only return the command as str. This can be used to
                concatenate multiple commands in conjunction with ``enqueue``.
                Also used for debugging.

            - enqueue: bool, defualts to False,
                Indicate whether add "R" (run) command to the command str.
                Has no effect in ``serialCommand``.

        :return: The device answer as future-like or bytes, If ``converter```\
        is given in keyargs, will return ``converter(result)``.
        :rtype: :class:`bytes` or future-like, which exposes the methods of\
        :class:`concurrent.futures.Future`
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        wait = keyargs.pop('wait', True)
        timeout = keyargs.pop('timeout', PumpClient.defaultTimeout)
        converter = keyargs.pop('converter', lambda x: x)
        priority = keyargs.pop('priority', 255)
        if not keyargs.pop('send', True):
            return command.decode('latin-1')

        cmd = np.concatenate(
            [[priority], [address], [int(move)], np.frombuffer(command, dtype=np.uint8)])
        result_t = self._device.sendCommand(
            cmd.astype(np.uint8), wait=wait, timeout=timeout)

        def parseResult(res):
            statusbyte = res[0]
            if res.size > 1:
                msg = res[1:]
                msg = msg.tobytes()
            else:
                msg = b''

            status = StatusByte(statusbyte, address=address, rawcommand=cmd)
            status.raiseIfError()
            return converter(msg)

        if not wait:
            # evil :P
            class ParsedAsyncResult(object):
                def __init__(self, asyncresult):
                    for attr in dir(asyncresult):
                        if not attr.startswith(
                                '__') and attr != 'get' and attr != 'result':
                            setattr(self, attr, getattr(asyncresult, attr))
                    self._get = asyncresult.get
                    self._result = asyncresult.result

                def get(self, *args):
                    result = self._get(*args)
                    return parseResult(result)

                def result(self, *args):
                    result = self._result(*args)
                    return parseResult(result)

            return ParsedAsyncResult(result_t)
        else:
            return parseResult(result_t)

# -----------FAST STATUS REQUESTS (Are polled in the device server).-----------
# functions do not require serial communication, they return almost
# instantaneously

    def deviceIds(self):
        """Returns a list with the detected devices on the serial bus.

        Use :meth:`~psdrive.PumpInterface.PumpClient.scanDevices` to scan for
        devices on the bus, if some devices were not recognized.

        :return: List with the device ids.
        :rtype: ndarray of int.
        :raises ~tango.DevError: if the communication with the device server fails
        """
        devtype = self._device.deviceType[:]
        return np.nonzero(devtype >= 0)[0] + 1

    def syringePumpIds(self):
        """Returns a list with the detected syringe pump devices on the\
        serial bus.

        Use :meth:`~psdrive.PumpInterface.PumpClient.scanDevices` to scan for
        devices on the bus, if some devices were not recognized.

        :return: List with the syringe pump device ids.
        :rtype: ndarray of int.
        :raises ~tango.DevError: if the communication with the device server fails
        """
        devtype = self._device.deviceType[:]
        return np.where(devtype == 1)[0] + 1

    def valvePositionerIds(self):
        """Returns a list with the detected valve positioner devices on the\
        serial bus.

        Use :meth:`~psdrive.PumpInterface.PumpClient.scanDevices` to scan for
        devices on the bus, if some devices were not recognized.

        :return: List with the valve positioner device ids.
        :rtype: ndarray of int.
        :raises ~tango.DevError: if the communication with the device server fails
        """
        devtype = self._device.deviceType[:]
        return np.where(devtype == 0)[0] + 1

    def getStatusByte(self, deviceId: int = -1):
        """Returns the last recieved :class:`~psdrive.DeviceStatus.StatusByte`.

        Consider using :meth:`~psdrive.PumpInterface.PumpClient.deviceStatus`
        for a full status update instead.

        :param int deviceId: indicate the device id, for which you want to get\
        the StatusByte. If set to -1, will return a dict with all StatusBytes,\
        defaults to -1.

        :return: The StatusByte or dict of the form {id : StatusByte}
        :rtype: :class:`~psdrive.DeviceStatus.StatusByte` or dict.
        :raises ~tango.DevError: if the communication with the device server fails
        """
        if deviceId == -1:
            status = np.array(self._device.statusbytes[:])
            ids = self.deviceIds()
            availablestatus = status[ids - 1]
            statusdict = OrderedDict()
            for sb, devid in zip(availablestatus, ids):
                statusdict[devid] = StatusByte(sb, short=True)
            return statusdict
        else:
            sb = self._device.statusbytes[deviceId - 1]
            return StatusByte(sb, short=True)

    def valveStatus(self, deviceId: int = -1):
        """Returns the last recieved :class:`~psdrive.DeviceStatus.ValveStatus`.

        Consider using :meth:`~psdrive.PumpInterface.PumpClient.deviceStatus`
        for a full status update instead.

        :param int deviceId: indicate the device id, for which you want to get\
        the ValveStatus. If set to -1, will return a dict with all ValveStatus,\
        defaults to -1.

        :return: The ValveStatus or dict of the form {id : ValveStatus}
        :rtype: :class:`~psdrive.DeviceStatus.ValveStatus` or dict.
        :raises ~tango.DevError: if the communication with the device server fails
        """
        if deviceId == -1:
            valvestat = np.array(self._device.valveStatus[:])
            ids = self.deviceIds()
            availablestatus = valvestat[ids - 1]
            statusdict = OrderedDict()
            for code, devid in zip(availablestatus, ids):
                statusdict[devid] = ValveStatus(code)
            return statusdict
        else:
            code = self._device.valveStatus[deviceId - 1]
            return ValveStatus(code)

    def syringeStatus(self, deviceId: int = -1):
        """Returns the last recieved :class:`~psdrive.DeviceStatus.SyringeStatus`.

        Consider using :meth:`~psdrive.PumpInterface.PumpClient.deviceStatus`
        for a full status update instead.

        :param int deviceId: indicate the device id, for which you want to get\
        the SyringeStatus. If set to -1, will return a dict with all SyringeStatus,\
        defaults to -1.

        :return: The SyringeStatus or dict of the form {id : SyringeStatus}
        :rtype: :class:`~psdrive.DeviceStatus.SyringeStatus` or dict.
        :raises ~tango.DevError: if the communication with the device server fails
        """
        if deviceId == -1:
            syringestat = np.array(self._device.syringeStatus[:])
            ids = self.syringePumpIds()
            availablestatus = syringestat[ids - 1]
            statusdict = OrderedDict()
            for code, devid in zip(availablestatus, ids):
                statusdict[devid] = SyringeStatus(code)
            return statusdict
        else:
            code = self._device.syringeStatus[deviceId - 1]
            return SyringeStatus(code)

    def deviceStatus(self, deviceId: int = -1):
        """Returns the most recent full device status stored on the server.

        The device server updates the device status continuously in the
        background, if no commands are send to the devices. The update rate
        depends on the number and type of devices on the serial bus.
        (Typically 0.1 s per device).
        If a device responds with the ``busy`` status, the server will only
        update the status of this device. This lowers the update latency to
        about 0.06 s per busy device.

        A call to *deviceStatus* is optimized for speed and requires
        only a single network call, even if the device status of multiple
        devices was requested.

        The device status is a :class:`dict` with the keys:
          - 'type': (:class:`str`) either 'MVP', 'PSD'. Returns 'unknown'\
          if the device was not recognized.
          - 'statusbyte': (:exc:`~psdrive.PumpStatus.StatusByte`)\
          Containing the current device status.
          - 'valve': (:exc:`~psdrive.PumpStatus.ValveStatus`)\
          The current Valve status
          - 'valvePos': (:class:`int`) current numerical\
          position of the valve
          - 'syringe': (:exc:`~psdrive.PumpStatus.SyringeStatus`)\
          Only if this is a :class:`~psdrive.device.Syringe`.
          - 'syringePos': (:class:`int`) syringe position in motor steps.\
          Only if this is a :class:`~psdrive.device.Syringe`.

        :param int deviceId: indicate the device id, for which you want to get\
        the status. If set to -1, will return a dict with the status of all\
        devices, defaults to -1.
        :return: The statusdict or dict of the form {dev_id : statusdict}
        :rtype: dict
        :raises ~tango.DevError: if the communication with the device server fails
        """
        statusbytes, valveStatus, syringeStatus,\
            valvePos, syringePos, deviceType = self._device.read_attributes(
      ["statusbytes", "valveStatus", "syringeStatus",
           "valvePos", "syringePos", "deviceType"])

        statusbytes = statusbytes.value
        valveStatus = valveStatus.value
        syringeStatus = syringeStatus.value
        valvePos = valvePos.value
        syringePos = syringePos.value
        deviceType = deviceType.value

        deviceids = np.nonzero(deviceType >= 0)[0] + 1

        def createDevStatus(devid):
            devstatus = {}
            devstatus['statusbyte'] = StatusByte(statusbytes[devid - 1])
            devstatus['busy'] = devstatus['statusbyte'].busy

            if deviceType[devid - 1] == 1:
                devstatus['type'] = 'PSD'
                devstatus['valve'] = ValveStatus(valveStatus[devid - 1])
                devstatus['valvePos'] = valvePos[devid - 1]
                devstatus['syringe'] = SyringeStatus(syringeStatus[devid - 1])
                devstatus['syringePos'] = syringePos[devid - 1]
            elif deviceType[devid - 1] == 0:
                devstatus['type'] = 'MVP'
                devstatus['valve'] = ValveStatus(valveStatus[devid - 1])
                devstatus['valvePos'] = valvePos[devid - 1]
            else:
                devstatus['type'] = 'unknown'
            return devstatus

        if deviceId < 0:
            statusdicts = OrderedDict()
            for devid in deviceids:
                statusdicts[devid] = createDevStatus(devid)
            return statusdicts
        else:
            return createDevStatus(deviceId)

    def getValvePosition(self, deviceId: int):
        """The current numerical valve position.

        :param int deviceId: device id
        :return: numerical valve position.
        :rtype: int
        """
        return self._device.valvePos[deviceId - 1]

    def getSyringePosition(self, deviceId: int):
        """The current syringe position in motor steps.

        :param int deviceId: device id
        :return: syringe position in motor steps.
        :rtype: int
        """
        return self._device.syringePos[deviceId - 1]

    def statusAllIds(self):
        """mostly for debugging!!! Use deviceStatus instead!

        also returns status of potentially not connected devices,
        use deviceStatus(-1) to get the status of the connected devices

        :return: dict of form: {deviceID : DeviceError}
        :rtype: dict
        :meta private:
        """
        status = np.array(self._device.statusbytes[:])
        ids = np.arange(status.size) + 1
        statusdict = OrderedDict()
        for sb, devid in zip(status, ids):
            statusdict[devid] = StatusByte(sb, short=True)
        return statusdict

    def getSyringe(self, deviceId: int = -1, syringetype: Type[Syringe] = None,
                   maxvolume: float = None, **keyargs):
        """Returns :class:`~psdrive.device.Syringe` devices controlled by this\
        PumpClient.

        You can provide a device id to get a specific Syringe. The default will\
        return all configured Syringes as dict with the device ids as keys.

        .. note::

            Only needs ``syringetype`` and ``maxvolume`` if the Syringe was not
            yet created.

        Will create a new Syringe class and add it to the list of controlled
        devices if in addtition of ``deviceId`` also a
        :class:`~psdrive.device.Syringe` class ``syringetype`` and the maxium
        capacity of the attached syringe ``maxvolume`` are provided.

        Example for creating a new Syringe:

        .. code-block:: python

            import psdrive as psd
            from psdrive.device import PSD4_smooth
            syringe_proxy = client.getSyringe(deviceId, PSD4_smooth, capacity)
            syringe_proxy.readConfig() # get current configuration directly \
from the device

        :param int deviceId: hardware device id of the syringe. If set to -1,\
        will return all controlled Syringes, defaults to -1.

        :param syringetype: Syringe class to create.
        :type syringetype: Type[:class:`~psdrive.device.Syringe`]

        :param float maxvolume: Maximum capacity of the attached syringe.

        :param keyargs: Additional keyargs passed to the constructor of the\
        Syringe.
        """
        if deviceId in self.__syringes:
            return self.__syringes[deviceId]
        elif isinstance(deviceId, str):
            for s in self.__syringes:
                if self.__syringes[s].name == deviceId:
                    return self.__syringes[s]
            else:
                raise ValueError(
                "If the syringe was not configured yet, you must provide the"
                "syringe class and the volume of the attached syringe")
        elif deviceId == -1:
            return self.__syringes
        elif syringetype is not None and maxvolume is not None:
            if not issubclass(syringetype, Syringe):
                raise ValueError("Has to be subclass of Syringe!")
            self.__syringes[deviceId] = syringetype(
                self, deviceId, maxvolume, **keyargs)
            return self.__syringes[deviceId]
        else:
            raise ValueError(
                "If the syringe was not configured yet, you must provide the"
                "syringe class and the volume of the attached syringe")

    def getValve(self, deviceId: int = -1, valvetype: Type[Valve] = None,
                 **keyargs):
        """Returns :class:`~psdrive.device.Valve` devices controlled by this\
        PumpClient.

        .. note ::

            Does not return devices which are also Syringe types!

        You can provide a device id to get a specific Valve. The default will\
        return all configured Valves as dict with the device ids as keys.

        .. note::

            Only needs ``valvetype`` if the Valve was not yet created.

        Will create a new Valve class and add it to the list of controlled
        devices if in addtition of ``deviceId`` also a
        :class:`~psdrive.device.Valve` class ``valvetype``.

        Example for creating a new Valve:

        .. code-block:: python

            import psdrive as psd
            from psdrive.device import Valve
            valve_proxy = client.getSyringe(deviceId, Valve)
            valve_proxy.readConfig() # get current configuration directly \
from the device

        :param int deviceId: hardware device id of the valve. If set to -1,\
        will return all controlled Valve, defaults to -1.

        :param valvetype: Valve\
        class to create.
        :type valvetype: Type[:class:`~psdrive.device.Valve`]

        :param keyargs: Additional keyargs passed to the constructor of the\
        Valve.
        """
        if deviceId in self.__valves:
            return self.__valves[deviceId]
        elif deviceId == -1:
            return self.__valves
        elif isinstance(deviceId, str):
            for s in self.__valves:
                if self.__valves[s].name == deviceId:
                    return self.__valves[s]
            else:
                raise ValueError(
                "If the valve was not configured yet, you must provide the"
                "valve class")
        elif valvetype is not None:
            if not issubclass(valvetype, Valve):
                raise ValueError("Has to be subclass of Valve!")
            self.__valves[deviceId] = valvetype(self, deviceId, **keyargs)
            return self.__valves[deviceId]
        else:
            raise ValueError(
                "If the valve was not configured yet,"
                "you must provide the valve class")

# ---------------------------------END of FAST REQUESTS-----------------------

    def waitForDeviceIdle(self, deviceId: int, timeout: float = None,
                          pollingperiod: float = 0.1):
        """Blocks until device is not busy.

        Polls deviceStatus(id).busy over the network every ``pollingperiod``
        seconds!

        :param int deviceId: The device hardware id.
        :param float timeout: Timeout of polling, Runs infinite if ``None``,\
        defaults to ``None``
        :param float pollingperiod: Pollingperiod in seconds. Defaults to 0.1 s
        :raises TimeoutError: If specified timeout has been reached.
        """
        time_start = time.time()
        if timeout is None:
            timeout = np.inf
        while(time.time() - time_start < timeout):
            if not self.getStatusByte(deviceId).busy:
                break
            time.sleep(pollingperiod)
        else:
            raise TimeoutError("wait for device idle: timeout reached")
        return True

    def waitForServerIdle(self, timeout: float = None,
                          pollingperiod: float = 0.1):
        """Blocks until server has finished sending commands to the devices.

        Polls :attr:`~psdrive.PumpInterface.PumpClient.state` over the network
        every ``pollingperiod`` seconds until the state is not ``RUNNING``.

        :param float timeout: Timeout of polling, Runs infinite if ``None``,\
        defaults to ``None``
        :param float pollingperiod: Pollingperiod in seconds. Defaults to 0.1 s
        :raises TimeoutError: If specified timeout has been reached.
        """
        time_start = time.time()
        if timeout is None:
            timeout = np.inf
        while(time.time() - time_start < timeout):
            if not self.state == tango.DevState.RUNNING:
                break
            time.sleep(pollingperiod)
        else:
            raise TimeoutError("wait for server idle: timeout reached")
        return True

    def initializeValve(self, deviceId: int = None, **keyargs):
        """Initializes a valve.

        If deviceId is set to None, will initialize the valves of all attached
        devices.
        """
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd = "h20000"
        else:
            cmd = "h20000R"
        if keyargs.pop('send', True):
            if deviceId is None:
                result = self.serialCommand(
                    int('5f', 16), cmd.encode('ascii'), True, **keyargs)
            else:
                result = self.serialCommandToId(
                    deviceId, cmd.encode('ascii'), True, **keyargs)
            return result
        else:
            return cmd

    def initializeSyringe(self, deviceId: int, output: int, speed: int,
                          backoff: int, **keyargs):
        """Initializes a syringe.

        .. note::
            Initializing a syringe overrides the configuration with
            the hardware defaults.

        :param int deviceId: Hardware device id of the syringe.

        :param int output: valve position where to initialize the syringe.

        :param int speed: Init speed code. Must be between 10 and 40, or\
        0 or 1. See the device manual for the meaning of the speed code.

        :param int backoff: Syringe will move `backoff` steps back after init.
        """
        if not 1 <= output <= 8:
            raise ValueError(
                "Possible valve positions are 1 <= output <= 8, is : %s" %
                output)
        if not 1 <= speed <= 40:
            raise ValueError(
                "Valid speed codes are 1(fast) <= speed <= 40(slow), is : %s" %
                speed)
        if not 0 <= backoff <= 12800:
            raise ValueError(
                "back-off steps k has to be in the range 0 <= k <= 12800, is : %s" %
                backoff)
        self.valveStatus(deviceId).raiseIfError()
        output += 26000
        speed += 10000
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd = "k%sh%sh%s" % (int(backoff), int(output), int(speed))
        else:
            cmd = "k%sh%sh%sR" % (int(backoff), int(output), int(speed))
        if keyargs.pop('send', True):
            if deviceId is None:
                result = self.serialCommand(
                    int('5f', 16), cmd.encode('ascii'), True, **keyargs)
            else:
                result = self.serialCommandToId(
                    deviceId, cmd.encode('ascii'), True, **keyargs)
            return result
        else:
            return cmd

    def initSyringeFromEncoder(self, deviceId: int, **keyargs):
        """Initializes a syringe from encoder position.

        Deprecated: needs rework.

        This is intended to be used only if normal initialization is not
        possible.
        For example, if a power loss occurs during an experiment.

        .. note::

            Doesn't seem to work with PSD/4 Smooth Flow devices. Hardware bug?

        :param int deviceId: The device hardware id.
        :returns: optional device answer string. (Should be b'')
        :rtype: bytes
        """
        print("Warning: Initialization from encoder.\n"
              "use normal initializeSyringe as soon as possible!")
        cmd = "zR"
        if deviceId is None:
            result = self.serialCommand(
                int('5f', 16), cmd.encode('ascii'), False, **keyargs)
        else:
            result = self.serialCommandToId(
                deviceId, cmd.encode('ascii'), False, **keyargs)
        return result

    def getSettings(self, deviceId: int, **keyargs):
        """Retrieves the currently active settings of the device.

        The settings are returned as dict with the setting name as key.

        Mirrors :meth:`setSettings`.

        .. note::

            This command uses multiple individual requests from the hardware,
            which results in a long execution time of more than 1 second.

        The settings can also be requested individually.

        :return: The current device settings.
        :rtype: dict
        """

        settings_futures = OrderedDict()
        settings = dict()
        settings_futures['firmware'] = self.getFirmware(
            deviceId, wait=False, timeout=0.5)
        settings_futures['valve type'] = self.getValveType(
            deviceId, wait=False, timeout=0.5)

        if self._device.syringePos[deviceId - 1] < 0:  # valve positioner
            settings['type'] = 'MVP'
        else:
            settings_futures['start velocity'] = self.getStartVelocity(
                deviceId, wait=False, timeout=0.5)
            settings_futures['maximum velocity'] = self.getMaximumVelocity(
                deviceId, wait=False, timeout=0.5)
            settings_futures['stop velocity'] = self.getStopVelocity(
                deviceId, wait=False, timeout=0.5)
            settings_futures['return steps'] = self.getReturnSteps(
                deviceId, wait=False, timeout=0.5)
            settings['type'] = 'PSD'

        for key in settings_futures:
            settings[key] = settings_futures[key].result()
        settings['id'] = deviceId
        return settings

    def getValveType(self, deviceId, **keyargs):
        keyargs['converter'] = lambda x: valveType[int(x)]
        result = self.serialCommandToId(deviceId, b'?21000', False, **keyargs)
        return result

    def getFirmware(self, deviceId, **keyargs):
        keyargs['converter'] = codecs.decode
        result = self.serialCommandToId(deviceId, b'&', False, **keyargs)
        return result

    def getStartVelocity(self, deviceId, **keyargs):
        keyargs['converter'] = int
        result = self.serialCommandToId(deviceId, b'?1', False, **keyargs)
        return result

    def getMaximumVelocity(self, deviceId, **keyargs):
        keyargs['converter'] = int
        result = self.serialCommandToId(deviceId, b'?2', False, **keyargs)
        return result

    def getStopVelocity(self, deviceId, **keyargs):
        keyargs['converter'] = int
        result = self.serialCommandToId(deviceId, b'?3', False, **keyargs)
        return result

    def getReturnSteps(self, deviceId, **keyargs):
        keyargs['converter'] = int
        result = self.serialCommandToId(deviceId, b'?12', False, **keyargs)
        return result

    def setSettings(self, deviceId: int, settingsdict: dict, **keyargs):
        """Send settings to a device. Uses a single command str.

        Mirrors :meth:`getSettings`.

        :param int deviceId: The device hardware id.
        :param dict settingsdict: The device configuration.
        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.
        :return: Dict with the Result of each command transmission.
        :rtype: dict
        """
        send = keyargs.pop('send', True)
        enqueue = keyargs.pop('enqueue', False)

        keyargs['send'] = False
        keyargs['enqueue'] = True
        cmd = ""
        if 'valve type' in settingsdict:
            cmd += self.setValveType(
                deviceId, settingsdict['valve type'], **keyargs)
        if 'start velocity' in settingsdict:
            cmd += self.setStartVelocity(
                deviceId, settingsdict['start velocity'], **keyargs)
        if 'maximum velocity' in settingsdict:
            cmd += self.setMaximumVelocity(
                deviceId, settingsdict['maximum velocity'], **keyargs)
        if 'stop velocity' in settingsdict:
            cmd += self.setStopVelocity(
                deviceId, settingsdict['stop velocity'], **keyargs)
        if 'return steps' in settingsdict:
            cmd += self.setReturnSteps(
                deviceId, settingsdict['return steps'], **keyargs)
        if 'acceleration' in settingsdict:
            cmd += self.setAcceleration(
                deviceId, settingsdict['acceleration'], **keyargs)

        if not enqueue:
            cmd += "R"

        if send:
            result = self.serialCommandToId(
                deviceId, cmd.encode('ascii'), False, **keyargs)

            return result
        else:
            return cmd

    def setValveType(self, deviceId, vtype, **keyargs):
        if isinstance(vtype, str):
            vtype = valveType_inv[vtype]
        vtype += 21000
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd = "h%s" % int(vtype)
        else:
            cmd = "h%sR" % int(vtype)
        if keyargs.pop('send', True):
            result = self.serialCommandToId(
                deviceId, cmd.encode('ascii'), False, **keyargs)
            return result
        else:
            return cmd

    def setStartVelocity(self, deviceId, velocity, **keyargs):
        if not 50 <= velocity <= 800:
            raise ValueError(
                "Start velocity v has to be in the range 50 <= v <= 800 motor steps/s, is : %s" %
                velocity)
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd = "v%s" % int(velocity)
        else:
            cmd = "v%sR" % int(velocity)
        if keyargs.pop('send', True):
            result = self.serialCommandToId(
                deviceId, cmd.encode('ascii'), False, **keyargs)
            return result
        else:
            return cmd

    def setMaximumVelocity(self, deviceId, velocity, **keyargs):
        if not 2 <= velocity <= 3400:
            raise ValueError(
                "Maximum velocity V has to be in the range 2 <= V <= 3400 motor steps/s, is : %s" %
                velocity)
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd = "V%s" % int(velocity)
        else:
            cmd = "V%sR" % int(velocity)
        if keyargs.pop('send', True):
            result = self.serialCommandToId(
                deviceId, cmd.encode('ascii'), False, **keyargs)
            return result
        else:
            return cmd

    def setStopVelocity(self, deviceId, velocity, **keyargs):
        if not 50 <= velocity <= 1700:
            raise ValueError(
                "Stop velocity c has to be in the range 50 <= c <= 1700 motor steps/s, is : %s" %
                velocity)
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd = "c%s" % int(velocity)
        else:
            cmd = "c%sR" % int(velocity)
        if keyargs.pop('send', True):
            result = self.serialCommandToId(
                deviceId, cmd.encode('ascii'), False, **keyargs)
            return result
        else:
            return cmd

    def setReturnSteps(self, deviceId, steps, **keyargs):
        if not 0 <= steps <= 6400:
            raise ValueError(
                "Return steps K has to be in the range 0 <= K <= 6400 motor steps, is : %s" %
                steps)
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd = "K%s" % int(steps)
        else:
            cmd = "K%sR" % int(steps)
        if keyargs.pop('send', True):
            result = self.serialCommandToId(
                deviceId, cmd.encode('ascii'), False, **keyargs)
            return result
        else:
            return cmd

    def setAcceleration(self, deviceId: int, acceleration: int, **keyargs):
        """Sets the acceleration of the syringe.

        The actual acceleration is mapped to an acceleration code,
        which is between 1 and 20,
        where 1 corresponds to 2500 steps/s^2 and 20 to 50000 steps/s^2

        The code is evaluated using: acceleration // 2500.

        :param int deviceId: hardware device id. Must be a PSD device id.
        :param int acceleration: syringe acceleration in steps/s^2.\
        Must be between 2500 and 50000
        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.
        :raises ValueError: if not\
        2500 <= acceleration <= 50000 motor steps/s^2
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        :returns: device answer string. (Should be b'')
        :rtype: bytes
        """
        if not 2500 <= acceleration <= 50000:
            raise ValueError(
                "Acceleration L has to be in the range 2500 <= L <= 50000 motor steps/s^2, is : %s" %
                acceleration)
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd = "L%s" % int(acceleration // 2500)
        else:
            cmd = "L%sR" % int(acceleration // 2500)
        if keyargs.pop('send', True):
            result = self.serialCommandToId(
                deviceId, cmd.encode('ascii'), False, **keyargs)
            return result
        else:
            return cmd

    def moveValve(self, deviceId: int, position: int, **keyargs):
        """Moves the valve to a new numerical position.

        Valid positions are 1 <= position <= 8.

        :param int deviceId: hardware device id.

        :param int position: New numerical valve position.
        """
        if not 1 <= position <= 8:
            raise ValueError(
                "Possible valve positions are 1 <= position <= 8, is : %s" %
                position)
        position += 26000
        self.valveStatus(deviceId).raiseIfError()
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd = "h%s" % int(position)
        else:
            cmd = "h%sR" % int(position)
        if keyargs.pop('send', True):
            result = self.serialCommandToId(
                deviceId, cmd.encode('ascii'), not enqueue, **keyargs)
            return result
        else:
            return cmd

    def moveSyringe(self, deviceId: int, stroke: int, velocity: int = -1,
                    valvePos: int = -1, **keyargs):
        """Moves the plunger of the syringe to an absolute position in\
        microsteps.

        Prior to the plunger movement, a movement of the valve of the
        PSD device into a new position can be performed by setting valvePos
        to the desired position.

        :param int deviceId: hardware device id. Must be a PSD device id.

        :param int stroke: Desired position of the syringe plunger in\
        microsteps. Must be in between 0 and 192000.

        :param int velocity: optional,\
        Maximum velocity of the plunger move in motorsteps/s.\
        Will retain the last set value if velocity is set to -1.\
        Has to be in the range 2 <= V <= 3400 motor steps/s.\
        The default is -1.

        :param int valvePos: optional,\
        Will optionally move the valve to this position prior to the\
        plunger move. The valve will not move if set to -1.\
        The default is -1.

        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.

        :raises ValueError: if not\
        2500 <= acceleration <= 50000 motor steps/s^2
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.

        :returns: device answer string. (Should be b'')
        :rtype: bytes
        """
        if not 0 <= stroke <= 192000:
            raise ValueError(
                "Possible syringe positions are 0 <= stroke <= 192000, is : %s" %
                stroke)
        cmd = ""
        if velocity >= 0:
            if not 2 <= velocity <= 3400:
                raise ValueError(
                    "Maximum velocity V has to be in the range 2 <= V <= 3400 motor steps/s, is : %s" %
                    velocity)
            cmd += "V%s" % int(velocity)
        if valvePos >= 0:
            self.valveStatus(deviceId).raiseIfError()
            if not 1 <= valvePos <= 8:
                raise ValueError(
                    "Possible valve positions are 1 <= valvePos <= 8, is : %s" %
                    valvePos)
            valvePos += 26000
            cmd += "h%s" % int(valvePos)
        self.syringeStatus(deviceId).raiseIfError()
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd += "A%s" % int(stroke)
        else:
            cmd += "A%sR" % int(stroke)
        if keyargs.pop('send', True):
            result = self.serialCommandToId(
                deviceId, cmd.encode('ascii'), not enqueue, **keyargs)
            return result
        else:
            return cmd

    def dispense(self, deviceId: int, microsteps: int,
                 velocity: int = -1, valvePos: int = -1, **keyargs):
        """Relative dispense: Moves the plunger of the syringe microsteps up.

        Prior to the plunger movement, a movement of the valve of the
        PSD device into a new position can be performed by setting valvePos
        to the desired position.

        :param int deviceId: hardware device id. Must be a PSD device id.

        :param int microsteps: Desired dispense microsteps.\
            The maximum dispense microsteps are stored in :attr:`syringePos`,\
            i.e. the stroke cannot be below 0.\
            Must be in between 0 and 192000.\

        :param int velocity: optional,\
        Maximum velocity of the plunger move in motorsteps/s.\
        Will retain the last set value if velocity is set to -1.\
        Has to be in the range 2 <= V <= 3400 motor steps/s.\
        The default is -1.

        :param int valvePos: optional,\
        Will optionally move the valve to this position prior to the\
        plunger move. The valve will not move if set to -1.\
        The default is -1.

        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.

        :raises ValueError: if stroke would go below 0.

        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.

        :returns: device answer string. (Should be b'')
        :rtype: bytes
        """
        if not 0 <= microsteps <= 192000 and not keyargs.get('enqueue', False):
            raise ValueError(
                "Possible syringe positions are 0 <= stroke <= 192000, is : %s" %
                microsteps)
        cmd = ""
        pos = self.getSyringePosition(deviceId)
        if pos < microsteps and not keyargs.get('enqueue', False):
            raise ValueError(
                "Desired dispense steps %s too large. current syringe position: %s" %
                (microsteps, pos))
        if velocity >= 0:
            if not 2 <= velocity <= 3400:
                raise ValueError(
                    "Maximum velocity V has to be in the range 2 <= V <= 3400 motor steps/s, is : %s" %
                    velocity)
            cmd += "V%s" % int(velocity)
        if valvePos >= 0:
            if not 1 <= valvePos <= 8:
                self.valveStatus(deviceId).raiseIfError()
                raise ValueError(
                    "Possible valve positions are 1 <= valvePos <= 8, is : %s" %
                    valvePos)
            valvePos += 26000
            cmd += "h%s" % int(valvePos)
        self.syringeStatus(deviceId).raiseIfError()
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd += "D%s" % int(microsteps)
        else:
            cmd += "D%sR" % int(microsteps)
        if keyargs.pop('send', True):
            result = self.serialCommandToId(
                deviceId, cmd.encode('ascii'), not enqueue, **keyargs)
            return result
        else:
            return cmd

    def pickup(self, deviceId: int, microsteps: int,
               velocity: int = -1, valvePos: int = -1, **keyargs):
        """Relative Pickup: Moves the plunger of the syringe microsteps down.

        Prior to the plunger movement, a movement of the valve of the
        PSD device into a new position can be performed by setting valvePos
        to the desired position.

        :param int deviceId: hardware device id. Must be a PSD device id.

        :param int microsteps: Desired dispense microsteps.\
            The maximum dispense microsteps are stored in :attr:`syringePos`,\
            i.e. the stroke cannot be below 0.\
            Must be in between 0 and 192000.\

        :param int velocity: optional,\
        Maximum velocity of the plunger move in motorsteps/s.\
        Will retain the last set value if velocity is set to -1.\
        Has to be in the range 2 <= V <= 3400 motor steps/s.\
        The default is -1.

        :param int valvePos: optional,\
        Will optionally move the valve to this position prior to the\
        plunger move. The valve will not move if set to -1.\
        The default is -1.

        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.

        :raises ValueError: if stroke would go below 0.

        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.

        :returns: device answer string. (Should be b'')
        :rtype: bytes

        """
        if not 0 <= microsteps <= 192000:
            raise ValueError(
                "Possible syringe positions are 0 <= stroke <= 192000, is : %s" %
                microsteps)
        pos = self.getSyringePosition(deviceId)
        if pos + microsteps > 192000 and not keyargs.get('enqueue', False):
            raise ValueError(
                "Desired pickup steps %s too large. current syringe position: %s" %
                (microsteps, pos))

        cmd = ""
        if velocity >= 0:
            if not 2 <= velocity <= 3400:
                raise ValueError(
                    "Maximum velocity V has to be in the range 2 <= V <= 3400 motor steps/s, is : %s" %
                    velocity)
            cmd += "V%s" % int(velocity)
        if valvePos >= 0:
            if not 1 <= valvePos <= 8:
                self.valveStatus(deviceId).raiseIfError()
                raise ValueError(
                    "Possible valve positions are 1 <= valvePos <= 8, is : %s" %
                    valvePos)
            valvePos += 26000
            cmd += "h%s" % int(valvePos)
        self.syringeStatus(deviceId).raiseIfError()
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd += "P%s" % int(microsteps)
        else:
            cmd += "P%sR" % int(microsteps)
        if keyargs.pop('send', True):
            result = self.serialCommandToId(
                deviceId, cmd.encode('ascii'), not enqueue, **keyargs)
            return result
        else:
            return cmd

    def fill(self, deviceId: int, velocity: int, valveToReservoir: int,
             **keyargs):
        """Completely refills a syringe from the valve position\
        ``valveToReservoir`` with the velocity ``velocity``.

        Prior to the plunger movement, the valve position will be changed
        to valveToReservoir.

        :param int deviceId: hardware device id. Must be a PSD device id.

        :param int velocity:\
        Maximum velocity of the plunger move in motorsteps/s.\
        Will retain the last set value if velocity is set to -1.\
        Has to be in the range 2 <= V <= 3400 motor steps/s.

        :param int valveToReservoir:\
        Will move the valve to this position prior to the\
        plunger move. The valve will not move if set to -1.

        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.

        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.

        :returns: device answer string. (Should be b'')
        :rtype: bytes

        """
        return self.moveSyringe(
            deviceId, 192000, velocity, valveToReservoir, **keyargs)

    def drain(self, deviceId: int, velocity: int, valveToWaste: int,
              **keyargs):
        """Empties a syringe into the valve position valveToWaste
        with the velocity velocity.

        Prior to the plunger movement, the valve position will be changed
        to valveToWaste.

        :param int deviceId: hardware device id. Must be a PSD device id.

        :param int velocity:\
        Maximum velocity of the plunger move in motorsteps/s.\
        Will retain the last set value if velocity is set to -1.\
        Has to be in the range 2 <= V <= 3400 motor steps/s.

        :param int valveToWaste:\
        Will move the valve to this position prior to the\
        plunger move. The valve will not move if set to -1.

        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.

        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.

        :returns: device answer string. (Should be b'')
        :rtype: bytes

        """
        return self.moveSyringe(deviceId, 0, velocity, valveToWaste, **keyargs)

    def delay(self, address: int, delaymilliseconds: int, **keyargs):
        """Instructs the device to wait for given amount of milliseconds.

        Probably only makes sense when combined with multiple commands, which
        are started with :meth:`executeCommands`

        :param int address: RS-485 bus address of a device or multiple devices.
        :param int delaymilliseconds: milliseconds to wait.
        """
        enqueue = keyargs.pop('enqueue', False)
        if enqueue:
            cmd = "M%s" % int(delaymilliseconds)
        else:
            cmd = "M%sR" % int(delaymilliseconds)
        if keyargs.pop('send', True):
            result = self.serialCommand(
                address,
                cmd.encode('ascii'),
                **keyargs)
            return result
        else:
            return cmd

    def executeCommands(self, address: int, **keyargs):
        """Instructs a device to execute the buffered commands.

        :param int address: RS-485 bus address of a device or multiple devices.
        """
        result = self.serialCommand(address, b'R', True, **keyargs)
        return result


if __name__ == '__main__':
    logger = mp.log_to_stderr()
    logger.setLevel(logging.INFO)

    p = PumpClient(port='COM4')
    p.waitServerReady()
