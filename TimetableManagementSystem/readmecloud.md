$env:PATH += ";C:\Users\Derick Mhidze\.local\bin"
claude --version

For a permanent fix, add C:\Users\Derick Mhidze\.local\bin to your system PATH:

Search "Edit environment variables" in Windows Start
Under User variables, select Path → Edit
Click New and add: C:\Users\Derick Mhidze\.local\bin
Click OK and restart VS Code
After that, claude will always be available in the VS Code terminal.

Push-Location TimetableManagementSystem; & "c:/Users/Derick Mhidze/ARDHI-AUTOMATED-TIMETABLE-SYSYEM/.venv/Scripts/python.exe" manage.py runserver