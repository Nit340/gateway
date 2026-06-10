@ECHO OFF

pushd %~dp0

REM Command file for Sphinx documentation

if "%SPHINXBUILD%" == "" (
	set SPHINXBUILD=sphinx-build
)
set SOURCEDIR=.
set BUILDDIR=_build

if "%1" == "" goto help
if "%1" == "help" goto help

if "%1" == "simplepdf" (
	%SPHINXBUILD% -b simplepdf %SOURCEDIR% %BUILDDIR%/simplepdf %SPHINXOPTS% %2
	goto end
)

%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %2
goto end

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %2
echo.
echo   simplepdf   to make PDF files using sphinx-simplepdf
goto end

:end
popd
