ARG PIP_DOWNLOAD_CACHE=/.cache/pip

FROM ubuntu:22.04
COPY ci/docker/linux/jenkins/apt-packages.txt /tmp/
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && \
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
