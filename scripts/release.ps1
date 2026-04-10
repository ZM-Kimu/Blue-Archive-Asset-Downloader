#!/usr/bin/env pwsh

[CmdletBinding()]
param(
    [string]$Version,
    [string]$BaseRef,
    [string]$HeadRef = "HEAD",
    [switch]$SkipPreflight,
    [switch]$SkipChangelog,
    [switch]$SkipCommit,
    [switch]$AllowDirtyWorkingTree,
    [Alias("AllowNonDevBranch")]
    [switch]$AllowNonReleaseBranch,
    [switch]$Push,
    [switch]$DryRun,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Read-TextValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Prompt,
        [Parameter(Mandatory = $true)]
        [string]$DefaultValue
    )

    if ($NonInteractive) {
        return $DefaultValue
    }

    $response = Read-Host "$Prompt [$DefaultValue]"
    if ([string]::IsNullOrWhiteSpace($response)) {
        return $DefaultValue
    }
    return $response.Trim()
}

function Read-BooleanValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Prompt,
        [Parameter(Mandatory = $true)]
        [bool]$DefaultValue
    )

    if ($NonInteractive) {
        return $DefaultValue
    }

    $defaultToken = if ($DefaultValue) { "Y/n" } else { "y/N" }

    while ($true) {
        $response = Read-Host "$Prompt [$defaultToken]"
        if ([string]::IsNullOrWhiteSpace($response)) {
            return $DefaultValue
        }

        switch ($response.Trim().ToLowerInvariant()) {
            "y" { return $true }
            "yes" { return $true }
            "n" { return $false }
            "no" { return $false }
            default { Write-Host "Please answer yes or no." -ForegroundColor Yellow }
        }
    }
}

function Invoke-GitText {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & git @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git $($Arguments -join ' ')`n$output"
    }
    return ($output -join "`n").Trim()
}

function Test-GitRef {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RefName
    )

    & git rev-parse --verify --quiet $RefName *> $null
    return $LASTEXITCODE -eq 0
}

function Get-PreferredRemote {
    $upstream = & git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}" 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($upstream)) {
        $parts = $upstream.Trim().Split("/", 2)
        if ($parts.Length -ge 2 -and -not [string]::IsNullOrWhiteSpace($parts[0])) {
            return $parts[0]
        }
    }

    if (Test-GitRef -RefName "origin/HEAD" -or Test-GitRef -RefName "origin/main") {
        return "origin"
    }

    $remotes = & git remote 2>$null
    if ($LASTEXITCODE -eq 0) {
        foreach ($remote in $remotes) {
            if (-not [string]::IsNullOrWhiteSpace($remote)) {
                return $remote.Trim()
            }
        }
    }

    throw "Unable to determine the preferred Git remote."
}

function Get-DefaultBaseRef {
    $remote = Get-PreferredRemote

    if (Test-GitRef -RefName "$remote/main") {
        return "$remote/main"
    }
    if (Test-GitRef -RefName "main") {
        return "main"
    }
    return "HEAD"
}

function Get-LatestTagRef {
    $tag = & git describe --tags --abbrev=0 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($tag)) {
        return $tag.Trim()
    }

    return $null
}

function Get-DefaultChangelogBaseRef {
    $latestTag = Get-LatestTagRef
    if ($latestTag) {
        return $latestTag
    }

    return Get-DefaultBaseRef
}

function Read-Utf8File {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
}

