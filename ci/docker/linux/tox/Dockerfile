ARG CONAN_USER_HOME=/conan
ARG PIP_DOWNLOAD_CACHE=/.cache/pip
FROM ubuntu:22.04
COPY ci/docker/linux/tox/apt-packages.txt /tmp/
RUN apt-get update && \
    apt-get install -y software-properties-common gpg-agent --no-install-recommends && \
    add-apt-repository ppa:deadsnakes/ppa && \
    DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get -y install tzdata && \
    apt-get update && \
     < /tmp/apt-packages.txt xargs apt-get install -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ARG PIP_EXTRA_INDEX_URL
ARG PIP_INDEX_URL
COPY requirements-ci.txt /tmp/python_requirements/
COPY requirements/ /tmp/python_requirements/requirements/
RUN python3 -m pip install pip --upgrade && pip3 install -r /tmp/python_requirements/requirements-ci.txt

ARG PIP_DOWNLOAD_CACHE
RUN mkdir -p ${PIP_DOWNLOAD_CACHE} && \
    chmod -R 777 ${PIP_DOWNLOAD_CACHE}
ENV PIP_DOWNLOAD_CACHE=${PIP_DOWNLOAD_CACHE}

COPY ci/docker/linux/shared/update_conan_compiler.py  /tmp/update_conan_compiler.py
ARG CONAN_USER_HOME
RUN conan config init && \
    conan config set general.revisions_enabled=1 && \
    conan profile update settings.compiler.version=$(cc -dumpfullversion -dumpversion | grep -oE  "^([0-9]+(\.)?)([0-9]+?)") default && \
    python3 /tmp/update_conan_compiler.py ${CONAN_USER_HOME}/.conan/settings.yml gcc $(cc -dumpfullversion -dumpversion | grep -oE  "^([0-9]+(\.)?)([0-9]+?)")
ENV CONAN_USER_HOME=${CONAN_USER_HOME}

WORKDIR /src
CMD tox --workdir /tmp/tox --recreate
