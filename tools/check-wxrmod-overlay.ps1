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
Expect-File 'Binaries\d3d9.dll' 'DF9A5215AE6B192376F118078ED2D31C0D794FDB13561738D7271966B64A273C'
Expect-File 'Binaries\mevr.ini' '49E0FD66A0CB81AF123B4F35DE8DE40F6EC1013CCCA74DC1C55896A14AF048B1'
Expect-File 'Binaries\mevr-TdEngine.ini' '3D09EE770B32728C4A4E3B848AF032AAAC685A15149218752DA0E5F02E3CF419'
Expect-File 'Binaries\MirrorsEdge.exe' 'EC0907678EA3F7DDD48950C0F9346D04EF6F8A6040227C1FFCD3CBCEF9E27C33'
Expect-File 'Binaries\PhysXCore.dll' $null
Expect-File 'Fallback\d3d9-mt.dll' 'D3742FCC0B700A02B914E54EB1CC375D8E3807430DF39F31D06F9BA086FB9616'
Expect-File 'TdGame\Config\DefaultHudEffects.ini' '40A4E4E7A04865BC12E46CF5B082F09D7E884D88B1236542F2993F495CB9917B'
Expect-File 'TdGame\CookedPC\Engine.u' '8C8A4C79FCFFCCC4882D27FFE522BC299B67D423595B921E0FAC518EF5B8E7FB'
Expect-File 'TdGame\CookedPC\TdGame.u' 'AF4A5ADA7972E949DF1F0C6588617143C86B8EF027F7FBC206ECFF1AD97B0524'
Expect-File 'TdGame\CookedPC\Ts_LOC_int.upk' '3448981058D0469E9BC5BA1AF475B810F9A4A0AC3424617DDF77B2A71DB5145B'
if (Test-Path -LiteralPath (Join-Path $OverlayDirectory 'Binaries\OpenAL32.dll')) {
    $fail.Add('Binaries\OpenAL32.dll is present - the WXR mod no longer ships or replaces OpenAL')
} else {
    $ok.Add('no bundled OpenAL32.dll')
}

Expect-Text 'Binaries\mevr.ini' '(?m)^\s*WinlatorXrGraphics\s*=\s*quest\s*$' 'WinlatorXrGraphics = quest'
Expect-Text 'Binaries\mevr.ini' '(?m)^\s*WinlatorXrInstallConfig\s*=\s*on\s*$' 'WinlatorXrInstallConfig = on'
Expect-Text 'Binaries\mevr.ini' '(?m)^\s*WinlatorXrStereo\s*=\s*mono\s*$' 'WinlatorXrStereo = mono'
Expect-Text 'Binaries\mevr.ini' '(?m)^\s*Resolution\s*=\s*auto\s*$' 'Resolution = auto'
Expect-Text 'Binaries\mevr.ini' '(?m)^\s*FrameCap\s*=\s*60\s*$' 'FrameCap = 60'
Expect-Text 'Binaries\mevr.ini' '(?m)^\s*HeadRollSign\s*=\s*0\s*$' 'HeadRollSign = 0'
Expect-Text 'Binaries\mevr.ini' '(?m)^\s*WinlatorXrFov\s*=\s*0\s*$' 'WinlatorXrFov = 0'
Expect-Text 'Binaries\mevr.ini' '(?m)^\s*WinlatorXrFovV\s*=\s*0\s*$' 'WinlatorXrFovV = 0'
Expect-Text 'Binaries\mevr.ini' '(?m)^\s*GameFov\s*=\s*105\s*$' 'GameFov = 105'
Expect-Text 'Binaries\mevr-TdEngine.ini' '(?m)^\s*DynamicShadows\s*=\s*False\s*$' 'DynamicShadows=False'
Expect-Text 'Binaries\mevr-TdEngine.ini' '(?m)^\s*LightEnvironmentShadows\s*=\s*False\s*$' 'LightEnvironmentShadows=False'
Expect-Text 'Binaries\mevr-TdEngine.ini' '(?m)^\s*Distortion\s*=\s*False\s*$' 'Distortion=False'
Expect-Text 'Binaries\mevr-TdEngine.ini' '(?m)^\s*DepthOfField\s*=\s*False\s*$' 'DepthOfField=False'
Expect-Text 'Binaries\mevr-TdEngine.ini' '(?m)^\s*ResX\s*=\s*1920\s*$' 'ResX=1920'
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
