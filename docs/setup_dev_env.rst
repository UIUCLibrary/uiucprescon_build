==============================
Set up Development Environment
==============================

This document provides instructions for setting up the build environment for the project. It includes details on required tools, dependencies, and configuration steps.

You can use pip but UV is recommended because it is significantly faster.

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

This will configure your development environment with all necessary dependencies.