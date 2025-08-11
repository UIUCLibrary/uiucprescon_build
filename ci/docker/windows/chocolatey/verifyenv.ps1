
if (!(Test-Path 'C:\Program Files\Git\cmd\git.exe'))
{
    throw 'git.exe not found' ; `
}
Write-Host "Finished install packages with Chocolatey"