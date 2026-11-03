@echo off
rem Flow Labs - Site Autopsy: real screenshot + real measurements + Flow Score
rem Usage: AUTOPSY.bat --url https://client-site.com --name "Sharma Dental" --city Pune
call "%~dp0tools\content-factory\autopsy.bat" %*
