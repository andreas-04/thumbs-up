; ThumbsUp Client NSIS Installer Script
; Creates a Windows installer with NFS client feature enablement

!include "MUI2.nsh"
!include "LogicLib.nsh"

; Installer attributes
Name "ThumbsUp Client"
OutFile "dist\ThumbsUp-Client-Setup.exe"
InstallDir "$PROGRAMFILES64\ThumbsUp Client"
InstallDirRegKey HKLM "Software\ThumbsUp\Client" "InstallDir"
RequestExecutionLevel admin

; Version information
VIProductVersion "0.0.0.0"
VIAddVersionKey "ProductName" "ThumbsUp Client"
VIAddVersionKey "FileVersion" "0.0.0"
VIAddVersionKey "ProductVersion" "0.0.0"
VIAddVersionKey "LegalCopyright" "MIT License"
VIAddVersionKey "FileDescription" "ThumbsUp Secure NAS Client"

; Interface settings
!define MUI_ABORTWARNING
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

; Pages
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Languages
!insertmacro MUI_LANGUAGE "English"

; Installer sections
Section "ThumbsUp Client" SecMain
    SetOutPath "$INSTDIR"
    
    ; Copy executable
    File "dist\thumbsup-client.exe"
    
    ; Create certificate directory
    CreateDirectory "$INSTDIR\certs"
    CreateDirectory "$APPDATA\ThumbsUp\certs"
    
    ; Create README for certificates
    FileOpen $0 "$INSTDIR\certs\README.txt" w
    FileWrite $0 "ThumbsUp Client Certificate Directory$\r$\n"
    FileWrite $0 "=====================================\$r$\n$\r$\n"
    FileWrite $0 "Place your certificate files here:$\r$\n"
    FileWrite $0 "  - client_cert.pem$\r$\n"
    FileWrite $0 "  - client_key.pem$\r$\n"
    FileWrite $0 "  - server_cert.pem$\r$\n$\r$\n"
    FileWrite $0 "Obtain these from your ThumbsUp administrator.$\r$\n"
    FileClose $0
    
    ; Add to PATH
    EnVar::SetHKLM
    EnVar::AddValue "PATH" "$INSTDIR"
    
    ; Create uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    
    ; Write registry keys
    WriteRegStr HKLM "Software\ThumbsUp\Client" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\ThumbsUp\Client" "Version" "0.0.0"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ThumbsUpClient" "DisplayName" "ThumbsUp Client"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ThumbsUpClient" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ThumbsUpClient" "DisplayVersion" "0.0.0"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ThumbsUpClient" "Publisher" "ThumbsUp Project"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ThumbsUpClient" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ThumbsUpClient" "NoRepair" 1
    
    ; Enable NFS Client feature
    DetailPrint "Enabling NFS Client feature (this may take a moment)..."
    nsExec::ExecToLog 'dism.exe /Online /Enable-Feature /FeatureName:ClientForNFS-Infrastructure /All /NoRestart'
    Pop $0
    ${If} $0 == 0
        DetailPrint "NFS Client feature enabled successfully"
    ${Else}
        DetailPrint "Warning: Could not enable NFS Client feature (error code: $0)"
        DetailPrint "You may need to enable it manually in Windows Features"
    ${EndIf}
    
    ; Create Start Menu shortcuts
    CreateDirectory "$SMPROGRAMS\ThumbsUp Client"
    CreateShortcut "$SMPROGRAMS\ThumbsUp Client\ThumbsUp Client.lnk" "$INSTDIR\thumbsup-client.exe"
    CreateShortcut "$SMPROGRAMS\ThumbsUp Client\Certificate Folder.lnk" "$INSTDIR\certs"
    CreateShortcut "$SMPROGRAMS\ThumbsUp Client\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
    
    ; Show completion message
    MessageBox MB_OK "ThumbsUp Client installed successfully!$\r$\n$\r$\nNext steps:$\r$\n1. Place your certificate files in: $INSTDIR\certs\$\r$\n2. Open Command Prompt as Administrator$\r$\n3. Run: thumbsup-client"
SectionEnd

; Uninstaller section
Section "Uninstall"
    ; Remove files
    Delete "$INSTDIR\thumbsup-client.exe"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir /r "$INSTDIR\certs"
    RMDir "$INSTDIR"
    
    ; Remove from PATH
    EnVar::SetHKLM
    EnVar::DeleteValue "PATH" "$INSTDIR"
    
    ; Remove Start Menu shortcuts
    RMDir /r "$SMPROGRAMS\ThumbsUp Client"
    
    ; Remove registry keys
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\ThumbsUpClient"
    DeleteRegKey HKLM "Software\ThumbsUp\Client"
    
    MessageBox MB_OK "ThumbsUp Client has been uninstalled."
SectionEnd
