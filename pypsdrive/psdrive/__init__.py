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

__all__ = ['device', 'fromFile', 'connect', 'start_server_fromFile',
           'server_list_ports', 'server_scan_ports']

from .PumpInterface import PumpClient
from . import device

import subprocess
import yaml
import atexit


def fromFile(filename: str):
    return PumpClient.fromFile(filename)


fromFile.__doc__ = PumpClient.fromFile.__doc__


def server_list_ports(filename: str):
    """Connects to a server and lists the available serial ports.
    """
    with open(filename, 'r') as f:
        config = yaml.safe_load(f)

    server = config['server']
    if not server['database']:
        name = "%s:%s/%s#dbase=no" % (server['host'], server['port'],
                                      server['tangoname'])
    else:
        name = server['tangoname']

    client = PumpClient(name)
    client._device.ping()  # check whether server is alive

    return client.listPorts()

def server_scan_ports(filename: str, deviceId: int):
    """Connects to a server and scans the available serial ports for a device id.

    The server needs to be disconnected from the serial port.
    
    """
    with open(filename, 'r') as f:
        config = yaml.safe_load(f)

    server = config['server']
    if not server['database']:
        name = "%s:%s/%s#dbase=no" % (server['host'], server['port'],
                                      server['tangoname'])
    else:
        name = server['tangoname']

    client = PumpClient(name)
    client._device.ping()  # check whether server is alive

    return client.scanPortsForId(deviceId)

def connect(tangodevice: str):
    """Connects to a configured device server and fetches the\
    configuration from the server.

    :param tangodevice: Tango device name. See :ref:`connectClientNoDb`\
    for further details.
    :type tangodevice: str
    :raises ~tango.DevError: if the communication with the device server or the serial communication fails
    :raises ~psdrive.PumpStatus.StatusByte: If the device responds with an error code.
    :return: The new client.
    :rtype: :class:`~psdrive.PumpInterface.PumpClient`
    """
    client = PumpClient(tangodevice)
    client.fetchConfig()
    return client


def start_server_fromFile(filename: str):
    """Starts a new device server in a subprocess with the settings in
    given config file.

    The process is still owned by the executing process. It will be
    killed if the process terminates.

    This function is not secured against shell injection attacks.
    It directly executes parameters given in the config file in the shell.

    :param filename: Path name to the YAML config file.
    :type filename: str
    :return: subprocess with the device server
    :rtype: :class:`subprocess.Popen`
    """
    with open(filename, 'r') as f:
        config = yaml.safe_load(f)

    server = config['server']
    if server['database']:
        args = [server['name']]
    else:
        args = [server['name'], '-ORBendPoint',
                "giop:tcp::%i" % server['port'], '-nodb', '-dlist',
                server['tangoname']]
    args = ["PumpServer"] + args
    process = subprocess.Popen(args)
    atexit.register(process.kill)
    return process
