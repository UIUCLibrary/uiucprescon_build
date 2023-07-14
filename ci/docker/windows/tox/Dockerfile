# escape=`
ARG VS_INSTALL_PATH="C:\BuildTools\"
ARG PIP_EXTRA_INDEX_URL
ARG PIP_INDEX_URL
ARG FROM_IMAGE=mcr.microsoft.com/dotnet/framework/sdk:4.8-windowsservercore-ltsc2019
FROM ${FROM_IMAGE} as certsgen
RUN certutil -generateSSTFromWU roots.sst

FROM ${FROM_IMAGE} as BASE_BUILDER

SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop';"]

COPY ci/docker/windows/tox/msvc/startup.bat c:/startup/startup.bat
ARG VS_INSTALL_PATH
RUN Invoke-WebRequest https://aka.ms/vs/17/release/vs_buildtools.exe -OutFile vs_buildtools.exe ; `
    Write-Host \"Installing Visual Studio Build Tools to ${Env:VS_INSTALL_PATH}\" ; `
    $ARGS_LIST = @(`
        '--quiet', `
        '--wait', `
        '--norestart', `
        '--nocache', `
        '--installPath', `
         ${Env:VS_INSTALL_PATH},`
        '--add Microsoft.VisualStudio.Workload.VCTools', `
        '--add Microsoft.VisualStudio.Component.VC.CLI.Support', `
        '--add Microsoft.VisualStudio.Component.VC.CoreBuildTools', `
        '--add Microsoft.VisualStudio.Component.VC.Tools.x86.x64', `
        '--add Microsoft.VisualStudio.ComponentGroup.VC.Tools.142.x86.x64', `
        '--add Microsoft.VisualStudio.Component.Windows10SDK.18362', `
        '--remove Microsoft.VisualStudio.Component.Windows10SDK.10240',`
        '--remove Microsoft.VisualStudio.Component.Windows10SDK.10586', `
        '--remove Microsoft.VisualStudio.Component.Windows10SDK.14393', `
        '--remove Microsoft.VisualStudio.Component.Windows81SDK'`
        ) ;`
    $process = Start-Process -NoNewWindow -PassThru -FilePath vs_buildtools.exe  `
    -ArgumentList $ARGS_LIST -Wait  ; `
    if ( $process.ExitCode -eq 0) `
    { `
        Write-Host 'Installing Visual Studio Build Tools - Done' ; `
    } `
    else `
    { `
        Get-ChildItem c:\\ ; `
        Get-ChildItem ${Env:ProgramFiles(x86)} ; `
        Get-ChildItem ${Env:VS_INSTALL_PATH} ; `
        Get-ChildItem ${Env:VS_INSTALL_PATH}\\Common7\\Tools ; `
        $message = \"Installing Visual Studio Build Tools exited with code $($process.ExitCode) \"; `
        Write-Host $message ;  `
        throw 'unable to continue' ; `
    } ; `
    Write-Host 'Testing for VsDevCmd.bat' ; `
    if (! (Test-Path "${Env:VS_INSTALL_PATH}\Common7\Tools\VsDevCmd.bat")) `
    { `
        Write-Host 'Testing for VsDevCmd.bat - Failed' ; `
        Start-Process -NoNewWindow -FilePath $Env:TEMP\\collect.exe -ArgumentList '-nologo -zip:${Env:TEMP}\\vslogs.zip' -Wait; `
        if (! (Test-Path '${Env:TEMP}\\vslogs.zip')) `
        { `
            throw 'VsDevCmd.bat not found and ${Env:TEMP}\\vslogs.zip never generated' ; `
        } ; `
        Expand-Archive -Path vslogs.zip -DestinationPath $Env:TEMP\\logs\\ ; `
        Get-Content -LiteralPath '$Env:TEMP\\logs\\[Content_Types].xml' ; `
        throw 'VsDevCmd.bat not found' ; `
    } ; `
    Write-Host "Testing for VsDevCmd.bat - Found" ; `
    Write-Host "Setting up compiler environment to run every time a command is run from CMD" ; `
    Set-ItemProperty -Path 'HKLM:\Software\Microsoft\Command Processor' -Name 'AutoRun' -Value "c:\startup\startup.bat" ; `
    Write-Host "Testing for CL" ; `
    cmd /S /C where cl ; `
    Write-Host "Testing for CL - Success"; `
    Write-Host "Removing build tools installer" ; `
    Remove-Item vs_buildtools.exe ; `
    Write-Host "Removing build tools installer - Done" ; `
    Write-Host "Finished installing Visual Studio Build Tools"

ARG CHOCOLATEY_SOURCE=https://chocolatey.org/api/v2
ARG ChocolateyEnvironmentDebug=false
COPY ci/docker/windows/tox/chocolatey/install_choco.ps1 choco/install_choco.ps1
RUN Set-ExecutionPolicy Bypass -Scope Process -Force; `
    ./choco/install_choco.ps1 ; `
    if( -not ([string]::IsNullOrEmpty($Env:CHOCOLATEY_SOURCE ))) `
    { `
        Write-Host "Adding $env:CHOCOLATEY_SOURCE to chocolatey sources" ; `
        choco source add -n=CHOCOLATEY_SOURCE --priority=1 -s=\"$env:CHOCOLATEY_SOURCE\"; `
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
ENV PIP_EXTRA_INDEX_URL=${PIP_EXTRA_INDEX_URL}
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
WORKDIR C:/src
CMD tox --workdir ${Env:TEMP}\tox\ -vv  --recreate -p=auto
