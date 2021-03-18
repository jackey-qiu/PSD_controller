# -*- coding: utf-8 -*-
###############################################################################
# Copyright (c) 2020 Timo Fuchs, Olaf Magnussen all rights reserved
#
# This software was developed during the PhD work of Timo Fuchs,
# within the group of Olaf Magnussen. Usage within the group is hereby granted.
###############################################################################
"""
This module contains device proxies for the different device types on the RS-485 bus.
They handle the metadata of the pumps (e.g. size of attached syringe) and convert hardware input/outputs to
physical values.

During normal operation, any device control should be performed via these device classes.
They provide a pythonic way to access to the main device attributes

:class:`Valve` is the base class for all devices. (This should maybe be changed´in the future)

"""
__author__ = "Timo Fuchs"
__copyright__ = "Copyright 2020, Timo Fuchs, Olaf Magnussen all rights reserved"
__credits__ = []
__license__ = "all rights reserved"
__version__ = "1.0.0"
__maintainer__ = "Timo Fuchs"
__email__ = "fuchs@physik.uni-kiel.de"

import numpy as np
import math
from typing import Any, Union
from collections import OrderedDict
import time
from .PumpServer import deviceIdToAddress

__all__ = ['Valve', 'Syringe', 'PSD4_smooth']


class Valve(object):
    """
    Base class for all device proxies with attached valves.
    This is also the default proxy implementation of Hamilton MVP/4 Standard valves.

    Before instantiation of a :class:`Valve`, the device server should be running and
    the :class:`~psdrive.PumpInterface.PumpClient` ``client`` is connected to the server.
    It is recommended to create a Valve object with the hardware address ``deviceId`` from the client using:

    >>> valve_proxy = client.getValve(deviceId)

    This will return a :class:`Valve` object ``valve`` with the current configuration from the client. This might raise an
    error, if the Valve is not configured.

    You can manually create a :class:`Valve` like this:

    >>> import psdrive as psd
    >>> valve_proxy = psd.device.Valve(client, deviceId)
    >>> valve_proxy.readConfig() # get configuration directly from the device

    Change valve position (if valve alias ``'Reservoir'`` is registered using :attr:`Valve.config` \
    or :meth:`Valve.setValvePosName`):

    >>> valve_proxy.valve = 'Reservoir' # move the valve to position 'Reservoir'
    >>> valve_proxy.join() # wait for the move to be completed (optional)

    If no valve alias is registered, you can also directly use hardware position ids:

    >>> valve_proxy.valve = 1 # move valve to numerical position 1
    >>> valve_proxy.join() # wait for the move to be completed (optional)

    To stop any movement of the device:

    >>> valve_proxy.stop()

    """
    deviceNo = 0

    def __init__(self, controller,
                 device_id: int, **keyargs):
        """Constructs a new Valve.

        :param controller: The controlling client.
        :type controller: ~psdrive.PumpInterface.PumpClient
        :param deviceId: The hardware device id.
        :type deviceId: int
        :param keyargs: optional

          - name: (:class:`str`) name of the device
          - config: (:class:`dict`) configuration of the device, see :doc:`Configuration` for further details
        """
        no = Valve.deviceNo
        Valve.deviceNo += 1
        self.controller = controller
        self.deviceId = device_id
        self.name = keyargs.get('name', 'unnamedValve-%s' % no)
        """Alias name of the syringe.

        :type: str
        """
        self.valveAlias = OrderedDict()
        self._config = keyargs.get('config', {})

    def __repr__(self):
        return "%s: name: %s; id %s" % (type(self), self.name, self.deviceId)

    def initValve(self, **keyargs) -> bytes:
        """Initializes the valve and reconfigures the valve if the valve\
        type given in :attr:`config`.

        :param keyargs: optional. Please refer to :meth:`~psdrive.PumpInterface.PumpClient.serialCommand`\
         for further details.
        :return: device answer string
        :rtype: bytes
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        send = keyargs.pop('send', True)
        enqueue = keyargs.pop('enqueue', False)

        keyargs['send'] = False
        keyargs['enqueue'] = True
        
        if 'valve type' in self.config:

            cmd = self.controller.setValveType(
                self.deviceId, self.config['valve type'] , **keyargs)
    
            cmd += self.controller.initializeValve(
                self.deviceId, **keyargs)
    
            cmd += self.controller.setValveType(
                self.deviceId, self.config['valve type'] , **keyargs)
            
        else:
            cmd = self.controller.initializeValve(
                self.deviceId, **keyargs)
        
        if not enqueue:
            cmd += "R"

        keyargs['send'] = send

        if send:
            return self.sendCmd(cmd, **keyargs)
        else:
            return cmd

    def setValvePosName(self, posId: int, name: str):
        """Sets a new valve position alias.

        :param posId: numerical hardware positon id of the valve position.
        :type posId: int
        :param name: Valve alias name
        :type posId: str
        """
        self.valveAlias[posId] = name

    @property
    def config(self) -> dict:
        """Holds the locally stored device configuration.

        This is not necessarily synchronized with the hardware.
        Use :meth:`~Valve.readConfig` to read the configuration from the hardware. Or use :meth:`~Valve.reconfigure` to
        configure the hardware with the the currently saved configuration.

        :getter: returns the stored configuration
        :setter: stores the device config and converts hardware specific units (motor steps etc.) into physical values\
         (e.g. volume). Does not update the hardware config. Use :meth:`~Valve.reconfigure` for this instead.
        :type: :class:`dict`
        """
        return self._config

    @config.setter
    def config(self, config: dict):
        """Stores the device config.
        :type: :class:`dict`
        """
        if 'valve alias' in config:
            for posid in config['valve alias']:
                self.setValvePosName(posid, config['valve alias'][posid])
        self.name = config.get('name', self.name)
        self._config = config

    def readConfig(self, store=False) -> dict:
        """Reads the current device config directly from the hardware.

        :param store: Indicate whether to store the current device config
        :type store: bool, optional, defaults to False
        :return: updated device config
        :rtype: dict
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        sett = self.controller.getSettings(self.deviceId)
        if store:
            self.config.update(sett)
            return self.config
        else:
            return sett

    def reconfigure(self, config: dict = None, **keyargs):
        """Updates the configuration of the hardware.

        Because multiple commands are send, this might take a while to execute.

        :param config: new device configuration. See :doc:`Configuration` for further details. The default updates the\
        hardware with the configuration stored in :attr:`~Valve.config`.
        :type config: dict, optional
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        if config is not None:
            self.config = config
        return self.controller.setSettings(self.deviceId, self.config, **keyargs)

    @property
    def busy(self) -> bool:
        """Indicates whether the device is busy.

        :return: busy status
        :rtype: bool
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        return self.controller.getStatusByte(self.deviceId).busy

    @property
    def status(self) -> dict:
        """returns the device status.

        The device status is a dict with the keys:
          - 'type': (:class:`str`) either 'MVP', 'PSD'. Returns 'unknown' if the device was not recognized.
          - 'statusbyte': (:exc:`~psdrive.PumpStatus.StatusByte`) Containing the current device status.
          - 'busy': (:class:`bool`) Indicates whether the device is busy.
          - 'valve': (:exc:`~psdrive.PumpStatus.ValveStatus`) The current Valve status
          - 'valvePos': (:class:`int` or :class:`str`) current position of the valve (either numerical or alias name)
          - 'syringe': (:exc:`~psdrive.PumpStatus.SyringeStatus`) Only if this is a :class:`~psdrive.device.Syringe`.
          - 'syringePos': (:class:`int`) syringe position in motor steps. Only if this is a :class:`~psdrive.device.Syringe`.

        :return: The device status as described above.
        :rtype: dict
        """
        stat = self.controller.deviceStatus(self.deviceId)
        if 'valvePos' in stat:
            valvePos = stat['valvePos']
            stat['valvePos'] = self.valveAlias.get(valvePos, valvePos)
        return stat

    @property
    def valve(self) -> Union[int, str]:
        """The current valve position.

        :getter: returns current valve position alias or numerical valve position, if valve alias is not set.
        :setter: moves the valve to the new position. Returns immediately. To wait for the movement to complete, \
        call :meth:`~psdrive.device.Valve.join`.
        :type: :class:`int` or :class:`str`
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        valvePos = self.controller.getValvePosition(self.deviceId)
        return self.valveAlias.get(valvePos, valvePos)

    @valve.setter
    def valve(self, position: Union[int, str]):
        valveId = self._valveId(position)
        self.controller.moveValve(self.deviceId, valveId)

    def moveValve(self, position: Union[int, str], **keyargs):
        """Moves the valve to a new position.

        Accepts valve position alias or numerical valve position.

        This method provides more flexibility compared to\
        just setting the :attr:`~Valve.valve` property.

        The :attr:`~Valve.busy` status will be ``True`` during the movement.\
        To wait for the movement to complete,\
        call :meth:`~psdrive.device.Syringe.join`.

        :param position: Desired valve position 
        :type position: float or str
        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        valveId = self._valveId(position)
        return self.controller.moveValve(self.deviceId, valveId, **keyargs)

    def join(self, timeout: float = math.inf) -> bool:
        """Wait until device status is not busy.

        :param timeout: set timeout in seconds, defaults to math.inf
        :type timeout: float, optional
        :raises TimeoutError: if timeout has been reached.
        """
        return self.controller.waitForDeviceIdle(
            self.deviceId, timeout=timeout)

    def delay(self, delaymilliseconds: int, **keyargs):
        """Programs the device to wait for given amounts of milliseconds before executing the next command.

        This function probably only makes sense if combined with other commands, which can be\
        achieved by sending multiple commands with 'enqueue' set to True in keyargs\
        (see :meth:`~psdrive.PumpInterface.PumpClient.serialCommand`) and starting the\
        program with :meth`~psdrive.device.Valve.executeCommands`.

        :param delaymilliseconds: delay time in milliseconds
        :type delaymilliseconds: int
        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        return self.controller.delay(self.deviceId, delaymilliseconds, **keyargs)

    def _valveId(self, position):
        if isinstance(position, int):
            return position
        else:
            for k in self.valveAlias:
                if self.valveAlias[k] == position:
                    return k
        raise KeyError("No such valve: %s" % position)

    @property
    def hwaddress(self):
        """holds the binary address of the device, when to be addressed as a single unit.

        :returns: device address
        :rtype: int
        """
        return deviceIdToAddress(self.deviceId)

    def executeCommands(self, **keyargs):
        """Starts the buffered command sequence.

        Commands which have been enqueued by setting enqueue=True can be executed with this command.

        :param keyargs: optional. Please refer to :meth:`~psdrive.PumpInterface.PumpClient.serialCommand`\
         for further details.
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        return self.controller.executeCommands(self.hwaddress, **keyargs)

    def stop(self):
        """Terminates any movement of the device.

        This can lead to a loss of motor steps, but the device should still be in a usable state.
        Initialization is recommended after execution of this command if highest absolute precision is required.

        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        return self.controller.stop(self.deviceId)

    def pauseBufferedCommands(self):
        """Stops the buffered command sequence after execution of the currently active command.

        Another call of :meth:`~psdrive.device.Valve.executeCommands` will resume the execution.

        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        return self.controller.pauseBufferedCommands(self.deviceId)
        
    def sendCmd(self,cmd: str, **keyargs):
        result = self.controller.serialCommandToId(
                    self.deviceId, cmd.encode('ascii'), True, **keyargs)
        return result


