# Drives a Mirror's Edge VR perf A/B: look around in unpaused gameplay, change the view distance
# from the VR panel, close it, look around again. Census windows are 900 frames each.
#
#   powershell -File tools\perf-ab.ps1
#
# The panel pauses the game, so the lookup phases are what make the two windows comparable: both
# sweep the camera over the same part of the level instead of sampling one frozen view.
param(
    [int]$BaselineSeconds = 30,
    [int]$AfterSeconds = 75
)

$xr = 'D:\xrtemp'
function Put([string]$names) {
    $temp = Join-Path $xr 'press.tmp'
    Set-Content -Path $temp -Value $names -Encoding ASCII
    try { Move-Item -Path $temp -Destination (Join-Path $xr 'press') -Force } catch { }
}

function Look([int]$seconds) {
    $end = (Get-Date).AddSeconds($seconds)
    $i = 0
    while ((Get-Date) -lt $end) {
        if ($i % 2 -eq 0) { Put 'RStickLeft:0.5' } else { Put 'RStickRight:0.5' }
        Start-Sleep -Milliseconds 1400
        $i++
    }
}

Write-Output 'phase 1: looking around (LODDistance = 100%)'
Look $BaselineSeconds

Write-Output 'phase 2: panel -> VIEW DISTANCE FACTOR -> 25%'
Put 'RStick:1.3'
Start-Sleep -Seconds 5
Put 'LStickDown:0.3'; Start-Sleep -Seconds 1
Put 'LStickDown:0.3'; Start-Sleep -Seconds 1
Put 'LStickDown:0.3'; Start-Sleep -Seconds 1
Put 'RA:0.3';          Start-Sleep -Seconds 1
Put 'LStickDown:0.3'; Start-Sleep -Seconds 1
Put 'LStickLeft:0.3';  Start-Sleep -Seconds 1
Put 'LStickLeft:0.3';  Start-Sleep -Seconds 1
Put 'LStickLeft:0.3';  Start-Sleep -Seconds 2

Write-Output 'phase 3: close the panel and unpause'
Put 'RStick:0.3'
Start-Sleep -Seconds 6

Write-Output 'phase 4: looking around (LODDistance = 25%)'
Look $AfterSeconds

Write-Output 'done'
$log = 'E:\tmp\Q3Mods\MirrorsEdge\GameFiles\ME\Binaries\mevr.log'
Get-Content $log | Select-String -Pattern '\[menu\] (opened|select|adjust|row)|\[lod\]' |
    ForEach-Object { $_.Line.Trim() }
