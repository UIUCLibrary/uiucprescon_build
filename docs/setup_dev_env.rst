===========
Development
===========

This document provides instructions for setting up the build environment for the project and performing recommend
development practices.

Set up Development Environment
==============================

You can use pip but `UV <https://docs.astral.sh/uv/>`_ is recommended because it is significantly faster.

1) Clone the repository and change to the project directory:

   .. code-block:: shell-session

      devuser@mylaptop ~ % git clone https://github.com/UIUCLibrary/uiucprescon_build.git
      devuser@mylaptop ~ % cd uiucprescon_build

3) Create a virtual environment and activate it.

    On Linux or macOS it should look like this:

    .. code-block:: shell-session

      devuser@mylaptop ~ % python -m venv venv
      devuser@mylaptop ~ % source venv/bin/activate


    On Windows it should look like this:

    .. code-block:: doscon

      C:\Users\devuser>python -m venv venv
      C:\Users\devuser>venv\Scripts\activate.bat

4) Install the required development packages using pip or UV. If you are using UV, you can run:

    .. code-block:: shell-session

      (venv) devuser@mylaptop ~ % uv pip install -r requirements-dev.txt

    If you are using pip, you can run:

    .. code-block:: shell-session

      (venv) devuser@mylaptop ~ % pip install -r requirements-dev.txt


5) Install the project in editable mode:

    .. code-block:: shell-session

      (venv) devuser@mylaptop ~ % uv pip install -e .

    or with pip:

    .. code-block:: shell-session

      (venv) devuser@mylaptop ~ % pip install -e .

This will configure your development environment with all necessary dependencies.

6) Add `pre-commit hooks <https://pre-commit.com>`_ for git :

    If you are using UV, you can run:

    .. code-block:: shell-session

      (venv) devuser@mylaptop ~ % uvx pre-commit install

    Otherwise, if you are using pip, you will have to install the pre-commit application manually in your virtual
    environment or elsewhere:

    .. code-block:: shell-session

      (venv) devuser@mylaptop ~ % python -m pip install pre-commit
      (venv) devuser@mylaptop ~ % pre-commit install



Bumping the Version
===================

Use commitizen to bump the version of the project. This will automatically update the version in the `pyproject.toml`
file.

For a release version bump, you can run:

.. code-block:: shell-session

   (venv) devuser@mylaptop ~ % cz bump
   [main f1170a4] bump: version 0.2.6.dev16 → 0.3.0

For a beta release version bump, you can run:

.. code-block:: shell-session

   (venv) devuser@mylaptop ~ % cz bump --prerelease=beta
   [main f1170a4] bump: version 0.2.6.dev16 → 0.3.0b0

For an alpha release version bump, you can run:

.. code-block:: shell-session

   (venv) devuser@mylaptop ~ % cz bump --prerelease=alpha

To bump the version to a development version, you can run:

.. code-block:: shell-session

   (venv) devuser@mylaptop ~ % cz bump --allow-no-commit --devrelease 17 --files-only
   (venv) devuser@mylaptop ~ % git commit -m "Next iteration"


.. important:: Do not push a release version to the HEAD!

    **Make sure before you push changes to the repository**, the version metadata
    for the last commit is a development version (i.e. it should end in dev
    followed by a number).

    After bumping the version version, the last commit should not be something
    like 0.1.8.

    It should be something like 0.1.9.dev0.
