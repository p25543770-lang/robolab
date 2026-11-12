@echo off
chcp 65001 >nul 2>&1
setlocal
title robolab - obnovlenie koda
cd /d "%~dp0"
set "ROBOLAB_SELF=%~f0"
echo.
echo   ================================
echo    robolab: obnovlenie koda
echo   ================================
echo.
rem ---------------------------------------------------------------
rem  PowerShell part of this file starts below the marker line.
rem  It is read from this very file and executed in memory, so the
rem  updater is this single .bat: nothing else to download.
rem ---------------------------------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = $env:ROBOLAB_SELF; if (-not ($p -and (Test-Path -LiteralPath $p))) { $p = (Get-ChildItem -LiteralPath (Get-Location).Path -Filter *.bat | Where-Object { (Get-Content -LiteralPath $_.FullName -Raw) -match 'POWERSHELL PART BELOW' } | Select-Object -First 1).FullName } $l = Get-Content -LiteralPath $p; $i = 0; while ($i -lt $l.Count -and $l[$i] -notmatch '^rem #### POWERSHELL PART BELOW ####$') { $i = $i + 1 }; Invoke-Expression (($l[($i + 1)..($l.Count - 1)]) -join [Environment]::NewLine)"
if errorlevel 1 goto failed
goto end

:failed
echo.
echo   Chto-to poshlo ne tak (net interneta?). Poprobuyte eshe raz.
echo   Ili skachayte vruchnuyu:
echo     https://raw.githubusercontent.com/p25543770-lang/robolab/main/robot.py

:end
echo.
echo   Nazhmite lyubuyu klavishu, chtoby zakryt okno.
pause >nul
endlocal
rem #### POWERSHELL PART BELOW ####
# ===================================================================
#  Update robot.py on this computer to the newest version from GitHub.
#  Put this file next to robot.py and double click it.
#  It needs nothing but Windows: PowerShell is already there.
# ===================================================================

$Repo   = 'p25543770-lang/robolab'
$Branch = 'main'
$File   = 'robot.py'
$OldSuf = '.old'

try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }

$Dir_ = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Dir_)) { $Dir_ = (Get-Location).Path }
# if this folder has no robot.py but a sub-folder does, use that one
if (-not (Test-Path (Join-Path $Dir_ $File))) {
    $sub = Get-ChildItem -LiteralPath $Dir_ -Directory -ErrorAction SilentlyContinue |
           Where-Object { Test-Path (Join-Path $_.FullName $File) } |
           Select-Object -First 1
    if ($null -ne $sub) { $Dir_ = $sub.FullName }
}
$target = Join-Path $Dir_ $File

# ---- messages: Russian from base64(UTF-8), English as a fallback
$RuOk = $true
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
} catch { $RuOk = $false }

$M = @{
    'downloading'  = '0KHQutCw0YfQuNCy0LDRjiDRgdCy0LXQttC40Lkgcm9ib3QucHkg0YEgR2l0SHViLi4u'
    'backup'       = '0KHRgtCw0YDRg9GOINCy0LXRgNGB0LjRjiDRgdC+0YXRgNCw0L3QuNC7INC60LDQuiByb2JvdC5weS5vbGQ='
    'updated'      = '0J7QsdC90L7QstC40Lsg0LrQvtC0LiDQotC10L/QtdGA0Ywg0LfQsNC70LXQudGC0LUgcm9ib3QucHkg0L3QsCDQutC40YDQv9C40Ycg0LrQsNC6INC+0LHRi9GH0L3Qvi4='
    'current'      = '0KMg0LLQsNGBINGD0LbQtSDRgdCw0LzQsNGPINGB0LLQtdC20LDRjyDQstC10YDRgdC40Y8uINCk0LDQudC7INC90LUg0LzQtdC90Y/Quy4='
    'created'      = '0KTQsNC50LvQsCByb2JvdC5weSDRgtGD0YIg0L3QtSDQsdGL0LvQviAtINGB0LrQsNGH0LDQuyDQvdC+0LLRi9C5Lg=='
    'failed'       = '0J3QtSDQv9C+0LvRg9GH0LjQu9C+0YHRjCDRgdC60LDRh9Cw0YLRjC4g0J/RgNC+0LLQtdGA0YzRgtC1INC40L3RgtC10YDQvdC10YIg0Lgg0LfQsNC/0YPRgdGC0LjRgtC1INC10YnRkSDRgNCw0Lcu'
    'file'         = '0KTQsNC50Ls6'
    'lines'        = '0KHRgtGA0L7Qujo='
    'old'          = '0KHRgtCw0YDQsNGPINCy0LXRgNGB0LjRjzo='
    'then'         = '0JTQsNC70YzRiNC1INC90LAg0LrQuNGA0L/QuNGH0LU6'
    'nochange'     = '0JjQt9C80LXQvdC10L3QuNC5INC90LXRgi4='
    'tryzip'       = '0J7RgdC90L7QstC90L7QuSDQsNC00YDQtdGBINC90LXQtNC+0YHRgtGD0L/QtdC9LCDQv9GA0L7QsdGD0Y4g0LDRgNGF0LjQsi4uLg=='
}

$E = @{
    'downloading'  = 'Downloading the newest robot.py from GitHub...'
    'backup'       = 'Old version kept as robot.py.old'
    'updated'      = 'Code updated. Now upload robot.py to the brick as usual.'
    'current'      = 'You already have the newest version. File not changed.'
    'created'      = 'There was no robot.py here - downloaded a new one.'
    'failed'       = 'Download failed. Check the internet and run again.'
    'file'         = 'File:'
    'lines'        = 'Lines:'
    'old'          = 'Old version:'
    'then'         = 'Then on the brick:'
    'nochange'     = 'Nothing changed.'
    'tryzip'       = 'Main address is not reachable, trying the archive...'
}

