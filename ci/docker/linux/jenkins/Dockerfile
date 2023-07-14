FROM ubuntu:20.04
COPY ci/docker/linux/jenkins/apt-packages.txt /tmp/
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    < /tmp/apt-packages.txt xargs apt-get install -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
ARG PIP_EXTRA_INDEX_URL
ARG PIP_INDEX_URL
COPY requirements/ /tmp/requirements/requirements/
COPY requirements-ci.txt /tmp/requirements/
RUN python3 -m pip install pip --upgrade && pip install -r /tmp/requirements/requirements-ci.txt