function Write-Utf8File {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Get-ProjectVersion {
    $content = Read-Utf8File (Join-Path (Get-RepoRoot) "pyproject.toml")
    $match = [regex]::Match($content, '(?m)^version = "([^"]+)"\s*$')
    if (-not $match.Success) {
        throw "Unable to locate the project version in pyproject.toml."
    }
    return $match.Groups[1].Value
}

function Get-ReadmeVersion {
    $content = Read-Utf8File (Join-Path (Get-RepoRoot) "README.md")
    $match = [regex]::Match($content, '(?m)^Blue Archive Asset Downloader v([^\r\n]+)\.\s*$')
    if (-not $match.Success) {
        throw "Unable to locate the README version marker."
    }
    return $match.Groups[1].Value
}

function Set-ProjectVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$NewVersion
    )

    $path = Join-Path (Get-RepoRoot) "pyproject.toml"
    $content = Read-Utf8File $path
    $currentVersion = [regex]::Match($content, '(?m)^version = "([^"]+)"\s*$')
    if ($currentVersion.Success -and $currentVersion.Groups[1].Value -eq $NewVersion) {
        if ($DryRun) {
            Write-Host "[dry-run] Project version already matches $NewVersion" -ForegroundColor Cyan
        }
        return
    }

    $updated = $content -creplace '(?m)^version = "[^"]+"\s*$', "version = `"$NewVersion`""

    if ($updated -eq $content) {
        throw "Unable to update the project version in pyproject.toml."
    }

    if ($DryRun) {
        Write-Host "[dry-run] Would update pyproject.toml version to $NewVersion" -ForegroundColor Cyan
        return
    }

    Write-Utf8File -Path $path -Content $updated
}

function Set-ReadmeVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$NewVersion
    )

    $path = Join-Path (Get-RepoRoot) "README.md"
    $content = Read-Utf8File $path
    $currentVersion = [regex]::Match($content, '(?m)^Blue Archive Asset Downloader v([^\r\n]+)\.\s*$')
    if ($currentVersion.Success -and $currentVersion.Groups[1].Value -eq $NewVersion) {
        if ($DryRun) {
            Write-Host "[dry-run] README version already matches $NewVersion" -ForegroundColor Cyan
        }
        return
    }

    $updated = $content -creplace '(?m)^Blue Archive Asset Downloader v[^\r\n]+\.\s*$', "Blue Archive Asset Downloader v$NewVersion."

    if ($updated -eq $content) {
        throw "Unable to update the README version marker."
    }

    if ($DryRun) {
        Write-Host "[dry-run] Would update README.md version to $NewVersion" -ForegroundColor Cyan
        return
    }

    Write-Utf8File -Path $path -Content $updated
}

function Invoke-PreflightChecks {
    $scriptPath = Join-Path $PSScriptRoot "run-preflight.ps1"
    Write-Host "Running preflight checks..." -ForegroundColor Cyan
    & $scriptPath
    if ($LASTEXITCODE -ne 0) {
        throw "Preflight checks failed."
    }
}

function Update-Changelog {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FromRef,
        [Parameter(Mandatory = $true)]
        [string]$ToRef
    )

    $scriptPath = Join-Path $PSScriptRoot "update_changelog.py"
    $outputPath = Join-Path (Get-RepoRoot) "CHANGELOG.md"

    if ($DryRun) {
        Write-Host "[dry-run] Would regenerate CHANGELOG.md from $FromRef..$ToRef" -ForegroundColor Cyan
        return
    }

    Write-Host "Regenerating CHANGELOG.md..." -ForegroundColor Cyan
    & python $scriptPath update --base $FromRef --head $ToRef --output $outputPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to regenerate CHANGELOG.md."
    }
}

function Finalize-ChangelogRelease {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ReleaseVersion
    )

    $scriptPath = Join-Path $PSScriptRoot "update_changelog.py"
    $outputPath = Join-Path (Get-RepoRoot) "CHANGELOG.md"
    $releaseDate = Get-Date -Format "yyyy-MM-dd"

    if ($DryRun) {
        Write-Host "[dry-run] Would finalize CHANGELOG.md as v$ReleaseVersion on $releaseDate" -ForegroundColor Cyan
        return
    }

    Write-Host "Finalizing CHANGELOG.md for v$ReleaseVersion..." -ForegroundColor Cyan
    & python $scriptPath finalize --version $ReleaseVersion --date $releaseDate --path $outputPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to finalize CHANGELOG.md."
    }
}

function Get-StagedReleaseFiles {
    $output = & git diff --cached --name-only -- pyproject.toml README.md CHANGELOG.md 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to inspect staged release files.`n$output"
    }
    return @($output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function New-ReleaseCommit {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ReleaseVersion
    )

    if ($DryRun) {
        Write-Host "[dry-run] Would create commit: chore(release): prepare v$ReleaseVersion" -ForegroundColor Cyan
        return
    }

    & git add -- pyproject.toml README.md CHANGELOG.md
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to stage release files."
    }

    $stagedFiles = Get-StagedReleaseFiles
    if ($stagedFiles.Count -eq 0) {
        Write-Host "No release file changes were staged. Skipping commit." -ForegroundColor Yellow
        return
    }

    & git commit -m "chore(release): prepare v$ReleaseVersion"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the release preparation commit."
    }
}

function Push-CurrentBranch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BranchName
    )

    $remote = Get-PreferredRemote

    if ($DryRun) {
        Write-Host "[dry-run] Would push branch '$BranchName' to $remote" -ForegroundColor Cyan
        return
    }

    & git push $remote $BranchName
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to push branch '$BranchName' to $remote."
    }
}

function Assert-VersionFormat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if ($Value -notmatch '^[0-9A-Za-z][0-9A-Za-z.\-+]*$') {
        throw "Release version '$Value' contains unsupported characters."
    }
}

Set-Location (Get-RepoRoot)

$currentBranch = Invoke-GitText -Arguments @("branch", "--show-current")
$workingTreeStatus = Invoke-GitText -Arguments @("status", "--short")
$currentVersion = Get-ProjectVersion
$readmeVersion = Get-ReadmeVersion

if ($readmeVersion -ne $currentVersion) {
    Write-Warning "README.md version ($readmeVersion) does not match pyproject.toml version ($currentVersion)."
}

