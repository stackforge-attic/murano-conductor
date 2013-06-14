#ps1

$WindowsAgentConfigBase64 = '%WINDOWS_AGENT_CONFIG_BASE64%'
$WindowsAgentConfigFile = "C:\Murano\Agent\WindowsAgent.exe.config"
$WindowsAgentLogFile = "C:\Murano\Agent\log.txt"

$NewComputerName = '%INTERNAL_HOSTNAME%'
$MuranoFileShare = '%MURANO_SERVER_ADDRESS%\share'

$RestartRequired = $false

Import-Module CoreFunctions

Write-Log "Updating Murano Windows Agent."
Stop-Service "Murano Agent"
Backup-File $WindowsAgentConfigFile
Remove-Item $WindowsAgentConfigFile -Force
Remove-Item $WindowsAgentLogFile -Force
ConvertFrom-Base64String -Base64String $WindowsAgentConfigBase64 -Path $WindowsAgentConfigFile
Exec sc.exe 'config','"Murano Agent"','start=','delayed-auto'
Write-Log "Service has been updated."

Write-Log "Adding environment variable 'MuranoFileShare' ..."
[Environment]::SetEnvironmentVariable('MuranoFileShare', $MuranoFileShare, 'System')
Write-Log "Environment variable added."

Write-Log "Renaming computer ..."
Rename-Computer -NewName $NewComputerName | Out-Null
Write-Log "New name assigned, restart required."
$RestartRequired = $true


Write-Log 'All done!'
if ( $RestartRequired ) {
    Write-Log "Restarting computer ..."
    Restart-Computer -Force
}
else {
    Start-Service 'Murano Agent'
}
