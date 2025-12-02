# list-versions.ps1 - List all App Engine versions with details
# Usage: .\list-versions.ps1

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "MyEstateAlly - Version List" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

Write-Host "Fetching versions..." -ForegroundColor Yellow

try {
    $versionsJson = gcloud app versions list --format="json" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error fetching versions. Make sure you're logged in to gcloud." -ForegroundColor Red
        Write-Host "Run: gcloud auth login" -ForegroundColor Yellow
        exit 1
    }
    $versions = $versionsJson | ConvertFrom-Json
    
    # Sort by creation time (newest first)
    $sortedVersions = $versions | Sort-Object { [DateTime]::Parse($_.version.createTime) } -Descending
    
    Write-Host ""
    Write-Host "Found $($sortedVersions.Count) version(s)" -ForegroundColor Green
    Write-Host ""
    Write-Host "-" * 60 -ForegroundColor Gray
    
    foreach ($v in $sortedVersions) {
        $trafficPercent = [math]::Round($v.traffic_split * 100, 1)
        $status = if ($v.traffic_split -eq 1.0) { 
            "[ACTIVE ✓]" -ForegroundColor Green 
        } elseif ($v.traffic_split -gt 0) { 
            "[PARTIAL: $trafficPercent%]" -ForegroundColor Yellow 
        } else { 
            "[INACTIVE]" -ForegroundColor DarkGray 
        }
        
        Write-Host ""
        Write-Host "Version ID: " -NoNewline -ForegroundColor Cyan
        Write-Host "$($v.id)" -ForegroundColor White
        Write-Host "  Status: " -NoNewline -ForegroundColor Gray
        Write-Host $status
        Write-Host "  Created: " -NoNewline -ForegroundColor Gray
        Write-Host "$($v.version.createTime)" -ForegroundColor White
        Write-Host "  Traffic: " -NoNewline -ForegroundColor Gray
        Write-Host "$trafficPercent%" -ForegroundColor White
        
        if ($v.traffic_split -eq 1.0) {
            Write-Host "  URL: " -NoNewline -ForegroundColor Gray
            Write-Host "https://estateally-ai-services.ue.r.appspot.com" -ForegroundColor White
        } else {
            Write-Host "  Test URL: " -NoNewline -ForegroundColor Gray
            Write-Host "https://$($v.id)-dot-estateally-ai-services.ue.r.appspot.com" -ForegroundColor DarkGray
        }
    }
    
    Write-Host ""
    Write-Host "-" * 60 -ForegroundColor Gray
    Write-Host ""
    Write-Host "To rollback, use: " -ForegroundColor Yellow
    Write-Host "  .\rollback.ps1" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Or manually: " -ForegroundColor Yellow
    Write-Host "  gcloud app versions migrate VERSION_ID" -ForegroundColor Cyan
    Write-Host ""
    
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}




