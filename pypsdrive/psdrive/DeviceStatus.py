# -*- coding: utf-8 -*-
"""
Copyright (c) 2020 Timo Fuchs, Olaf Magnussen all rights reserved

This software was developed during the PhD work of Timo Fuchs,
within the group of Olaf Magnussen. Usage within the group is hereby granted.

"""
__author__ = "Timo Fuchs"
__copyright__ = "Copyright 2020, Timo Fuchs, Olaf Magnussen all rights reserved"
__credits__ = []
__license__ = "all rights reserved"
__version__ = "1.0.0"
__maintainer__ = "Timo Fuchs"
__email__ = "fuchs@physik.uni-kiel.de"

import numpy as np
from collections import OrderedDict


class ValveStatus(Exception):
    valveCode = OrderedDict(sorted([
        (0, 'No error'),
        (1, "Valve not initialized"),
        (2, "Valve initialization error"),
        (4, "Valve stall"),
        (16, "Valve not enabled"),
        (32, "Valve is busy"),
        (255, 'No device answer'),
        (512, "Status not available")
    ], reverse=True))

    def __init__(self, statuscode, *args, **keyargs):
        self.statuscode = statuscode

        stat = ValveStatus.decodeStatus(self.statuscode)
        args += stat
        if 'address' in keyargs:
            self.address = keyargs.pop('address', None)
            args += ("address: %s" % self.address,)

        super(ValveStatus, self).__init__(*args)

    def raiseIfError(self):
        if hasattr(self, "address"):
            broadcast = isBroadcast(self.address)
        else:
            broadcast = False
        if self.statuscode != 0 and not broadcast:
            raise self

    @staticmethod
    def decodeStatus(statuscode):
        stat = statuscode
        if statuscode in ValveStatus.valveCode:
            return (ValveStatus.valveCode[statuscode],)
        retval = ()
        for code in ValveStatus.valveCode:
            if int(stat - code) >= 0:
                retval += (ValveStatus.valveCode[code],)
                stat -= code
                if stat <= 0:
                    return retval
        return ("Invalid valve status: %s" % statuscode,)


class SyringeStatus(Exception):
    syringeCode = OrderedDict(sorted([
        (0, 'No error'),
        (1, "Syringe not initialized"),
        (6, "Syringe stall"),
        (8, "Syringe initialization error"),
        (255, 'No device answer'),
        (512, "Status not available")
    ], reverse=True))

    def __init__(self, statuscode, *args, **keyargs):
        self.statuscode = statuscode

        stat = SyringeStatus.decodeStatus(self.statuscode)
        args += stat
        if 'address' in keyargs:
            self.address = keyargs.pop('address', None)
            args += ("address: %s" % self.address,)

        super(SyringeStatus, self).__init__(*args)

    def raiseIfError(self):
        if hasattr(self, "address"):
            broadcast = isBroadcast(self.address)
        else:
            broadcast = False
        if self.statuscode != 0 and not broadcast:
            raise self

    @staticmethod
    def decodeStatus(statuscode):
        stat = statuscode
        if statuscode in SyringeStatus.syringeCode:
            return (SyringeStatus.syringeCode[statuscode],)
        retval = ()
        for code in SyringeStatus.syringeCode:
            if int(stat - code) >= 0:
                retval += (SyringeStatus.syringeCode[code],)
                stat -= code
                if stat <= 0:
                    return retval
        return ("Invalid syringe status: %s" % statuscode,)


class StatusByte(Exception):
    """

    """

    deviceErrorsFull = {255: 'No device answer',
                        223: 'No device answer',
                        0: 'No error',
                        1: 'Initialization error – occurs when the device fails to initialize.',
                        2: 'Invalid command – occurs when an unrecognized command is used.',
                        3: 'Invalid operand – occurs when and invalid parameter is given with a command.',
                        4: 'Invalid command sequence – occurs when the command communication protocol is incorrect.',
                        6: 'EEPROM failure – occurs when the EEPROM is faulty.',
                        7: 'Device not initialized – occurs when the device fails to initialize.',
                        9: 'Syringe overload – occurs when the syringe encounters excessive back pressure.',
                        10: 'Valve overload – occurs when the valve drive encounters excessive back pressure.',
                        11: 'Syringe move not allowed – when the valve is in the bypass or throughput position, syringe move commands are not allowed.',
                        15: 'Device is busy – occurs when the command buffer is full.',
                        32: 'Invalid statusbyte - Statusbyte does not match the correct bit pattern'}

    deviceErrors = {255: 'No device answer',
                    223: 'No device answer',
                    0: 'No error',
                    1: 'Initialization error',
                    2: 'Invalid command',
                    3: 'Invalid operand',
                    4: 'Invalid command sequence',
                    6: 'EEPROM failure',
                    7: 'Device not initialized',
                    9: 'Syringe overload',
                    10: 'Valve overload',
                    11: 'Syringe move not allowed',
                    15: 'Device is busy',
                    32: 'Invalid statusbyte'
                    }

    def __init__(self, statusbyte, *args, **keyargs):
        self.statusbyte = statusbyte
        self.busy, self.errorcode = StatusByte.decodeStatusbyte(statusbyte)
        args += ("busy: %s" % self.busy,)
        if 'address' in keyargs:
            self.address = keyargs.pop('address', None)
            args += ("address: %s" % self.address,)
        if 'rawcommand' in keyargs:
            self.rawcommand = keyargs.pop('rawcommand', None)
            args += ("command: %s" % self.rawcommand,)
        if keyargs.pop('short', False):
            super(StatusByte, self).__init__(
                StatusByte.deviceErrors[self.errorcode], *args)
        else:
            super(StatusByte, self).__init__(
                StatusByte.deviceErrorsFull[self.errorcode], *args)

    def raiseIfError(self):
        if hasattr(self, "address"):
            broadcast = isBroadcast(self.address)
        else:
            broadcast = False
        if self.errorcode != 0 and not broadcast:
            raise self

    @staticmethod
    def isBusyStatus(statusbyte):
        return not np.all(statusbyte & int('20', 16))

    @staticmethod
    def decodeStatusbyte(status):
        if status == 255:
            return False, 255
        if status == 223:
            return True, 223
        if status & int('11010000', 2) != int('01000000', 2):
            return False, 32
        busy = StatusByte.isBusyStatus(status)
        errorcode = status & int('0f', 16)
        return busy, errorcode


def isBroadcast(address):
    assert address < 255
    return not ((address & int('f0', 16)) == int(
        '30', 16) or address == int('40', 16))
