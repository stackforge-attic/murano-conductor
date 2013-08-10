Function Set-LocalUserPassword {
    param (
        [String] $UserName,
        [String] $Password,
        [Switch] $Force
    )
    
    trap { Stop-Execution $_ }
    
    if ((Get-WmiObject Win32_UserAccount -Filter "LocalAccount = 'True' AND Name='$UserName'") -eq $null) {
        throw "Unable to find local user account '$UserName'"
    }
    
    if ($Force) {
        Write-Log "Changing password for user '$UserName' to '*****'" # :)
        ([ADSI] "WinNT://./$UserName").SetPassword($Password)
    }
    else {
        Write-LogWarning "You are trying to change password for user '$UserName'. To do this please run the command again with -Force parameter."
        $UserAccount
    }
}

