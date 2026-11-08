# Preflight check for the local Release/WXRMOD overlay.
#
#   .\tools\check-wxrmod-overlay.ps1
#   .\tools\check-wxrmod-overlay.ps1 -GameDirectory 'E:\path\to\Mirror''s Edge'
#
# This validates the local overlay only. It does not launch the game, prove a
# headset result, or replace a real device test.

param(
    [string]$OverlayDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) 'Release\WXRMOD'),
    [string]$GameDirectory = ''
)

$ErrorActionPreference = 'Stop'
$fail = New-Object System.Collections.Generic.List[string]
$warn = New-Object System.Collections.Generic.List[string]
$ok = New-Object System.Collections.Generic.List[string]

function Expect-File([string]$relative, [string]$sha256) {
    $path = Join-Path $OverlayDirectory $relative
    if (-not (Test-Path -LiteralPath $path)) {
        $fail.Add("missing: $relative")
        return
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    if ($sha256 -and $actual -ne $sha256) {
        $fail.Add("hash mismatch: $relative`n  expected $sha256`n  actual   $actual")
    } else {
        $ok.Add("$relative  $actual")
    }
}

function Expect-Text([string]$relative, [string]$pattern, [string]$label) {
    $path = Join-Path $OverlayDirectory $relative
    if (-not (Test-Path -LiteralPath $path)) { return }
    $text = Get-Content -LiteralPath $path -Raw
    if ($text -notmatch $pattern) {
        $fail.Add("$relative is missing $label")
    } else {
        $ok.Add("$relative contains $label")
    }
}

Write-Host "Overlay: $OverlayDirectory"
if (-not (Test-Path -LiteralPath $OverlayDirectory)) {
    Write-Error "overlay directory not found: $OverlayDirectory"
    exit 1
}

# The three install files plus the game/config files the tweak tool touched.
Expect-File 'Binaries\d3d9.dll' '13EA706950A32D0DE3294CF455C10E85085F5A5A1CEEC11FA06ED307B160E39C'
Expect-File 'Binaries\mevr.ini' 'A87EB263711190BC3C9FF21A3D6CBBFDFA310E7007A7382E412665A1E2651173'
Expect-File 'Binaries\mevr-TdEngine.ini' 'A44BC437F6AF52519D0CC8DC2E294AFCB9F15892E8ECDAB33F6A435741423D47'
Expect-File 'Binaries\MirrorsEdge.exe' 'EC0907678EA3F7DDD48950C0F9346D04EF6F8A6040227C1FFCD3CBCEF9E27C33'
Expect-File 'Binaries\OpenAL32.dll' '0F8AC05ADF791904D6ECF74CDE08F6C0ED84411FC55DDC7B1B5E3EB106F34D4D'
Expect-File 'Binaries\PhysXCore.dll' $null
Expect-File 'Fallback\d3d9-mt.dll' '89E604D63DC1B43BF8C761C93531E1A425FD75C13809D0C38FB2DC72F6BD5410'
Expect-File 'TdGame\Config\DefaultHudEffects.ini' '40A4E4E7A04865BC12E46CF5B082F09D7E884D88B1236542F2993F495CB9917B'
Expect-File 'TdGame\CookedPC\Engine.u' '91C2D37C38361100831A682D88127FB30261FBF0F9751E3E7C1308D2964380EB'
Expect-File 'TdGame\CookedPC\TdGame.u' '866F6F4AC7582F6B56B620FBEF452320757B21856905970707BE193A1E7017FB'
Expect-File 'TdGame\CookedPC\Ts_LOC_int.upk' 'B11DAB124A3C2D124158378CA70BB10087251E5F552EE1582A12C9D03348F1E3'

Expect-Text 'Binaries\mevr.ini' '(?m)^\s*WinlatorXrGraphics\s*=\s*quest\s*$' 'WinlatorXrGraphics = quest'
Expect-Text 'Binaries\mevr.ini' '(?m)^\s*WinlatorXrInstallConfig\s*=\s*on\s*$' 'WinlatorXrInstallConfig = on'
Expect-Text 'Binaries\mevr.ini' '(?m)^\s*WinlatorXrStereo\s*=\s*mono\s*$' 'WinlatorXrStereo = mono'
Expect-Text 'Binaries\mevr.ini' '(?m)^\s*Resolution\s*=\s*1440x1080\s*$' 'Resolution = 1440x1080'
Expect-Text 'Binaries\mevr.ini' '(?m)^\s*FrameCap\s*=\s*72\s*$' 'FrameCap = 72'
Expect-Text 'Binaries\mevr-TdEngine.ini' '(?m)^\s*DynamicShadows\s*=\s*False\s*$' 'DynamicShadows=False'
Expect-Text 'Binaries\mevr-TdEngine.ini' '(?m)^\s*LightEnvironmentShadows\s*=\s*False\s*$' 'LightEnvironmentShadows=False'
Expect-Text 'Binaries\mevr-TdEngine.ini' '(?m)^\s*Distortion\s*=\s*False\s*$' 'Distortion=False'
Expect-Text 'Binaries\mevr-TdEngine.ini' '(?m)^\s*DepthOfField\s*=\s*False\s*$' 'DepthOfField=False'
Expect-Text 'Binaries\mevr-TdEngine.ini' '(?m)^\s*ResX\s*=\s*1440\s*$' 'ResX=1440'
Expect-Text 'Binaries\mevr-TdEngine.ini' '(?m)^\s*ResY\s*=\s*1080\s*$' 'ResY=1080'
if ((Get-Content -LiteralPath (Join-Path $OverlayDirectory 'Binaries\mevr-TdEngine.ini') -Raw) -match '(?m)^\[AppCompat\]') {
    $warn.Add('mevr-TdEngine.ini still contains [AppCompat]; desktop CPU/GPU scores may leak into the headset')
}

# x86 PE check without dumpbin.
$dll = Join-Path $OverlayDirectory 'Binaries\d3d9.dll'
$bytes = [System.IO.File]::ReadAllBytes($dll)
$pe = [BitConverter]::ToInt32($bytes, 0x3C)
$machine = [BitConverter]::ToUInt16($bytes, $pe + 4)
if ($machine -ne 0x014C) { $fail.Add("d3d9.dll is not x86 (machine 0x{0:X4})" -f $machine) }
else { $ok.Add('d3d9.dll is x86') }

if ($GameDirectory) {
    $gameExe = Join-Path $GameDirectory 'Binaries\MirrorsEdge.exe'
    if (Test-Path -LiteralPath $gameExe) {
        $h = (Get-FileHash -LiteralPath $gameExe -Algorithm SHA256).Hash
        if ($h -eq '58DE3DF21F40E9953E00BE92F7749097832BAD02E5B657D8485CDB61F360A3DD') {
            $ok.Add('target exe is the expected untouched GOG build')
        } elseif ($h -eq 'EC0907678EA3F7DDD48950C0F9346D04EF6F8A6040227C1FFCD3CBCEF9E27C33') {
            $ok.Add('target exe is already the patched build')
        } else {
            $fail.Add("target MirrorsEdge.exe is neither the expected untouched nor patched GOG build:`n  $h")
        }
    } else {
        $warn.Add("target Binaries\MirrorsEdge.exe not found under $GameDirectory")
    }
    $bak = Join-Path $GameDirectory 'Binaries\PhysXCore.bak'
    if (Test-Path -LiteralPath $bak) { $ok.Add('target has PhysXCore.bak (the overlay supplies PhysXCore.dll)') }
    else { $warn.Add('target Binaries\PhysXCore.bak not found; verify PhysXCore.dll is present') }
    $oldIni = Join-Path $GameDirectory 'Binaries\mevr.ini'
    if (Test-Path -LiteralPath $oldIni) { $warn.Add('target already has Binaries\mevr.ini; back it up before overwriting') }
}

$ok | ForEach-Object { Write-Host "PASS  $_" }
$warn | ForEach-Object { Write-Host "WARN  $_" }
$fail | ForEach-Object { Write-Host "FAIL  $_" }
Write-Host ""
if ($fail.Count) {
    Write-Host "OVERLAY CHECK FAILED ($($fail.Count) problem(s))"
    exit 1
}
Write-Host "OVERLAY CHECK PASSED ($($ok.Count) checks, $($warn.Count) warning(s))"
exit 0
