PyBirch Database Documentation
==============================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   getting_started
   architecture
   models
   services
   web_interface
   api_reference
   contributing

PyBirch Database is a comprehensive laboratory data management system designed 
for tracking samples, equipment, procedures, and measurements in research environments.

Features
--------

* **Sample Management** - Track physical samples with full fabrication history
* **Equipment Registry** - Manage lab equipment, instruments, and maintenance
* **Procedure Library** - Version-controlled fabrication and measurement procedures
* **Project Organization** - Group resources by lab and project
* **Scan Integration** - Native integration with PyBirch measurement system
* **Issue Tracking** - Built-in bug reports and equipment issue management
* **Web Interface** - Flask-based UI for browsing and managing data
* **OAuth Authentication** - Google OAuth support for secure access

Quick Start
-----------

Start the web server::

    cd database
    python run_web.py

Then visit http://127.0.0.1:5000 in your browser.

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
