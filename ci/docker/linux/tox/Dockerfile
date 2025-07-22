
ARG UV_CACHE_DIR=/.cache/uv
# UV Cache directory. Change this only if you need to override the default location.

ARG CONAN_CENTER_PROXY_V2_URL=https://center2.conan.io
# If you want to use a diffrent remote for Conan, such as a proxy. Set the CONAN_CENTER_PROXY_V2_URL
# Not this is only for building the image. The actual conan center proxy URL is set in the remotes.json file.

ARG CONAN_USER_HOME=/conan
ARG CONAN_HOME=${CONAN_USER_HOME}/.conan2
ARG PIPX_HOME=/pipx
ARG PIP_DOWNLOAD_CACHE=/.cache/pip
FROM ubuntu:22.04 AS base
COPY ci/docker/linux/tox/apt-packages.txt /tmp/
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

FROM base AS conan_builder
ARG CONAN_USER_HOME
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && \
    apt-get install -y --no-install-recommends jq && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
COPY requirements-dev.txt /tmp/requirements/requirements-dev.txt
ARG CONAN_CENTER_PROXY_V2_URL
ARG CONAN_HOME
ARG PIP_DOWNLOAD_CACHE
ARG UV_CACHE_DIR
COPY ci/docker/shared/conan/remotes.json  ${CONAN_HOME}/remotes.json
COPY tests/conan_test_libraries.json /tests/conan_test_libraries.json
COPY ci/docker/linux/tox/conan/profile.ini ${CONAN_HOME}/profiles/default
ENV UV_CONSTRAINT=/tmp/requirements/requirements-dev.txt
RUN --mount=type=cache,target=${PIP_DOWNLOAD_CACHE},sharing=locked \
    --mount=type=cache,target=${UV_CACHE_DIR},sharing=locked \
    python3 -m venv venv && \
    ./venv/bin/pip --disable-pip-version-check install uv && \
    ./venv/bin/uvx --with cmake conan profile detect --exist-ok &&  \
    if [ "$(jq -r '.remotes[0].url' ${CONAN_HOME}/remotes.json )" != "${CONAN_CENTER_PROXY_V2_URL}" ]; then \
        echo "Setting the conan center url for building cache: ${CONAN_CENTER_PROXY_V2_URL}" && \
        cp ${CONAN_HOME}/remotes.json /tmp/remotes.json && \
        ./venv/bin/uvx --with cmake conan remote update conan-center --url ${CONAN_CENTER_PROXY_V2_URL}; \
    fi && \
    requires_string=$(jq -r '.conan_test_libraries."2".zstd.requires[] | "--requires=\(.)"' /tests/conan_test_libraries.json | paste -sd' ' -) && \
    options_string=$(jq -r '.conan_test_libraries."2".zstd.default_options | to_entries[] | "--options=\(.key)=\(.value)"' /tests/conan_test_libraries.json | paste -sd' ' -) && \
    ./venv/bin/uvx --with cmake conan install $requires_string $options_string --build=missing && \
    ./venv/bin/uvx --with cmake conan cache clean "*" -b --source --build --temp && \
    if [ "$(jq -r '.remotes[0].url' ${CONAN_HOME}/remotes.json )" != "${CONAN_CENTER_PROXY_V2_URL}" ]; then \
      mv -f /tmp/remotes.json ${CONAN_HOME}/remotes.json; \
    fi && \
    rm -rf venv

FROM base
ARG PIP_EXTRA_INDEX_URL
ARG PIP_INDEX_URL

ARG PIP_DOWNLOAD_CACHE
RUN mkdir -p ${PIP_DOWNLOAD_CACHE} && \
    chmod -R 777 ${PIP_DOWNLOAD_CACHE}
ENV PIP_DOWNLOAD_CACHE=${PIP_DOWNLOAD_CACHE}

ARG CONAN_USER_HOME
ARG CONAN_HOME
COPY --from=conan_builder ${CONAN_HOME}/ ${CONAN_HOME}/
ENV CONAN_USER_HOME=${CONAN_USER_HOME} \
    CONAN_HOME=${CONAN_HOME}
