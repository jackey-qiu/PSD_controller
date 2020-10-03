# -*- coding: utf-8 -*-
"""
Created on Thu Jul 16 17:20:04 2020

@author: Timo
"""

import numpy as np
from collections import OrderedDict
import functools
import multiprocessing as mp
import logging

import time

from .CommunicationServer import deviceIdToAddress, DeviceError

class Valve(object):
    deviceNo = 0
    
    def __init__(self, controller, deviceId, **keyargs):
        no = Valve.deviceNo
        Valve.deviceNo += 1
        self.controller = controller
        self.deviceId = deviceId
        self.name = keyargs.get('name','unnamedValve-%s' % no)
        self.settings = keyargs.get('settings',OrderedDict())
        self.valveAlias = OrderedDict()
        
    def __repr__(self):
        return "%s: name: %s; id %s" % (type(self),self.name,self.deviceId)
    
    def initValve(self,**keyargs):
        return self.controller.initializeValve(self.deviceId,**keyargs)
    
    def setValvePosName(self,posId,name):
        self.valveAlias[posId] = name
    
    @property
    def busy(self):
        return self.controller.deviceStatus(self.deviceId).busy
    
    @property
    def status(self):
        return self.controller.deviceStatus(self.deviceId)
    
    @property
    def valve(self):
        posId = self.controller.getValvePosition(self.deviceId)
        if posId in self.valveAlias:
            return self.valveAlias[posId]
        else:
            return posId
        
    @valve.setter
    def valve(self,position):
        valveId = self._valveId(position)
        self.controller.moveValve(self.deviceId,valveId)
        
    def join(self,timeout=3600):
        return self.controller.waitForDeviceIdle(self.deviceId,timeout=timeout)
        
    def delay(self,delaymilliseconds,**keyargs):
        self.controller.delay(self.deviceId,delaymilliseconds,**keyargs)
        
    def _valveId(self,position):
        if isinstance(position, int):
            return position
        else:
            for k in self.valveAlias:
                if self.valveAlias[k] == position:
                    return k
        raise KeyError("No such valve: %s" % position)
        
    @property
    def hwaddress(self):
        return deviceIdToAddress(self.deviceId)
    
    def executeCommands(self,**keyargs):
        self.controller.executeCommands(self.hwaddress,**keyargs)
        
    def terminateMovement(self,**keyargs):
        self.controller.terminateMovement(self.deviceId,**keyargs)
        
    def stopCommandBuffer(self,**keyargs):
        return self.controller.stopCommandBuffer(self.deviceId,**keyargs)
        


