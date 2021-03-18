#####################
Welcome to pyPSDrive!
#####################

The documentation of pyPSDrive can be found `here <http://fuchs.page.physik.uni-kiel.de/pypsdrive>`_ (Only accessible from within the Kiel University network).

pyPSDrive consist of a `Tango <https://www.tango-controls.org/>`_ device server 
for `Hamilton syringe pump drives <https://www.hamiltoncompany.com/oem/oem-components/syringe-pumps/psd4>`_ 
and `valve positioner devices <https://www.hamiltoncompany.com/oem/oem-components/valve-positioners>`_ on a RS-485 bus
as well as a specialized client software.

Both allow easy integration of the hardware into the complex Supervisory Control and Data Acquisition ( `SCADA <https://en.wikipedia.org/wiki/SCADA>`_ ) systems at large-scale research facilities like ESRF or DESY.

Installation
============

pyPSDrive requires at least python version ``python >= 3.6`` and `setuptools <https://setuptools.readthedocs.io>`_. All other dependencies are listed in section `Dependencies`_ .

First make sure that `python <https://www.python.org/>`_ and the common packages `numpy <http://www.numpy.org/>`_ and `gevent <http://www.gevent.org/>`_ are installed. 
These are typically available in the most common python distributions like `Anaconda <https://www.anaconda.com/>`_ or `Enthought <https://www.enthought.com/>`_ .

`PyTango <https://pytango.readthedocs.io/>`_ is available as Debian package or can be installed
from the binaries for Anaconda distributions in the channel `tango-controls <https://anaconda.org/tango-controls/>`_ for most operating systems.
You can then simply install PyTango with

.. code-block:: bash 

    conda install -c tango-controls pytango

`PyTango <https://pytango.readthedocs.io/>`_ requires more dependencies if you want to build it from the source. Please refer to the manual `here <https://pytango.readthedocs.io/en/stable/start.html>`_ .

All other dependencies are python-only and are listed in PyPi.

Using pip you can then install pyPSDrive from the top level of the source package (with the file ``setup.py``) with

.. code-block:: bash 

    pip install .

This will handle all other dependencies.

Dependencies
------------

.. _dependencies:

The mandatory dependencies are:

- `PyTango <https://pytango.readthedocs.io/>`_
- `gevent <http://www.gevent.org/>`_
- `pySerial <https://pythonhosted.org/pyserial/>`_
- `PyYAML <https://pyyaml.org/>`_
- `numpy <http://www.numpy.org/>`_

pyPSDrive utilizes the Tango ecosystem for easy integration into the `SCADA <https://en.wikipedia.org/wiki/SCADA>`_ systems
used at synchrotrons. To use the full featureset it is recommended to install Tango database.

- `Tango Controls <https://www.tango-controls.org>`_

The complete list of dependencies with the minimal version is described in the
``requirement.txt`` at the top level of the source package.

Quickstart
==========

For operation, you need to start the device server, which is called ``PumpServer`` and subsequently connect to this server with a client. 
The first connected client needs to configure the server.

For a single computer, which operates as server and client, it is sufficient to use Tango without a running database.
*pyPSDrive* provides the function ``psdrive.start_server_fromFile`` to start the server as subprocess from a config file.
The example file ``nodb_configuration_nodevices.yml`` can found under ``/examples/nodb_configuration_nodevices.yml``.
Using this configuration, you can start a server and a ``PumpClient`` ``client`` like this:

.. code-block:: python
    
    import psdrive as psd
    psd.start_server_fromFile("nodb_configuration_nodevices.yml")
    client = psd.fromFile("nodb_configuration_nodevices.yml")

.. note:: 

    You might have to change the serial port in the config file according to your hardware.


The call of ``psdrive.fromFile`` does multiple things:

#. Searches for the device server specified in ``nodb_configuration_nodevices.yml`` and connects to it.
#. Instructs the server to open the serial port specified in the config file.
#. The server searches for devices on the serial bus).
#. Configures the devices on the bus, if a configuration is given in the config file.
#. Generates device proxies for the configured devices.
#. Stores the config file on the device server.

If this returns successfully, you can use all functions exposed in ``PumpClient``.
For example, to check which devices are on the bus you can use the functions ``PumpClient.deviceIds``, 
``PumpClient.syringePumpIds`` and ``PumpClient.valvePositionerIds``.
Or to get the device status, use ``PumpClient.deviceStatus``.

This interface, however, doesn't provide any abstractions like conversion of motor steps to liquid volume.
For this, you should use the High-level device API in ``psdrive.device``, which you can access through ``PumpClient.getSyringe`` and ``PumpClient.getValve`` after the devices have been configured.
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
- the version of the device (here: ``PSD4_smooth``, this should be a class in the ``device`` module)
- The type of the attached valve (``3-way 90 degree distribution valve``)
- The maximum volume of the attached syringe (here: 12500 :math:`\mathrm{\mu L}`)

To reload the configuration you can use ``PumpClient.readConfigfile``

.. code-block:: python

    client.readConfigfile("nodb_configuration.yml")

After the settings have been applied, you can get the ``PSD4_smooth`` using

.. code-block:: python

    syringe_proxy = client.getSyringe(1) # provide the hardware id as argument
    
The class ``PSD4_smooth`` is a subclass of ``Syringe``, which provides a simple, pythonic interface for scripting of actions:

Examples of Syringe operation
=============================

First initialize the syringe (see ``Syringe.initSyringe``) with valve position at 
``'Waste'`` (This position must be configured in the ``valve alias`` section :ref:`above <configshort>` )
and 200 :math:`\mathrm{\mu L / s}`:

.. code-block:: python

    syringe_proxy.initSyringe('Waste', 200)
    syringe_proxy.join() # wait for the move to be completed

You can change the absolute position of the syringe with the liquid flow rate stored in ``Syringe.rate`` like this:

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
    
Dispense 1000 :math:`\mathrm{\mu L }` liquid with 100 :math:`\mathrm{\mu L / s}` into ``'Cell'``.

.. code-block:: python

    syringe_proxy.dispense(1000, 100, 'Cell')
    
Pick up 1000 :math:`\mathrm{\mu L }` liquid with 100 :math:`\mathrm{\mu L / s}` from ``'Reservoir'``, wait 2 s, then change speed to 50 :math:`\mathrm{\mu L / s}` 
and wait until the syringe stops. 

.. code-block:: python

    syringe_proxy.pickup(1000, 100, 'Reservoir')
    time.sleep(2)
    syringe_proxy.rate = 50
    syringe_proxy.join()

Change valve position (if valve alias 'Reservoir' is registered using the config file above,\
``Valve.config`` or ``Valve.setValvePosName``):

.. code-block:: python

    syringe_proxy.valve = 'Reservoir' # move the valve to position 'Reservoir'

If no valve alias is registered, you can also always directly use hardware position ids:

.. code-block:: python

    syringe_proxy.valve = 1 # move valve to numerical position 1

To stop any movement of the device:

.. code-block:: python

    syringe_proxy.stop()
