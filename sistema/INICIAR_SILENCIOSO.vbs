Option Explicit
Dim sh, fso, base
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = base
' 0 = janela oculta; False = não travar o atalho esperando retorno.
sh.Run Chr(34) & base & "\INICIAR_OCULTO.bat" & Chr(34), 0, False
