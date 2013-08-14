#ps1

$WindowsAgentConfigBase64 = '%WINDOWS_AGENT_CONFIG_BASE64%'
$WindowsAgentConfigFile = "C:\Murano\Agent\WindowsAgent.exe.config"
$WindowsAgentLogFile = "C:\Murano\Agent\log.txt"

$NewComputerName = '%INTERNAL_HOSTNAME%'
$MuranoFileShare = '\\%MURANO_SERVER_ADDRESS%\share'

$RestartRequired = $false

Import-Module CoreFunctions
Initialize-Logger 'CloudBase-Init' 'C:\Murano\PowerShell.log'

$ErrorActionPreference = 'Stop'

trap {
    Write-LogError '<exception>'
	Write-LogError $_ -EntireObject
	Write-LogError '</exception>'
	exit 1
}

Write-Log "Updating Murano Windows Agent."
Stop-Service "Murano Agent"
Backup-File $WindowsAgentConfigFile
Remove-Item $WindowsAgentConfigFile -Force
Remove-Item $WindowsAgentLogFile -Force
ConvertFrom-Base64String -Base64String $WindowsAgentConfigBase64 -Path $WindowsAgentConfigFile
Exec sc.exe 'config','"Murano Agent"','start=','delayed-auto'
Write-Log "Service has been updated."

Write-Log "Adding environment variable 'MuranoFileShare' = '$MuranoFileShare' ..."
[Environment]::SetEnvironmentVariable('MuranoFileShare', $MuranoFileShare, [EnvironmentVariableTarget]::Machine)
Write-Log "Environment variable added."

Write-Log "Renaming computer to '$NewComputerName' ..."
$null = Rename-Computer -NewName $NewComputerName -Force

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
