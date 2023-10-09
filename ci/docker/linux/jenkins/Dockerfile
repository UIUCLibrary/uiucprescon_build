ARG CONAN_USER_HOME=/conan
ARG PIP_DOWNLOAD_CACHE=/.cache/pip

FROM ubuntu:22.04
COPY ci/docker/linux/jenkins/apt-packages.txt /tmp/
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
COPY requirements/ /tmp/requirements/requirements/
COPY requirements-ci.txt /tmp/requirements/
RUN python3 -m pip install pip --upgrade && pip install -r /tmp/requirements/requirements-ci.txt

COPY ci/docker/linux/shared/update_conan_compiler.py  /tmp/update_conan_compiler.py
ARG CONAN_USER_HOME
RUN conan config init && \
    conan config set general.revisions_enabled=1 && \
    conan profile update settings.compiler.version=$(cc -dumpfullversion -dumpversion | grep -oE  "^([0-9]+(\.)?)([0-9]+?)") default && \
    python3 /tmp/update_conan_compiler.py ${CONAN_USER_HOME}/.conan/settings.yml gcc $(cc -dumpfullversion -dumpversion | grep -oE  "^([0-9]+(\.)?)([0-9]+?)")
ENV CONAN_USER_HOME=${CONAN_USER_HOME}