function Say([string]$key) {
    if ($RuOk) {
        try {
            Write-Host ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($M[$key])))
            return
        } catch { }
    }
    Write-Host $E[$key]
}

function Get-Bytes([string]$url) {
    try {
        $wc = New-Object Net.WebClient
        $wc.Headers.Add('User-Agent', 'robolab-updater')
        $wc.Encoding = [Text.Encoding]::UTF8
        return $wc.DownloadData($url)
    } catch {
        return $null
    }
}

function As-Text($bytes) {
    if ($null -eq $bytes -or $bytes.Length -eq 0) { return $null }
    try {
        if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
            return [Text.Encoding]::UTF8.GetString($bytes, 3, $bytes.Length - 3)
        }
        return [Text.Encoding]::UTF8.GetString($bytes)
    } catch {
        return $null
    }
}

function From-Zip($bytes) {
    if ($null -eq $bytes -or $bytes.Length -lt 4) { return $null }
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('robolab-' + [Guid]::NewGuid().ToString('N') + '.zip')
    try {
        [IO.File]::WriteAllBytes($tmp, $bytes)
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [IO.Compression.ZipFile]::OpenRead($tmp)
        try {
            foreach ($item in $zip.Entries) {
                if ($item.Name -eq $File -and $item.FullName -like '*/' + $File) {
                    $reader = New-Object IO.StreamReader($item.Open(), [Text.Encoding]::UTF8)
                    try { return $reader.ReadToEnd() } finally { $reader.Close() }
                }
            }
        } finally { $zip.Dispose() }
    } catch {
        return $null
    } finally {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    }
    return $null
}

Say 'downloading'

# ---- 1. the file itself (three addresses, the servers differ)
$text = $null
$urls = @(
    ('https://raw.githubusercontent.com/' + $Repo + '/' + $Branch + '/' + $File),
    ('https://github.com/' + $Repo + '/raw/' + $Branch + '/' + $File),
    ('https://raw.githubusercontent.com/' + $Repo + '/main/' + $File)
)
foreach ($u in $urls) {
    Write-Host ('  ' + $u) -ForegroundColor DarkGray
    $text = As-Text (Get-Bytes $u)
    if ($text -and $text.Length -gt 2000 -and $text.Contains('def main(')) { break }
    $text = $null
}

# ---- 2. still nothing: take the zip archive of the branch
if (-not $text) {
    Say 'tryzip'
    $zipUrls = @(
        ('https://codeload.github.com/' + $Repo + '/zip/refs/heads/' + $Branch),
        ('https://github.com/' + $Repo + '/archive/refs/heads/' + $Branch + '.zip')
    )
    foreach ($u in $zipUrls) {
        Write-Host ('  ' + $u) -ForegroundColor DarkGray
        $text = From-Zip (Get-Bytes $u)
        if ($text) { break }
    }
}

if (-not $text) {
    Say 'failed'
    exit 1
}

# ---- 3. sanity check: it must look like the program
if (-not $text.Contains('def main(') -or -not $text.Contains('RUN MODE')) {
    Say 'failed'
    Write-Host '  (downloaded file does not look like robot.py)' -ForegroundColor DarkGray
    exit 1
}

$newText = $text.Replace("`r`n", "`n")

# ---- 4. compare with what is here
$oldText = $null
if (Test-Path $target) {
    try { $oldText = [IO.File]::ReadAllText($target, [Text.Encoding]::UTF8) } catch { $oldText = $null }
}

$same = $false
if ($oldText) {
    if ($oldText.Replace("`r`n", "`n") -eq $newText) { $same = $true }
}

Write-Host ''
if ($same) {
    Say 'current'
    Say 'file'
    Write-Host ('  ' + $target) -ForegroundColor Green
    Say 'lines'
    Write-Host ('  ' + $newText.Split("`n").Count) -ForegroundColor Green
    Write-Host ''
    Say 'then'
    Write-Host ('  brickrun --directory="/home/robot/robolabs2" "/home/robot/robolabs2/robot.py"') -ForegroundColor DarkGray
    Write-Host ''
    Say 'nochange'
    exit 0
}

$created = -not (Test-Path $target)
if (-not $created) {
    Copy-Item $target ($target + $OldSuf) -Force
}

try {
    [IO.File]::WriteAllText($target, $newText, (New-Object Text.UTF8Encoding $false))
} catch {
    Say 'failed'
    Write-Host ('  ' + $_.Exception.Message) -ForegroundColor DarkGray
    exit 1
}

if ($created) { Say 'created' } else { Say 'updated' }
if (-not $created) { Say 'backup' }
Say 'file'
Write-Host ('  ' + $target) -ForegroundColor Green
Say 'lines'
$oldLines = 0
if ($oldText) { $oldLines = $oldText.Split("`n").Count }
Write-Host ('  ' + $oldLines + ' -> ' + $newText.Split("`n").Count) -ForegroundColor Green
if (-not $created) {
    Say 'old'
    Write-Host ('  ' + $target + $OldSuf) -ForegroundColor DarkGray
}
Write-Host ''
Say 'then'
Write-Host '  brickrun --directory="/home/robot/robolabs2" "/home/robot/robolabs2/robot.py"' -ForegroundColor DarkGray
Write-Host ''
exit 0
