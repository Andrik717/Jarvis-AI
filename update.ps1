#requires -Version 5.1
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

$stage = Join-Path $root ".jarvis_update_staging"
$files = @(
    "jarvis/brain.py",
    "jarvis/app.py",
    "jarvis/tts.py",
    "jarvis/audio.py",
    "jarvis/config.py",
    "jarvis/asr.py",
    "jarvis/pc_control.py",
    "jarvis_tts_diagnostic.py"
)
$stagedFiles = @()
$installedTargets = @()
$createdTargets = @()
$success = $false

try {
    if (-not (Test-Path -LiteralPath (Join-Path $root "jarvis\__init__.py"))) {
        throw "The jarvis package was not found. Run this updater from the project folder."
    }
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "Python launcher py was not found."
    }

    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
    New-Item -ItemType Directory -Path $stage -Force | Out-Null

    Write-Host "Downloading update files..."
    foreach ($relative in $files) {
        $localRelative = $relative.Replace([char]47, [char]92)
        $stagedPath = Join-Path $stage $localRelative
        $stagedDirectory = Split-Path -Parent $stagedPath
        New-Item -ItemType Directory -Path $stagedDirectory -Force | Out-Null

        $url = "https://raw.githubusercontent.com/Andrik717/Jarvis-AI/main/" + $relative
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $stagedPath

        if (-not (Test-Path -LiteralPath $stagedPath)) {
            throw "Download did not create file: $relative"
        }
        if ((Get-Item -LiteralPath $stagedPath).Length -lt 100) {
            throw "Downloaded file is unexpectedly small: $relative"
        }
        $stagedFiles += $stagedPath
        Write-Host "Downloaded: $relative"
    }

    $stagedTts = Join-Path $stage "jarvis\tts.py"
    if (-not (Select-String -LiteralPath $stagedTts -Pattern "^\s*def reset_stop\(" -Quiet)) {
        throw "Downloaded tts.py is missing reset_stop. No project files were changed."
    }
    if (-not (Select-String -LiteralPath $stagedTts -Pattern "ru-RU-DmitryNeural" -Quiet)) {
        throw "Downloaded TTS file is missing the Dmitry voice setting."
    }
    if (Select-String -LiteralPath $stagedTts -Pattern "SAPI|_sapi|SpVoice|last_fallback_error" -Quiet) {
        throw "Downloaded TTS file still contains a Windows speech fallback."
    }

    $stagedBrain = Join-Path $stage "jarvis\brain.py"
    if (-not (Select-String -LiteralPath $stagedBrain -SimpleMatch -Pattern "MAX_HISTORY_MESSAGES = 20" -Quiet)) {
        throw "Downloaded brain.py is missing the conversation context update."
    }

    $stagedApp = Join-Path $stage "jarvis\app.py"
    if (-not (Select-String -LiteralPath $stagedApp -SimpleMatch -Pattern "weather_context" -Quiet)) {
        throw "Downloaded app.py is missing contextual follow-up handling."
    }
    if (-not (Select-String -LiteralPath $stagedApp -SimpleMatch -Pattern "previous_user_text" -Quiet)) {
        throw "Downloaded app.py is missing recent dialogue context routing."
    }

    $stagedAsr = Join-Path $stage "jarvis\asr.py"
    if (-not (Select-String -LiteralPath $stagedAsr -Pattern 'def transcribe\(self, audio: np.ndarray, context: str = ""\)' -Quiet)) {
        throw "Downloaded asr.py is missing contextual local speech recognition."
    }
    if (-not (Select-String -LiteralPath $stagedBrain -Pattern "def transcription_context\(" -Quiet)) {
        throw "Downloaded brain.py is missing the speech context provider."
    }
    if (-not (Select-String -LiteralPath $stagedApp -SimpleMatch -Pattern "context=self.brain.transcription_context" -Quiet)) {
        throw "Downloaded app.py is not passing dialogue context to speech recognition."
    }

    $stagedPcControl = Join-Path $stage "jarvis\pc_control.py"
    foreach ($required in @("def _search_web(", "def _is_close_alias(", "taskkill.exe")) {
        if (-not (Select-String -LiteralPath $stagedPcControl -SimpleMatch -Pattern $required -Quiet)) {
            throw "Downloaded pc_control.py is missing required feature: $required"
        }
    }

    Write-Host "Checking downloaded Python files..."
    $compileArgs = @("-3.12", "-m", "py_compile") + $stagedFiles
    & py @compileArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Python syntax check failed. No project files were changed."
    }

    Write-Host "Creating backups and installing files..."
    foreach ($relative in $files) {
        $localRelative = $relative.Replace([char]47, [char]92)
        $target = Join-Path $root $localRelative
        $source = Join-Path $stage $localRelative
        $targetDirectory = Split-Path -Parent $target

        if (-not (Test-Path -LiteralPath $targetDirectory)) {
            New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
        }
        if (Test-Path -LiteralPath $target) {
            Copy-Item -LiteralPath $target -Destination ($target + ".bak") -Force
        }
        else {
            $createdTargets += $target
        }

        $installedTargets += $target
        Copy-Item -LiteralPath $source -Destination $target -Force
        Write-Host "Installed: $relative"
    }

    $installedTts = Join-Path $root "jarvis\tts.py"
    $installedTtsText = Get-Content -LiteralPath $installedTts -Raw
    if ($installedTtsText -notmatch "def reset_stop") {
        throw "Installed tts.py is missing reset_stop."
    }

    Write-Host "Checking installed Python files..."
    $installedCompileArgs = @("-3.12", "-m", "py_compile") + $installedTargets
    & py @installedCompileArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Installed files failed the Python syntax check."
    }

    Write-Host ""
    Write-Host "Updating Edge TTS package..."
    & py -3.12 -m pip install --upgrade edge-tts
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Edge TTS package could not be upgraded. The diagnostic will show the installed version." -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Testing Dmitry voice directly, outside the Jarvis interface..."
    & py -3.12 (Join-Path $root "jarvis_tts_diagnostic.py")
    $ttsDiagnosticExit = $LASTEXITCODE
    if ($ttsDiagnosticExit -eq 0) {
        Write-Host "Edge TTS direct test passed." -ForegroundColor Green
    }
    else {
        Write-Host "WARNING: Edge TTS direct test failed (exit $ttsDiagnosticExit). The report above identifies the local failure; speech will remain silent until Edge TTS is available." -ForegroundColor Yellow
    }

    $success = $true
    Write-Host ""
    Write-Host "UPDATE SUCCESSFUL. Backups were saved as .bak files." -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host ("UPDATE FAILED: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host "Restoring files changed by this update..." -ForegroundColor Yellow

    [array]::Reverse($installedTargets)
    foreach ($target in $installedTargets) {
        $backup = $target + ".bak"
        if (Test-Path -LiteralPath $backup) {
            Copy-Item -LiteralPath $backup -Destination $target -Force
        }
    }
    foreach ($target in $createdTargets) {
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Force
        }
    }
    throw
}

if ($success -and (Test-Path -LiteralPath $stage)) {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