class Syringe(Valve):
    """
    Base class for all device proxies of syringe drive devices. These have one attached syringe, which can be controlled via this interface.
    Because all Hamilton Syringe Drives also have an attached valve, this class inherits from :class:`Valve` and all methods from this class also work with a Syringe class.
    
    .. note::
        This is an abstract class. It should never be directly instantiated.
    
    This class provides a common interface to all syringe drive devices. 
    Implementations must provide the respective hardware informations like motor steps/stroke etc or have to override the functions in this class.  

    Before instantiation of a :class:`Syringe`, the device server should be running and
    the :class:`~psdrive.PumpInterface.PumpClient` ``client`` is connected to the server.
    It is recommended to create a Syringe object with the hardware address ``deviceId`` from the client using:

    >>> syringe_proxy = client.getSyringe(deviceId)

    This will return a :class:`Syringe` object ``syringe_proxy``\
    with the current configuration from the client. Note, that the object will\
    be of a subclass of :class:`Syringe`, which might provide more specific\
    interface with the type of syringe. This will raise an\
    error, if the Syringe is not yet configured.
    
    You can change the absolute position of the syringe like this:
    
    >>> syringe_proxy.volume = 10000 # in muL.
    >>> syringe_proxy.join() # wait for the move to be completed (optional)

    Change valve position (if valve alias 'Reservoir' is registered using :attr:`Valve.config` \
    or :meth:`Valve.setValvePosName`):

    >>> syringe_proxy.valve = 'Reservoir' # move the valve to position 'Reservoir'
    >>> syringe_proxy.join() # wait for the move to be completed (optional)

    If no valve alias is registered, you can also directly use hardware position ids:

    >>> syringe_proxy.valve = 1 # move valve to numerical position 1
    >>> syringe_proxy.join() # wait for the move to be completed (optional)

    To stop any movement of the device:

    >>> syringe_proxy.stop()

    """
    deviceNo = 0

    def __init__(self, controller, deviceId, capacity, **keyargs):
        """Default contructor for a Syringe. Syringe is an abstract class.\
        Should never be called directly.

        :param controller: The controlling client.
        :type controller: ~psdrive.PumpInterface.PumpClient
        :param deviceId: The hardware device id.
        :type deviceId: int
        :param capacity: The maximum capacity of the attached syringe in :math:`\mathrm{\mu L}` .
        :type capacity: int
        :param keyargs: optional parameters

          - name: (:class:`str`) name of the device
          - config: (:class:`dict`) configuration of the device, see :doc:`Configuration` for further details
        :type keyargs: dict, optional
        """

        self.maxvolume = capacity  # muL
        """Capacity of the syringe in :math:`\mathrm{\mu L}`,\
        if the plunger is fully extracted.

        :type: float
        """
        no = Syringe.deviceNo
        Syringe.deviceNo += 1
        self.controller = controller
        self.deviceId = deviceId
        self.name = keyargs.get('name', 'unnamedSyringe-%s' % no)
        self._config = keyargs.get('config', {})
        self.valveAlias = OrderedDict()

    def __str__(self):
        return "%s\n%s" % (repr(self), self.status)

    def initSyringe(self, valvepos: Union[int, str],
                    rate: float, backoffvolume: float = None, **keyargs):
        """Initializes and reconfigures the syringe.

        .. note::
            Also sends the currently saved configuration in :attr:`config` to
            the device. Otherwise initializing a syringe would override the
            configuration with the hardware defaults.

        :param valvepos: numerical or alias position of valve, where to\
        connect to for initializtion.
        :param float rate: Init speed in muL/s. Must be\
        :attr:`~Syringe.mininitrate` < ``rate`` < :attr:`~Syringe.maxinitrate`
        :param float backoffvolume: Syringe moves this amount back after\
        initialization. This avoids syringe stalls and damage to the syringe.\
        If set to None (the default), will use ``'backoff volume'`` in\
        :attr:`~Valve.config`.
        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.

        :raises ~tango.DevError: if the communication with the device server\
        or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with\
        an error code.
        """
        speed_rate = type(self).speed_stepsps * \
            (self.maxvolume / type(self).maxsteps)
        speedidx = np.argmin(np.abs(speed_rate - rate))
        speed = type(self).speedcodes[speedidx]
        if not 10 <= speed <= 40 and speed != 1 and speed != 0:
            raise ValueError("Invalid init rate, has to be in between %s and %s" % (self.mininitrate,self.maxinitrate))
        valveId = self._valveId(valvepos)
        if backoffvolume is None:
            if 'backoff volume' in self.config:
                backoffvolume = self.config['backoff volume']
            else:
                raise ValueError("You must provide backoff steps setting for syringe initialization.")
        backoff = (type(self).maxsteps / self.maxvolume) * backoffvolume

        send = keyargs.pop('send', True)
        enqueue = keyargs.pop('enqueue', False)

        keyargs['send'] = False
        keyargs['enqueue'] = True

        cmd = self.controller.initializeSyringe(
            self.deviceId, valveId, speed, backoff, **keyargs)

        cmd += self.reconfigure(**keyargs)
        if not enqueue:
            cmd += "R"

        keyargs['send'] = send

        if send:
            return self.sendCmd(cmd, **keyargs)
        else:
            return cmd

    @property
    def config(self):
        # for documentation see: Valve.config
        return self._config

    @config.setter
    def config(self, config):
        # for documentation see: Valve.config
        self.maxvolume = config.get('syringevolume', self.maxvolume)
        if 'start rate' in config and 'start velocity' not in config:
            config['start velocity'] = config['start rate'] * (type(self).maxsteps/self.maxvolume)
        if 'stop rate' in config and 'stop velocity' not in config:
            config['stop velocity'] = config['stop rate'] * (type(self).maxsteps/self.maxvolume)
        if 'return volume' in config and 'return steps' not in config:
            config['return steps'] = config['return volume'] * (type(self).maxsteps/self.maxvolume)
        if 'backoff volume' in config and 'backoff steps' not in config:
            config['backoff steps'] = config['backoff volume'] * (type(self).maxsteps/self.maxvolume)
        if 'valve alias' in config:
            for posid in config['valve alias']:
                self.setValvePosName(posid, config['valve alias'][posid])
        self.name = config.get('name', self.name)
        self._config = config

    def readConfig(self, store: bool = False) -> dict:
        # for documentation see: Valve.readConfig, this only extends the 
        config = super().readConfig(store)
        config['start rate'] = config['start velocity'] * (self.maxvolume/type(self).maxsteps)
        config['stop rate'] = config['stop velocity'] * (self.maxvolume/type(self).maxsteps)
        config['return volume'] = config['return steps'] * (self.maxvolume/type(self).maxsteps)
        if store:
            self.config.update(config)
            return self.config
        else:
            return config

    @property
    def status(self):
        stat = super().status
        if 'syringePos' in stat:
            stat['volume'] = (
                self.maxvolume / type(self).maxmusteps) * stat['syringePos']
        return stat

    @property
    def volume(self):
        """The syringe plunger position, converted to remaining volume in the syringe in :math:`\mathrm{\mu L}`.  

        The maximum capacity of the syringe can be accessed with :attr:`~Syringe.maxvolume`.
        
        For more flexibility and efficient combination of commands use\
        :meth:`~Syringe.move` instead.
        
        The :attr:`~Valve.busy` status will be ``True`` during the movement. To wait for the movement to complete,\
        call :meth:`~psdrive.device.Syringe.join`.
        
        :getter: returns the current syringe volume.
        :setter: moves the plunger to the position which corresponds to the required syringe volume with the speed :attr:`~Syringe.rate`.\
        Returns immediately. The :attr:`~Syringe.busy` status will be ``True`` during the movement. To wait for the movement to complete,\
        call :meth:`~psdrive.device.Valve.join`.
        :type: :class:`float`
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        """
        pos = self.controller.getSyringePosition(self.deviceId)  # musteps
        vol = (self.maxvolume / type(self).maxmusteps) * pos
        return vol

    @volume.setter
    def volume(self, volume):
        musteps = (type(self).maxmusteps / self.maxvolume) * volume
        self.controller.moveSyringe(self.deviceId, musteps, -1, -1)

    @property
    def rate(self):
        """Current liquid flow rate in :math:`\mathrm{\mu L/s}` .
        
        You can change the flow rate while the plunger is moving. This is called *On-the-fly* change.
        
        The maximum/minimum flow rate depends on the specific syringe drive type and the size of the attached syringe:
        
          - During normal operation: :attr:`~Syringe.minrate` < :attr:`~Syringe.rate` < :attr:`~Syringe.maxrate`
          - When performing *On-the-fly* changes: :attr:`~Syringe.minrate` < :attr:`~Syringe.rate` < :attr:`~Syringe.maxrate_OnTheFly`
        
        :getter: returns the current flow rate.
        :setter: Sets the flow rate. 
        :type: :class:`float`
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        :raises ValueError: If the flow rate is not within the limits
        """
        v = self.controller.getMaximumVelocity(self.deviceId)
        return v * (self.maxvolume / type(self).maxsteps)

    @rate.setter
    def rate(self, rate):
        if self.busy:
            if rate > self.maxrate_OnTheFly:
                raise ValueError(
                    "Flow rate %s muL/s too high. Max rate when changing the rate on the fly is %s" %
                    (rate, self.maxrate_OnTheFly))
        else:
            if rate > self.maxrate:
                raise ValueError(
                    "Flow rate %s muL/s too high. Maximum flow rate is %s" %
                    (rate, self.maxrate))
        if rate < self.minrate:
            raise ValueError(
                "Flow rate %s muL/s too low. Minimum flow rate is %s" %
                (rate, self.minrate))
        velocity = (type(self).maxsteps / self.maxvolume) * rate
        self.controller.setMaximumVelocity(self.deviceId, velocity)

    @property
    def maxrate(self):
        """Maximum liquid flow :attr:`~Syringe.rate` during normal operation in :math:`\mathrm{\mu L/s}` .
        
        :type: :class:`float`
        """
        return (self.maxvolume / type(self).maxsteps) * \
            type(self).velocity_maximum_stepsps

    @property
    def maxrate_OnTheFly(self):
        """Maximum liquid flow :attr:`~Syringe.rate` when changing the flow rate *On-the-fly* in :math:`\mathrm{\mu L/s}` .
        
        :type: :class:`float`
        """
        return (self.maxvolume / type(self).maxsteps) * \
            type(self).velocity_max_stepsps_OnTheFly

    @property
    def minrate(self):
        """Minimum liquid flow :attr:`~Syringe.rate` during normal operation in :math:`\mathrm{\mu L/s}` .
        
        :type: :class:`float`
        """
        return (self.maxvolume / type(self).maxsteps) * \
            type(self).velocity_minimum_stepsps
            
    @property
    def maxinitrate(self):
        """Maximum liquid flow rate allowed during syringe initializaion in :math:`\mathrm{\mu L/s}` (see :meth:`~Syringe.initSyringe`).
        
        :type: :class:`float`
        """
        return (self.maxvolume / type(self).maxsteps) * \
            type(self).speed_stepsps[9]
            
    @property
    def mininitrate(self):
        """Minimum liquid flow rate allowed during syringe initializaion in :math:`\mathrm{\mu L/s}` (see :meth:`~Syringe.initSyringe`).
        
        :type: :class:`float`
        """
        return (self.maxvolume / type(self).maxsteps) * \
            type(self).speed_stepsps[39]

    def dispense(self, volume, rate=-1, valvePos=-1, **keyargs):
        """Dispenses given amount of liquid from the syringe.
        
        The :attr:`~Valve.busy` status will be ``True`` during the movement. To wait for the movement to complete,\
        call :meth:`~psdrive.device.Valve.join`.
        
        :param volume: Amount of liquid to dispense in :math:`\mathrm{\mu L}`.
        :type volume: float
        :param rate: flow rate during dispense in :math:`\mathrm{\mu L/s}`.\
        Defaults to the value in :attr:`~Syringe.rate`.
        :type rate: float, optional, must be :attr:`~Syringe.minrate` <\
        :attr:`~Syringe.rate` < :attr:`~Syringe.maxrate`
        :param valvePos: Connect to this valve position :attr:`~Valve.valve` prior dispensing the liquid.\
        The default doesn't change the valve position.
        :type valvePos: int or float, optional
        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        :raises ValueError: If not enough volume is inside the syringe.
        :raises ValueError: If the flow rate is not within the limits (see :attr:`~Syringe.rate`).
        """
        musteps = int((type(self).maxmusteps / self.maxvolume) * volume)
        if rate > 0:
            if rate > self.maxrate:
                raise ValueError(
                    "Flowrate %s muL/s too high. Maximum flowrate is %s" %
                    (rate, self.maxrate))
            if rate < self.minrate:
                raise ValueError(
                    "Flow rate %s muL/s too low. Minimum flow rate is %s" %
                    (rate, self.minrate))
            velocity = int((type(self).maxsteps / self.maxvolume) * rate)
        else:
            velocity = -1  # do not change rate
        valvePos = self._valveId(valvePos)
        return self.controller.dispense(
            self.deviceId, musteps, velocity, valvePos, **keyargs)

    def pickup(self, volume, rate=-1, valvePos=-1, **keyargs):
        """Pulls given amount of liquid into the syringe.
        
        The :attr:`~Valve.busy` status will be ``True`` during the movement. To wait for the movement to complete,\
        call :meth:`~psdrive.device.Syringe.join`.
        
        :param volume: Amount of liquid to pickup in :math:`\mathrm{\mu L}`.
        :type volume: float
        :param rate: flow rate during pickup in :math:`\mathrm{\mu L/s}`.\
        Defaults to the value in :attr:`~Syringe.rate`.
        :type rate: float, optional, must be :attr:`~Syringe.minrate` <\
        :attr:`~Syringe.rate` < :attr:`~Syringe.maxrate`
        :param valvePos: Connect to this valve position :attr:`~Valve.valve` prior picking up the liquid.\
        The default doesn't change the valve position.
        :type valvePos: int or float, optional
        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        :raises ValueError: If pickup would exceed the capacity of the syringe.
        :raises ValueError: If the flow rate is not within the limits (see :attr:`~Syringe.rate`).
        """
        musteps = int((type(self).maxmusteps / self.maxvolume) * volume)
        if rate > 0:
            if rate > self.maxrate:
                raise ValueError(
                    "Flowrate %s muL/s too high. Maximum flowrate is %s" %
                    (rate, self.maxrate))
            if rate < self.minrate:
                raise ValueError(
                    "Flow rate %s muL/s too low. Minimum flow rate is %s" %
                    (rate, self.minrate))
            velocity = int((type(self).maxsteps / self.maxvolume) * rate)
        else:
            velocity = -1  # do not change rate
        valvePos = self._valveId(valvePos)
        return self.controller.pickup(
            self.deviceId, musteps, velocity, valvePos, **keyargs)

    def move(self, volume, rate=-1, valvePos=-1, **keyargs):
        """Moves the plunger to an absolute volume of the syringe.
        
        This method provides more flexibility compared to\
        just setting the :attr:`~Syringe.volume` property.
        
        The :attr:`~Valve.busy` status will be ``True`` during the movement. To wait for the movement to complete,\
        call :meth:`~psdrive.device.Syringe.join`.
        
        :param volume: Desired liquid volume of the syringe in :math:`\mathrm{\mu L}`.
        :type volume: float
        :param rate: flow rate during movement in :math:`\mathrm{\mu L/s}`.\
        Defaults to the value in :attr:`~Syringe.rate`.
        :type rate: float, optional, must be :attr:`~Syringe.minrate` <\
        :attr:`~Syringe.rate` < :attr:`~Syringe.maxrate`
        :param valvePos: Connect to this valve position :attr:`~Valve.valve` prior plunger movement.\
        The default doesn't change the valve position.
        :type valvePos: int or float, optional
        :param optional keyargs: See\
        :meth:`~psdrive.PumpInterface.PumpClient.serialCommand` for further\
        details.
        :raises ~tango.DevError: if the communication with the device server or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
        :raises ValueError: If the capacity of the syringe will be exceeded or is below :math:`0 \: \mathrm{\mu L/s}`.
        :raises ValueError: If the flow rate is not within the limits (see :attr:`~Syringe.rate`).
        """
        musteps = int((type(self).maxmusteps / self.maxvolume) * volume)
        if rate > 0:
            if rate > self.maxrate:
                raise ValueError(
                    "Flowrate %s muL/s too high. Maximum flowrate is %s" %
                    (rate, self.maxrate))
            if rate < self.minrate:
                raise ValueError(
                    "Flow rate %s muL/s too low. Minimum flow rate is %s" %
                    (rate, self.minrate))
            velocity = int((type(self).maxsteps / self.maxvolume) * rate)
        else:
            velocity = -1  # do not change rate
        valvePos = self._valveId(valvePos)
        return self.controller.moveSyringe(
            self.deviceId, musteps, velocity, valvePos, **keyargs)

    def fill(self, valvePos=-1, rate=-1, **keyargs):
        """Refills syringe from valve port ``valvePos`` with flow rate ``rate``.
        
        If a valve alias ``'Reservoir'`` is set and a ``defaultFillRate`` is\
        set as an attribute of this class, fill will use these settings for\
        the filling of the syringe.
        
        Apart for this, is just an alias for :meth:`~Syringe.move`:
        
        >>> syringe_proxy.move(syringe_proxy.maxvolume, valvePos, rate, **keyargs)
        
        See :meth:`Syringe.move` for further details.
        """
        if valvePos == -1 and 'Reservoir' in self.valveAlias:
            valvePos = 'Reservoir'
        if rate == -1 and hasattr(self, 'defaultFillRate'):
            rate = self.defaultFillRate
        return self.move(self.maxvolume, rate, valvePos, **keyargs)

    def drain(self, valvePos=-1, rate=-1, **keyargs):
        """Empties syringe to valve port ``valvePos`` with flow rate ``rate``.
        
        If a valve alias ``'Waste'`` is set and a ``defaultDrainRate`` is\
        set as an attribute of this class, drain will use these settings for\
        the emptying of the syringe.
        
        Apart for this, is just an alias for :meth:`~Syringe.move`:
        
        >>> syringe_proxy.move(0, valvePos, rate, **keyargs)
        
        See :meth:`Syringe.move` for further details.
        """
        if valvePos == -1 and 'Waste' in self.valveAlias:
            valvePos = 'Waste'
        if rate == -1 and hasattr(self, 'defaultDrainRate'):
            rate = self.defaultDrainRate
        return self.move(0., rate, valvePos, **keyargs)


class PSD4_smooth(Syringe):
    """You can manually create a :class:`Syringe` like this:

    >>> import psdrive as psd
    >>> syringe_proxy = psd.device.PSD4_smooth(client, deviceId, capacity)
    >>> syringe_proxy.readConfig() # get configuration directly from the device
    
    with ``capacity``, the maximum capacity (volume) of the attached syringe in :math:`\mathrm{\mu L}` . 
    """

    maxmusteps = 192000
    maxsteps = 48000  # 192000/4

    speedcodes = np.arange(40) + 1
    speed_stepsps = np.zeros(40)
    speed_stepsps[:2] = 3400. - 200. * np.arange(2)
    speed_stepsps[2:15] = 2800. - 200. * np.arange(13)

    speed_stepsps[15:33] = 200. - 10 * np.arange(18)
    speed_stepsps[33:] = 20. - 2 * np.arange(7)

    velocity_maximum_stepsps = 3400
    velocity_minimum_stepsps = 2

    accelerationcode = np.arange(20) + 1
    acceleration = accelerationcode * 2500  # steps/s^2

    velocity_max_stepsps_OnTheFly = 800


if __name__ == '__main__':
    pass
