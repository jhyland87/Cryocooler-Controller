On Error Resume Next

'Setting up the script to work with the file system.
Set WshShell = WScript.CreateObject("WScript.Shell")
Set FileSysObj = CreateObject("Scripting.FileSystemObject")
Set objSysInfo = CreateObject("ADSystemInfo")

strUser = CreateObject("WScript.Network").UserName

strAppData = WshShell.ExpandEnvironmentStrings("%APPDATA%")


SigFolder = StrAppData & "\Microsoft\Signatures\"
SigFile = SigFolder & strUser & "-Stirling" & ".htm"


'Setting placeholders for the signature. They will be automatically replaced with data from Active Directory.

MsgBox("Zorg dat Outlook afgesloten is voordat u verder gaat")

strNaam = InputBox("Vul uw complete naam in zoals deze in de handtekening mag komen:", "Naam")
strFunctie = InputBox("Vul uw complete functie in zoals deze in de handtekening mag komen:", "Functie")
strTelefoon = InputBox("Vul uw vaste telefoon nummer, met landcode, zonder spaties en toevoegingen in. VB: 31402677367.", "Telefoon nummer")
strMobiel = InputBox("Vul uw mobiele nummer met landcode in zonder spaties en toevoegingen. VB: 31658817359. Laat leeg indien niet van toepassing:", "Mobiel nummer")
strEmail = InputBox("Vul uw complete emailadres in zoals deze in de handtekening mag komen. VB: j.janssen@stirlingcryogenics.com:", "Email")
strAfsluiting = InputBox("Vul de tekst in waarmee u uw mails gebruikelijk afsluit, zoals Met vriendelijke groet, ", "Afsluiting mail")

strMobielWeergave = Mid(strMobiel, 1, 2)  & space(1) & Mid(strMobiel, 3, 1) & space(1) & Mid(strMobiel, 4, 3) & space(1) & Mid(strMobiel, 7, 3) & space(1) & Mid(strMobiel, 10, 2)

strTelefoonWeergave = Mid(strTelefoon, 1, 2)  & space(1) & Mid(strTelefoon, 3, 2) & space(1) & Mid(strTelefoon, 5, 2) & space(1) & Mid(strTelefoon, 7, 2) & space(1) & Mid(strTelefoon, 9, 3)


'Creating HTM signature file for the user's profile.
Set CreateSigFile = FileSysObj.CreateTextFile (SigFile, True, True)

'Signature’s HTML code

