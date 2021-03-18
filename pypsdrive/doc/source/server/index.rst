.. _startingServer:

#################################
Starting device server and client
#################################

For operation, you need to start the device server, which is called ``PumpServer`` and subsequently connect to this server with a client. 
The first connected client needs to configure the server. Clients, which connect afterwards can fetch the configuration from the server. 

Running the device server with Tango database
---------------------------------------------

If you have a Tango database running, please register the server in the database according to the `documentation <https://tango-controls.readthedocs.io/en/latest/tutorials-and-howtos/how-tos/how-to-start-device-server.html>`_ .
The server is accessible in the path. If the server is registered as ``<instance>`` you can start the server using

.. code-block:: bash

    $ PumpServer <instance>

from a terminal window. For example, if the server instance is called ``pump1`` :

.. code-block:: bash

    $ PumpServer pump1
    
This will start an unconfigured server. Configuration will be done once the client sends the corresponding command.

Running the device server without Tango database
------------------------------------------------

For this you have to manually keep track of the ports and device names used for the connections. 
A server instance ``<instance>`` on port ``<port>``, which handles the device name ``<devname>`` can be started using

.. code-block:: bash

    $ PumpServer <instance> -ORBendPoint giop:tcp::<port> -nodb -dlist <devname>

from a terminal window. For example, if the server instance is called ``pump1`` with the device ``exp/ec/pump1`` on port ``50005``: 

.. code-block:: bash

    $ PumpServer pump1 -ORBendPoint giop:tcp::50005 -nodb -dlist exp/ec/pump1

This will start an unconfigured server. Configuration will be done once the client sends the corresponding command.

Connection of a client and server configuration
-----------------------------------------------

It is recommended to first generate a configuration file with the device configuration. 
Each server requires its own configuration file. Details on the device configuration can be found in :doc:`Configuration`.
A simple configuration file for a single computer ``localhost`` without database with no devices attached can be downloaded :download:`here <../../../examples/nodb_configuration_nodevices.yml>`.  

If the device configuration is stored in ``./configuration.yml``, you can start the client from a python shell with

.. code-block:: python

    import psdrive as psd
    client = psd.fromFile("./configuration.yml")

This will send a command to the server to open the serial port specified in ``./configuration.yml`` and scan for the devices on this serial port. This can take a few seconds.
Will also save the contents of ``./configuration.yml`` on the server.

Another call to ``psd.fromFile`` will not reconfigure the server, but will just connect to the server specified in ``./configuration.yml``. 
To reconfigure the device server from a config file, call :meth:`~psdrive.PumpInterface.PumpClient.readConfigfile`.

.. _connectClientNoDb:

Connection of a client without config file
------------------------------------------

It is possible to just connect to a configured device server and fetch the configuration from the server with

.. code-block:: python

    import psdrive as psd
    client = psd.connect("<devname>")

if a Tango database is available, or

.. code-block:: python

    import psdrive as psd
    client = psd.connect("<hostname>:<port>/<devname>#dbase=no")
    
if no database is available.




