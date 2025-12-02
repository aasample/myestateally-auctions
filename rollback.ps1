# rollback.ps1 - Quick rollback to previous version
# Usage: .\rollback.ps1

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "MyEstateAlly - Version Rollback Tool" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

Write-Host "Fetching versions..." -ForegroundColor Yellow

# Get all versions
try {
    $versionsJson = gcloud app versions list --format="json" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error fetching versions. Make sure you're logged in to gcloud." -ForegroundColor Red
        Write-Host "Run: gcloud auth login" -ForegroundColor Yellow
        exit 1
    }
    $versions = $versionsJson | ConvertFrom-Json
} catch {
    Write-Host "Error parsing versions. Please check gcloud is installed and configured." -ForegroundColor Red
    exit 1
}

# Find current version (serving 100% traffic)
$current = $versions | Where-Object { $_.traffic_split -eq 1.0 } | Select-Object -First 1

# Sort all versions by creation time (newest first)
$allVersions = $versions | Sort-Object { [DateTime]::Parse($_.version.createTime) } -Descending

if ($current) {
    Write-Host "Current version: " -NoNewline -ForegroundColor Green
    Write-Host "$($current.id)" -ForegroundColor White
    Write-Host "Created: " -NoNewline -ForegroundColor Gray
    Write-Host "$($current.version.createTime)" -ForegroundColor White
} else {
    Write-Host "No active version found." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Available versions:" -ForegroundColor Yellow
Write-Host "-" * 60 -ForegroundColor Gray

$i = 0
$versionList = @()
foreach ($v in ($allVersions | Select-Object -First 10)) {
    $trafficPercent = [math]::Round($v.traffic_split * 100, 1)
    $status = if ($v.traffic_split -eq 1.0) { 
        " [ACTIVE]" -ForegroundColor Green 
    } elseif ($v.traffic_split -gt 0) { 
        " [PARTIAL: $trafficPercent%]" -ForegroundColor Yellow 
    } else { 
        " [INACTIVE]" -ForegroundColor DarkGray 
    }
    
    Write-Host "  $i. " -NoNewline -ForegroundColor Cyan
    Write-Host "$($v.id)" -NoNewline -ForegroundColor White
    Write-Host $status
    Write-Host "     Created: $($v.version.createTime)" -ForegroundColor DarkGray
    $versionList += $v.id
    $i++
}

Write-Host ""
$choice = Read-Host "Enter number to rollback to (or press Enter for previous version, 'q' to quit)"

if ($choice -eq 'q' -or $choice -eq 'Q') {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit 0
}

if ([string]::IsNullOrWhiteSpace($choice)) {
    # Rollback to previous version
    if ($allVersions.Count -lt 2) {
        Write-Host "No previous version available." -ForegroundColor Red
        exit 1
    }
    $targetVersion = ($allVersions | Select-Object -Skip 1 | Select-Object -First 1).id
    Write-Host ""
    Write-Host "Rolling back to previous version: " -NoNewline -ForegroundColor Yellow
    Write-Host "$targetVersion" -ForegroundColor White
} else {
    $index = [int]$choice
    if ($index -lt 0 -or $index -ge $versionList.Count) {
        Write-Host "Invalid choice." -ForegroundColor Red
        exit 1
    }
    $targetVersion = $versionList[$index]
    
    if ($targetVersion -eq $current.id) {
        Write-Host "This version is already active." -ForegroundColor Yellow
        exit 0
    }
    
    Write-Host ""
    Write-Host "Rolling back to version: " -NoNewline -ForegroundColor Yellow
    Write-Host "$targetVersion" -ForegroundColor White
}

Write-Host ""
Write-Host "Executing rollback..." -ForegroundColor Yellow

# Execute rollback
try {
    $result = gcloud app versions migrate $targetVersion 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "=" * 60 -ForegroundColor Green
        Write-Host "✅ Rollback successful!" -ForegroundColor Green
        Write-Host "=" * 60 -ForegroundColor Green
        Write-Host ""
        Write-Host "Your app is now using version: " -NoNewline -ForegroundColor Green
        Write-Host "$targetVersion" -ForegroundColor White
        Write-Host ""
        Write-Host "App URL: " -NoNewline -ForegroundColor Cyan
        Write-Host "https://estateally-ai-services.ue.r.appspot.com" -ForegroundColor White
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "❌ Rollback failed!" -ForegroundColor Red
        Write-Host $result -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "❌ Error during rollback: $_" -ForegroundColor Red
    exit 1
}




