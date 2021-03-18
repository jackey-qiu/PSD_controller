.. _api_psdrive:

#############
API Reference
#############

Rules for this API:

- Commands are non-blocking by default. If a command blocks, it must be noted in the documentation.
- But commands are send synchronously to the server by default.
  I.e. it waits until the network communication was completed and waits for the device answer.  
  A command, which consist of multiple requests might be split into multiple asynchronous requests,
  but at the end it must be synchronized.

Due to some hardware limitations (presumably bugs), errors are often not passed from the hardware devices to the controlling server. 
This library aims to recognize these faulty commands and raises python errors in this case.

Module overview:

.. toctree::
   :maxdepth: 1
   
   device.rst
   operations.rst
   PumpInterface.rst

:mod:`psdrive`: Top level functions
-----------------------------------

.. automodule:: psdrive.__init__
    :members:

