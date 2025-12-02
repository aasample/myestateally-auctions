# Rollback Guide for Google App Engine Deployments

## ✅ **Yes, You Can Undo Deployments!**

Google App Engine **automatically keeps all versions** of your application. Every time you deploy, it creates a new version, so you can always roll back to any previous version.

## 🎯 **How It Works**

When you deploy with `gcloud app deploy`, App Engine:
1. ✅ Creates a **new version** (e.g., `20250107t123456`)
2. ✅ **Keeps all old versions** (they remain available)
3. ✅ Serves traffic to the **newest version** by default
4. ✅ You can **switch back** to any old version anytime

## 📋 **Quick Commands**

### **1. List All Versions**
```powershell
gcloud app versions list
```

This shows:
- Version ID
- Traffic allocation (which version is active)
- Creation date
- Status

### **2. View Details of a Specific Version**
```powershell
gcloud app versions describe VERSION_ID
```

### **3. Rollback to Previous Version**

**Option A: Switch to a Specific Version (Recommended)**
```powershell
# First, find the version you want
gcloud app versions list

# Then switch to that version (replaces current)
gcloud app versions migrate VERSION_ID

# OR split traffic between versions (gradual rollback)
gcloud app services set-traffic default --splits=VERSION_ID=100
```

**Option B: Quick Rollback to Previous Version**
```powershell
# Get the previous version ID
$versions = gcloud app versions list --format="value(version.id)" --sort-by=~creationTime
$previousVersion = ($versions -split "`n")[1]  # Second item (previous)

# Rollback to previous version
gcloud app versions migrate $previousVersion
```

**Option C: Stop New Version (Emergency)**
```powershell
# Stop serving traffic to the latest version
gcloud app versions stop VERSION_ID
```

### **4. Delete Old Versions (Optional Cleanup)**
```powershell
# Delete a specific version
gcloud app versions delete VERSION_ID

# Delete multiple old versions (keeps last 5)
$versions = gcloud app versions list --format="value(version.id)" --sort-by=~creationTime
$versionsToDelete = ($versions -split "`n")[5..(($versions -split "`n").Length-1)]
foreach ($v in $versionsToDelete) {
    gcloud app versions delete $v --quiet
}
```

## 🔄 **Rollback Scenarios**

### **Scenario 1: Immediate Rollback (Broke Something)**

If your new deployment breaks:
```powershell
# 1. List versions to see what's available
gcloud app versions list

# 2. Rollback to the previous working version
gcloud app versions migrate PREVIOUS_VERSION_ID

# That's it! Your app is now using the old version.
```

### **Scenario 2: Gradual Rollback (Testing)**

If you want to gradually move traffic back:
```powershell
# Move 50% traffic to old version, 50% to new
gcloud app services set-traffic default --splits=OLD_VERSION=50,NEW_VERSION=50

# Then after testing, move 100% to old version
gcloud app services set-traffic default --splits=OLD_VERSION=100
```

### **Scenario 3: Compare Versions**

Test both versions side-by-side:
```powershell
# Serve 90% traffic to stable, 10% to new version
gcloud app services set-traffic default --splits=STABLE_VERSION=90,NEW_VERSION=10

# Monitor the new version
# If it works well, gradually increase to 100%
# If not, rollback fully
```

## 🎯 **Best Practices**

### **1. Always Test Locally First**
```powershell
# Test before deploying
python run_local.py
# Open http://localhost:8080 and test thoroughly
```

### **2. Deploy with Version Notes**
```powershell
# Deploy with a version note (for tracking)
gcloud app deploy --version=v1-0-1 --no-promote
# Then test the new version before promoting
```

### **3. Keep Important Versions**
Don't delete versions immediately - keep them for a few days in case you need to rollback.

### **4. Use Version Labels**
When you have a working version, note its version ID:
```powershell
# Get current version
gcloud app versions list --filter="traffic_split=1.0"
```

### **5. Test New Version Before Full Traffic**
```powershell
# Deploy without promoting (no traffic)
gcloud app deploy --no-promote

# Test at: https://VERSION_ID-dot-YOUR-PROJECT.appspot.com

# If good, promote it:
gcloud app versions migrate VERSION_ID

