@echo off
chcp 65001 >nul 2>&1
setlocal
title robolab
cd /d "%~dp0"
set "ROBOLAB_SELF=%~f0"
echo.
echo   ==========================================
echo    robolab: obnovlenie i zapusk na robota
echo   ==========================================
echo.

rem ---------------------------------------------------------------
rem  It is read from the file itself and executed in memory:
rem  nothing extra is downloaded to the disk and nothing is
rem  unpacked next to your files.
rem ---------------------------------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -Command "$l = Get-Content -LiteralPath $env:ROBOLAB_SELF; $i = 0; while ($i -lt $l.Count -and $l[$i] -notmatch '^rem #### POWERSHELL PART BELOW ####$') { $i = $i + 1 }; Invoke-Expression (($l[($i + 1)..($l.Count - 1)]) -join [Environment]::NewLine)"
if errorlevel 1 goto failed
goto end

:failed
echo.
echo   Ne poluchilos. Proverte internet i poprobuyte eshe raz.
echo   Ili skachayte vruchnuyu:
echo     https://raw.githubusercontent.com/p25543770-lang/robolab/main/robot.py
echo     https://github.com/p25543770-lang/robolab/archive/refs/heads/main.zip

:end
echo.
echo   Gotovo. Nazhmite lyubuyu klavishu, chtoby zakryt okno.
pause >nul
endlocal

rem  ---- never run the PowerShell lines as batch commands ----
exit /b 0
rem #### POWERSHELL PART BELOW ####
# ===================================================================
#  robolab - updates itself and uploads to the brick
#    step 1: downloads the newest project from GitHub
#    step 2: if the files here are older, they are replaced
#            (old program kept as robot.py.old)
#    step 3: asks - upload to the robot and run now?  -> ssh + brickrun
#
#  Nothing else is needed: PowerShell, tar, ssh and scp are already
#  in Windows 10/11. No python, no pip, no pybricksdev.
#
#  Settings are below: brick address ($Host_), user, folder, branch.
#  This file is pure ASCII on purpose; messages are printed from
#  base64 (UTF-8) with an English fallback for old consoles.
# ===================================================================

# ---- settings (change them here if needed)
$Host_ = '192.168.0.128'      # brick address: USB is always 192.168.0.128
$User_ = 'robot'              # ev3dev user
$Dir_ = ''                    # '' = into the current folder / next to this file
$Branch_ = 'main'
$RemoteDir = '/home/robot/robolabs2'

$ErrorActionPreference = 'Stop'
$Repo = 'p25543770-lang/robolab'

# ---- keep the window open at the end (the script is usually started
# ---- as  irm ... | iex  and a closing window hides everything)
try {
    $Host.UI.RawUI.WindowTitle = 'robolab - do not close this window'
} catch { }

# ---- console in UTF-8; if that fails, English texts are used
$RuOk = $true
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
    $null = [Console]::OutputEncoding.GetBytes('A')
} catch {
    $RuOk = $false
}

