[CmdletBinding()]
param(
    [ValidateSet("Claude", "Codex", "OpenCode")]
    [string]$Agent = $(if ($env:SKILLS_AGENT) { $env:SKILLS_AGENT } else { "Claude" }),
    [string]$Target = $env:SKILLS_TARGET,
    [string]$Skill = $(if ($env:SKILLS_NAME) { $env:SKILLS_NAME } else { "bsp" }),
    [string]$Ref = $(if ($env:SKILLS_REF) { $env:SKILLS_REF } else { "main" }),
    [string]$Repository = $(if ($env:SKILLS_REPOSITORY) { $env:SKILLS_REPOSITORY } else { "brake71/1c-ssl-skills" }),
    [string]$SourceDirectory = $env:SKILLS_SOURCE_DIR
)

$ErrorActionPreference = "Stop"

if ($Skill -notmatch "^[a-z0-9][a-z0-9-]*$") {
    throw "Invalid skill name '$Skill'."
}
if ($Repository -notmatch "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$") {
    throw "Invalid GitHub repository '$Repository'."
}
if ([string]::IsNullOrWhiteSpace($Ref) -or $Ref -match "\s") {
    throw "Invalid git ref '$Ref'."
}

$userHome = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
if ([string]::IsNullOrWhiteSpace($Target)) {
    $Target = switch ($Agent) {
        "Claude" {
            $configRoot = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $userHome ".claude" }
            Join-Path $configRoot "skills"
        }
        "Codex" {
            $configRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $userHome ".codex" }
            Join-Path $configRoot "skills"
        }
        "OpenCode" {
            $configRoot = if ($env:XDG_CONFIG_HOME) { $env:XDG_CONFIG_HOME } else { Join-Path $userHome ".config" }
            Join-Path (Join-Path $configRoot "opencode") "skills"
        }
    }
}

$fullTarget = [IO.Path]::GetFullPath($Target)
$filesystemRoot = [IO.Path]::GetPathRoot($fullTarget)
$directorySeparators = [char[]]@("\", "/")
if ($fullTarget.TrimEnd($directorySeparators) -eq $filesystemRoot.TrimEnd($directorySeparators)) {
    throw "Refusing to use '$fullTarget' as the skills directory."
}

$downloadDirectory = $null
$transactionDirectory = $null
$destination = Join-Path $fullTarget $Skill
$backup = $null

try {
    if ($SourceDirectory) {
        $repositoryRoot = [IO.Path]::GetFullPath($SourceDirectory)
    }
    else {
        $downloadDirectory = Join-Path ([IO.Path]::GetTempPath()) ("skill-download-" + [guid]::NewGuid().ToString("N"))
        $archive = Join-Path $downloadDirectory "repository.zip"
        $extracted = Join-Path $downloadDirectory "extracted"
        New-Item -ItemType Directory -Path $extracted -Force | Out-Null

        $encodedRef = [uri]::EscapeDataString($Ref)
        $archiveUrl = "https://codeload.github.com/$Repository/zip/$encodedRef"
        Invoke-WebRequest -Uri $archiveUrl -OutFile $archive -UseBasicParsing
        Expand-Archive -LiteralPath $archive -DestinationPath $extracted

        $repositoryRoot = Get-ChildItem -LiteralPath $extracted -Directory | Select-Object -First 1 -ExpandProperty FullName
        if (-not $repositoryRoot) {
            throw "Downloaded archive has no repository root directory."
        }
    }

    $sourceSkill = Join-Path (Join-Path $repositoryRoot "skills") $Skill
    if (-not (Test-Path -LiteralPath (Join-Path $sourceSkill "SKILL.md") -PathType Leaf)) {
        throw "Skill '$Skill' not found at $sourceSkill."
    }

    New-Item -ItemType Directory -Path $fullTarget -Force | Out-Null
    $transactionDirectory = Join-Path $fullTarget (".skill-install-" + [guid]::NewGuid().ToString("N"))
    $staged = Join-Path $transactionDirectory $Skill
    New-Item -ItemType Directory -Path $transactionDirectory | Out-Null
    Copy-Item -LiteralPath $sourceSkill -Destination $staged -Recurse

    $backup = Join-Path $transactionDirectory "previous"
    if (Test-Path -LiteralPath $destination) {
        Move-Item -LiteralPath $destination -Destination $backup
    }
    Move-Item -LiteralPath $staged -Destination $destination

    Remove-Item -LiteralPath $transactionDirectory -Recurse -Force
    $transactionDirectory = $null
    $backup = $null
}
catch {
    if ($backup -and (Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $destination)) {
        Move-Item -LiteralPath $backup -Destination $destination
    }
    throw
}
finally {
    if ($transactionDirectory -and (Test-Path -LiteralPath $transactionDirectory)) {
        Remove-Item -LiteralPath $transactionDirectory -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($downloadDirectory -and (Test-Path -LiteralPath $downloadDirectory)) {
        Remove-Item -LiteralPath $downloadDirectory -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Output "Installed '$Skill' from '$Repository@$Ref' to '$destination'."
