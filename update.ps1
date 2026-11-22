$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

$stage = Join-Path $root '.jarvis_update_staging'
$files = @(
    'jarvis/brain.py',
    'jarvis/app.py',
    'jarvis/tts.py',
    'jarvis/audio.py',
    'jarvis/config.py',
    'jarvis/asr.py',
    'jarvis/pc_control.py'
)
$stagedFiles = @()
$installedTargets = New-Object System.Collections.Generic.List[string]
$createdTargets = New-Object System.Collections.Generic.List[string]
$success = $false

try {
    if (-not (Test-Path -LiteralPath (Join-Path $root 'jarvis\__init__.py'))) {
        throw 'The jarvis package was not found. Run this updater from the project folder.'
    }
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw 'Python launcher "py" was not found.'
    }

    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
    New-Item -ItemType Directory -Path $stage -Force | Out-Null

    Write-Host 'Downloading update files...'
    foreach ($relative in $files) {
        $localRelative = $relative.Replace('/', '\')
        $stagedPath = Join-Path $stage $localRelative
        $stagedDirectory = Split-Path -Parent $stagedPath
        New-Item -ItemType Directory -Path $stagedDirectory -Force | Out-Null

        $url = 'https://raw.githubusercontent.com/Andrik717/Jarvis-AI/main/' + $relative
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

    $stagedTts = Join-Path $stage 'jarvis\tts.py'
    if (-not (Select-String -LiteralPath $stagedTts -Pattern '^\s*def reset_stop\(' -Quiet)) {
        throw 'Downloaded jarvis/tts.py does not contain SpeechOutput.reset_stop. No project files were changed.'
    }

    if (-not (Select-String -LiteralPath $stagedTts -Pattern 'ru-RU-DmitryNeural' -Quiet)) {
        throw 'Downloaded TTS file does not contain the confirmed Dmitry voice.'
    }

    $stagedBrain = Join-Path $stage 'jarvis\brain.py'
    if (-not (Select-String -LiteralPath $stagedBrain -Pattern 'MAX_HISTORY_MESSAGES = 20' -Quiet)) {
        throw 'Downloaded brain.py is missing the expected conversation-context update.'
    }

    $stagedApp = Join-Path $stage 'jarvis\app.py'
    if (-not (Select-String -LiteralPath $stagedApp -Pattern 'weather_context' -Quiet)) {
        throw 'Downloaded app.py is missing contextual follow-up handling.'
    }

    $stagedAsr = Join-Path $stage 'jarvis\asr.py'
    if (-not (Select-String -LiteralPath $stagedAsr -Pattern 'def transcribe\(self, audio: np.ndarray, context: str = ""\)' -Quiet)) {
        throw 'Downloaded asr.py is missing contextual local speech recognition.'
    }

    if (-not (Select-String -LiteralPath $stagedBrain -Pattern 'def transcription_context\(' -Quiet)) {
        throw 'Downloaded brain.py is missing the speech context provider.'
    }

    if (-not (Select-String -LiteralPath $stagedApp -Pattern 'context=self.brain.transcription_context' -Quiet)) {
        throw 'Downloaded app.py is not passing dialogue context to speech recognition.'
    }

    $stagedPcControl = Join-Path $stage 'jarvis\pc_control.py'
    if (-not (Select-String -LiteralPath $stagedPcControl -Pattern 'def _search_web\(' -Quiet)) {
        throw 'Downloaded pc_control.py is missing in-chat web search.'
    }

    if (-not (Select-String -LiteralPath $stagedPcControl -Pattern 'def _is_close_alias\(' -Quiet)) {
        throw 'Downloaded pc_control.py is missing safe typo matching for known commands.'
    }

    if (-not (Select-String -LiteralPath $stagedPcControl -Pattern 'открою' -Quiet)) {
        throw 'Downloaded pc_control.py is missing natural Russian command forms.'
    }

    if (-not (Select-String -LiteralPath $stagedPcControl -Pattern 'taskkill.exe' -Quiet)) {
        throw 'Downloaded pc_control.py is missing allowlisted application closing.'
    }

    if (-not (Select-String -LiteralPath $stagedApp -SimpleMatch -Pattern 'handle_command(question, previous_user_text=previous_user_text)' -Quiet)) {
        throw 'Downloaded app.py is not passing recent dialogue context to command routing.'
    }

    Write-Host 'Checking downloaded Python files...'
    $compileArgs = @('-3.12', '-m', 'py_compile') + $stagedFiles
    & py @compileArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Python syntax check failed. No project files were changed.'
    }

    Write-Host 'Creating backups and installing files...'
    foreach ($relative in $files) {
        $localRelative = $relative.Replace('/', '\')
        $target = Join-Path $root $localRelative
        $source = Join-Path $stage $localRelative
        $targetDirectory = Split-Path -Parent $target

        if (-not (Test-Path -LiteralPath $targetDirectory)) {
            New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
        }

        if (Test-Path -LiteralPath $target) {
            Copy-Item -LiteralPath $target -Destination ($target + '.bak') -Force
        }
        else {
            $createdTargets.Add($target)
        }

        $installedTargets.Add($target)
        Copy-Item -LiteralPath $source -Destination $target -Force
        Write-Host "Installed: $relative"
    }

    $installedTts = Join-Path $root 'jarvis\tts.py'
    if (-not (Select-String -LiteralPath $installedTts -Pattern '^\s*def reset_stop\(' -Quiet)) {
        throw 'Installed jarvis/tts.py is missing SpeechOutput.reset_stop.'
    }

    Write-Host 'Checking installed Python files...'
    $installedCompileArgs = @('-3.12', '-m', 'py_compile') + @($installedTargets.ToArray())
    & py @installedCompileArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Installed files failed the Python syntax check.'
    }

    $success = $true
    Write-Host ''
    Write-Host 'UPDATE SUCCESSFUL. Backups were saved as .bak files.' -ForegroundColor Green
}
catch {
    Write-Host ''
    Write-Host ('UPDATE FAILED: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Restoring files changed by this update...' -ForegroundColor Yellow

    $restoreTargets = @($installedTargets.ToArray())
    [array]::Reverse($restoreTargets)
    foreach ($target in $restoreTargets) {
        $backup = $target + '.bak'
        if (Test-Path -LiteralPath $backup) {
            Copy-Item -LiteralPath $backup -Destination $target -Force
        }
    }
    foreach ($target in $createdTargets) {
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Force
        }
    }
    exit 1
}
finally {
    if ($success -and (Test-Path -LiteralPath $stage)) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
    elseif (Test-Path -LiteralPath $stage) {
        Write-Host ('Staging files kept for diagnosis: ' + $stage)
    }
}