# If bad, just delete it:
gcloud app versions delete VERSION_ID
```

## 🛠️ **Helper Scripts**

### **Quick Rollback Script**

Create `rollback.ps1`:
```powershell
# rollback.ps1 - Quick rollback to previous version
Write-Host "Fetching versions..." -ForegroundColor Yellow

$versions = gcloud app versions list --format="json" | ConvertFrom-Json
$current = $versions | Where-Object { $_.traffic_split -eq 1.0 } | Select-Object -First 1
$allVersions = $versions | Sort-Object { $_.version.createTime } -Descending

Write-Host "`nCurrent version: $($current.id)" -ForegroundColor Green
Write-Host "Created: $($current.version.createTime)" -ForegroundColor Gray

Write-Host "`nPrevious versions:" -ForegroundColor Yellow
$i = 1
foreach ($v in ($allVersions | Select-Object -Skip 1 | Select-Object -First 5)) {
    Write-Host "  $i. $($v.id) - $($v.version.createTime)" -ForegroundColor Cyan
    $i++
}

$choice = Read-Host "`nEnter number to rollback to (or press Enter for previous version)"
if ([string]::IsNullOrWhiteSpace($choice)) {
    $targetVersion = ($allVersions | Select-Object -Skip 1 | Select-Object -First 1).id
} else {
    $targetVersion = ($allVersions | Select-Object -Skip 1 | Select-Object -First 5)[$choice - 1].id
}

Write-Host "`nRolling back to: $targetVersion" -ForegroundColor Yellow
gcloud app versions migrate $targetVersion

Write-Host "`n✅ Rollback complete!" -ForegroundColor Green
Write-Host "Your app is now using version: $targetVersion" -ForegroundColor Green
```

## ⚠️ **Important Notes**

### **Data Persistence**
- ⚠️ **Rolling back code does NOT roll back database/data**
- If your new version changed data structures, the old version might not work with new data
- Always backup data before major deployments

### **Environment Variables**
- Versions share the same environment variables from `app.yaml`
- If you changed `app.yaml` env vars, all versions will use the new values
- To rollback env vars, you need to redeploy with the old `app.yaml`

### **Costs**
- ✅ Old versions don't cost money if they're not serving traffic
- ⚠️ Versions still count toward your App Engine quota
- 💡 Delete very old versions you don't need anymore

### **Custom Domains**
- Custom domains always point to the **current active version**
- When you rollback, your domain automatically uses the rolled-back version
- No DNS changes needed

## 📊 **Monitoring Versions**

### **Check Which Version is Active**
```powershell
gcloud app versions list --filter="traffic_split>0"
```

### **See All Versions with Details**
```powershell
gcloud app versions list --format="table(id,traffic_split,createTime,servingStatus)"
```

### **Get Version URLs**
Each version has its own URL:
- Active version: `https://YOUR-PROJECT.appspot.com`
- Specific version: `https://VERSION_ID-dot-YOUR-PROJECT.appspot.com`

Test a specific version before rolling back:
```powershell
# Deploy without promoting
gcloud app deploy --no-promote

# Get the version ID from the output
# Test at: https://NEW-VERSION-ID-dot-YOUR-PROJECT.appspot.com
```

## ✅ **Safety Checklist**

Before deploying:
- [ ] Tested locally with `python run_local.py`
- [ ] Reviewed all code changes
- [ ] Checked environment variables in `app.yaml`
- [ ] Noted current version ID (in case rollback needed)

After deploying:
- [ ] Verified app works at main URL
- [ ] Tested key features
- [ ] Checked error logs: `gcloud app logs tail`
- [ ] Confirmed version ID for this deployment

If rollback needed:
- [ ] Identified previous working version ID
- [ ] Executed rollback command
- [ ] Verified app works after rollback
- [ ] Fixed issues in code before next deployment

## 🚀 **Summary**

**You can always undo a deployment because:**
1. ✅ Every deployment creates a new version
2. ✅ Old versions are automatically kept
3. ✅ You can switch versions with one command
4. ✅ No data loss (unless code changes broke compatibility)
5. ✅ Instant rollback available

**Most common rollback command:**
```powershell
gcloud app versions migrate PREVIOUS_VERSION_ID
```

**Don't worry about deploying - you can always go back!** 🎉




