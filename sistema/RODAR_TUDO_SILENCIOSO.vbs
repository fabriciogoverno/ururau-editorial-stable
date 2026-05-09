Option Explicit
Dim sh, fso, base, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = base
cmd = Chr(34) & base & "\RODAR_TUDO_REAL.bat" & Chr(34)
' 0 = janela oculta; False = não esperar. Console operacional fica no painel.
sh.Run cmd, 0, False
