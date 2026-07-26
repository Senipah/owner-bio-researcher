param(
    [string]$PythonVersion = "3.12",
    [string]$VenvName = "venv"
)

$ErrorActionPreference = "Stop"

function Resolve-RepoChildPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,
        [Parameter(Mandatory = $true)]
        [string]$ChildPath
    )

    $rootFull = [IO.Path]::GetFullPath($RepoRoot)
    $candidateFull = [IO.Path]::GetFullPath((Join-Path $rootFull $ChildPath))
    $rootPrefix = $rootFull.TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar

    if (-not $candidateFull.StartsWith(
        $rootPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to use a venv path outside this repository: $candidateFull"
    }
    return $candidateFull
}

function Remove-LocalVenv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $resolvedPath = [IO.Path]::GetFullPath($Path)
    $resolvedRoot = [IO.Path]::GetFullPath($RepoRoot)
    $rootPrefix = $resolvedRoot.TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedPath.StartsWith(
        $rootPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to delete a directory outside this repository: $resolvedPath"
    }

    Get-ChildItem -LiteralPath $resolvedPath -Recurse -Force -ErrorAction SilentlyContinue |
        ForEach-Object {
            try { $_.Attributes = [IO.FileAttributes]::Normal } catch {}
        }
    Remove-Item -LiteralPath $resolvedPath -Recurse -Force
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$requirementsPath = Join-Path $repoRoot "requirements.txt"
$venvPath = Resolve-RepoChildPath -RepoRoot $repoRoot -ChildPath $VenvName

if (-not (Test-Path -LiteralPath $requirementsPath)) {
    throw "requirements.txt was not found at $requirementsPath"
}

$availableVersion = & py "-$PythonVersion" -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>$null
if ($LASTEXITCODE -ne 0 -or $availableVersion -ne $PythonVersion) {
    throw "Python $PythonVersion is required. Install it so 'py -$PythonVersion' works."
}

Write-Host "Repository: $repoRoot"
Write-Host "Recreating: $venvPath"
Remove-LocalVenv -Path $venvPath -RepoRoot $repoRoot

& py "-$PythonVersion" -m venv $venvPath
if ($LASTEXITCODE -ne 0) {
    throw "Python failed to create the virtual environment."
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "The virtual environment does not contain $venvPython"
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip."
}

& $venvPython -m pip install -r $requirementsPath
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install requirements."
}

Write-Host ""
Write-Host "Environment ready."
Write-Host "Activate with: .\$VenvName\Scripts\Activate.ps1"
Write-Host "Or run scripts directly with: .\$VenvName\Scripts\python.exe"
