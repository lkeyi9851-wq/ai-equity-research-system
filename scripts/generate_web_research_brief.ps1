param(
    [Parameter(Mandatory = $true)]
    [string]$Company,

    [Parameter(Mandatory = $true)]
    [string]$Ticker,

    [string]$Market,
    [string]$OutputDir = "outputs",
    [string]$Output,
    [int]$PerQuery = 4,
    [int]$MaxQueries = 3,
    [int]$TimeoutSeconds = 25,
    [ValidateSet("auto", "yahoo", "yfinance")]
    [string]$MarketProvider = "auto",
    [ValidateSet("search", "llm", "auto")]
    [string]$ResearchProvider = "search",
    [string[]]$EvidenceTask,
    [string]$PythonPath,
    [switch]$SkipSearch,
    [switch]$Online
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ProjectVenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EnvPython = $env:AI_EQUITY_PYTHON
$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

function Test-PythonRuntime {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe
    )

    if (-not (Test-Path -LiteralPath $PythonExe)) {
        return $false
    }

    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $PythonExe -c "import sys; sys.exit(0)" *> $null
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
} elseif ($EnvPython -and (Test-PythonRuntime -PythonExe $EnvPython)) {
    $Python = $EnvPython
} elseif (Test-PythonRuntime -PythonExe $ProjectVenvPython) {
    $Python = $ProjectVenvPython
} elseif ((Get-Command python -ErrorAction SilentlyContinue) -and (Test-PythonRuntime -PythonExe (Get-Command python).Source)) {
    $Python = (Get-Command python).Source
} elseif (Test-PythonRuntime -PythonExe $BundledPython) {
    Write-Warning "Using Codex bundled Python as a local fallback. For OpenClaw, use the project .venv, system Python, AI_EQUITY_PYTHON, or -PythonPath."
    $Python = $BundledPython
} else {
    throw "No usable Python runtime found. Set AI_EQUITY_PYTHON, pass -PythonPath, or create a working project .venv."
}

$ArgsList = @(
    (Join-Path $ProjectRoot "src\web_research_brief.py"),
    "--company", $Company,
    "--ticker", $Ticker,
    "--output-dir", $OutputDir,
    "--per-query", $PerQuery,
    "--max-queries", $MaxQueries,
    "--timeout-seconds", $TimeoutSeconds,
    "--market-provider", $MarketProvider,
    "--research-provider", $ResearchProvider
)

if ($Market) {
    $ArgsList += @("--market", $Market)
}

if ($Output) {
    $ArgsList += @("--output", $Output)
}

if ($EvidenceTask) {
    foreach ($Task in $EvidenceTask) {
        $ArgsList += @("--evidence-task", $Task)
    }
}

if ($Online) {
    $ArgsList += "--online"
}

if ($SkipSearch) {
    $ArgsList += "--skip-search"
}

& $Python @ArgsList
