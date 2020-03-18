===============================
kerasltiprovider
===============================

.. image:: https://travis-ci.com/into-ai/kerasltiprovider.svg?branch=master
        :target: https://travis-ci.com/into-ai/kerasltiprovider
        :alt: Build Status

.. image:: https://img.shields.io/pypi/v/kerasltiprovider.svg
        :target: https://pypi.python.org/pypi/kerasltiprovider
        :alt: PyPI version

.. image:: https://img.shields.io/github/license/into-ai/kerasltiprovider
        :target: https://github.com/into-ai/kerasltiprovider
        :alt: License

.. image:: https://readthedocs.org/projects/kerasltiprovider/badge/?version=latest
        :target: https://kerasltiprovider.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://codecov.io/gh/into-ai/kerasltiprovider/branch/master/graph/badge.svg
        :target: https://codecov.io/gh/into-ai/kerasltiprovider
        :alt: Test Coverage

""""""""

Your short description here. `into-ai.github.io/kerasltiprovider <https://into-ai.github.io/kerasltiprovider>`_

.. code-block:: console

    $ pip install kerasltiprovider

See the `official documentation`_ for more information.

.. _official documentation: https://kerasltiprovider.readthedocs.io

.. code-block:: python

    import kerasltiprovider

Development
-----------

To get a development instance up and running quickly, run::

    $ FLASK_SECRET_KEY=123 ASSIGNMENTS_PY_CONFIG=$(realpath ./examples/sample_assignments.py) ENABLE_DEBUG_LAUNCHER=True PRODUCTION=False CONSUMER_KEY_SECRET=123=test python serve.py

For detailed instructions see `CONTRIBUTING <CONTRIBUTING.rst>`_.

Tests
~~~~~~~
You can run tests with

.. code-block:: console

    $ invoke test
    $ invoke test --min-coverage=90     # Fail when code coverage is below 90%
    $ invoke type-check                 # Run mypy type checks

Linting and formatting
~~~~~~~~~~~~~~~~~~~~~~~~
Lint and format the code with

.. code-block:: console

    $ invoke format
    $ invoke lint

All of this happens when you run ``invoke pre-commit``.

Note
-----

This project is still in the alpha stage and should not be considered production ready.