CreateSigFile.WriteLine "<!DOCTYPE HTML PUBLIC '-//W3C//DTD HTML 4.0 Transitional//EN'>"	
CreateSigFile.WriteLine "<html lang='en' xmlns='http://www.w3.org/1999/xhtml' xmlns:o='urn:schemas-microsoft-com:office:office'>"	
CreateSigFile.WriteLine "<head>"	
CreateSigFile.WriteLine "<meta content='text/html; charset=utf-8' http-equiv='Content-Type'>"	
CreateSigFile.WriteLine "<meta name='viewport' content='width=device-width,initial-scale=1'>"	
CreateSigFile.WriteLine "<meta name='x-apple-disable-message-reformatting'>"	
CreateSigFile.WriteLine "<title></title>"	
CreateSigFile.WriteLine "<!--[if mso]>"	
CreateSigFile.WriteLine "<noscript>"	
CreateSigFile.WriteLine "<xml>"	
CreateSigFile.WriteLine "<o:OfficeDocumentSettings>"	
CreateSigFile.WriteLine "<o:PixelsPerInch>96</o:PixelsPerInch>"	
CreateSigFile.WriteLine "</o:OfficeDocumentSettings>"	
CreateSigFile.WriteLine "</xml>"	
CreateSigFile.WriteLine "</noscript>"	
CreateSigFile.WriteLine "<![endif]-->"	
CreateSigFile.WriteLine "<style>"	
CreateSigFile.WriteLine "table, td, div, h1, p {font-family: ;  color:#000000; font-weight:300; font-size: 9pt; }"	
CreateSigFile.WriteLine "table, td {border:0px;}"	
CreateSigFile.WriteLine "a[x-apple-data-detectors] {"	
CreateSigFile.WriteLine "color: inherit !important;"	
CreateSigFile.WriteLine "text-decoration: none !important;"	
CreateSigFile.WriteLine "font-size: inherit !important;"	
CreateSigFile.WriteLine "font-family: inherit !important;"	
CreateSigFile.WriteLine "font-weight: inherit !important;"	
CreateSigFile.WriteLine "line-height: inherit !important;"	
CreateSigFile.WriteLine "}"	
CreateSigFile.WriteLine "u + #body a {"	
CreateSigFile.WriteLine "color: inherit !important;"	
CreateSigFile.WriteLine "text-decoration: none !important;"	
CreateSigFile.WriteLine "font-size: inherit !important;"	
CreateSigFile.WriteLine "font-family: inherit !important;"	
CreateSigFile.WriteLine "font-weight: inherit !important;"	
CreateSigFile.WriteLine "line-height: inherit !important;"	
CreateSigFile.WriteLine "}"	
CreateSigFile.WriteLine "#MessageViewBody a {"	
CreateSigFile.WriteLine "color: inherit !important;"	
CreateSigFile.WriteLine "text-decoration: none !important;"	
CreateSigFile.WriteLine "font-size: inherit !important;"	
CreateSigFile.WriteLine "font-family: inherit !important;"	
CreateSigFile.WriteLine "font-weight: inherit !important;"	
CreateSigFile.WriteLine "line-height: inherit !important;"	
CreateSigFile.WriteLine "}"	
CreateSigFile.WriteLine "</style>"	
CreateSigFile.WriteLine "</head>"	
CreateSigFile.WriteLine "<body id='body' style='margin:0;padding:0;'>"	

If (Len("" & strAfsluiting) = 0) Then
	CreateSigFile.WriteLine ""	
Else
	CreateSigFile.WriteLine strAfsluiting & "<br/>"	
	CreateSigFile.WriteLine "<br/>"	
End If