class Syringe(Valve):
    deviceNo = 0
    
    def __init__(self, controller, deviceId, maxvolume, **keyargs):
        no = Syringe.deviceNo
        Syringe.deviceNo += 1
        self.controller = controller
        self.deviceId = deviceId
        self.maxvolume = maxvolume #muL
        self.name = keyargs.get('name','unnamedSyringe-%s' % no)
        self.settings = keyargs.get('settings',OrderedDict())
        self.valveAlias = OrderedDict()
             
    def initSyringe(self,valvepos,rate,backoffvolume,**keyargs):
        speed_rate = type(self).speed_stepsps*(self.maxvolume/type(self).maxsteps)
        speedidx = np.argmin(np.abs(speed_rate - rate))
        speed = type(self).speedcodes[speedidx]
        valveId = self._valveId(valvepos)
        backoff = (type(self).maxsteps/self.maxvolume)*backoffvolume
        return self.controller.initializeSyringe(self.deviceId,valveId,speed,backoff,**keyargs)
        
    @property
    def volume(self):
        pos = self.controller.getSyringePos(self.deviceId) # musteps
        vol = (self.maxvolume/type(self).maxmusteps)*pos
        return vol
    
    @volume.setter
    def volume(self,volume):
        musteps = (type(self).maxmusteps/self.maxvolume)*volume
        self.controller.moveSyringe(self.deviceId,musteps,-1,-1,True)
    
    @property
    def rate(self):
        v = self.controller.getMaximumVelocity(self.deviceId)
        return v*(self.maxvolume/type(self).maxsteps)
    
    @rate.setter
    def rate(self,rate):
        """
        On-the-fly changes are allowed.

        Parameters
        ----------
        rate : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """
        velocity = (type(self).maxsteps/self.maxvolume)*rate
        self.controller.setMaximumVelocity(self.deviceId,velocity,True)
        
    @property
    def maxrate(self):
        return (self.maxvolume/type(self).maxsteps)*type(self).velocity_maximum_stepsps
    
    @property
    def minrate(self):
        return (self.maxvolume/type(self).maxsteps)*type(self).velocity_minimum_stepsps
    
    def dispense(self,volume,rate=-1,valvePos=-1,**keyargs):
        musteps = (type(self).maxmusteps/self.maxvolume)*volume
        velocity = (type(self).maxsteps/self.maxvolume)*rate
        valvePos = self._valveId(valvePos)
        return self.controller.dispense(self.deviceId,musteps,velocity,valvePos,**keyargs)
    
    def pickup(self,volume,rate=-1,valvePos=-1,**keyargs):
        musteps = (type(self).maxmusteps/self.maxvolume)*volume
        velocity = (type(self).maxsteps/self.maxvolume)*rate
        valvePos = self._valveId(valvePos)
        return self.controller.pickup(self.deviceId,musteps,velocity,valvePos,**keyargs)
        
    def move(self,volume,rate=-1,valvePos=-1,**keyargs):
        musteps = (type(self).maxmusteps/self.maxvolume)*volume
        velocity = (type(self).maxsteps/self.maxvolume)*rate
        valvePos = self._valveId(valvePos)
        return self.controller.moveSyringe(self.deviceId,musteps,velocity,valvePos,**keyargs)
    
    def fill(self,valvePos=-1,rate=-1,**keyargs):
        if valvePos == -1 and 'Reservoir' in self.valveAlias:
            valvePos = 'Reservoir'
        if rate == -1 and hasattr(self, 'defaultFillRate'):
            rate = self.defaultFillRate
        return self.move(self.maxvolume,rate,valvePos,**keyargs)
    
    def drain(self,valvePos=-1,rate=-1,**keyargs):
        if valvePos == -1 and 'Waste' in self.valveAlias:
            valvePos = 'Waste'
        if rate == -1 and hasattr(self, 'defaultDrainRate'):
            rate = self.defaultDrainRate
        return self.move(0.,rate,valvePos,**keyargs)
    
    
        
    
        
class PSD4_smooth(Syringe):
    
    maxmusteps = 192000
    maxsteps = 48000 #192000/4
    
    speedcodes = np.arange(40)+1
    speed_stepsps = np.zeros(40)
    speed_stepsps[:2] = 3400. - 200.*np.arange(2)
    speed_stepsps[2:15] = 2800. - 200.*np.arange(13)
    
    speed_stepsps[15:33] = 200. - 10*np.arange(18)
    speed_stepsps[33:] = 20. - 2*np.arange(7)
    
    velocity_maximum_stepsps = 3420
    velocity_minimum_stepsps = 2
    
    accelerationcode = np.arange(20)+1
    acceleration = accelerationcode*2500 # steps/s^2
    


