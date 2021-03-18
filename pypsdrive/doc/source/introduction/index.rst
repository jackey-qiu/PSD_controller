#########################
Introduction to pyPSDrive
#########################

This page will explain the basics of the software.

Principle of Operation
======================

pyPSDrive consist of a `Tango <https://tango-controls.readthedocs.io/en/latest/development/advanced/TangoDeviceServerModel.html>`_ device server and a 
specialized Tango client software. 

The device server runs on the computer with the Hamilton PSD/4 syringe drive devices or MVP/4 valve positioner devices attached to a RS-232 or RS-485 port in a daisy-chain. 
Each serial port with devices has an individual device server process associated to it, which continuously monitors the device status in the background.

The client software provides a pythonic way to access the syringe drive devices from any computer which has a TCP/IP connection to the 
server computers. Moreover, it is possible to connect multiple client instances to the same device server (e.g. one computer in the control room, one computer in the experimental hutch and another computer far away in "homeoffice" *fck Coronavirus* ). 
Similarly, it is also possible to have multiple servers connected to the same client.

Because the device status is continuously updated by the device server, a status update only requires a very fast TCP/IP communication from the server to the client compared to the slow serial communication.
The server uses the `gevent <http://www.gevent.org/>`_ library to operate in a `Green Mode <https://pytango.readthedocs.io/en/stable/green_modes/green.html>`_ , which allows asynchronous function calls to the server. 
In practice, this means that status requests can be performed even while the server is still working on another request.

Quickstart
==========

For operation, you need to start the device server, which is called ``PumpServer`` and subsequently connect to this server with a client. 
The first connected client needs to configure the server.

For a single computer, which operates as server and client, it is sufficient to use Tango without a running database.
*pyPSDrive* provides the function :func:`psdrive.start_server_fromFile` to start the server as subprocess from a config file.
The example file ``nodb_configuration_nodevices.yml`` can be downloaded :download:`here <../../../examples/nodb_configuration_nodevices.yml>`.
Using this configuration, you can start a server and a :class:`~psdrive.PumpInterface.PumpClient` ``client`` like this:

.. code-block:: python
    
    import psdrive as psd
    psd.start_server_fromFile("nodb_configuration_nodevices.yml")
    client = psd.fromFile("nodb_configuration_nodevices.yml")

.. note:: 

    You might have to change the serial port in the config file according to your hardware.

For more details on how to start a devcie server and a client please refer to :ref:`startingServer`.

The call of :func:`psdrive.fromFile` does multiple things:

#. Searches for the device server specified in ``nodb_configuration_nodevices.yml`` and connects to it.
#. Instructs the server to open the serial port specified in the config file (see :meth:`psdrive.PumpClient.connectPort`).
#. The server searches for devices on the serial bus (see :meth:`psdrive.PumpClient.scanDevices`).
#. Configures the devices on the bus, if a configuration is given in the config file.
#. Generates device proxies for the configured devices. (See :mod:`psdrive.device`).
#. Stores the config file on the device server.

If this returns successfully, you can use all functions exposed in :class:`~psdrive.PumpClient`.
For example, to check which devices are on the bus you can use the functions :meth:`~psdrive.PumpClient.deviceIds`, 
:meth:`~psdrive.PumpClient.syringePumpIds` and :meth:`~psdrive.PumpClient.valvePositionerIds`.
Or to get the device status, use :meth:`~psdrive.PumpClient.deviceStatus`.

This interface, however, doesn't provide any abstractions like conversion of motor steps to liquid volume.
For this, you should use the High-level device API in :mod:`psdrive.device`, which you can access through :meth:`~psdrive.PumpClient.getSyringe` and :meth:`~psdrive.PumpClient.getValve` after the devices have been configured.
Configuration can be done using the config file during creation of the client.

Let's say that we have a PSD/4 Smooth Flow syringe pump connected with hardware id ``1``. You should then add the following configuration to the ``devices`` section of the ``nodb_configuration_nodevices.yml`` file:

