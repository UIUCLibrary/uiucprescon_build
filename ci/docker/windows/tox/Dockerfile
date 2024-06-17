# escape=`
ARG PIPX_HOME=c:\pipx
ARG VS_INSTALL_PATH="C:\BuildTools"
ARG PIP_EXTRA_INDEX_URL
ARG PIP_INDEX_URL
ARG FROM_IMAGE=mcr.microsoft.com/dotnet/framework/sdk:4.8-windowsservercore-ltsc2019
FROM ${FROM_IMAGE} as certsgen
RUN certutil -generateSSTFromWU roots.sst

FROM ${FROM_IMAGE} as BASE_BUILDER

SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop';"]

COPY ci/docker/windows/tox/msvc/startup.bat c:/startup/startup.bat
COPY ci/docker/windows/tox/msvc/visual_studio_config.json c:/setup/config.vsconfig
COPY ci/docker/windows/tox/msvc/install_msvc.ps1 c:/scripts/install_msvc.ps1
ARG VS_INSTALL_PATH

RUN c:/scripts/install_msvc.ps1 ${Env:VS_INSTALL_PATH} c:/setup/config.vsconfig; `
    Get-ChildItem C:\Users\ContainerAdministrator\AppData\Local\Temp | Remove-Item -Recurse -Force -Verbose
ARG CHOCOLATEY_SOURCE=https://chocolatey.org/api/v2
ARG ChocolateyEnvironmentDebug=false
ARG chocolateyVersion
COPY ci/docker/windows/tox/chocolatey/install.ps1 c:/choco/install.ps1
COPY ci/docker/windows/tox/chocolatey/get_latest_chocolatey_url.ps1 c:/choco/get_latest_chocolatey_url.ps1
RUN Set-ExecutionPolicy Bypass -Scope Process -Force; `
    $chocolateyDownloadUrl = c:/choco/get_latest_chocolatey_url.ps1 -packageRepo $env:CHOCOLATEY_SOURCE; `
    c:/choco/install.ps1 -ChocolateyDownloadUrl $chocolateyDownloadUrl;`
    if( -not ([string]::IsNullOrEmpty($Env:CHOCOLATEY_SOURCE ))) `
    { `
        Write-Host "Adding $env:CHOCOLATEY_SOURCE to chocolatey sources" ; `
        choco source add -n=CHOCOLATEY_SOURCE --priority=1 -s=\"${env:CHOCOLATEY_SOURCE}\"; `
    }; `
    Write-Host "Disabling Showing Download Progress" ; `
    choco feature disable -n=showDownloadProgress ; `
    Remove-Item -Force -Recurse ${Env:TEMP}\*


ADD ci/docker/windows/tox/chocolatey/python.xml choco/python.config
RUN C:\ProgramData\chocolatey\bin\choco.exe install -y --stoponfirstfailure --no-progress --verbose choco/python.config ;`
    Remove-Item C:\Users\ContainerAdministrator\AppData\Local\Temp\chocolatey -Recurse ; `
    refreshenv ; `
    Remove-Item -Force -Recurse ${Env:TEMP}\* ; `
    py --list ;`
    Write-Host "Installing Python with Chocolatey - Done"

ADD ci/docker/windows/tox/chocolatey/packages.xml choco/packages.config
RUN C:\ProgramData\chocolatey\bin\choco.exe sources ; `
    C:\ProgramData\chocolatey\bin\choco.exe install -y --stoponfirstfailure --no-progress --verbose choco/packages.config ;`
    Remove-Item C:\Users\ContainerAdministrator\AppData\Local\Temp\chocolatey -Recurse ; `
    refreshenv ; `
    Remove-Item -Force -Recurse ${Env:TEMP}\* ; `
    if (!(Test-Path 'C:\Program Files\Git\cmd\git.exe')) `
    { `
        throw 'git.exe not found' ; `
    }; `
    Write-Host "Finished install packages with Chocolatey"

# ==============================================================================
#
FROM BASE_BUILDER
COPY --from=certsgen c:/roots.sst roots.sst
RUN certutil -addstore -f root roots.sst ; `
    del roots.sst
ARG PIP_EXTRA_INDEX_URL
ARG PIP_INDEX_URL
SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop';"]

COPY requirements-ci.txt c:/python_requirements/
COPY requirements/ c:/python_requirements/requirements
RUN python -m pip install pip --upgrade ; `
    pip install wheel ; `
    pip install -r c:\python_requirements\requirements-ci.txt

ARG PIPX_HOME
ENV PIPX_HOME=${PIPX_HOME}
ENV PIPX_BIN_DIR=${PIPX_HOME}\bin


RUN py -3 -m pip install --no-cache-dir pipx ; `
    py -3 -m pipx ensurepath
RUN py -3 -m pipx install 'devpi-client<7.0'

ENV PIP_EXTRA_INDEX_URL=${PIP_EXTRA_INDEX_URL}
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
WORKDIR C:/src
CMD tox --workdir ${Env:TEMP}\tox\ -vv  --recreate -p=auto