class ExchangePair(object):
    
    sharedAdresses = {
        (1,2) : int('41',16),
        (3,4) : int('43',16),
        (5,6) : int('45',16),
        (7,8) : int('47',16),
        (9,10) : int('49',16),
        (11,12) : int('4B',16),
        (13,14) : int('4D',16),
        (15,16) : int('4F',16)
        }
    
    
    def __init__(self, pushSyr, pullSyr):
        if not isinstance(pushSyr, Syringe) or not isinstance(pullSyr, Syringe):
            raise ValueError("Arguments have to be of type Syringe!")
        
        self.pushSyr = pushSyr
        self.pullSyr = pullSyr
        if self.pushSyr.controller is self.pullSyr.controller:
            if {self.pushSyr.deviceId, self.pullSyr.deviceId} in ExchangePair.sharedAdresses:
                self.sharedAddress = ExchangePair.sharedAdresses[{self.pushSyr.deviceId, self.pullSyr.deviceId}]
                self.sharedController = self.pushSyr.controller
        if not hasattr(self,'sharedAddress'):
            mp.get_logger().info("No shared hardware address between exchange pair %r and %r; this may cause precision loss!" % (self.pushSyr,self.pullSyr))
        
    def swap(self):
        self.pushSyr, self.pullSyr = self.pullSyr, self.pushSyr
        
    @property
    def exchangeableVolume(self):
        return min(self.pushSyr.volume,self.pullSyr.maxvolume - self.pullSyr.volume)
        
    def __call__(self,volume,rate,dispensedelay=0.0):
        """
        

        Parameters
        ----------
        volume : TYPE
            DESCRIPTION.
        rate : TYPE
            DESCRIPTION.
        dispensedelay : float, optional
            Time in s the syringe waits until operation. The default is 0.0.

        Raises
        ------
        Exception
            DESCRIPTION.

        Returns
        -------
        None.

        """
        if self.pushSyr.busy or self.pullSyr.busy:
            raise Exception("Devices are busy")
        #self.pushSyr.rate = rate
        #self.pullSyr.rate = rate
        try:
            if dispensedelay > 0:
                self.pushSyr.delay(int(dispensedelay*1000))
            elif dispensedelay < 0:
                self.pullSyr.delay(int(-dispensedelay*1000))
            
            self.pushSyr.dispense(volume,rate,-1,enqueue=True) # not start yet
            self.pullSyr.pickup(volume,rate,-1,enqueue=True)
        except Exception:
            self.pushSyr.stopCommandBuffer()
            self.pullSyr.stopCommandBuffer()
            raise
            
        
        if hasattr(self,'sharedAddress'):
            self.sharedController.executeCommands(self.sharedAddress) # simultaneously start both pumps
        else:
            try:
                self.pushSyr.executeCommands()
                self.pullSyr.executeCommands()
            except Exception:
                self.pushSyr.terminateMovement()
                self.pullSyr.terminateMovement()
                raise
        self._currentrate = rate
        
    def increaseVolume(self,volume,rate):
        if self.pushSyr.busy and self.pullSyr.busy:
            newpullrate = self._currentrate - rate
            if newpullrate < self.pullSyr.minrate:
                newpullrate = self.pullSyr.minrate
            increaseTime = volume/(self._currentrate - newpullrate)
            self.pullSyr.rate = newpullrate
            time.sleep(increaseTime)
            self.pullSyr.rate = self._currentrate
        else:
            if self.pushSyr.join(1):
                self.pushSyr.dispense(volume,rate,-1)
            
                
    def decreaseVolume(self,volume,rate):
        if self.pushSyr.busy and self.pullSyr.busy:
            newpushrate = self._currentrate - rate
            if newpushrate < self.pushSyr.minrate:
                newpushrate = self.pushSyr.minrate
            decreaseTime = volume/(self._currentrate - newpushrate)
            self.pushSyr.rate = newpushrate
            time.sleep(decreaseTime)
            self.pushSyr.rate = self._currentrate
        else:
            if self.pullSyr.join(1):
                self.pullSyr.pickup(volume,rate,-1)
                
                
    
    def changeRate(self,rate):
        """
        This should be used for on-the-fly changes to the exchange rate.
        Has no effect if pumps are not exchanging

        Parameters
        ----------
        rate : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """
        if self.pushSyr.busy and self.pullSyr.busy:
            self.pushSyr.rate = rate
            self.pullSyr.rate = rate
            self._currentrate = rate
            
            
        
        
        
        
        
if __name__ == '__main__':
    pass

    
    