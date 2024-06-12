param (
    [Parameter(Mandatory=$true)][String]$InstallPath,
    [String]$VsbuildtoolsURL='https://aka.ms/vs/17/release/vs_buildtools.exe'

)

function TestInstalledProperty ($VS_INSTALL_PATH) {
    Write-Host 'Testing for VsDevCmd.bat'
    if (! (Test-Path "${VS_INSTALL_PATH}\Common7\Tools\VsDevCmd.bat"))
    {
        Write-Host 'Testing for VsDevCmd.bat - Failed'
        Start-Process -NoNewWindow -FilePath ${Env:TEMP}\collect.exe -ArgumentList "-nologo -zip:${Env:TEMP}\vslogs.zip" -Wait
        if (! (Test-Path "${Env:TEMP}\vslogs.zip"))
        {
            throw "VsDevCmd.bat not found and ${Env:TEMP}\vslogs.zip never generated"
        }
        Expand-Archive -Path vslogs.zip -DestinationPath ${Env:TEMP}\logs\
        Get-Content -LiteralPath "${Env:TEMP}\logs\[Content_Types].xml"
        throw 'VsDevCmd.bat not found'
    }

    Write-Host "Testing for VsDevCmd.bat - Found"
    Write-Host "Setting up compiler environment to run every time a command is run from CMD"
    Set-ItemProperty -Path 'HKLM:\Software\Microsoft\Command Processor' -Name 'AutoRun' -Value "c:\startup\startup.bat"
    Write-Host "Testing for CL"
    cmd /S /C where cl
    Write-Host "Testing for CL - Success"
    Write-Host "Removing build tools installer"
    Remove-Item vs_buildtools.exe
    Write-Host "Removing build tools installer - Done"
    Write-Host "Finished installing Visual Studio Build Tools"
}
function InstallMSVC ($VS_INSTALL_PATH) {
    Invoke-WebRequest $VsbuildtoolsURL -OutFile vs_buildtools.exe
    Write-Host "Installing Visual Studio Build Tools to ${VS_INSTALL_PATH}"
    $ARGS_LIST = @(`
        '--quiet', `
        '--wait', `
        '--norestart', `
        '--nocache', `
        '--installPath', `
         ${VS_INSTALL_PATH},`
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
    )
    $process = Start-Process -NoNewWindow -PassThru -FilePath vs_buildtools.exe  -ArgumentList $ARGS_LIST -Wait

    if ( $process.ExitCode -eq 0) {
        Write-Host 'Installing Visual Studio Build Tools - Done'
    } else {
        Get-ChildItem c:\
        Get-ChildItem ${Env:ProgramFiles(x86)}
        Get-ChildItem ${VS_INSTALL_PATH}
        Get-ChildItem ${VS_INSTALL_PATH}\Common7\Tools
        $message = "Installing Visual Studio Build Tools exited with code $($process.ExitCode)"
        Write-Host $message
        throw 'unable to continue'
    }
}
InstallMSVC $InstallPath

TestInstalledProperty $InstallPath
