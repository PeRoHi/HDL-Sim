Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
gui = """" & root & "\start_ui_gui.pyw"""

commands = Array( _
  "py -3.12 " & gui, _
  "py -3 " & gui, _
  "pythonw " & gui, _
  "python " & gui _
)

For Each cmd In commands
  If TryRun(shell, cmd) Then
    WScript.Quit 0
  End If
Next

MsgBox "Python 3.12 が見つかりません。" & vbCrLf & vbCrLf & _
  "https://www.python.org/downloads/ からインストールしてください。" & vbCrLf & _
  "または start-ui.bat をお試しください。", _
  vbCritical, "HDL-Sim"

Function TryRun(sh, cmd)
  On Error Resume Next
  rc = sh.Run("cmd /c " & cmd, 0, True)
  If Err.Number <> 0 Then
    TryRun = False
    Exit Function
  End If
  TryRun = (rc = 0)
End Function