if ($currentBranch -notmatch '^release\/v[0-9A-Za-z][0-9A-Za-z.\-+]*$') {
    Write-Warning "Current branch is '$currentBranch'. Release preparation is usually performed on 'release/vX.Y.Z' branches."
    $continueOnCurrentBranch = if ($PSBoundParameters.ContainsKey("AllowNonReleaseBranch") -or $PSBoundParameters.ContainsKey("AllowNonDevBranch")) {
        $AllowNonReleaseBranch.IsPresent
    }
    else {
        Read-BooleanValue -Prompt "Continue on the current branch?" -DefaultValue $false
    }

    if (-not $continueOnCurrentBranch) {
        throw "Release preparation cancelled."
    }
}

if (-not [string]::IsNullOrWhiteSpace($workingTreeStatus)) {
    Write-Warning "Working tree is not clean. Only release files will be staged automatically."
    $continueWithDirtyTree = if ($PSBoundParameters.ContainsKey("AllowDirtyWorkingTree")) {
        $AllowDirtyWorkingTree.IsPresent
    }
    else {
        Read-BooleanValue -Prompt "Continue with the current working tree?" -DefaultValue $false
    }

    if (-not $continueWithDirtyTree) {
        throw "Release preparation cancelled."
    }
}

$targetVersion = if ($PSBoundParameters.ContainsKey("Version")) {
    $Version
}
else {
    Read-TextValue -Prompt "Release version" -DefaultValue $currentVersion
}

Assert-VersionFormat -Value $targetVersion

$defaultBaseRef = Get-DefaultChangelogBaseRef

$resolvedBaseRef = if ($PSBoundParameters.ContainsKey("BaseRef")) {
    $BaseRef
}
else {
    Read-TextValue -Prompt "Changelog base ref" -DefaultValue $defaultBaseRef
}

$resolvedHeadRef = if ($PSBoundParameters.ContainsKey("HeadRef")) {
    $HeadRef
}
else {
    Read-TextValue -Prompt "Changelog head ref" -DefaultValue $HeadRef
}

if (-not (Test-GitRef -RefName $resolvedBaseRef)) {
    throw "Git ref '$resolvedBaseRef' does not exist."
}

if (-not (Test-GitRef -RefName $resolvedHeadRef)) {
    throw "Git ref '$resolvedHeadRef' does not exist."
}

$runPreflight = if ($PSBoundParameters.ContainsKey("SkipPreflight")) {
    -not $SkipPreflight.IsPresent
}
else {
    Read-BooleanValue -Prompt "Run preflight checks?" -DefaultValue $true
}

$updateChangelog = if ($PSBoundParameters.ContainsKey("SkipChangelog")) {
    -not $SkipChangelog.IsPresent
}
else {
    Read-BooleanValue -Prompt "Regenerate CHANGELOG.md?" -DefaultValue $true
}

$createCommit = if ($PSBoundParameters.ContainsKey("SkipCommit")) {
    -not $SkipCommit.IsPresent
}
else {
    Read-BooleanValue -Prompt "Create a release preparation commit?" -DefaultValue $true
}

$pushBranch = if ($PSBoundParameters.ContainsKey("Push")) {
    $Push.IsPresent
}
else {
    Read-BooleanValue -Prompt "Push the current branch after preparation?" -DefaultValue $false
}

Write-Host ""
Write-Host "Release plan" -ForegroundColor Green
Write-Host "  Branch:      $currentBranch"
Write-Host "  Version:     $currentVersion -> $targetVersion"
Write-Host "  Git range:   $resolvedBaseRef .. $resolvedHeadRef"
Write-Host "  Preflight:   $runPreflight"
Write-Host "  Changelog:   $updateChangelog"
Write-Host "  Commit:      $createCommit"
Write-Host "  Push:        $pushBranch"
Write-Host "  Dry run:     $DryRun"
Write-Host ""

if (-not (Read-BooleanValue -Prompt "Proceed with release preparation?" -DefaultValue $true)) {
    throw "Release preparation cancelled."
}

if ($runPreflight) {
    Invoke-PreflightChecks
}

Set-ProjectVersion -NewVersion $targetVersion
Set-ReadmeVersion -NewVersion $targetVersion

if ($updateChangelog) {
    Update-Changelog -FromRef $resolvedBaseRef -ToRef $resolvedHeadRef
    Finalize-ChangelogRelease -ReleaseVersion $targetVersion
}

if ($createCommit) {
    New-ReleaseCommit -ReleaseVersion $targetVersion
}

if ($pushBranch) {
    Push-CurrentBranch -BranchName $currentBranch
}

Write-Host ""
Write-Host "Release preparation completed." -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  1. Push '$currentBranch' when the release preparation is ready."
Write-Host "  2. Open a pull request from '$currentBranch' to 'main' manually."
Write-Host "  3. After the PR is merged into 'main', GitHub Actions will create the tag and GitHub Release from CHANGELOG.md."
