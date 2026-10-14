Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "d:\ARREGLO-ANTIGAVITY"
PythonExe = "C:\Users\carlo\AppData\Local\Programs\Python\Python313\pythonw.exe"
ScriptPath = "d:\ARREGLO-ANTIGAVITY\cli.py"
WshShell.Run """" & PythonExe & """ """ & ScriptPath & """ watch", 0, False
