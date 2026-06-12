@rem Gradle startup script for Windows

@if "%DEBUG%"=="" @echo off
setlocal enabledelayedexpansion

set DIRNAME=%~dp0
if "%DIRNAME%"=="" set DIRNAME=.

set WRAPPER_JAR="%DIRNAME%gradle\wrapper\gradle-wrapper.jar"
set WRAPPER_LAUNCHER=org.gradle.wrapper.GradleWrapperMain

java.exe %* -classpath %WRAPPER_JAR% %WRAPPER_LAUNCHER%
