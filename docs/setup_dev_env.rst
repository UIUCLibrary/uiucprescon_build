==============================
Set up Development Environment
==============================

This document provides instructions for setting up the build environment for the project. It includes details on required tools, dependencies, and configuration steps.

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


