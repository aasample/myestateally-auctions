# MyEstateAlly - Squarespace Domain Deployment Guide

## 🏢 **Deploying MyEstateAlly with Squarespace Domains**

Since your domains (myestateally.com and myestateally.app) are purchased through Squarespace, follow these specific instructions for connecting them to Google Cloud App Engine.

## ⚠️ **Important Squarespace Differences:**

### **🔧 DNS Configuration Requirements:**
- **Longer Propagation Time** - 24-72 hours (vs. 15-60 minutes for other providers)
- **Different Interface** - Squarespace has unique DNS management
- **Email Considerations** - Preserve MX records if using Squarespace email
- **Record Conflicts** - Must delete existing records before adding CNAME

## 📋 **Step-by-Step Squarespace Deployment:**

### **1. Deploy to Google Cloud App Engine**

```bash
# Navigate to your MyEstateAlly directory
cd myestateally-complete

# Deploy to Google Cloud
gcloud app deploy

# Note the generated App Engine URL (e.g., https://your-project.appspot.com)
```

### **2. Configure Custom Domains in Google Cloud**

1. **Open Google Cloud Console**
2. **Navigate to App Engine → Settings → Custom Domains**
3. **Click "Add a custom domain"**
4. **Enter your domain:** `myestateally.com`
5. **Verify domain ownership** (use HTML meta tag method - easiest for Squarespace)
6. **Repeat for:** `myestateally.app`

### **3. Configure DNS in Squarespace**

#### **Access Squarespace DNS Settings:**
1. **Log in to Squarespace**
2. **Go to Settings → Domains**
3. **Click on myestateally.com**
4. **Click "DNS Settings"**

#### **Delete Existing Records:**
⚠️ **IMPORTANT:** Delete these existing records first:
- Any existing `@` (root domain) A records
- Any existing `www` CNAME records
- Any existing AAAA records pointing to the domain

#### **Add New CNAME Records:**
Add these records in Squarespace DNS:

```
Record Type: CNAME
Host: @
Points to: ghs.googlehosted.com
TTL: 3600 (or Auto)

Record Type: CNAME  
Host: www
Points to: ghs.googlehosted.com
TTL: 3600 (or Auto)
```

#### **Preserve Email Records (If Using Squarespace Email):**
Keep these MX records if you use Squarespace email:
```
Record Type: MX
Host: @
Points to: mx.squarespace.com
Priority: 10
```

### **4. Repeat for myestateally.app**

Follow the same process for your .app domain:
1. **Add custom domain in Google Cloud**
2. **Configure DNS in Squarespace for myestateally.app**
3. **Add same CNAME records**

### **5. Domain Verification**

#### **HTML Meta Tag Method (Recommended for Squarespace):**
1. **Google Cloud will provide an HTML meta tag**
2. **In Squarespace:** Settings → Advanced → Code Injection
3. **Add the meta tag to Header Code Injection**
4. **Save and return to Google Cloud to verify**

## ⏱️ **Timeline Expectations:**

### **Immediate (0-15 minutes):**
- ✅ Google Cloud deployment complete
- ✅ DNS records added in Squarespace
- ✅ Domain verification completed

### **24-48 Hours:**
- 🔄 Initial DNS propagation
- 🔄 SSL certificates provisioning
- 🔄 Some regions may access the site

### **48-72 Hours:**
- ✅ Complete global DNS propagation
- ✅ SSL certificates fully active
- ✅ All users worldwide can access

## 🔍 **Verification Steps:**

### **Check DNS Propagation:**
```bash
# Check if CNAME records are propagating
nslookup myestateally.com
nslookup myestateally.app

# Should show ghs.googlehosted.com
```

### **Test SSL Certificates:**
- Visit https://myestateally.com
- Check for green padlock icon
- Verify certificate is issued by Google

### **Test PWA Installation:**
- Visit site on mobile device
- Look for "Add to Home Screen" prompt
- Test offline functionality

## ⚠️ **Common Squarespace Issues & Solutions:**

### **Issue: "Domain already in use"**
**Solution:** Delete existing A records in Squarespace first

### **Issue: "SSL certificate pending"**
**Solution:** Wait 24-48 hours for Google to provision certificates

### **Issue: "Email stopped working"**
**Solution:** Ensure MX records for Squarespace email are preserved

### **Issue: "Site not loading after 72 hours"**
**Solution:** 
1. Check DNS records are exactly as specified
2. Contact Squarespace support for DNS propagation issues
3. Verify domain verification in Google Cloud

## 📧 **Email Considerations:**

### **If Using Squarespace Email:**
- ✅ Keep existing MX records
- ✅ Email will continue working normally
- ✅ No interruption to email service

### **If Using Google Workspace:**
- 🔄 Update MX records to Google Workspace
- 🔄 Configure email forwarding if needed

## 🎯 **Service Account Configuration:**

When deploying to Google Cloud, use:
- **Service Account:** "Estate Ally Vision Service"
- **Reason:** Optimized for AI vision processing features
- **Security:** Follows principle of least privilege

## ✅ **Final Verification Checklist:**

- [ ] Google Cloud deployment successful
- [ ] Custom domains added in Google Cloud Console
- [ ] Domain ownership verified
- [ ] CNAME records added in Squarespace
- [ ] Existing conflicting records deleted
- [ ] Email MX records preserved (if applicable)
- [ ] SSL certificates active (may take 24-48 hours)
- [ ] PWA installation working on mobile
- [ ] Family sharing links functional
- [ ] All features tested and working

## 🚀 **Expected Results:**

After successful deployment:
- **myestateally.com** → Full MyEstateAlly application
- **myestateally.app** → PWA-optimized version
- **Mobile Installation** → Users can install like native app
- **Family Sharing** → Complete family member management
- **AI Features** → Photo analysis and price estimation

## 📞 **Support Resources:**

- **Google Cloud Support:** For App Engine deployment issues
- **Squarespace Support:** For DNS configuration problems
- **This Guide:** For step-by-step troubleshooting

**Your MyEstateAlly application will be live on your custom Squarespace domains within 24-72 hours!**

