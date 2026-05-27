# escape=`
ARG FROM_IMAGE=mcr.microsoft.com/dotnet/framework/sdk:4.8.1

ARG VS_INSTALL_PATH="C:\BuildTools"

ARG PIP_EXTRA_INDEX_URL
ARG PIP_INDEX_URL

ARG CONAN_USER_HOME=C:/Users/ContainerAdministrator
# Path where conan data will be stored

ARG CONAN_HOME=${CONAN_USER_HOME}/.conan2

ARG CONAN_CENTER_PROXY_V2_URL=https://center2.conan.io
# If you want to use a diffrent remote for Conan, such as a proxy. Set the CONAN_CENTER_PROXY_V2_URL
# Not this is only for building the image. The actual conan center proxy URL is set in the remotes.json file.

FROM ${FROM_IMAGE} AS certsgen
RUN certutil -generateSSTFromWU roots.sst

FROM ${FROM_IMAGE} AS BASE_BUILDER

SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop';"]

COPY ci/docker/windows/msvc/visual_studio_config.json c:/setup/config.vsconfig
COPY ci/docker/windows/msvc/install_msvc.ps1 c:/scripts/install_msvc.ps1
ARG VS_INSTALL_PATH
ARG VS_VERSION="2022"
ARG VS_DevCmdArguments="-arch=amd64"
ARG VS_DevPowershellArguments='-arch=amd64'

RUN c:/scripts/install_msvc.ps1 -InstallPath ${Env:VS_INSTALL_PATH} -VSConfigFile c:/setup/config.vsconfig -DevCmdArguments ${Env:VS_DevCmdArguments} -DevPowershellArguments ${Env:VS_DevPowershellArguments} -VSVersion ${Env:VS_VERSION}; `
    Write-Host "Note: Exporting This layer can take a while."
COPY ci/docker/windows/scoop c:/scoopinstall
RUN irm get.scoop.sh -outfile 'install.ps1' ; `
    .\install.ps1 -RunAsAdmin ; `
    Remove-Item -Path ".\install.ps1" ; `
    scoop install git ; `
    scoop bucket add versions ; `
    scoop import c:/scoopinstall/scoopfile.json ; `
    uv python update-shell ; `
    scoop cache show ; `
    Write-Host "Cleaning up cache" ;`
    scoop cache clean ; `
    Write-Host "Cleaning up cache - Done" ;`
    Write-Host "Verifying installed packages" ;`
    c:/scoopinstall/verifyenv.ps1 ;`
    Write-Host "Verifying installed packages - Done"

RUN uv python update-shell

FROM BASE_BUILDER AS CONAN_BUILDER
ARG UV_EXTRA_INDEX_URL
ARG UV_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PIP_INDEX_URL
ARG CONAN_HOME
COPY ci/docker/shared/conan/remotes.json  ${CONAN_HOME}/remotes.json
COPY ci/docker/windows/conan/profile.ini ${CONAN_HOME}/profiles/default
COPY tests/test_files/zstd_from_conan/conanfile.py c:/tests/test_files/zstd_from_conan/conanfile.py
ARG CONAN_CENTER_PROXY_V2_URL
RUN uvx --with cmake --with ninja conan profile detect --exist-ok ; `
    $conanCenterUrl = (((Get-Content -Raw -Path ${Env:CONAN_HOME}\remotes.json) | ConvertFrom-Json).remotes[0].url);`
    if (${env:CONAN_CENTER_PROXY_V2_URL} -ne ${conanCenterUrl}) { `
      Write-Host "Using a proxy for conan center: $Env:CONAN_CENTER_PROXY_V2_URL" ; `
      Copy-Item -Path "${Env:CONAN_HOME}\remotes.json" -Destination "c:\remotes.json" ; `
      uvx --with cmake --with ninja conan remote update conan-center --url ${env:CONAN_CENTER_PROXY_V2_URL}; `
    }; `
    uvx --with cmake --with ninja conan install c:/tests/test_files/zstd_from_conan/conanfile.py --build=missing -pr:b=default ; `
    if ($LASTEXITCODE -ne 0) { `
      throw \"Command 'conan install' failed with exit code: $LASTEXITCODE\"`
    } ;`
    uvx --with cmake --with ninja conan cache clean "*" -b --source --build --temp ; `
    uv cache clean --no-progress ; `
    if (${env:CONAN_CENTER_PROXY_V2_URL} -ne ${conanCenterUrl}) { `
      Move-Item -Path "c:\remotes.json" -Destination "${Env:CONAN_HOME}\remotes.json" -Force ;`
    }
# ==============================================================================
FROM BASE_BUILDER

COPY --from=certsgen c:/roots.sst roots.sst
RUN certutil -addstore -f root roots.sst ; `
    del roots.sst

ARG CONAN_USER_HOME
ARG CONAN_HOME
COPY --from=CONAN_BUILDER ${CONAN_HOME}/ ${CONAN_HOME}/
ENV CONAN_USER_HOME=${CONAN_USER_HOME}`
    CONAN_HOME=${CONAN_HOME}
LABEL purpose=ci