# ---- Russian texts as base64(UTF-8) so this file needs no encoding setup
$M = @{
    'downloading'  = '0KHQutCw0YfQuNCy0LDRjiDQv9GA0L7QtdC60YIg0YEgR2l0SHViLi4u'
    'done'         = '0JPQvtGC0L7QstC+LiDQpNCw0LnQu9GLINC70LXQttCw0YIg0LIg0L/QsNC/0LrQtTo='
    'backup'       = '0KHRgtCw0YDRi9C5IHJvYm90LnB5INGB0L7RhdGA0LDQvdGR0L0g0LrQsNC6IHJvYm90LnB5Lm9sZA=='
    'askrun'       = '0JfQsNC70LjRgtGMINC90LAg0YDQvtCx0L7RgtCwINC4INC30LDQv9GD0YHRgtC40YLRjCDRgdC10LnRh9Cw0YE/IFtZL25d'
    'uploading'    = '0JrQvtC/0LjRgNGD0Y4g0L3QsCDQutC40YDQv9C40YcuLi4='
    'running'      = '0JfQsNC/0YPRgdC60LDRjiDQvdCwINC60LjRgNC/0LjRh9C1LiDQn9Cw0YDQvtC70Ywg0LrQuNGA0L/QuNGH0LAg0L/QviDRg9C80L7Qu9GH0LDQvdC40Y46IG1ha2Vy'
    'failed'       = '0J3QtSDRg9C00LDQu9C+0YHRjCDRgdC60LDRh9Cw0YLRjC4g0J/RgNC+0LLQtdGA0YzRgtC1INC40L3RgtC10YDQvdC10YIg0Lgg0L/QvtC/0YDQvtCx0YPQudGC0LUg0LXRidGRINGA0LDQty4='
    'nossh'        = '0J3QtSDQvdCw0LnQtNC10L0gc3NoLiDQktC60LvRjtGH0LjRgtC1IE9wZW5TU0ggQ2xpZW50OiDQn9Cw0YDQsNC80LXRgtGA0YsgLSDQn9GA0LjQu9C+0LbQtdC90LjRjyAtINCU0L7Qv9C+0LvQvdC40YLQtdC70YzQvdGL0LUg0LrQvtC80L/QvtC90LXQvdGC0YsgLSBPcGVuU1NIIENsaWVudC4='
    'noconnect'    = '0J3QtSDRg9C00LDQu9C+0YHRjCDQv9C+0LTQutC70Y7Rh9C40YLRjNGB0Y8g0Log0LrQuNGA0L/QuNGH0YMuINCf0YDQvtCy0LXRgNGM0YLQtSDQutCw0LHQtdC70YwsINGH0YLQviDQutC40YDQv9C40Ycg0LLQutC70Y7Rh9GR0L0sINC4INCw0LTRgNC10YEu'
    'cancelled'    = '0KTQsNC50LvRiyDRgtC+0LvRjNC60L4g0YHQutCw0YfQsNC90YsuINCX0LDQu9C40YLRjCDQvdCwINGA0L7QsdC+0YLQsCDQstGA0YPRh9C90YPRjjo='
    'vscode'       = '0JTQsNC70YzRiNC1OiDQvtGC0LrRgNC+0LnRgtC1INCyIFZTIENvZGUg0L/QsNC/0LrRgw=='
    'f5'           = '0Lgg0L3QsNC20LzQuNGC0LUgRjUsINCy0YvQsdC10YDQuNGC0LU6IEVWMyAoZXYzZGV2KTog0LfQsNC70LjRgtGMINC4INC30LDQv9GD0YHRgtC40YLRjA=='
    'password'     = '0KHQtdC50YfQsNGBINGB0L/RgNC+0YHQuNGCINC/0LDRgNC+0LvRjCDQutC40YDQv9C40YfQsCAtINCy0LLQtdC00LjRgtC1IG1ha2VyICjQv9GA0Lgg0LLQstC+0LTQtSDQvdC1INCy0LjQtNC90L4pLg=='
    'extract'      = '0KDQsNGB0L/QsNC60L7QstGL0LLQsNGOLi4u'
    'addr'         = '0JDQtNGA0LXRgSDQutC40YDQv9C40YfQsDo='
    'closing'      = '0J3QtSDQt9Cw0LrRgNGL0LLQsNC50YLQtSDRjdGC0L4g0L7QutC90L46INC40LTRkdGCINGA0LDQsdC+0YLQsCDRgSDQutC40YDQv9C40YfQvtC8Lg=='
    'asking'       = '0J/RgNC+0LLQtdGA0Y/Rjiwg0LXRgdGC0Ywg0LvQuCDQvdCwIEdpdEh1YiDQstC10YDRgdC40Y8g0L3QvtCy0LXQtS4uLg=='
    'current'      = '0KMg0LLQsNGBINGD0LbQtSDRgdCw0LzQsNGPINGB0LLQtdC20LDRjyDQstC10YDRgdC40Y8uINCd0LjRh9C10LPQviDQvdC1INC80LXQvdGP0Y4u'
    'updated'      = '0J7QsdC90L7QstC40Lsg0YTQsNC50LvRiyDQtNC+INGB0LLQtdC20LXQuSDQstC10YDRgdC40Lgg0YEgR2l0SHViLg=='
    'step1'        = '0KjQsNCzIDEg0LjQtyAyOiDQv9GA0L7QstC10YDRj9GOINC+0LHQvdC+0LLQu9C10L3QuNGPINC90LAgR2l0SHVi'
    'step2'        = '0KjQsNCzIDIg0LjQtyAyOiDQt9Cw0LvQuNCy0LDRjiDQv9GA0L7Qs9GA0LDQvNC80YMg0L3QsCDQutC40YDQv9C40Yc='
}