CreateSigFile.WriteLine "<table width='550px' cellpadding='0' cellspacing='0' border='0' style='font-family: ""Myriad Pro"", Myriad, ""Liberation Sans"", ""Nimbus Sans L"", ""Helvetica Neue"", Helvetica, Arial, sans-serif;  color:#000000; font-weight:300;  border-collapse:collapse;border:0;border-spacing:0; width:550px;'>"	
CreateSigFile.WriteLine "<tr>"	
CreateSigFile.WriteLine "<td width='160px'><a href='https://www.stirlingcryogenics.com/'><img width='120' height='110' style='width: 120px; height:110px; display: block; margin: 0px; border: 0px;' src='https://www.stirlingcryogenics.com/files/logo-stirling-cryogenics.png'/></a></td>"	
CreateSigFile.WriteLine "<td width='19px' style='position:relative; width:19px; font-size:0px;'>&nbsp;</td>"	
CreateSigFile.WriteLine "<td width='2px' style='position:relative; width:2px; font-size:0px;'>&nbsp;</td>"	
CreateSigFile.WriteLine "<td width='19px' style='position:relative; width:19px; font-size:0px;'>&nbsp;</td>"	
CreateSigFile.WriteLine "<td colspan='5' style='vertical-align:bottom;'>"	
CreateSigFile.WriteLine "<table cellpadding='0' cellspacing='0' border='0'  height='40px' style='font-family: ""Myriad Pro"", Myriad, ""Liberation Sans"", ""Nimbus Sans L"", ""Helvetica Neue"", Helvetica, Arial, sans-serif;  color:#000000;  height:60px; vertical-align:middle; border-collapse:collapse;border:0;border-spacing:0; height:40px;'>"	
CreateSigFile.WriteLine "<tr>"	
CreateSigFile.WriteLine "<td>"	
CreateSigFile.WriteLine "<b style='font-size:1.2em; font-weight:600;'>" & strNaam & "</b><br/>"	
CreateSigFile.WriteLine "<span style='font-weight:300;'>" & strFunctie & "</span>"	
CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "</tr>"	
CreateSigFile.WriteLine "</table>"	
CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "</tr> "	
CreateSigFile.WriteLine "<tr>"	
CreateSigFile.WriteLine "<td colspan='8' style='height:30px' height='30'>"	
CreateSigFile.WriteLine "&nbsp;"	
CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "</tr> "	
CreateSigFile.WriteLine "<tr>"	
CreateSigFile.WriteLine "<td  width='160px'>"	
CreateSigFile.WriteLine "<table cellpadding='0' cellspacing='0' border='0' style='font-family: ""Myriad Pro"", Myriad, ""Liberation Sans"", ""Nimbus Sans L"", ""Helvetica Neue"", Helvetica, Arial, sans-serif;  color:#000000; font-weight:300;  border-collapse:collapse;border:0;border-spacing:0;'>"	
CreateSigFile.WriteLine "<tr>"	
CreateSigFile.WriteLine "<td>"	
CreateSigFile.WriteLine "Science Park Eindhoven 5003"	
CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "</tr>"	
CreateSigFile.WriteLine "<tr>"	
CreateSigFile.WriteLine "<td>"	
CreateSigFile.WriteLine "5692 EB Son, The Netherlands"	
CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "</tr>"	
CreateSigFile.WriteLine "</table>"	
CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "<td width='19px' style='position:relative; width:19px; font-size:0px;'>&nbsp;</td>"	
CreateSigFile.WriteLine "<td width='2px' style='position:relative; width:2px; background-color:#0069a3; font-size:0px;'>&nbsp;</td>"	
CreateSigFile.WriteLine "<td width='19px' style='position:relative; width:19px; font-size:0px;'>&nbsp;</td>"	
CreateSigFile.WriteLine "<td width='140px'>"	
CreateSigFile.WriteLine "<table cellpadding='0' cellspacing='0' border='0' style='font-family: ""Myriad Pro"", Myriad, ""Liberation Sans"", ""Nimbus Sans L"", ""Helvetica Neue"", Helvetica, Arial, sans-serif;  color:#000000; font-weight:300;  border-collapse:collapse;border:0;border-spacing:0;'>"	
CreateSigFile.WriteLine "<tr>"	
CreateSigFile.WriteLine "<td>"	
CreateSigFile.WriteLine "<b style='font-weight:600;'>T&nbsp;</b>"	
CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "<td>"	
CreateSigFile.WriteLine "<a x-apple-data-detectors='true' style='color:#000000; text-decoration:none !important; text-decoration:none; white-space: nowrap;' href='tel:+" & strTelefoon & "'>+" & strTelefoonWeergave & "</a>"	
CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "</tr>"	
CreateSigFile.WriteLine "<tr>"	
CreateSigFile.WriteLine "<td>"	

If (Len("" & strMobiel) = 0) Then
	CreateSigFile.WriteLine "<td>"	
Else
	CreateSigFile.WriteLine "<b style='font-weight:600;'>M&nbsp;</b>"	
End If

CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "<td>"	

If (Len("" & strMobiel) = 0) Then
	CreateSigFile.WriteLine "&nbsp;"	
Else
	CreateSigFile.WriteLine "<a style='color:#000000; text-decoration: none; white-space: nowrap;' href='tel:+" & strMobiel & "'>+" & strMobielWeergave & "</a>"	
End If

CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "</tr>"	
CreateSigFile.WriteLine "</table>"	
CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "<td width='19px' style='position:relative; width:19px; font-size:0px;'>&nbsp;</td>"	
CreateSigFile.WriteLine "<td width='2px' style='position:relative; width:2px; background-color:#0069a3; font-size:0px;'>&nbsp;</td>"	
CreateSigFile.WriteLine "<td width='19px' style='position:relative; width:19px; font-size:0px;'>&nbsp;</td>"	
CreateSigFile.WriteLine "<td width='170px'>"	
CreateSigFile.WriteLine "<table cellpadding='0' cellspacing='0' border='0' style='font-family: ""Myriad Pro"", Myriad, ""Liberation Sans"", ""Nimbus Sans L"", ""Helvetica Neue"", Helvetica, Arial, sans-serif;  color:#000000; font-weight:300;  border-collapse:collapse;border:0;border-spacing:0;'>"	
CreateSigFile.WriteLine "<tr>"	
CreateSigFile.WriteLine "<td>"	
CreateSigFile.WriteLine "<a style='color:#000000; text-decoration: none; white-space: nowrap;' href='mailto:" & strEmail & "'>" & strEmail & "</a>"	
CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "</tr>"	
CreateSigFile.WriteLine "<tr>"	
CreateSigFile.WriteLine "<td>"	
CreateSigFile.WriteLine "<a style='color:#000000; text-decoration: none; white-space: nowrap;' href='https://www.stirlingcryogenics.com/'>www.stirlingcryogenics.com</a>"	
CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "</tr>"	
CreateSigFile.WriteLine "</table>"	
CreateSigFile.WriteLine "</td>"	
CreateSigFile.WriteLine "</tr>"	
CreateSigFile.WriteLine "</table>"	
CreateSigFile.WriteLine "</body>"	
CreateSigFile.WriteLine "</html>"

CreateSigFile.Close

Set objWord = CreateObject("Word.Application")
Set objSignatureObjects = objWord.EmailOptions.EmailSignature
objSignatureObjects.NewMessageSignature = strUser & "-Stirling"
objSignatureObjects.ReplyMessageSignature = strUser & "-Stirling"
objWord.Quit


'==========================================================================
' Set Signature As Default
'==========================================================================
Call SetDefaultSignature(strUser & "-Stirling", "")

Sub SetDefaultSignature(strSigName, strProfile)
const HKEY_CURRENT_USER = &H80000001
const HKEY_LOCAL_MACHINE = &H80000002
strComputer = "."

 Set objreg = GetObject("winmgmts:" & "{impersonationLevel=impersonate}!\\" & _
strComputer & "\root\default:StdRegProv") 

'Determine path to outlook.exe
strKeyOutlookAppPath = "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE"
strOutlookPath = "Path"
objreg.GetStringValue HKEY_LOCAL_MACHINE,strKeyOutlookAppPath,strOutlookPath,strOutlookPathValue

'Verify that the outlook.exe exist and get version information
Set objFSO = CreateObject("Scripting.FileSystemObject") 
If objFSO.FileExists(strOutlookPathValue & "outlook.exe") Then
	strOutlookVersionNumber = objFSO.GetFileVersion(strOutlookPathValue & "outlook.exe")
	strOutlookVersion = Left(strOutlookVersionNumber, inStr(strOutlookVersionNumber, ".0") - 1)
End If

'Set profile Registry path based on Outlook version
If strOutlookVersion >= 15 Then
	strKeyPath = "Software\Microsoft\Office\" & strOutlookVersion & ".0\Outlook\Profiles\"
	strDisableKeyPath = "Software\Microsoft\Office\" & strOutlookVersion & ".0\Common\MailSettings\"
	Else    
	strKeyPath = "Software\Microsoft\Windows NT\CurrentVersion\Windows Messaging Subsystem\Profiles\"
	strDisableKeyPath = "Software\Microsoft\Office\" & strOutlookVersion & ".0\Common\MailSettings\"
End If

 If strProfile = "" Then
 objreg.GetStringValue HKEY_CURRENT_USER, _
 strKeyPath, "DefaultProfile", strProfile
 End If

myArray = StringToByteArray(strSigName, True)
strKeyPath = strKeyPath & strProfile & "\9375CFF0413111d3B88A00104B2A6676"
objreg.EnumKey HKEY_CURRENT_USER, strKeyPath, arrProfileKeys


For Each subkey In arrProfileKeys
	strsubkeypath = strKeyPath & "\" & subkey

	objreg.SetStringValue HKEY_CURRENT_USER, strsubkeypath, "New Signature", strSigName 
	objreg.SetStringValue HKEY_CURRENT_USER, strsubkeypath, "Reply-Forward Signature", strSigName
Next
End Sub

MsgBox("De handtekening is ingesteld")
