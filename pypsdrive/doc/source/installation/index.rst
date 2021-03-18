############
Installation
############
This page shows you how to install pyPSDrive.

The latest Windows binaries can be downloaded :download:`here <binaries/PumpServer.zip>`. These only allow starting of a device server and a simple command line interface.

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
