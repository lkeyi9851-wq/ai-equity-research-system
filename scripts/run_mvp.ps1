param(
    [string]$InputFile,

    [string]$Request,
    [string]$Company,
    [string]$Ticker,
    [string]$Market,
    [ValidateSet("off", "auto", "online")]
    [string]$WebMode = "auto",
    [ValidateSet("auto", "yahoo", "yfinance")]
    [string]$MarketProvider = "auto",
    [ValidateSet("search", "llm", "auto")]
    [string]$ResearchProvider = "search",
    [int]$WebTimeoutSeconds = 25,
    [string]$Language = "EN",
    [string]$OutputDir = "outputs",
    [string]$PythonPath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ProjectVenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EnvPython = $env:AI_EQUITY_PYTHON
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

function Test-PythonModules {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe,
        [string[]]$Modules = @()
    )

    if (-not (Test-Path -LiteralPath $PythonExe)) {
        return $false
    }

    $ModuleList = ($Modules | ForEach-Object { "'$_'" }) -join ","
    $CheckCode = "import importlib.util, sys; missing=[m for m in [$ModuleList] if importlib.util.find_spec(m) is None]; sys.exit(1 if missing else 0)"
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $PythonExe -c $CheckCode *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
}

if ($PythonPath) {
    if (-not (Test-Path -LiteralPath $PythonPath)) {
        throw "PythonPath not found: $PythonPath"
    }
    $Python = $PythonPath
} elseif ($EnvPython -and (Test-PythonModules -PythonExe $EnvPython -Modules @("openpyxl", "pypdf"))) {
    $Python = $EnvPython
} elseif (Test-PythonModules -PythonExe $ProjectVenvPython -Modules @("openpyxl", "pypdf")) {
    $Python = $ProjectVenvPython
} elseif ((Get-Command python -ErrorAction SilentlyContinue) -and (Test-PythonModules -PythonExe (Get-Command python).Source -Modules @("openpyxl", "pypdf"))) {
    $Python = (Get-Command python).Source
} elseif (Test-PythonModules -PythonExe $BundledPython -Modules @("openpyxl", "pypdf")) {
    Write-Warning "Using Codex bundled Python as a local fallback. For OpenClaw, install requirements.txt and set AI_EQUITY_PYTHON or use the project .venv."
    $Python = $BundledPython
} else {
    throw "No usable Python runtime found with required modules: openpyxl, pypdf. Install dependencies with: python -m pip install -r requirements.txt, or set AI_EQUITY_PYTHON / pass -PythonPath."
}

$ArgsList = @(
    (Join-Path $ProjectRoot "src\mvp_research_memo.py"),
    "--language", $Language,
    "--web-mode", $WebMode,
    "--market-provider", $MarketProvider,
    "--research-provider", $ResearchProvider,
    "--web-timeout-seconds", $WebTimeoutSeconds,
    "--output-dir", $OutputDir
)

if ($InputFile) {
    $ArgsList += @("--input", $InputFile)
}

if ($Request) {
    $ArgsList += @("--request", $Request)
}

if ($Company) {
    $ArgsList += @("--company", $Company)
}

if ($Ticker) {
    $ArgsList += @("--ticker", $Ticker)
}

if ($Market) {
    $ArgsList += @("--market", $Market)
}

& $Python @ArgsList