$E = @{
    'downloading'  = 'Downloading the project from GitHub...'
    'done'         = 'Done. Files are here:'
    'backup'       = 'Old robot.py kept as robot.py.old'
    'askrun'       = 'Upload to the robot and run now? [Y/n]'
    'uploading'    = 'Copying to the brick...'
    'running'      = 'Starting on the brick. Default brick password: maker'
    'failed'       = 'Download failed. Check the internet and try again.'
    'nossh'        = 'ssh not found. Turn on OpenSSH Client: Settings - Apps - Optional features - OpenSSH Client.'
    'noconnect'    = 'Cannot reach the brick. Check the cable, that the brick is on, and the address.'
    'cancelled'    = 'Files are only downloaded. Upload them by hand:'
    'vscode'       = 'Next: open this folder in VS Code'
    'f5'           = 'and press F5, choose: EV3 (ev3dev): upload and run'
    'password'     = 'It will ask the brick password - type maker (nothing is shown).'
    'extract'      = 'Unpacking...'
    'addr'         = 'Brick address:'
    'closing'      = 'Do not close this window: it is talking to the brick.'
    'asking'       = 'Checking GitHub for a newer version...'
    'current'      = 'You already have the newest version. Nothing changed.'
    'updated'      = 'Files updated from GitHub.'
    'step1'        = 'Step 1 of 2: checking GitHub for updates'
    'step2'        = 'Step 2 of 2: uploading the program to the brick'
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

Write-Host ''
Write-Host '=== robolab ===' -ForegroundColor Cyan
Write-Host ''

function Run-RoboLab {
    # ---------------- where to unpack ----------------
    if ([string]::IsNullOrWhiteSpace($Dir_)) {
        if ($PSScriptRoot) {
            $Dir_ = $PSScriptRoot
        } elseif (Test-Path (Join-Path (Get-Location).Path 'robot.py')) {
            $Dir_ = (Get-Location).Path          # already inside the project
        } elseif (Test-Path (Join-Path (Get-Location).Path 'robolab\robot.py')) {
            $Dir_ = Join-Path (Get-Location).Path 'robolab'
        } else {
            $Dir_ = Join-Path (Get-Location).Path 'robolab'
        }
    }

    # ---------------- download ----------------
    Write-Host ''
    Say 'step1'
    Say 'downloading'
    $tmp = $env:TEMP
    if ([string]::IsNullOrWhiteSpace($tmp) -or -not (Test-Path $tmp)) { $tmp = $Dir_ }
    $zip = Join-Path $tmp ('robolab-' + $Branch_ + '.zip')
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
    $urls = @(
        ('https://codeload.github.com/' + $Repo + '/zip/refs/heads/' + $Branch_),
        ('https://github.com/' + $Repo + '/archive/refs/heads/' + $Branch_ + '.zip')
    )
    $ok = $false
    foreach ($u in $urls) {
        try {
            Write-Host ('  ' + $u) -ForegroundColor DarkGray
            Invoke-WebRequest -Uri $u -OutFile $zip -UseBasicParsing -TimeoutSec 90
            if ((Get-Item $zip).Length -gt 1000) { $ok = $true; break }
        } catch {
            $ok = $false
        }
    }
    if (-not $ok) {
        Say 'failed'
        return 1
    }

    # ---------------- unpack ----------------
    Say 'extract'
    $stage = Join-Path $tmp ('robolab-stage-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    $tar = Join-Path $env:SystemRoot 'System32\tar.exe'
    if (Test-Path $tar) {
        & $tar -xf $zip -C $stage
    } else {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($zip, $stage)
    }
    $srcRoot = Get-ChildItem -Path $stage -Directory | Select-Object -First 1
    if (-not $srcRoot) { Say 'failed'; return 1 }

    New-Item -ItemType Directory -Path $Dir_ -Force | Out-Null
    $newRobot = Join-Path $srcRoot.FullName 'robot.py'
    $oldRobot = Join-Path $Dir_ 'robot.py'
    $same = $false
    if ((Test-Path $oldRobot) -and (Test-Path $newRobot)) {
        $h1 = (Get-FileHash $oldRobot -Algorithm SHA256).Hash
        $h2 = (Get-FileHash $newRobot -Algorithm SHA256).Hash
        if ($h1 -eq $h2) { $same = $true }
    }
    if ($same) {
        Say 'current'
        # still refresh the other files (docs, tools, install.ps1, ...)
        Get-ChildItem -Path $srcRoot.FullName -Force | ForEach-Object {
            if ($_.Name -ne 'robot.py') {
                Copy-Item $_.FullName $Dir_ -Recurse -Force
            }
        }
    } else {
        if (Test-Path $oldRobot) {
            Copy-Item $oldRobot (Join-Path $Dir_ 'robot.py.old') -Force
            Say 'backup'
        }
        Copy-Item (Join-Path $srcRoot.FullName '*') $Dir_ -Recurse -Force
        Say 'updated'
    }
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $zip -Force -ErrorAction SilentlyContinue

    Write-Host ''
    Say 'done'
    Write-Host ('  ' + $Dir_) -ForegroundColor Green
    Write-Host ''

    # ---------------- upload and run ----------------
    Write-Host ''
    Say 'step2'
    $target = $User_ + '@' + $Host_
    $hasSsh = ($null -ne (Get-Command ssh -ErrorAction SilentlyContinue)) -and
              ($null -ne (Get-Command scp -ErrorAction SilentlyContinue))

    $doRun = $false
    Say 'addr'
    Write-Host ('  ' + $target + '   ' + $RemoteDir) -ForegroundColor DarkGray
    Write-Host ''
    Say 'askrun'
    $answer = Read-Host
    $noWords = @('n', 'no', 'not', 'net')
    $ans = $answer.Trim().ToLower()
    $isNo = $false
    if ($ans.StartsWith([string][char]0x043D)) { $isNo = $true }
    foreach ($w in $noWords) { if ($ans -eq $w) { $isNo = $true } }
    if ($isNo) { $doRun = $false } else { $doRun = $true }

    $optSsh = @('-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL',
                '-o', 'ConnectTimeout=10', '-o', 'NumberOfPasswordPrompts=3')

    if ($doRun -and -not $hasSsh) {
        Say 'nossh'
        $doRun = $false
    }

    if ($doRun) {
        Say 'password'
        Write-Host ''
        Say 'uploading'
        & ssh @optSsh $target ('mkdir -p ' + $RemoteDir)
        if ($LASTEXITCODE -ne 0) {
            Say 'noconnect'
            $doRun = $false
        } else {
            & scp @optSsh (Join-Path $Dir_ 'robot.py') ($target + ':' + $RemoteDir + '/robot.py')
            if ($LASTEXITCODE -ne 0) {
                Say 'noconnect'
                $doRun = $false
            }
        }
        if ($doRun) {
            Write-Host ''
            Say 'running'
            $cmd = 'brickrun --directory="' + $RemoteDir + '" "python3 ' + $RemoteDir + '/robot.py"'
            Write-Host ('  ' + $cmd) -ForegroundColor DarkGray
            Write-Host ''
            & ssh @optSsh $target $cmd
            return 0
        }
    }

    if ($doRun -eq $false) {
        Say 'cancelled'
        Write-Host ('  scp robot.py ' + $target + ':' + $RemoteDir + '/') -ForegroundColor DarkGray
        Write-Host ('  ssh ' + $target + ' brickrun --directory="' + $RemoteDir + '" "' + $RemoteDir + '/robot.py"') -ForegroundColor DarkGray
        Write-Host ''
    }

    Say 'vscode'
    Write-Host ('  ' + $Dir_) -ForegroundColor Green
    Say 'f5'
    Write-Host ''
}

Run-RoboLab

# ---- keep the window open at the end: with  irm ... | iex  the console
# ---- closes instantly and the messages would be lost
Write-Host ''
Say 'closing'
Write-Host ''
try {
    Write-Host 'Press Enter to close...' -ForegroundColor DarkGray
    $null = Read-Host
} catch { }