.. _configshort:

.. code-block:: yaml

      1: #hardware address
        name: Reservoir cell inlet 1
        type: PSD
        class: PSD4_smooth
        valve type: 3-way 90 degree distribution valve
        valve alias:
          1: Reservoir
          2: Waste
          3: Cell
        syringevolume: 12500 #muL
        start rate: 20 #muL/s
        stop rate: 20 #muL/s
        return volume: 0 #muL
        acceleration: 10000 #steps/s^2
        backoff volume: 5 #muL
        default init rate: 200 #muL/s
        default rate: 50 #muL/s

This will specify 

- the device type (``PSD`` : syringe drive, ``MVP`` : valve positioner)
- the version of the device (here: :class:`~psdrive.device.PSD4_smooth`, this should be a class in the :mod:`psdrive.device` module)
- The type of the attached valve (``3-way 90 degree distribution valve``)
- The maximum volume of the attached syringe (here: 12500 :math:`\mathrm{\mu L}`)

The other settings are described in :ref:`Config` or are hardware specific and described in the corresponding class in :mod:`psdrive.device`.

To reload the configuration you can use :meth:`~psdrive.PumpClient.readConfigfile`

.. code-block:: python

    client.readConfigfile("nodb_configuration.yml")

After the settings have been applied, you can get the :class:`~psdrive.device.PSD4_smooth` using

.. code-block:: python

    syringe_proxy = client.getSyringe(1) # provide the hardware id as argument
    
The class :class:`~psdrive.device.PSD4_smooth` is a subclass of :class:`~psdrive.device.Syringe`, which provides a simple, pythonic interface for scripting of actions:

Examples of Syringe operation
=============================

First initialize the syringe (see :meth:`~psdrive.device.Syringe.initSyringe`) with valve position at 
``'Waste'`` (This position must be configured in the ``valve alias`` section :ref:`above <configshort>` )
and 200 :math:`\mathrm{\mu L / s}`:

.. code-block:: python

    syringe_proxy.initSyringe('Waste', 200)
    syringe_proxy.join() # wait for the move to be completed

You can change the absolute position of the syringe with the liquid flow rate stored in :attr:`~psdrive.device.Syringe.rate` like this:

.. code-block:: python
    
    syringe_proxy.rate = 50 # change syringe speed to 50 muL/s (optional)
    syringe_proxy.volume = 10000 # in muL.
    
To check whether the syringe is still moving:

>>> syringe_proxy.busy
True

To get the current syringe volume:

>>> syringe_proxy.volume
8900
>>> time.sleep(1)
>>> syringe_proxy.volume
8950
    
Dispense 1000 :math:`\mathrm{\mu L }` liquid with 100 :math:`\mathrm{\mu L / s}` into ``'Cell'``. (see :meth:`~psdrive.device.Syringe.dispense`)

.. code-block:: python

    syringe_proxy.dispense(1000, 100, 'Cell')
    
Pick up 1000 :math:`\mathrm{\mu L }` liquid with 100 :math:`\mathrm{\mu L / s}` from ``'Reservoir'``, wait 2 s, then change speed to 50 :math:`\mathrm{\mu L / s}` 
and wait until the syringe stops. (see :meth:`~psdrive.device.Syringe.pickup`)

.. code-block:: python

    syringe_proxy.pickup(1000, 100, 'Reservoir')
    time.sleep(2)
    syringe_proxy.rate = 50
    syringe_proxy.join()

Change valve position (if valve alias 'Reservoir' is registered using the config file :ref:`above <configshort>`,\
:attr:`~psdrive.device.Valve.config` or :meth:`~psdrive.device.Valve.setValvePosName`):

.. code-block:: python

    syringe_proxy.valve = 'Reservoir' # move the valve to position 'Reservoir'

If no valve alias is registered, you can also always directly use hardware position ids:

.. code-block:: python

    syringe_proxy.valve = 1 # move valve to numerical position 1

To stop any movement of the device:

.. code-block:: python

    syringe_proxy.stop()







