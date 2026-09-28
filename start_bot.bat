@ECHO OFF
SETLOCAL EnableExtensions EnableDelayedExpansion
CD /D "%~dp0"

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
IF ERRORLEVEL 1 (
	ECHO Kepler requires python version 3.10 or newer to run properly.
	PAUSE
	EXIT /B 1
)

IF NOT EXIST ".venv\Scripts\python.exe" (
	ECHO Creating virtual environment...
	python -m venv .venv
	IF ERRORLEVEL 1 (
		ECHO Failed to create virtual environment.
		PAUSE
		EXIT /B 1
	)

)

SET "REQUIREMENTS_HASH="
FOR /F "skip=1 tokens=1" %%H IN ('certutil -hashfile requirements.txt SHA256') DO IF NOT DEFINED REQUIREMENTS_HASH SET "REQUIREMENTS_HASH=%%H"
SET "INSTALLED_HASH="
IF EXIST ".venv\requirements.sha256" SET /P "INSTALLED_HASH="<".venv\requirements.sha256"

IF NOT "!REQUIREMENTS_HASH!"=="!INSTALLED_HASH!" (
	ECHO Installing dependencies...
	.venv\Scripts\python.exe -m pip install -r requirements.txt
	IF ERRORLEVEL 1 (
		ECHO Failed to install dependencies.
		PAUSE
		EXIT /B 1
	)
	>".venv\requirements.sha256" ECHO !REQUIREMENTS_HASH!
)

:KEPLER
.venv\Scripts\python.exe -u main.py
SET "EXIT_CODE=%ERRORLEVEL%"

IF "%EXIT_CODE%" EQU "26" GOTO RESTART_KEPLER
ECHO.
ECHO Kepler stopped with exit code %EXIT_CODE%.
PAUSE
EXIT /B %EXIT_CODE%

:RESTART_KEPLER
ECHO Restarting Kepler...
GOTO KEPLER