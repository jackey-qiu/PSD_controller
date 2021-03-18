# -*- coding: utf-8 -*-
###############################################################################
# Copyright (c) 2020 Timo Fuchs, Olaf Magnussen all rights reserved
#
# This software was developed during the PhD work of Timo Fuchs,
# within the group of Olaf Magnussen. Usage within the group is hereby granted.
###############################################################################
"""This module contains optimized functions for frequently used operations.

"""
__author__ = "Timo Fuchs"
__copyright__ = "Copyright 2020, Timo Fuchs, Olaf Magnussen all rights reserved"
__credits__ = []
__license__ = "all rights reserved"
__version__ = "1.0.0"
__maintainer__ = "Timo Fuchs"
__email__ = "fuchs@physik.uni-kiel.de"

import time
from .device import Syringe

__all__ = ['ExchangePair']


class ExchangePair(object):
    """Container class for synchronized movement of two syringes to control\
    the amount of liquid in an electrochemical cell.

    - The :class:`~psdrive.device.Syringe` ``pushSyr`` serves as liquid\
        reservoir.
    - The :class:`~psdrive.device.Syringe` ``pullSyr`` is used to remove\
        liquid from the cell.

    Exchanging means that the Syringe ``pushSyr`` dispenses the same amount
    of liquid as the Syringe ``pullSyr`` at the same time.
    """

    deviceNo = 0

    sharedAdresses = {
        frozenset({1, 2}): int('41', 16),
        frozenset({3, 4}): int('43', 16),
        frozenset({5, 6}): int('45', 16),
        frozenset({7, 8}): int('47', 16),
        frozenset({9, 10}): int('49', 16),
        frozenset({11, 12}): int('4B', 16),
        frozenset({13, 14}): int('4D', 16),
        frozenset({15, 16}): int('4F', 16)
    }

    def __init__(self, pushSyr: Syringe, pullSyr: Syringe, **keyargs):
        """
        :param psdrive.device.Syringe pushSyr: Syringe which increases the\
        amount of liquid in the cell.
        :param psdrive.device.Syringe pullSyr: Syringe which decreases the\
        amount of liquid in the cell.
        """
        if not issubclass(type(pushSyr), Syringe) or not issubclass(
                type(pullSyr), Syringe):
            raise ValueError("Arguments have to be of type Syringe!")
        self.pushSyr = pushSyr
        self.pullSyr = pullSyr

        no = ExchangePair.deviceNo
        ExchangePair.deviceNo += 1
        self.name = keyargs.get('name', 'unnamedExch-%s' % no)

        self._rate = self.maxrate_OnTheFly/2

        self.drainrate = self.maxrate/2
        self.fillrate = self.maxrate/2

        self.prePressure = 0  # muL
        self.underPressure = 0  # muL
        self.bubbleDispense = 0

        self.dispensedelay = 0  # s

        self.valveConnections = {'pullSyr': {}, 'pushSyr': {}}

        if self.pushSyr.controller is self.pullSyr.controller:
            if frozenset({self.pushSyr.deviceId, self.pullSyr.deviceId}
                         ) in ExchangePair.sharedAdresses:
                self.sharedAddress = ExchangePair.sharedAdresses[frozenset(
                    {self.pushSyr.deviceId, self.pullSyr.deviceId})]
                self.sharedController = self.pushSyr.controller
        if not hasattr(self, 'sharedAddress'):
            print(
                "No shared hardware address between exchange pair %r and %r;"
                "this may cause precision loss!" %
                (self.pushSyr, self.pullSyr))

    def __repr__(self):
        return "%s %s:\npushSyr: %r\npullSyr:%r" % (type(self), self.name,
                                                    self.pushSyr, self.pullSyr)

    def __str__(self):
        return "%s %s:\npushSyr: %s\npullSyr:%s" % (type(self), self.name,
                                                    self.pushSyr, self.pullSyr)

    def configure(self, config):
        """Configures the ExchangePair from a config dict generated from the
        standard config file.
        """
        self.fillrate = config['defaultFillRate']
        self.drainrate = config['defaultDrainRate']
        self.rate = config['defaultRate']
        self.prePressure = config['prePressure']
        self.prePressureRate = config['prePressureRate']
        self.underPressure = config['underPressure']
        self.underPressureRate = config['underPressureRate']
        self.dispenseDelay = config['dispenseDelay']
        self.bubbleDispense = config['bubbleDispense']
        self.valveConnections['pullSyr'] = config['pullSyr']
        self.valveConnections['pushSyr'] = config['pushSyr']

    @property
    def rate(self):
        """Global liquid flow rate for this pair in :math:`\textrm{\mu L / s}`

        You can change the flow rate while an exchange is still happening.
        This is called *On-the-fly* change.

        The maximum/minimum flow rate depends on the specific syringe drive
        type and the size of the attached syringe:

          - During normal operation: :attr:`~ExchangePair.minrate` <\
          :attr:`~ExchangePair.rate` < :attr:`~ExchangePair.maxrate`
          - When performing *On-the-fly* changes:\
          :attr:`~ExchangePair.minrate` < :attr:`~ExchangePair.rate` <\
          :attr:`~ExchangePair.maxrate_OnTheFly`

        :getter: returns the current flow rate.
        :setter: Sets the flow rate.
        :type: :class:`float`
        :raises ~tango.DevError: if the communication with the device server\
        or the serial communication fails
        :raises ~psdrive.PumpStatus.StatusByte: If the device responds\
        with an error code.
        :raises ValueError: If the flow rate is not within the limits
        """
        return self._rate

    @rate.setter
    def rate(self, rate: float):

        if rate < self.minrate:
            raise ValueError("Desired rate too low for"
                             "one of the syringes")

        if self.pushSyr.busy and self.pullSyr.busy:  # on-the-fly change
            if rate > self.maxrate_OnTheFly:
                raise ValueError("Desired on-the-fly rate too high for"
                                 "one of the syringes")
            self.pushSyr.rate = rate
            self.pullSyr.rate = rate
            self._rate = rate
        else:
            if rate > self.maxrate:
                raise ValueError("Desired rate too high for"
                                 "one of the syringes")
            self._rate = rate

    @property
    def minrate(self):
        """Minimum exchange rate.
        """
        return max(self.pushSyr.minrate, self.pullSyr.minrate)

    @property
    def maxrate(self):
        """Maximum exchange rate.
        """
        return min(self.pushSyr.maxrate, self.pullSyr.maxrate)

    @property
    def maxrate_OnTheFly(self):
        """Maximum exchange rate when changing rate *On-the-fly*.
        """
        return min(self.pushSyr.maxrate_OnTheFly,
                   self.pullSyr.maxrate_OnTheFly)

    @property
    def exchangeableVolume(self):
        """Maximum exchangeable volume.

        Either remaining liquid in pushSyr or remaining empty space in
        pullSyr.

        """
        return min(self.pushSyr.volume,
                   self.pullSyr.maxvolume - self.pullSyr.volume)

    def _excecuteCmds(self):
        if hasattr(self, 'sharedAddress'):
            self.sharedController.executeCommands(
                self.sharedAddress)  # simultaneously start both pumps
        else:
            try:
                self.pushSyr.executeCommands()
                self.pullSyr.executeCommands()
            except Exception:
                self.stop()
                raise

    def exchange(self, volume: float, rate: float = -1):
        """Exchanges liquid volume through the cell.

        """
        if self.pushSyr.busy or self.pullSyr.busy:
            raise Exception("Devices are busy")

        if rate > 0:
            self.rate = rate

        # Switch both valves to cell and perform pressurization, if required
        try:
            cmd = ""
            if self.pushSyr.valve != self.valveConnections['pushSyr']['Cell']:
                cmd += self.pushSyr.moveValve(
                    self.valveConnections['pushSyr']['Cell'],
                    enqueue=True, send=False)
                if self.prePressure > 0:
                    cmd += self.pushSyr.dispense(self.prePressure, self.prePressure,
                                          enqueue=True, send=False)
                cmd += "R"
                self.pushSyr.sendCmd(cmd)
                
            cmd = ""
            if self.pullSyr.valve != self.valveConnections['pullSyr']['Cell']:
                cmd += self.pullSyr.moveValve(
                    self.valveConnections['pullSyr']['Cell'],
                    enqueue=True, send=False )
                if self.underPressure > 0:
                    cmd += self.pullSyr.pickup(self.underPressure, self.underPressureRate,
                                        enqueue=True, send=False)
                cmd += "R"
                self.pullSyr.sendCmd(cmd)
                
        except Exception:
            self.pushSyr.pauseBufferedCommands()  # delete commands
            self.pullSyr.pauseBufferedCommands()  # or is stop() required?
            raise

        #self._excecuteCmds()

        # wait until pre movement has finished.
        self.pushSyr.join()
        self.pullSyr.join()

        try:
            #if self.dispenseDelay > 0:
            #    self.pushSyr.delay(int(self.dispenseDelay * 1000),
            #                       enqueue=True)
            #elif self.dispenseDelay < 0:
            #    self.pullSyr.delay(int(-self.dispenseDelay * 1000),
            #                       enqueue=True)
            # actual exchange command
            fut_disp = self.pushSyr.dispense(
                volume, self.rate, -1, enqueue=True,wait=False, priority=100)  # not start yet
            fut_pick = self.pullSyr.pickup(volume, self.rate, -1, enqueue=True,wait=False, priority=100)
        except Exception:
            self.pushSyr.pauseBufferedCommands()
            self.pullSyr.pauseBufferedCommands()
            raise

        self._excecuteCmds()
        fut_disp.result()
        fut_pick.result()
        

    def prepare(self):
        """Refills reservoir syrionge and empties waste syringe.
        """
        if self.pushSyr.busy or self.pullSyr.busy:
            raise Exception("Devices are busy")
        try:
            pushcmd = ""
            pullcmd = ""
            # fill reservoir syringe
            pushcmd += self.pushSyr.fill(self.valveConnections['pushSyr']['Reservoir'],
                              self.fillrate,
                              enqueue=True, send=False )
            # empty waste syringe
            pullcmd += self.pullSyr.drain(self.valveConnections['pullSyr']['Waste'],
                               self.drainrate,
                               enqueue=True, send=False )

            if self.bubbleDispense > 0:
                pushcmd += self.pushSyr.dispense(self.bubbleDispense, self.drainrate,
                                      self.valveConnections['pushSyr']['Waste'],
                                      enqueue=True, send=False )

            # Switch both valves to cell and perform pressurization,if required
            pushcmd += self.pushSyr.moveValve(
                self.valveConnections['pushSyr']['Cell'],
                enqueue=True, send=False)

            if self.prePressure > 0:
                pushcmd += self.pushSyr.dispense(self.prePressure, self.prePressureRate,
                                      enqueue=True, send=False)

            pullcmd += self.pullSyr.moveValve(self.valveConnections['pullSyr']['Cell'],
                                   enqueue=True, send=False)
            if self.underPressure > 0:
                pullcmd += self.pullSyr.pickup(self.underPressure, self.underPressureRate,
                                    enqueue=True, send=False)
            self.pushSyr.sendCmd(pushcmd)
            self.pullSyr.sendCmd(pullcmd)
        except Exception:
            self.pushSyr.pauseBufferedCommands()  # delete commands
            self.pullSyr.pauseBufferedCommands()  # or is stop() required?
            raise

        self._excecuteCmds()

    def increaseVolume(self, volume: float, rate: float = -1):
        """Increases liquid volume in the cell by dispensing from the pushSyr.

        Also works during exchange.
        """
        if rate == -1:
            rate = self.rate
        
        if self.pushSyr.busy and self.pullSyr.busy:
            newpullrate = self.rate - rate
            newpushrate = self.rate
            if newpullrate < self.pullSyr.minrate:
                newpullrate = self.pullSyr.minrate
                newpushrate = rate + newpullrate
                if newpushrate > self.pushSyr.maxrate_OnTheFly:
                    newpushrate = self.pushSyr.maxrate_OnTheFly
            
            increaseTime = volume / (newpushrate - newpullrate)
            self.pullSyr.rate = newpullrate
            if newpushrate != self.rate:
                self.pushSyr.rate = newpushrate
                increaseTime -= 0.06 # time adjustment for sending commands
                if increaseTime > 0:
                    time.sleep(increaseTime)
                self.pushSyr.rate = self.rate
            else:
                time.sleep(increaseTime)
            self.pullSyr.rate = self.rate
        else:
            if self.pushSyr.join(1):
                self.pushSyr.dispense(volume, rate, -1)

    def decreaseVolume(self, volume: float, rate: float = -1):
        """Decreases liquid volume in the cell by picking up from the pullSyr.

        Also works during exchange.
        """
        if rate == -1:
            rate = self.rate
            
        if self.pushSyr.busy and self.pullSyr.busy:
            newpushrate = self.rate - rate
            newpullrate = self.rate
            if newpushrate < self.pushSyr.minrate:
                newpushrate = self.pushSyr.minrate
                newpullrate = rate + newpushrate
                if newpullrate > self.pullSyr.maxrate_OnTheFly:
                    newpullrate = self.pullSyr.maxrate_OnTheFly
                    
            decreaseTime = volume / (newpullrate - newpushrate)
            self.pushSyr.rate = newpushrate
            
            if newpullrate != self.rate:
                self.pullSyr.rate = newpullrate
                decreaseTime -= 0.06 # time adjustment for sending commands
                if decreaseTime > 0:
                    time.sleep(decreaseTime)
                self.pullSyr.rate = self.rate
            else:
                time.sleep(decreaseTime)

            self.pushSyr.rate = self.rate
        else:
            if self.pullSyr.join(1):
                self.pullSyr.pickup(volume, rate, -1)

    def stop(self):
        """Stops any movement of both controlled syringes.
        """
        if hasattr(self, 'sharedAddress'):
            # simultaneously stop both pumps
            self.sharedController.stop(address=self.sharedAddress)
        else:
            self.pushSyr.stop()
            self.pullSyr.stop()


if __name__ == '__main__':
    pass
