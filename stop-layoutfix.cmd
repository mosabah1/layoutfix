@echo off
rem Stops any running layoutfix instance, whether it runs from source or as the
rem packaged executable.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'layoutfix.exe' -or ($_.Name -eq 'pythonw.exe' -and $_.CommandLine -like '*layoutfix.py*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
