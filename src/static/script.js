/**
 * MyEstateAlly - Main Application JavaScript
 * AI-Powered Estate Management with Family Sharing
 */

// Dark mode detection and initialization
(function initializeDarkMode() {
    // Check for system dark mode preference
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.classList.add('dark-mode');
        document.body.classList.add('dark-mode');
    }
})();

/**
 * Main MyEstateAlly Application Class
 */
class MyEstateAllyApp {
    constructor() {
        this.currentUser = null;
        this.inventory = [];
        this.documents = [];
        this.familyMembers = [];
        this.legacyItems = [];
        this.sharingSettings = {
            enabled: true,
            show_for_sale_only: false,
            allow_wanted_tagging: true
        };
        this.currentShareLink = null;
        this.newItemPhotos = [];  // base64 data URLs for photos being added
        this.mobilePhotoInterval = null;

        this.init();
    }

    /**
     * Initialize the application
     */
    async init() {
        console.log('MyEstateAlly app initializing...');

        // Hard-close every modal on startup. Use visibility+pointerEvents in
        // addition to display so an old cached CSS "display:flex !important"
        // can't keep a modal visible — visibility:hidden always wins visually.
        document.querySelectorAll('.modal').forEach(m => {
            m.style.display = 'none';
            m.style.visibility = 'hidden';
            m.style.pointerEvents = 'none';
        });

        // Wait for auth check to complete BEFORE loading dashboard data
        const isAuthenticated = await this.checkAuthStatus();

        // Always set up event listeners
        this.setupEventListeners();

        // Only initialize dashboard if authenticated
        if (!isAuthenticated) {
            console.log('User not authenticated, skipping dashboard initialization');
            return; // Stop here for login page
        }

        // Dashboard initialization (only for authenticated users)
        console.log('User authenticated, initializing dashboard...');
        this.setupHeroUpload();
        this.loadInventory();
        this.loadDocuments();
        this.loadFamilyData();
        this.updateStats();

        // Load estate settlement data
        this.loadEstateTimeline();
        this.updateDisposalStats();
        this.setupPWA();

        // Listen for inventory updates from mobile upload
        window.addEventListener('message', (event) => {
            if (event.data && event.data.type === 'inventory_updated') {
                console.log('Inventory updated from mobile upload, refreshing...');
                this.loadInventory();
            }
        });

        console.log('MyEstateAlly app initialized successfully');
    }

    /**
     * Setup PWA functionality
     */
    setupPWA() {
        // Register service worker if available
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/sw.js')
                .then(registration => {
                    console.log('MyEstateAlly PWA: Service Worker registered successfully');
                })
                .catch(error => {
                    console.log('MyEstateAlly PWA: Service Worker registration failed:', error);
                });
        }
    }

    /**
     * Check authentication status
     */
    async checkAuthStatus() {
        try {
            const response = await fetch('/api/auth/status');
            const data = await response.json();

            if (data.success && data.authenticated) {
                this.currentUser = data.user;
                console.log('User authenticated:', this.currentUser.name);
                this.updateAuthUI(true);

                // Load estates and update selector
                if (data.estates) {
                    this.updateEstateSelector(data.estates, data.current_estate_id);
                }

                // If no current estate but estates exist, switch to first one
                if (!data.current_estate_id && data.estates && data.estates.length > 0) {
                    await this.switchEstate(data.estates[0].id);
                }

                // If no estates exist, show welcome modal - MANDATORY for first-time users
                if (!data.estates || data.estates.length === 0) {
                    console.warn('User has no estates - showing mandatory welcome modal');

                    // Show welcome modal for first-time users
                    setTimeout(() => {
                        this.showWelcomeModal();

                        // Make modal backdrop non-dismissible for users with no estates
                        const welcomeModal = document.getElementById('welcome-modal');
                        if (welcomeModal) {
                            welcomeModal.classList.add('mandatory-modal');
                            // Prevent backdrop clicks from closing modal
                            welcomeModal.onclick = (e) => {
                                if (e.target === welcomeModal) {
                                    // Show toast instead of closing
                                    this.showMessage('Please create your first estate to continue', 'warning');
                                }
                            };
                        }

                        // On mobile, also show persistent message
                        if (window.innerWidth <= 768) {
                            this.showMessage('Create your first estate to get started', 'info');
                        }
                    }, 500);

                    // Disable interactions with main UI until estate is created
                    const mainContent = document.querySelector('.main');
                    if (mainContent) {
                        mainContent.style.pointerEvents = 'none';
                        mainContent.style.opacity = '0.5';
                    }
                }

                return true; // User is authenticated
            }

            // No valid session — only auto-open the auth modal if NOT on the landing page.
            // On the landing page, visitors should browse freely and open the modal via CTA buttons.
            this.updateAuthUI(false);
            if (!document.querySelector('.hero')) {
                this.openModal('auth-modal');
            }
            return false; // User is not authenticated

        } catch (error) {
            console.error('Auth check failed:', error);
            // Fallback to showing auth UI
            this.updateAuthUI(false);
            if (!document.querySelector('.hero')) {
                this.openModal('auth-modal');
            }
            return false; // Auth check failed, treat as not authenticated
        }
    }

    /**
     * Create demo user session
     */
    async createDemoSession() {
        try {
            const response = await fetch('/api/auth/demo', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentUser = data.user;
                localStorage.setItem('myestateally_session', data.session_id);
                console.log('Demo user created:', this.currentUser.name);
            } else {
                // Ultimate fallback
                this.currentUser = {
                    id: 'demo-user',
                    name: 'Demo User',
                    email: 'demo@myestateally.com'
                };
            }
            
        } catch (error) {
            console.error('Demo session creation failed:', error);
            // Ultimate fallback
            this.currentUser = {
                id: 'demo-user',
                name: 'Demo User',
                email: 'demo@myestateally.com'
            };
        }
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Home button (logo)
        document.getElementById('home-button')?.addEventListener('click', () => {
            this.switchTab('dashboard');
        });

        // Navigation
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const section = e.target.closest('.nav-btn').dataset.section;
                this.switchTab(section);
                this.closeMobileMenu(); // Close mobile menu when switching tabs
            });
        });

        // Quick actions
        document.getElementById('add-item-btn')?.addEventListener('click', () => this.switchTab('inventory'));
        document.getElementById("ai-pricing-btn")?.addEventListener("click", () => this.switchTab("ai-pricing"));
        document.getElementById('add-inventory-item')?.addEventListener('click', () => this.openModal('add-item-modal'));

        // AI Pricing functionality
        document.getElementById("lookup-pricing-btn")?.addEventListener("click", () => this.lookupPricing());
        document.getElementById("pricing-item-select")?.addEventListener("change", (e) => this.onInventoryItemSelect(e));
        document.getElementById("browse-inventory-btn")?.addEventListener("click", () => this.switchTab("inventory"));
        document.getElementById('qr-upload-btn')?.addEventListener('click', () => this.generateQRCodeHero());

        // Family sharing
        document.getElementById('invite-member-btn')?.addEventListener('click', () => this.openModal('invite-family-modal'));
        document.getElementById('generate-link-btn')?.addEventListener('click', () => this.generateShareLink());
        document.getElementById('copy-link-btn')?.addEventListener('click', () => this.copyShareLink());
        
        // Family settings
        document.getElementById('sharing-enabled')?.addEventListener('change', (e) => this.updateSharingSettings());
        document.getElementById('for-sale-only')?.addEventListener('change', (e) => this.updateSharingSettings());
        document.getElementById('wanted-tagging')?.addEventListener('change', (e) => this.updateSharingSettings());

        // Family invite form
        document.getElementById('invite-family-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.inviteFamilyMember();
        });

        // Estate settlement form handlers
        document.getElementById('add-task-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.addTask();
        });

        document.getElementById('disposal-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.disposeItem();
        });

        // Authentication forms
        // Progressive auth event listeners
        document.getElementById('email-check-form')?.addEventListener('submit', handleEmailCheck);
        document.getElementById('password-form')?.addEventListener('submit', handlePasswordLogin);
        document.getElementById('signup-password-form')?.addEventListener('submit', handleSignup);
        document.getElementById('mfa-form')?.addEventListener('submit', handleMfaVerification);
        document.getElementById('mfa-setup-verify-form')?.addEventListener('submit', handleMfaSetupVerify);
        
        // Setup MFA digit inputs
        setupMfaDigitInputs();
        
        // Legacy form listeners (for backwards compatibility)
        document.getElementById('login-form-content')?.addEventListener('submit', (e) => {
            e.preventDefault();
            const email = document.getElementById('login-email').value.trim();
            const password = document.getElementById('login-password').value.trim();
            this.login(email, password);
        });

        document.getElementById('signup-form-content')?.addEventListener('submit', (e) => {
            e.preventDefault();
            const name = document.getElementById('signup-name').value.trim();
            const email = document.getElementById('signup-email').value.trim();
            const password = document.getElementById('signup-password').value.trim();
            this.signup(name, email, password);
        });

        // Modal close handlers
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const modal = e.target.closest('.modal');
                if (modal) {
                    this.closeModal(modal.id);
                }
            });
        });

        // Click outside modal to close
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.closeModal(e.target.id);
            }
        });

        // Inventory refresh button
        document.getElementById('refresh-inventory')?.addEventListener('click', () => {
            console.log('Manual inventory refresh triggered');
            this.loadInventory();
        });
    }

    /**
     * Set up hero upload functionality
     */
    setupHeroUpload() {
        const uploadArea = document.getElementById('hero-upload-area');
        const fileInput = document.getElementById('hero-photo-upload');

        if (!uploadArea || !fileInput) return;

        // Click to upload
        uploadArea.addEventListener('click', () => {
            fileInput.click();
        });

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('drag-over');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('drag-over');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.processHeroPhoto(files[0]);
            }
        });

        // File input change
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.processHeroPhoto(e.target.files[0]);
            }
        });

        // "Take Photo" button — opens the camera on mobile (capture attr),
        // file picker on desktop. Was previously a dead button with no listener.
        document.getElementById('take-photo-btn')?.addEventListener('click', () => {
            fileInput.click();
        });
    }

    /**
     * Switch between tabs/sections
     */
    switchTab(sectionName) {
        // Update navigation
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-section="${sectionName}"]`)?.classList.add('active');

        // Update sections
        document.querySelectorAll('.section').forEach(section => {
            section.classList.remove('active');
        });
        document.getElementById(sectionName)?.classList.add('active');

        // Load section-specific data
        if (sectionName === 'family') {
            this.loadFamilyData();
        } else if (sectionName === 'inventory') {
            this.loadInventory();
        } else if (sectionName === 'legacy') {
            this.loadLegacy();
        }
    }

    /**
     * Trigger hero photo upload
     */
    triggerHeroUpload() {
        const fileInput = document.getElementById('hero-photo-upload');
        if (fileInput) {
            fileInput.click();
        }
    }

    /**
     * Process hero photo upload
     */
    async processHeroPhoto(file) {
        if (!file) return;

        // Validate file type
        const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/heic', 'image/heif'];
        if (!validTypes.includes(file.type) && !file.name.toLowerCase().match(/\.(jpg|jpeg|png|heic|heif)$/)) {
            this.showMessage('Please select a valid image file (JPG, PNG, HEIC)', 'error');
            return;
        }

        // Check file size (10MB limit)
        if (file.size > 10 * 1024 * 1024) {
            this.showMessage('Image is too large. Please try a smaller image.', 'error');
            return;
        }

        this.showLoading('Analyzing photo with AI...');

        try {
            // Convert HEIC to JPEG if needed
            let processedFile = file;
            if (file.type === 'image/heic' || file.type === 'image/heif' || file.name.toLowerCase().endsWith('.heic')) {
                processedFile = await this.convertHEICToJPEG(file);
            }

            // Compress large images
            if (processedFile.size > 2 * 1024 * 1024) {
                processedFile = await this.compressImage(processedFile);
            }

            const formData = new FormData();
            formData.append('photo', processedFile);

            const response = await fetch('/api/hero/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                // Item was automatically created
                if (result.item) {
                    this.showMessage(`Item "${result.item.name}" added to inventory!`, 'success');
                    // Reload inventory to show the new item
                    await this.loadInventory();
                    // Switch to inventory tab
                    this.switchTab('inventory');
                } else {
                    // Just analysis, no item created
                    this.showMessage('Photo analyzed successfully!', 'success');
                    this.displayAIAnalysis(result.analysis);
                }
            } else {
                throw new Error(result.error || 'Upload failed');
            }
        } catch (error) {
            console.error('Hero upload error:', error);
            this.showMessage('Upload failed. Please try again.', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Convert HEIC to JPEG using Canvas
     */
    async convertHEICToJPEG(file) {
        return new Promise((resolve) => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            
            img.onload = () => {
                canvas.width = img.width;
                canvas.height = img.height;
                ctx.drawImage(img, 0, 0);
                
                canvas.toBlob((blob) => {
                    const convertedFile = new File([blob], file.name.replace(/\.heic$/i, '.jpg'), {
                        type: 'image/jpeg'
                    });
                    resolve(convertedFile);
                }, 'image/jpeg', 0.8);
            };
            
            img.onerror = () => resolve(file); // Fallback to original file
            img.src = URL.createObjectURL(file);
        });
    }

    /**
     * Compress image using Canvas
     */
    async compressImage(file) {
        return new Promise((resolve) => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            
            img.onload = () => {
                // Calculate new dimensions (max 1920x1080)
                let { width, height } = img;
                const maxWidth = 1920;
                const maxHeight = 1080;
                
                if (width > maxWidth || height > maxHeight) {
                    const ratio = Math.min(maxWidth / width, maxHeight / height);
                    width *= ratio;
                    height *= ratio;
                }
                
                canvas.width = width;
                canvas.height = height;
                ctx.drawImage(img, 0, 0, width, height);
                
                canvas.toBlob((blob) => {
                    const compressedFile = new File([blob], file.name, {
                        type: 'image/jpeg'
                    });
                    resolve(compressedFile);
                }, 'image/jpeg', 0.8);
            };
            
            img.onerror = () => resolve(file); // Fallback to original file
            img.src = URL.createObjectURL(file);
        });
    }

    /**
     * Generate QR code for mobile upload
     */
    async generateQRCodeHero() {
        this.openModal('qr-modal');
        
        // Reset QR container to loading state
        const qrContainer = document.getElementById('qr-code');
        qrContainer.innerHTML = `
            <div class="qr-loading">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Generating QR Code...</p>
            </div>
        `;
        
        try {
            // Add timeout to prevent hanging
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
            
            const response = await fetch('/api/qr/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();

            if (result.success) {
                qrContainer.innerHTML = `<img src="${result.qr_code}" alt="QR Code" style="max-width: 100%; height: auto; border-radius: 8px;">`;
            } else {
                throw new Error(result.error || 'Failed to generate QR code');
            }
        } catch (error) {
            console.error('QR generation error:', error);
            let errorMessage = 'Failed to generate QR code. Please try again.';
            
            if (error.name === 'AbortError') {
                errorMessage = 'QR code generation timed out. Please try again.';
            } else if (error.message.includes('HTTP error')) {
                errorMessage = 'Server error. Please try again later.';
            }
            
            qrContainer.innerHTML = `
                <div style="padding: 20px; text-align: center; color: #ef4444;">
                    <i class="fas fa-exclamation-triangle" style="font-size: 24px; margin-bottom: 10px;"></i>
                    <p>${errorMessage}</p>
                    <button onclick="window.app.generateQRCodeHero()" class="btn primary" style="margin-top: 10px;">
                        <i class="fas fa-redo"></i> Try Again
                    </button>
                </div>
            `;
        }
    }

    /**
     * Display AI analysis results
     */
    displayAIAnalysis(analysis) {
        // Pre-fill the add item modal with AI analysis results
        document.getElementById('item-name').value = analysis.item_name || '';
        document.getElementById('item-category').value = analysis.category || '';
        document.getElementById('item-description').value = analysis.description || '';

        // Use average of min/max for estimated value
        const avgValue = Math.round((analysis.estimated_value_min + analysis.estimated_value_max) / 2);
        document.getElementById('item-value').value = avgValue || '';

        // Store the photo URL if available
        if (analysis.photo_url) {
            this.currentItemPhoto = analysis.photo_url;
        }

        // Show success message
        const message = `AI identified: ${analysis.item_name} (${analysis.category})\nEstimated value: $${analysis.estimated_value_min}-$${analysis.estimated_value_max}\nOpening add item form...`;
        this.showMessage(message, 'success');

        // Open the add item modal after a brief delay
        setTimeout(() => {
            this.openModal('add-item-modal');
        }, 1000);

        // Add to activity
        this.addActivity(`AI analyzed new item: ${analysis.item_name}`);
    }

    /**
     * Load inventory data
     */
    async loadInventory() {
        // Guard: Skip if not authenticated
        if (!this.currentUser) {
            console.log('Skipping inventory load - user not authenticated');
            return;
        }

        try {
            console.log('Loading inventory...');
            const response = await fetch('/api/items');
            const result = await response.json();
            
            console.log('Inventory API response:', result);
            console.log('Response status:', response.status);
            console.log('Response headers:', Object.fromEntries(response.headers.entries()));

            if (result.success) {
                this.inventory = result.items;
                console.log('Inventory loaded:', this.inventory);
                console.log('Inventory length:', this.inventory ? this.inventory.length : 'undefined');
                console.log('First item:', this.inventory && this.inventory.length > 0 ? this.inventory[0] : 'none');
                this.updateInventoryDisplay();
                this.updateStats();
                this.populatePricingInventory();
            } else {
                console.error('Inventory API returned error:', result.error);
                // Try debug endpoint
                try {
                    const debugResponse = await fetch('/api/debug/inventory');
                    const debugResult = await debugResponse.json();
                    console.log('Debug inventory response:', debugResult);
                } catch (debugError) {
                    console.error('Debug endpoint error:', debugError);
                }
            }
        } catch (error) {
            console.error('Error loading inventory:', error);
            console.error('Error details:', {
                name: error.name,
                message: error.message,
                stack: error.stack
            });
        }
    }

    /**
     * Update inventory display
     */
    updateInventoryDisplay() {
        const grid = document.getElementById('inventory-grid');
        const empty = document.getElementById('inventory-empty');

        console.log('Updating inventory display...');
        console.log('Grid element:', grid);
        console.log('Inventory length:', this.inventory ? this.inventory.length : 'undefined');
        console.log('Inventory:', this.inventory);

        if (!grid) {
            console.error('Inventory grid element not found!');
            return;
        }

        if (!this.inventory || this.inventory.length === 0) {
            console.log('No inventory items, showing empty state');
            grid.style.display = 'none';
            if (empty) empty.style.display = 'block';
            return;
        }

        console.log('Displaying inventory items');
        if (empty) empty.style.display = 'none';
        grid.style.display = 'grid';

        const htmlContent = this.inventory.map(item => `
            <div class="inventory-item" data-item-id="${item.id}">
                <div class="item-checkbox">
                    <input type="checkbox" class="item-select-checkbox" data-item-id="${item.id}" onchange="app.updateBulkActions()">
                </div>
                <div class="item-image">
                    ${item.photo ? `<img src="${item.photo}" alt="${item.name}">` : '<i class="fas fa-image"></i>'}
                </div>
                <div class="item-info">
                    <h4>${item.name || 'Unnamed Item'}</h4>
                    <p class="item-category">${item.category || 'Uncategorized'}</p>
                    <p class="item-description">${item.description || 'No description'}</p>
                    <p class="item-value item-value-editable" onclick="app.quickEditValue('${item.id}', ${item.estimatedValue || 0})" title="Click to edit value">$${(item.estimatedValue || 0).toLocaleString()} <i class="fas fa-pencil-alt item-value-edit-icon"></i></p>
                    ${this.getDestinationBadgeHTML(item)}
                    ${this.getListingBadgeHTML(item)}
                    ${item.familyHistory ? '<span class="family-history-indicator"><i class="fas fa-heart"></i> Story</span>' : ''}
                    <div class="item-actions">
                        <button class="edit-btn" onclick="app.editItem('${item.id}')">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button class="pricing-btn" onclick="app.lookupItemPricing('${item.id}')">
                            <i class="fas fa-search-dollar"></i> Price
                        </button>
                        <button class="sell-btn" onclick="app.openListingAssistant('${item.id}')" title="Sell on Facebook Marketplace, eBay, or Craigslist">
                            <i class="fas fa-store"></i> Sell
                        </button>
                        <button class="disposal-btn" onclick="app.showDisposalModal('${item.id}')" title="Mark as disposed">
                            <i class="fas fa-trash-alt"></i> Dispose
                        </button>
                        <button class="delete-btn" onclick="app.deleteItem('${item.id}')">
                            <i class="fas fa-trash"></i> Delete
                        </button>
                    </div>
                </div>
            </div>
        `).join('');

        // Update bulk actions toolbar visibility
        this.updateBulkActions();
        
        console.log('Generated HTML:', htmlContent);
        grid.innerHTML = htmlContent;
        console.log('Grid innerHTML set, grid children count:', grid.children.length);
    }

    /**
     * Generate destination badge HTML for an item card.
     * Falls back to legacy forSale / assignedTo fields for old items.
     */
    getDestinationBadgeHTML(item) {
        const dest = item.destination;
        if (dest === 'sell') return '<span class="for-sale-badge">For Sale</span>';
        if (dest === 'family') {
            const d = item.destinationDetail ? ` \u2014 ${item.destinationDetail}` : '';
            return `<span class="family-badge">Family/Heir${d}</span>`;
        }
        if (dest === 'charity') {
            const d = item.destinationDetail ? ` \u2014 ${item.destinationDetail}` : '';
            return `<span class="charity-badge">Charity${d}</span>`;
        }
        // Backward compat for legacy items without destination field
        if (!dest && item.forSale) return '<span class="for-sale-badge">For Sale</span>';
        if (!dest && item.assignedTo) return `<span class="assigned-badge">Assigned to ${item.assignedTo}</span>`;
        return ''; // keep or unrecognized
    }

    /**
     * Badge showing which marketplaces the item is currently listed on.
     */
    getListingBadgeHTML(item) {
        const l = item.listings || {};
        const names = [];
        if (l.facebook) names.push('Facebook');
        if (l.ebay) names.push('eBay');
        if (l.craigslist) names.push('Craigslist');
        if (l.poshmark) names.push('Poshmark');
        if (!names.length) return '';
        return `<span class="listed-badge"><i class="fas fa-store"></i> Listed: ${names.join(' · ')}</span>`;
    }

    /**
     * Show/hide and relabel the destinationDetail field in the edit modal.
     */
    onEditDestinationChange() {
        const sel = document.getElementById('editDestination');
        const group = document.getElementById('editDestinationDetailGroup');
        const label = document.getElementById('editDestinationDetailLabel');
        const input = document.getElementById('editDestinationDetail');
        if (!sel || !group) return;
        const val = sel.value;
        if (val === 'family') {
            group.style.display = 'block';
            label.textContent = 'Name of Recipient:';
            input.placeholder = "Recipient's name";
        } else if (val === 'charity') {
            group.style.display = 'block';
            label.textContent = 'Organization Name:';
            input.placeholder = 'Charity or organization name';
        } else {
            group.style.display = 'none';
            input.value = '';
        }
    }

    /**
     * Show/hide and relabel the destinationDetail field in the Add Item modal.
     */
    onAddItemDestinationChange() {
        const sel = document.getElementById('item-destination');
        const group = document.getElementById('item-destination-detail-group');
        const label = document.getElementById('item-destination-detail-label');
        const input = document.getElementById('item-destination-detail');
        if (!sel || !group) return;
        const val = sel.value;
        if (val === 'family') {
            group.style.display = 'block';
            label.textContent = 'Name of Recipient';
            input.placeholder = "Recipient's name";
        } else if (val === 'charity') {
            group.style.display = 'block';
            label.textContent = 'Organization Name';
            input.placeholder = 'Charity or organization name';
        } else {
            group.style.display = 'none';
            input.value = '';
        }
    }

    /**
     * Edit an inventory item
     */
    editItem(itemId) {
        const item = this.inventory.find(i => i.id === itemId);
        if (!item) {
            this.showMessage('Item not found', 'error');
            return;
        }

        // Derive destination from new field or legacy fields (backward compat)
        const itemDest = item.destination || (item.forSale ? 'sell' : (item.assignedTo ? 'family' : 'keep'));
        const itemDestDetail = item.destinationDetail || item.assignedTo || '';
        const showDetail = itemDest === 'family' || itemDest === 'charity';
        const detailLabel = itemDest === 'charity' ? 'Organization Name:' : 'Name of Recipient:';
        const detailPlaceholder = itemDest === 'charity' ? 'Charity or organization name' : "Recipient's name";

        // Create edit form
        const editForm = `
            <div class="edit-modal" id="editModal">
                <div class="edit-content">
                    <h3>Edit Item</h3>
                    <form id="editForm">
                        <div class="form-group">
                            <label for="editName">Name:</label>
                            <input type="text" id="editName" value="${item.name || ''}" required>
                        </div>
                        <div class="form-group">
                            <label for="editCategory">Category:</label>
                            <select id="editCategory">
                                <option value="Electronics" ${item.category === 'Electronics' ? 'selected' : ''}>Electronics</option>
                                <option value="Furniture" ${item.category === 'Furniture' ? 'selected' : ''}>Furniture</option>
                                <option value="Clothing" ${item.category === 'Clothing' ? 'selected' : ''}>Clothing</option>
                                <option value="Books" ${item.category === 'Books' ? 'selected' : ''}>Books</option>
                                <option value="Jewelry" ${item.category === 'Jewelry' ? 'selected' : ''}>Jewelry</option>
                                <option value="General" ${item.category === 'General' ? 'selected' : ''}>General</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="editDescription">Description:</label>
                            <textarea id="editDescription" rows="3">${item.description || ''}</textarea>
                        </div>
                        <div class="form-group">
                            <label for="editFamilyHistory"><i class="fas fa-heart"></i> Family History <span class="field-hint">Who it belonged to, memories, significance</span></label>
                            <textarea id="editFamilyHistory" rows="5" placeholder="Share the memory or history behind this item...">${item.familyHistory || ''}</textarea>
                        </div>
                        <div class="form-group">
                            <label for="editValue">Estimated Value ($):</label>
                            <input type="number" id="editValue" value="${item.estimatedValue || 0}" min="0" step="0.01">
                        </div>
                        <div class="form-group">
                            <label for="editDestination">Destination:</label>
                            <select id="editDestination">
                                <option value="keep" ${itemDest === 'keep' ? 'selected' : ''}>Keep</option>
                                <option value="sell" ${itemDest === 'sell' ? 'selected' : ''}>Sell</option>
                                <option value="family" ${itemDest === 'family' ? 'selected' : ''}>Assign to Family / Heir</option>
                                <option value="charity" ${itemDest === 'charity' ? 'selected' : ''}>Assign to Charity</option>
                            </select>
                        </div>
                        <div class="form-group" id="editDestinationDetailGroup" style="display: ${showDetail ? 'block' : 'none'};">
                            <label for="editDestinationDetail" id="editDestinationDetailLabel">${detailLabel}</label>
                            <input type="text" id="editDestinationDetail" value="${itemDestDetail}" maxlength="200" placeholder="${detailPlaceholder}">
                        </div>
                        <div class="form-actions">
                            <button type="button" onclick="app.closeEditModal()">Cancel</button>
                            <button type="submit">Save Changes</button>
                        </div>
                    </form>
                </div>
            </div>
        `;

        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', editForm);

        // Wire destination dropdown change handler
        const editDestSelect = document.getElementById('editDestination');
        if (editDestSelect) {
            editDestSelect.addEventListener('change', () => this.onEditDestinationChange());
        }

        // Handle form submission
        document.getElementById('editForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveItem(itemId);
        });
    }

    /**
     * Save edited item
     */
    async saveItem(itemId) {
        const formData = {
            name: document.getElementById('editName').value,
            category: document.getElementById('editCategory').value,
            description: document.getElementById('editDescription').value,
            familyHistory: document.getElementById('editFamilyHistory')?.value?.trim() || '',
            estimatedValue: parseFloat(document.getElementById('editValue').value) || 0,
            destination: document.getElementById('editDestination').value,
            destinationDetail: document.getElementById('editDestinationDetail')?.value?.trim() || ''
        };

        try {
            const response = await fetch(`/api/items/${itemId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            const result = await response.json();
            
            if (result.success) {
                this.showMessage('Item updated successfully!', 'success');
                this.closeEditModal();
                this.loadInventory(); // Refresh the inventory
            } else {
                this.showMessage(`Error: ${result.error}`, 'error');
            }
        } catch (error) {
            console.error('Error saving item:', error);
            this.showMessage('Failed to save item. Please try again.', 'error');
        }
    }

    /**
     * Close edit modal
     */
    closeEditModal() {
        const modal = document.getElementById('editModal');
        if (modal) {
            modal.remove();
        }
    }

    /**
     * Lookup pricing for a specific inventory item
     */
    lookupItemPricing(itemId) {
        // Switch to AI Pricing tab
        this.switchTab('ai-pricing');
        
        // Pre-populate the form with the selected item
        setTimeout(() => {
            const select = document.getElementById('pricing-item-select');
            if (select) {
                select.value = itemId;
                this.onInventoryItemSelect({ target: { value: itemId } });
            }
        }, 100);
    }

    /**
     * Delete an inventory item
     */
    async deleteItem(itemId) {
        const item = this.inventory.find(i => i.id === itemId);
        if (!item) {
            this.showMessage('Item not found', 'error');
            return;
        }

        if (confirm(`Are you sure you want to delete "${item.name}"?`)) {
            try {
                const response = await fetch(`/api/items/${itemId}`, {
                    method: 'DELETE'
                });

                const result = await response.json();
                
                if (result.success) {
                    this.showMessage('Item deleted successfully!', 'success');
                    this.loadInventory(); // Refresh the inventory
                } else {
                    this.showMessage(`Error: ${result.error}`, 'error');
                }
            } catch (error) {
                console.error('Error deleting item:', error);
                this.showMessage('Failed to delete item. Please try again.', 'error');
            }
        }
    }

    /**
     * Handle manual item addition
     */
    async handleAddItem(event) {
        event.preventDefault();

        const name = document.getElementById('item-name').value.trim();
        const category = document.getElementById('item-category').value;
        const description = document.getElementById('item-description').value.trim();
        const estimatedValue = parseFloat(document.getElementById('item-value').value) || 0;
        const destination = document.getElementById('item-destination')?.value || 'keep';
        const destinationDetail = document.getElementById('item-destination-detail')?.value?.trim() || '';

        if (!name && this.newItemPhotos.length === 0) {
            this.showMessage('Please enter an item name or add at least one photo', 'error');
            return;
        }
        if (!category) {
            this.showMessage('Please select a category', 'error');
            return;
        }

        try {
            const response = await fetch('/api/items', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name,
                    category,
                    description,
                    familyHistory: document.getElementById('item-family-history')?.value?.trim() || '',
                    estimatedValue,
                    destination,
                    destinationDetail,
                    photos: this.newItemPhotos,
                    photo: this.newItemPhotos[0] || ''
                })
            });

            const result = await response.json();

            if (result.success) {
                this.showMessage('Item added successfully!', 'success');
                this.newItemPhotos = [];
                this.renderNewItemPhotoThumbnails();
                this.closeModal('add-item-modal');
                document.getElementById('add-item-form').reset();
                this.onAddItemDestinationChange(); // Re-hide detail group after reset
                this.loadInventory(); // Refresh inventory
            } else {
                this.showMessage(`Error: ${result.error}`, 'error');
            }
        } catch (error) {
            console.error('Error adding item:', error);
            this.showMessage('Failed to add item. Please try again.', 'error');
        }
    }

    /**
     * AI Lookup — auto-fill Add Item form fields from item name
     */
    async aiLookupItem() {
        const nameInput = document.getElementById('item-name');
        const btn = document.getElementById('ai-lookup-btn');
        const name = nameInput ? nameInput.value.trim() : '';

        if (!name && this.newItemPhotos.length === 0) {
            this.showMessage('Please enter an item name or add photos first', 'error');
            return;
        }

        if (btn) {
            btn.disabled = true;
            const lookupLabel = this.newItemPhotos.length > 0 ? 'Analyzing photos...' : 'Looking up...';
            btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${lookupLabel}`;
        }

        try {
            const descriptionEl = document.getElementById('item-description');
            const currentDescription = descriptionEl ? descriptionEl.value.trim() : '';

            // Log photo sizes to help diagnose upload issues
            if (this.newItemPhotos.length > 0) {
                this.newItemPhotos.forEach((p, i) => {
                    console.log(`AI Lookup photo[${i}]: ${Math.round(p.length / 1024)}KB`);
                });
            }

            const response = await fetch('/api/ai/lookup-item', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    description: currentDescription,
                    photos: this.newItemPhotos
                })
            });

            if (!response.ok) {
                let errMsg = 'AI lookup failed. Please try again.';
                try {
                    const errData = await response.json();
                    if (errData && errData.error) errMsg = errData.error;
                } catch (_) {}
                throw new Error(errMsg);
            }

            const data = await response.json();

            if (data.success) {
                const lookup = data.lookup;
                const filled = [];

                // Fill item name if AI identified it from photos (when name field was empty)
                const nameEl = document.getElementById('item-name');
                if (nameEl && !nameEl.value.trim() && lookup.item_name) {
                    nameEl.value = lookup.item_name;
                    filled.push('item name');
                }

                // Fill category only if unselected
                const categoryEl = document.getElementById('item-category');
                if (categoryEl && !categoryEl.value && lookup.category) {
                    categoryEl.value = lookup.category;
                    filled.push('category');
                }

                // Fill description only if empty
                if (descriptionEl && !currentDescription && lookup.description) {
                    descriptionEl.value = lookup.description;
                    filled.push('description');
                }

                // Fill value only if 0 or blank
                const valueEl = document.getElementById('item-value');
                const currentValue = valueEl ? parseFloat(valueEl.value) || 0 : 0;
                if (valueEl && currentValue === 0 && lookup.estimated_value) {
                    valueEl.value = lookup.estimated_value;
                    filled.push('estimated value');
                }

                if (filled.length > 0) {
                    this.showMessage(`AI filled: ${filled.join(', ')}`, 'success');
                } else {
                    this.showMessage('AI lookup complete — all fields already filled', 'info');
                }
            } else {
                this.showMessage(data.error || 'AI lookup failed', 'error');
            }
        } catch (error) {
            console.error('Error with AI lookup:', error);
            this.showMessage(error.message || 'Failed to get AI lookup. Please try again.', 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-magic"></i> AI Lookup';
            }
        }
    }

    /**
     * Compress a photo for item storage.
     * Max 800px, 65% JPEG quality → ~50-80KB per photo.
     * Returns a base64 data URL string.
     */
    async compressItemPhoto(file) {
        // Use createImageBitmap which automatically applies EXIF orientation
        // (fixes 90°-rotated phone photos). Falls back to FileReader for HEIC/unsupported formats.
        try {
            let bitmap;
            try {
                // imageOrientation:'from-image' respects EXIF — supported in Chrome 81+, Safari 17+, Firefox 93+
                bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
            } catch (e) {
                // Option not supported — try without it (no EXIF correction on older browsers)
                bitmap = await createImageBitmap(file);
            }

            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            let { width, height } = bitmap;
            const maxDim = 800;
            if (width > maxDim || height > maxDim) {
                const ratio = Math.min(maxDim / width, maxDim / height);
                width = Math.round(width * ratio);
                height = Math.round(height * ratio);
            }
            canvas.width = width;
            canvas.height = height;
            ctx.drawImage(bitmap, 0, 0, width, height);
            if (bitmap.close) bitmap.close();
            return canvas.toDataURL('image/jpeg', 0.65);

        } catch (err) {
            // createImageBitmap not supported or format not renderable (e.g., HEIC on older iOS).
            // Fall back to loading via <img> + canvas so we still get compression & resizing.
            return new Promise(resolve => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = new Image();
                    img.onload = () => {
                        try {
                            const canvas = document.createElement('canvas');
                            const ctx = canvas.getContext('2d');
                            let { width, height } = img;
                            const maxDim = 800;
                            if (width > maxDim || height > maxDim) {
                                const ratio = Math.min(maxDim / width, maxDim / height);
                                width = Math.round(width * ratio);
                                height = Math.round(height * ratio);
                            }
                            canvas.width = width;
                            canvas.height = height;
                            ctx.drawImage(img, 0, 0, width, height);
                            resolve(canvas.toDataURL('image/jpeg', 0.65));
                        } catch (canvasErr) {
                            // Canvas also failed — last resort: use raw data URL (may be too large for AI)
                            console.warn('Canvas fallback failed, using raw data URL:', canvasErr);
                            resolve(e.target.result);
                        }
                    };
                    img.onerror = () => resolve(null);
                    img.src = e.target.result;
                };
                reader.onerror = () => resolve(null);
                reader.readAsDataURL(file);
            });
        }
    }

    /**
     * Called by file input onchange — loops files and delegates to addNewItemPhoto().
     */
    async handleNewItemPhotoSelect(event) {
        const files = Array.from(event.target.files || []);
        event.target.value = '';  // reset so same file can be re-selected

        for (const file of files) {
            if (this.newItemPhotos.length >= 4) {
                this.showMessage('Maximum 4 photos allowed', 'error');
                break;
            }
            await this.addNewItemPhoto(file);
        }
    }

    /**
     * Validate, HEIC-convert if needed, compress, and push a single photo.
     */
    async addNewItemPhoto(file) {
        const isImage = file.type.startsWith('image/') || !file.type;
        const validExt = /\.(jpg|jpeg|png|heic|heif|webp|gif|bmp|avif)$/i.test(file.name);
        if (!isImage && !validExt) {
            this.showMessage('Please select a valid image file', 'error');
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            this.showMessage('Image is too large (max 10MB)', 'error');
            return;
        }

        try {
            let processedFile = file;
            if (file.type === 'image/heic' || file.type === 'image/heif' ||
                file.name.toLowerCase().endsWith('.heic')) {
                processedFile = await this.convertHEICToJPEG(file);
            }
            const dataUrl = await this.compressItemPhoto(processedFile);
            if (!dataUrl) {
                this.showMessage("Could not read photo. If it's stored in iCloud, open the Photos app and wait for it to download, then try again.", 'error');
                return;
            }
            this.newItemPhotos.push(dataUrl);
            this.renderNewItemPhotoThumbnails();
        } catch (err) {
            console.error('Error processing photo:', err);
            this.showMessage('Failed to process photo. Please try another.', 'error');
        }
    }

    /**
     * Rebuild the thumbnail grid from this.newItemPhotos.
     */
    renderNewItemPhotoThumbnails() {
        const grid = document.getElementById('new-item-photos-grid');
        const addBtn = document.getElementById('add-item-photo-btn');

        if (!grid) return;

        grid.innerHTML = this.newItemPhotos.map((dataUrl, idx) => `
            <div class="photo-thumb-wrapper">
                <img class="photo-thumb" src="${dataUrl}" alt="Item photo ${idx + 1}">
                <button type="button" class="photo-thumb-remove"
                        onclick="window.app.removeNewItemPhoto(${idx})"
                        title="Remove photo">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `).join('');

        if (addBtn) {
            addBtn.disabled = this.newItemPhotos.length >= 4;
        }
        const mobileBtn = document.getElementById('add-mobile-photo-btn');
        if (mobileBtn) mobileBtn.disabled = this.newItemPhotos.length >= 4;
    }

    /**
     * Remove one photo by index, re-render thumbnails.
     */
    removeNewItemPhoto(index) {
        this.newItemPhotos.splice(index, 1);
        this.renderNewItemPhotoThumbnails();
    }

    // ===================================================================
    // BULK PHOTO IMPORT
    // ===================================================================

    /** Open modal and reset all bulk state */
    showBulkPhotoImportModal() {
        this.bulkPhotos  = [];  // [{dataUrl, name}]
        this.bulkResults = [];  // [{photo,name,category,description,estimatedValue,include}]
        this._bulkShowStep('upload');
        const grid = document.getElementById('bulk-photo-grid');
        if (grid) grid.innerHTML = '';
        const actions = document.getElementById('bulk-upload-actions');
        if (actions) actions.style.display = 'none';
        const inp = document.getElementById('bulk-file-input');
        if (inp) inp.value = '';
        const modal = document.getElementById('bulk-photo-modal');
        if (modal) {
            modal.style.display = 'flex';
            modal.style.visibility = 'visible';
            modal.style.pointerEvents = 'auto';
        }
    }

    closeBulkPhotoModal() {
        const modal = document.getElementById('bulk-photo-modal');
        if (modal) {
            modal.style.display = 'none';
            // visibility+pointerEvents defeat old cached CSS "display:flex !important"
            // which would otherwise override the inline display:none
            modal.style.visibility = 'hidden';
            modal.style.pointerEvents = 'none';
        }
        this.bulkPhotos  = [];
        this.bulkResults = [];
        // reload inventory in case some were saved before close
        this.loadInventory();
    }

    _bulkShowStep(step) {
        ['upload', 'processing', 'review', 'done'].forEach(s => {
            const el = document.getElementById(`bulk-step-${s}`);
            if (el) el.style.display = (s === step) ? '' : 'none';
        });
    }

    /** Handle file-input change or drop — compress and thumbnail each photo */
    async handleBulkPhotoSelect(files) {
        const fileList = Array.from(files || []);
        if (!fileList.length) return;

        const MAX = 30;
        const available = MAX - this.bulkPhotos.length;
        if (available <= 0) {
            this.showMessage(`Maximum ${MAX} photos per batch`, 'warning');
            return;
        }
        const toAdd = fileList.slice(0, available);
        if (fileList.length > available) {
            this.showMessage(`Only first ${available} photos added (${MAX} max per batch)`, 'warning');
        }

        // Show a temporary "loading…" placeholder while we compress
        const grid = document.getElementById('bulk-photo-grid');
        const placeholder = document.createElement('div');
        placeholder.className = 'bulk-thumb bulk-thumb-loading';
        placeholder.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        if (grid) grid.appendChild(placeholder);

        for (const file of toAdd) {
            const isImage = file.type.startsWith('image/') || !file.type;
            const validExt = /\.(jpg|jpeg|png|heic|heif|webp|gif|bmp|avif)$/i.test(file.name);
            if (!isImage && !validExt) continue;
            if (file.size > 10 * 1024 * 1024) continue;
            try {
                let processedFile = file;
                if (file.type === 'image/heic' || file.type === 'image/heif' ||
                    file.name.toLowerCase().endsWith('.heic')) {
                    processedFile = await this.convertHEICToJPEG(file);
                }
                const dataUrl = await this.compressItemPhoto(processedFile);
                if (!dataUrl) continue;
                // Use filename (minus extension) as initial name hint
                const hint = file.name.replace(/\.[^.]+$/, '').replace(/[-_]/g, ' ');
                this.bulkPhotos.push({ dataUrl, hint });
            } catch (e) {
                console.warn('Skipping photo:', file.name, e);
            }
        }

        if (grid && placeholder.parentNode) grid.removeChild(placeholder);
        this._bulkRenderThumbs();

        const actions = document.getElementById('bulk-upload-actions');
        if (actions) actions.style.display = this.bulkPhotos.length ? 'flex' : 'none';
        const countEl = document.getElementById('bulk-photo-count');
        if (countEl) countEl.textContent =
            `${this.bulkPhotos.length} photo${this.bulkPhotos.length !== 1 ? 's' : ''} ready`;
    }

    handleBulkDrop(event) {
        event.preventDefault();
        event.stopPropagation();
        const dt = event.dataTransfer;
        if (dt && dt.files && dt.files.length) this.handleBulkPhotoSelect(dt.files);
        const dz = document.getElementById('bulk-dropzone');
        if (dz) dz.classList.remove('bulk-dropzone-over');
    }

    handleBulkDragOver(event) {
        event.preventDefault();
        const dz = document.getElementById('bulk-dropzone');
        if (dz) dz.classList.add('bulk-dropzone-over');
    }

    handleBulkDragLeave() {
        const dz = document.getElementById('bulk-dropzone');
        if (dz) dz.classList.remove('bulk-dropzone-over');
    }

    removeBulkPhoto(index) {
        this.bulkPhotos.splice(index, 1);
        this._bulkRenderThumbs();
        const actions = document.getElementById('bulk-upload-actions');
        if (actions) actions.style.display = this.bulkPhotos.length ? 'flex' : 'none';
        const countEl = document.getElementById('bulk-photo-count');
        if (countEl) countEl.textContent =
            `${this.bulkPhotos.length} photo${this.bulkPhotos.length !== 1 ? 's' : ''} ready`;
    }

    _bulkRenderThumbs() {
        const grid = document.getElementById('bulk-photo-grid');
        if (!grid) return;
        grid.innerHTML = this.bulkPhotos.map((p, i) => `
            <div class="bulk-thumb">
                <img src="${p.dataUrl}" alt="Photo ${i + 1}">
                <button class="bulk-thumb-remove" onclick="app.removeBulkPhoto(${i})" title="Remove">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `).join('');
    }

    /** Run AI lookup on every photo in sequence, with progress */
    async runBulkAILookup() {
        if (!this.bulkPhotos.length) return;
        this._bulkShowStep('processing');
        this.bulkResults = [];

        const total = this.bulkPhotos.length;
        const fill = document.getElementById('bulk-progress-fill');
        const txt  = document.getElementById('bulk-progress-text');

        for (let i = 0; i < total; i++) {
            if (txt)  txt.textContent  = `Identifying photo ${i + 1} of ${total}…`;
            if (fill) fill.style.width = `${Math.round((i / total) * 100)}%`;

            const photo = this.bulkPhotos[i];
            const result = {
                photo: photo.dataUrl,
                name:  '',
                category: '',
                description: '',
                estimatedValue: 0,
                confidence: '',
                include: true
            };

            try {
                const resp = await fetch('/api/ai/lookup-item', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ photos: [photo.dataUrl] })
                });
                if (resp.ok) {
                    const data = await resp.json();
                    if (data.success && data.lookup) {
                        const l = data.lookup;
                        result.name          = l.item_name    || photo.hint || `Item ${i + 1}`;
                        result.category      = l.category     || '';
                        result.description   = l.description  || '';
                        result.estimatedValue = l.estimated_value || 0;
                        result.confidence    = l.confidence   || '';
                    }
                }
            } catch (e) {
                console.warn(`AI lookup failed for photo ${i + 1}:`, e);
            }

            // Fallback name from filename hint if AI gave nothing
            if (!result.name) result.name = photo.hint || `Item ${i + 1}`;
            this.bulkResults.push(result);
        }

        if (fill) fill.style.width = '100%';
        if (txt)  txt.textContent  = 'All done! Review your items below.';
        await new Promise(r => setTimeout(r, 500));

        this._bulkRenderReview();
        this._bulkShowStep('review');
    }

    _bulkRenderReview() {
        const grid     = document.getElementById('bulk-review-grid');
        const countEl  = document.getElementById('bulk-review-count');
        if (!grid) return;

        const included = this.bulkResults.filter(r => r.include).length;
        if (countEl) countEl.textContent =
            `${included} item${included !== 1 ? 's' : ''} ready to save`;

        const CATS = ['Furniture','Jewelry','Electronics','Art','Books','Clothing','Other'];
        const catOpts = CATS.map(c => `<option value="${c}">${c}</option>`).join('');

        grid.innerHTML = this.bulkResults.map((item, i) => `
            <div class="bulk-review-card${!item.include ? ' bulk-excluded' : ''}" id="bulk-card-${i}">
                <div class="bulk-card-photo">
                    <img src="${item.photo}" alt="Item ${i + 1}">
                    ${item.confidence ? `<span class="bulk-confidence bulk-conf-${item.confidence}">${item.confidence}</span>` : ''}
                    <button class="bulk-card-toggle" onclick="app.toggleBulkItem(${i})"
                        title="${item.include ? 'Remove from import' : 'Add back'}">
                        <i class="fas fa-${item.include ? 'times' : 'plus'}"></i>
                    </button>
                </div>
                <div class="bulk-card-fields">
                    <input  class="bulk-field" type="text"   placeholder="Item name *"
                        value="${this._esc(item.name)}"
                        oninput="app.updateBulkItem(${i},'name',this.value)">
                    <select class="bulk-field" onchange="app.updateBulkItem(${i},'category',this.value)">
                        <option value="">Category…</option>
                        ${catOpts}
                    </select>
                    <input  class="bulk-field" type="number" placeholder="Est. Value $" min="0"
                        value="${item.estimatedValue || ''}"
                        oninput="app.updateBulkItem(${i},'estimatedValue',parseFloat(this.value)||0)">
                    <textarea class="bulk-field bulk-field-desc" rows="2"
                        placeholder="Description (optional)"
                        oninput="app.updateBulkItem(${i},'description',this.value)">${this._esc(item.description)}</textarea>
                </div>
            </div>
        `).join('');

        // Restore select values after DOM is written
        this.bulkResults.forEach((item, i) => {
            const sel = document.querySelector(`#bulk-card-${i} select`);
            if (sel && item.category) sel.value = item.category;
        });
    }

    _esc(str) {
        return (str || '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;');
    }

    updateBulkItem(index, field, value) {
        if (this.bulkResults[index]) this.bulkResults[index][field] = value;
    }

    toggleBulkItem(index) {
        if (!this.bulkResults[index]) return;
        this.bulkResults[index].include = !this.bulkResults[index].include;
        this._bulkRenderReview();
    }

    /** POST all included items to the bulk-save endpoint */
    async saveBulkItems() {
        const toSave = this.bulkResults.filter(r => r.include && r.name.trim());
        if (!toSave.length) {
            this.showMessage('No items to save — check that each item has a name', 'warning');
            return;
        }

        const btns = document.querySelectorAll('#bulk-step-review .btn.primary');
        btns.forEach(b => { b.disabled = true; b.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving…'; });

        try {
            const resp = await fetch('/api/items/bulk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    items: toSave.map(r => ({
                        name:           r.name.trim(),
                        category:       r.category     || '',
                        description:    r.description  || '',
                        estimatedValue: r.estimatedValue || 0,
                        destination:    'keep',
                        photo:          r.photo,
                        photos:         [r.photo]
                    }))
                })
            });

            const data = await resp.json();
            if (data.success) {
                const titleEl = document.getElementById('bulk-done-title');
                const msgEl   = document.getElementById('bulk-done-message');
                if (titleEl) titleEl.textContent =
                    `${data.saved} Item${data.saved !== 1 ? 's' : ''} Added!`;
                if (msgEl) {
                    let msg = `Successfully added ${data.saved} item${data.saved !== 1 ? 's' : ''} to your inventory.`;
                    if (data.errors && data.errors.length)
                        msg += ` (${data.errors.length} item${data.errors.length !== 1 ? 's' : ''} could not be saved)`;
                    msgEl.textContent = msg;
                }
                this._bulkShowStep('done');
                this.loadInventory();
            } else {
                throw new Error(data.error || 'Save failed');
            }
        } catch (e) {
            this.showMessage(e.message || 'Failed to save items. Please try again.', 'error');
            btns.forEach(b => { b.disabled = false; b.innerHTML = '<i class="fas fa-save"></i> Save All Items'; });
        }
    }

    /**
     * Show inline QR panel for mobile photo capture in the Add Item modal.
     */
    async openMobileCameraForItem() {
        if (this.newItemPhotos.length >= 4) {
            this.showMessage('Maximum 4 photos allowed', 'error');
            return;
        }
        const panel = document.getElementById('mobile-photo-qr-panel');
        const options = document.getElementById('add-photo-options');
        if (!panel || !options) return;

        panel.innerHTML = `<div class="mobile-qr-loading"><i class="fas fa-spinner fa-spin"></i><p>Generating QR code...</p></div>`;
        options.style.display = 'none';
        panel.style.display = 'block';

        try {
            const response = await fetch('/api/qr/photo-session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const result = await response.json();
            if (!result.success) throw new Error(result.error || 'Failed');

            panel.innerHTML = `
                <div class="mobile-qr-content">
                    <img src="${result.qr_code}" alt="QR Code" class="mobile-qr-image">
                    <p class="mobile-qr-label"><i class="fas fa-mobile-alt"></i> Scan with your phone's camera</p>
                    <p class="mobile-qr-hint">Take or select a photo — it will appear here automatically.</p>
                    <div class="mobile-qr-waiting">
                        <i class="fas fa-circle-notch fa-spin"></i>
                        <span>Waiting for photo...</span>
                    </div>
                    <button type="button" class="add-photo-btn mobile-qr-cancel-btn"
                            onclick="window.app.cancelMobilePhotoCapture()">
                        <i class="fas fa-times"></i> Cancel
                    </button>
                </div>`;
            this.startMobilePhotoPolling(result.session_id);
        } catch (err) {
            console.error('Mobile photo QR error:', err);
            panel.innerHTML = `
                <div class="mobile-qr-error">
                    <i class="fas fa-exclamation-triangle"></i>
                    <p>Failed to generate QR code.</p>
                    <button type="button" class="add-photo-btn"
                            onclick="window.app.openMobileCameraForItem()">
                        <i class="fas fa-redo"></i> Retry
                    </button>
                    <button type="button" class="add-photo-btn"
                            onclick="window.app.cancelMobilePhotoCapture()">Cancel</button>
                </div>`;
        }
    }

    /**
     * Poll every 2.5s until a photo arrives from the mobile device (max 5 min).
     */
    startMobilePhotoPolling(sessionId) {
        if (this.mobilePhotoInterval) clearInterval(this.mobilePhotoInterval);
        const startTime = Date.now();
        this.mobilePhotoInterval = setInterval(async () => {
            if (Date.now() - startTime > 5 * 60 * 1000) {
                this.cancelMobilePhotoCapture();
                this.showMessage('Mobile photo capture timed out. Please try again.', 'warning');
                return;
            }
            try {
                const response = await fetch(`/api/qr/photo-poll/${sessionId}`);
                if (!response.ok) return;
                const data = await response.json();
                if (data.ready && data.photo) {
                    clearInterval(this.mobilePhotoInterval);
                    this.mobilePhotoInterval = null;
                    await this.addNewItemPhotoFromDataUrl(data.photo);
                    this.cancelMobilePhotoCapture();
                    this.showMessage('Photo added from mobile!', 'success');
                }
            } catch (err) {
                console.warn('Mobile photo poll error (will retry):', err);
            }
        }, 2500);
    }

    /**
     * Stop polling and restore the photo buttons.
     */
    cancelMobilePhotoCapture() {
        if (this.mobilePhotoInterval) {
            clearInterval(this.mobilePhotoInterval);
            this.mobilePhotoInterval = null;
        }
        const panel = document.getElementById('mobile-photo-qr-panel');
        const options = document.getElementById('add-photo-options');
        if (panel) panel.style.display = 'none';
        if (options) options.style.display = 'flex';
    }

    /**
     * Add a photo that arrived as a data URL (from mobile QR capture).
     * Re-compresses to 800px / 65% JPEG so it matches the direct-file-pick pipeline
     * and stays well under the 200KB AI-lookup size limit.
     */
    async addNewItemPhotoFromDataUrl(dataUrl) {
        if (this.newItemPhotos.length >= 4) {
            this.showMessage('Maximum 4 photos allowed', 'error');
            return;
        }
        try {
            const compressed = await new Promise((resolve, reject) => {
                const img = new Image();
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    let { width, height } = img;
                    const maxDim = 800;
                    if (width > maxDim || height > maxDim) {
                        const ratio = Math.min(maxDim / width, maxDim / height);
                        width = Math.round(width * ratio);
                        height = Math.round(height * ratio);
                    }
                    canvas.width = width;
                    canvas.height = height;
                    ctx.drawImage(img, 0, 0, width, height);
                    resolve(canvas.toDataURL('image/jpeg', 0.65));
                };
                img.onerror = () => reject(new Error('Image load failed'));
                img.src = dataUrl;
            });
            this.newItemPhotos.push(compressed);
        } catch (err) {
            // Fall back to original data URL if canvas compression fails
            console.warn('QR photo compression failed, using original:', err);
            this.newItemPhotos.push(dataUrl);
        }
        this.renderNewItemPhotoThumbnails();
    }

    /**
     * Populate inventory dropdown for pricing lookup
     */
    populatePricingInventory() {
        const select = document.getElementById('pricing-item-select');
        if (!select) return;
        
        // Clear existing options except the first one
        select.innerHTML = '<option value="">Choose an item from your inventory...</option>';
        
        // Add inventory items
        this.inventory.forEach(item => {
            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = `${item.name} (${item.category}) - $${item.estimatedValue}`;
            select.appendChild(option);
        });
    }

    /**
     * Show desire analysis for family decision making
     */
    async showDesireAnalysis() {
        try {
            // Get the current share ID from family settings
            const shareId = this.sharingSettings?.share_id;
            if (!shareId) {
                this.showMessage('No family sharing link found. Please create a family sharing link first.', 'info');
                return;
            }

            // Show loading
            const modal = document.getElementById('desire-analysis-modal');
            const analysisItems = document.getElementById('analysis-items');
            analysisItems.innerHTML = '<div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i> Loading desire analysis...</div>';
            openModal('desire-analysis-modal');

            // Fetch desire analysis
            const response = await fetch(`/api/family/desire-analysis/${shareId}`);
            const result = await response.json();

            if (result.success) {
                this.displayDesireAnalysis(result);
            } else {
                throw new Error(result.error || 'Failed to load desire analysis');
            }
        } catch (error) {
            console.error('Error loading desire analysis:', error);
            this.showMessage('Failed to load desire analysis. Please try again.', 'error');
        }
    }

    /**
     * Display desire analysis results
     */
    displayDesireAnalysis(data) {
        const summary = data.summary;
        const analysis = data.analysis;

        // Update summary stats
        document.getElementById('total-items-with-desires').textContent = summary.total_items_with_desires;
        document.getElementById('high-conflict-items').textContent = summary.high_conflict_items;
        document.getElementById('total-family-members').textContent = summary.total_family_members;

        // Display analysis items
        const analysisItems = document.getElementById('analysis-items');
        if (analysis.length === 0) {
            analysisItems.innerHTML = '<div class="empty-state"><i class="fas fa-info-circle"></i><p>No items have been tagged by family members yet.</p></div>';
            return;
        }

        const itemsHtml = analysis.map(item => this.createDesireAnalysisCard(item)).join('');
        analysisItems.innerHTML = itemsHtml;
    }

    /**
     * Create desire analysis card for an item
     */
    createDesireAnalysisCard(analysisItem) {
        const item = analysisItem.item;
        const desires = analysisItem.desire_analysis.desires;
        const conflictLevel = analysisItem.conflict_level;
        const averageDesire = analysisItem.average_desire;

        const conflictBadge = conflictLevel === 'high' ? 
            '<span class="conflict-badge high">High Conflict</span>' : 
            '<span class="conflict-badge none">No Conflict</span>';

        const desiresHtml = desires.map(desire => `
            <div class="desire-entry">
                <span class="member-name">${desire.member_name}</span>
                <div class="desire-level-display">
                    <span class="desire-level-number">${desire.desire_level}</span>
                    <span class="desire-level-label">${this.getDesireLevelLabel(desire.desire_level)}</span>
                </div>
            </div>
        `).join('');

        return `
            <div class="desire-analysis-card ${conflictLevel === 'high' ? 'high-conflict' : ''}">
                <div class="item-header">
                    <div class="item-image">
                        ${item.photo ? `<img src="${item.photo}" alt="${item.name}">` : '<i class="fas fa-image"></i>'}
                    </div>
                    <div class="item-info">
                        <h4>${item.name}</h4>
                        <p class="item-category">${item.category}</p>
                        <p class="item-value">$${item.estimatedValue || 0}</p>
                        ${conflictBadge}
                    </div>
                </div>
                
                <div class="desire-summary">
                    <div class="desire-stats">
                        <div class="stat">
                            <span class="stat-label">Average Desire:</span>
                            <span class="stat-value">${averageDesire}/5</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Total Desires:</span>
                            <span class="stat-value">${desires.length}</span>
                        </div>
                    </div>
                    
                    <div class="desire-list">
                        <h5>Family Member Desires:</h5>
                        ${desiresHtml}
                    </div>
                </div>
                
                <div class="analysis-actions">
                    <button class="btn primary" onclick="app.showAssignmentModal('${item.id}')">
                        <i class="fas fa-user-check"></i> Assign Item
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Get desire level label
     */
    getDesireLevelLabel(level) {
        const labels = {
            1: 'Not interested',
            2: 'Somewhat interested', 
            3: 'Interested',
            4: 'Really want it',
            5: 'Must have!'
        };
        return labels[level] || 'Unknown';
    }

    /**
     * Show assignment modal for an item
     */
    async showAssignmentModal(itemId) {
        try {
            // Get item details
            const item = this.inventory.find(i => i.id === itemId);
            if (!item) {
                this.showMessage('Item not found', 'error');
                return;
            }

            // Get desire analysis for this item
            const shareId = this.sharingSettings?.share_id;
            const response = await fetch(`/api/family/desire-analysis/${shareId}`);
            const result = await response.json();

            if (!result.success) {
                throw new Error(result.error || 'Failed to load desire analysis');
            }

            const analysisItem = result.analysis.find(a => a.item.id === itemId);
            if (!analysisItem) {
                this.showMessage('No desire data found for this item', 'info');
                return;
            }

            // Populate assignment modal
            this.populateAssignmentModal(item, analysisItem);
            openModal('assignment-modal');
        } catch (error) {
            console.error('Error showing assignment modal:', error);
            this.showMessage('Failed to load assignment data. Please try again.', 'error');
        }
    }

    /**
     * Populate assignment modal with item and desire data
     */
    populateAssignmentModal(item, analysisItem) {
        const preview = document.getElementById('assignment-item-preview');
        const desireSummary = document.getElementById('assignment-desire-summary');
        const memberSelect = document.getElementById('assign-to-member');

        // Item preview
        preview.innerHTML = `
            <div class="item-preview">
                <div class="item-image">
                    ${item.photo ? `<img src="${item.photo}" alt="${item.name}">` : '<i class="fas fa-image"></i>'}
                </div>
                <div class="item-info">
                    <h4>${item.name}</h4>
                    <p class="item-category">${item.category}</p>
                    <p class="item-value">$${item.estimatedValue || 0}</p>
                </div>
            </div>
        `;

        // Desire summary
        const desires = analysisItem.desire_analysis.desires;
        const desiresHtml = desires.map(desire => `
            <div class="desire-entry">
                <span class="member-name">${desire.member_name}</span>
                <span class="desire-level">Level ${desire.desire_level}: ${this.getDesireLevelLabel(desire.desire_level)}</span>
            </div>
        `).join('');

        desireSummary.innerHTML = `
            <h5>Family Member Desires:</h5>
            <div class="desire-list">
                ${desiresHtml}
            </div>
        `;

        // Populate member select
        memberSelect.innerHTML = '<option value="">Select family member...</option>';
        desires.forEach(desire => {
            const option = document.createElement('option');
            option.value = desire.member_code;
            option.textContent = `${desire.member_name} (Level ${desire.desire_level})`;
            memberSelect.appendChild(option);
        });
    }

    /**
     * Handle inventory item selection for pricing
     */
    onInventoryItemSelect(event) {
        const itemId = event.target.value;
        if (!itemId) return;
        
        const item = this.inventory.find(i => i.id === itemId);
        if (item) {
            document.getElementById('pricing-item-name').value = item.name;
            document.getElementById('pricing-item-category').value = item.category;
            document.getElementById('pricing-item-description').value = item.description || '';
        }
    }

    /**
     * Perform AI pricing lookup
     */
    async lookupPricing() {
        const itemSelect = document.getElementById('pricing-item-select');
        const itemName = document.getElementById('pricing-item-name').value.trim();
        const itemCategory = document.getElementById('pricing-item-category').value;
        const itemDescription = document.getElementById('pricing-item-description').value.trim();
        
        if (!itemSelect.value && !itemName) {
            this.showMessage('Please select an item from inventory or enter an item name.', 'error');
            return;
        }

        // Track which item this lookup is for (so we can apply the price later)
        this.pricingCurrentItemId = itemSelect.value || null;
        this.pricingCurrentPrice = null;
        const applyBtn = document.getElementById('apply-price-btn');
        if (applyBtn) applyBtn.style.display = 'none';

        // Show loading state
        this.showPricingLoading();
        
        try {
            const requestData = {
                item_id: itemSelect.value || null,
                item_name: itemName,
                item_category: itemCategory,
                item_description: itemDescription
            };
            
            const response = await fetch('/api/pricing/lookup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.displayPricingResults(result.data);
            } else {
                throw new Error(result.error || 'Failed to lookup pricing');
            }
        } catch (error) {
            console.error('Pricing lookup error:', error);
            this.showMessage('Failed to lookup pricing. Please try again.', 'error');
        } finally {
            this.hidePricingLoading();
        }
    }

    /**
     * Show pricing loading state
     */
    showPricingLoading() {
        document.getElementById('pricing-loading').style.display = 'block';
        document.getElementById('pricing-results').style.display = 'none';
        
        // Animate loading steps
        const steps = document.querySelectorAll('.loading-steps .step');
        let currentStep = 0;
        
        const stepInterval = setInterval(() => {
            steps.forEach(step => step.classList.remove('active'));
            if (currentStep < steps.length) {
                steps[currentStep].classList.add('active');
                currentStep++;
            } else {
                clearInterval(stepInterval);
            }
        }, 800);
    }

    /**
     * Hide pricing loading state
     */
    hidePricingLoading() {
        document.getElementById('pricing-loading').style.display = 'none';
    }

    /**
     * Display pricing results
     */
    displayPricingResults(data) {
        // Update results header
        document.getElementById('pricing-item-title').textContent = `Pricing Analysis: ${data.item_name}`;
        document.getElementById('average-price').textContent = `$${data.summary.overall_average.toFixed(2)}`;
        document.getElementById('price-range').textContent = `$${data.summary.price_range.min.toFixed(2)} - $${data.summary.price_range.max.toFixed(2)}`;
        
        // Update market trend
        const trendElement = document.getElementById('market-trend');
        trendElement.textContent = data.ai_analysis.market_trend.charAt(0).toUpperCase() + data.ai_analysis.market_trend.slice(1);
        trendElement.className = `stat-value trend ${data.ai_analysis.market_trend}`;
        
        // Update recommended price
        document.getElementById('recommended-price').textContent = `$${data.ai_analysis.recommended_price.toFixed(2)}`;
        document.getElementById('confidence-score').textContent = `${Math.round(data.ai_analysis.confidence_score * 100)}% confidence`;

        // Store price for apply-to-item button and show it if an inventory item was selected
        this.pricingCurrentPrice = data.ai_analysis.recommended_price;
        const applyBtn = document.getElementById('apply-price-btn');
        if (applyBtn) {
            applyBtn.style.display = this.pricingCurrentItemId ? 'inline-flex' : 'none';
        }

        // Update market insights
        const insightsList = document.getElementById('market-insights');
        insightsList.innerHTML = data.ai_analysis.market_insights.map(insight => `<li>${insight}</li>`).join('');
        
        // Update selling recommendations
        const recommendationsList = document.getElementById('selling-recommendations');
        recommendationsList.innerHTML = data.ai_analysis.selling_recommendations.map(rec => `<li>${rec}</li>`).join('');
        
        // Update platform results
        this.displayPlatformResults(data.platforms);
        
        // Show results
        document.getElementById('pricing-results').style.display = 'block';
    }

    /**
     * Display platform results
     */
    displayPlatformResults(platforms) {
        const platformGrid = document.getElementById('platform-grid');
        platformGrid.innerHTML = '';
        
        Object.entries(platforms).forEach(([key, platform]) => {
            const platformCard = document.createElement('div');
            platformCard.className = 'platform-card';
            platformCard.innerHTML = `
                <div class="platform-header">
                    <i class="${platform.icon}"></i>
                    <h5>${platform.name}</h5>
                </div>
                <div class="platform-stats">
                    <div class="platform-stat">
                        <span class="stat-label">Average</span>
                        <span class="stat-value">$${platform.average_price.toFixed(2)}</span>
                    </div>
                    <div class="platform-stat">
                        <span class="stat-label">Range</span>
                        <span class="stat-value">$${platform.price_range.min.toFixed(2)} - $${platform.price_range.max.toFixed(2)}</span>
                    </div>
                </div>
                <div class="platform-results-list">
                    ${platform.results.map(result => `
                        <a href="${result.url}" target="_blank" rel="noopener noreferrer" class="result-item-link">
                            <div class="result-item">
                                <div class="result-title">${result.title}</div>
                                <div class="result-details">
                                    <span class="result-price">$${result.price.toFixed(2)}</span>
                                    <span class="result-condition">${result.condition}</span>
                                    <span class="result-confidence">${Math.round(result.confidence * 100)}%</span>
                                    <i class="fas fa-external-link-alt result-link-icon"></i>
                                </div>
                            </div>
                        </a>
                    `).join('')}
                </div>
            `;
            platformGrid.appendChild(platformCard);
        });
    }

    /**
     * Apply the AI-recommended pricing to the selected inventory item's estimated value
     */
    async applyPricingToItem() {
        if (!this.pricingCurrentItemId || !this.pricingCurrentPrice) {
            this.showMessage('No item or price available to apply.', 'error');
            return;
        }

        const item = this.inventory.find(i => i.id === this.pricingCurrentItemId);
        const itemName = item ? item.name : 'this item';
        const priceFormatted = `$${this.pricingCurrentPrice.toFixed(2)}`;

        if (!confirm(`Set estimated value of "${itemName}" to ${priceFormatted}?`)) {
            return;
        }

        const applyBtn = document.getElementById('apply-price-btn');
        if (applyBtn) {
            applyBtn.disabled = true;
            applyBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving…';
        }

        try {
            const response = await fetch(`/api/items/${this.pricingCurrentItemId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ estimatedValue: this.pricingCurrentPrice })
            });

            if (!response.ok) {
                let errMsg = 'Failed to update price.';
                try {
                    const errData = await response.json();
                    if (errData && errData.error) errMsg = errData.error;
                } catch (_) {}
                throw new Error(errMsg);
            }

            const result = await response.json();
            if (result.success) {
                this.showMessage(`Price updated to ${priceFormatted} for "${itemName}"`, 'success');
                await this.loadInventory();
                // Hide button after successful apply
                if (applyBtn) applyBtn.style.display = 'none';
            } else {
                throw new Error(result.error || 'Failed to update price.');
            }
        } catch (error) {
            console.error('Apply pricing error:', error);
            this.showMessage(error.message || 'Failed to update price. Please try again.', 'error');
        } finally {
            if (applyBtn) {
                applyBtn.disabled = false;
                applyBtn.innerHTML = '<i class="fas fa-check-circle"></i> Use This Price';
            }
        }
    }

    /**
     * Quickly update an item's estimated value inline from the inventory card
     */
    async quickEditValue(itemId, currentValue) {
        const newValueStr = prompt(`Enter new estimated value for this item:`, currentValue);
        if (newValueStr === null) return; // user cancelled

        const newValue = parseFloat(newValueStr.replace(/[^0-9.]/g, ''));
        if (isNaN(newValue) || newValue < 0) {
            this.showMessage('Please enter a valid positive number.', 'error');
            return;
        }

        try {
            const response = await fetch(`/api/items/${itemId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ estimatedValue: newValue })
            });

            if (!response.ok) {
                let errMsg = 'Failed to update value.';
                try {
                    const errData = await response.json();
                    if (errData && errData.error) errMsg = errData.error;
                } catch (_) {}
                throw new Error(errMsg);
            }

            const result = await response.json();
            if (result.success) {
                this.showMessage(`Value updated to $${newValue.toFixed(2)}`, 'success');
                await this.loadInventory();
            } else {
                throw new Error(result.error || 'Failed to update value.');
            }
        } catch (error) {
            console.error('Quick edit value error:', error);
            this.showMessage(error.message || 'Failed to update value. Please try again.', 'error');
        }
    }

    /**
     * Update statistics
     */
    updateStats() {
        // Guard: Skip if not authenticated
        if (!this.currentUser) {
            console.log('Skipping stats update - user not authenticated');
            return;
        }

        const totalItems = this.inventory.length;
        const totalValue = this.inventory.reduce((sum, item) => sum + (item.estimatedValue || 0), 0);
        const forSaleItems = this.inventory.filter(item =>
            item.destination === 'sell' || (!item.destination && item.forSale)
        ).length;
        const assignedItems = this.inventory.filter(item =>
            item.destination === 'family' || item.destination === 'charity' ||
            (!item.destination && item.assignedTo)
        ).length;

        document.getElementById('total-items').textContent = totalItems;
        document.getElementById('total-value').textContent = `$${totalValue.toLocaleString()}`;
        document.getElementById('for-sale-items').textContent = forSaleItems;
        document.getElementById('assigned-items').textContent = assignedItems;

        // Refresh the personalised welcome card whenever stats update
        this.updateWelcomeCard();
    }

    /**
     * Returns a time-of-day greeting string.
     */
    getTimeGreeting() {
        const hour = new Date().getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 17) return 'Good afternoon';
        return 'Good evening';
    }

    /**
     * Populate the personalised dashboard welcome card and onboarding steps.
     * Called by updateStats() and by updateEstateSelector().
     */
    updateWelcomeCard() {
        if (!this.currentUser) return;

        const greetingEl  = document.getElementById('dashboard-greeting');
        const subtitleEl  = document.getElementById('dashboard-subtitle');
        const nextStepCard = document.getElementById('next-step-card');

        // --- Greeting ---
        const firstName = this.currentUser.name
            ? this.currentUser.name.trim().split(/\s+/)[0]
            : 'there';
        if (greetingEl) greetingEl.textContent = `${this.getTimeGreeting()}, ${firstName}!`;

        // --- Subtitle: estate name + item count ---
        const estateSelect = document.getElementById('estate-select');
        const estateName = (estateSelect && estateSelect.selectedIndex >= 0)
            ? estateSelect.options[estateSelect.selectedIndex].text
            : null;
        const totalItems = this.inventory.length;

        if (subtitleEl) {
            if (estateName && totalItems > 0) {
                subtitleEl.textContent = `${estateName} · ${totalItems} item${totalItems !== 1 ? 's' : ''} catalogued`;
            } else if (estateName) {
                subtitleEl.textContent = `${estateName} · Start adding items to build your inventory`;
            } else {
                subtitleEl.textContent = 'Create or select an estate to get started';
            }
        }

        // --- Onboarding card: show while < 5 items, hide once they're active ---
        if (!nextStepCard) return;

        if (totalItems >= 5) {
            nextStepCard.style.display = 'none';
            return;
        }
        nextStepCard.style.display = '';  // let CSS control visibility

        // Step 1 — Add item
        const stepAddItem = document.getElementById('step-add-item');
        if (stepAddItem) {
            const done = totalItems > 0;
            stepAddItem.classList.toggle('completed', done);
            const icon = stepAddItem.querySelector('.step-icon');
            if (icon) icon.className = done
                ? 'fas fa-check-circle step-icon'
                : 'fas fa-camera-retro step-icon';
        }

        // Step 2 — Invite family
        const stepInviteFamily = document.getElementById('step-invite-family');
        if (stepInviteFamily) {
            const done = !!(this.familyMembers && this.familyMembers.length > 0);
            stepInviteFamily.classList.toggle('completed', done);
            const icon = stepInviteFamily.querySelector('.step-icon');
            if (icon) icon.className = done
                ? 'fas fa-check-circle step-icon'
                : 'fas fa-user-plus step-icon';
        }
    }

    /**
     * Load family data
     */
    async loadFamilyData() {
        // Guard: Skip if not authenticated
        if (!this.currentUser) {
            console.log('Skipping family data load - user not authenticated');
            return;
        }

        try {
            // Load family members
            const membersResponse = await fetch('/api/family/members');
            const membersResult = await membersResponse.json();

            if (membersResult.success) {
                this.familyMembers = membersResult.members;
                this.updateFamilyMembersDisplay();
                this.updateFamilyStats();
            } else {
                this.familyMembers = [];
                this.updateFamilyMembersDisplay();
                if (membersResult.error) {
                    this.showMessage(membersResult.error, 'info');
                }
                return;
            }

            // Load sharing settings
            const settingsResponse = await fetch('/api/family/settings');
            const settingsResult = await settingsResponse.json();

            if (settingsResult.success) {
                this.sharingSettings = settingsResult.settings;
                this.updateSharingSettingsDisplay();
            }

            // Load sharing link
            try {
                const linkResponse = await fetch('/api/family/share-link');
                const linkResult = await linkResponse.json();

                if (linkResult.success) {
                    this.currentShareLink = linkResult.share_link;
                    document.getElementById('sharing-link').value = this.currentShareLink;
                }
            } catch (error) {
                // No existing link, that's okay
            }

        } catch (error) {
            console.error('Error loading family data:', error);
        }
    }

    /**
     * Update family members display
     */
    updateFamilyMembersDisplay() {
        const list = document.getElementById('family-members-list');
        const empty = document.getElementById('family-empty');

        if (!list) return;

        if (this.familyMembers.length === 0) {
            list.style.display = 'none';
            if (empty) empty.style.display = 'block';
            return;
        }

        if (empty) empty.style.display = 'none';
        list.style.display = 'block';

        list.innerHTML = this.familyMembers.map(member => `
            <div class="family-member-card">
                <div class="member-info">
                    <div class="member-header">
                        <h4>${member.name}</h4>
                        <span class="member-role role-${member.role || 'heir'}">
                            <i class="fas ${this.getRoleIcon(member.role)}"></i>
                            ${this.getRoleLabel(member.role)}
                        </span>
                    </div>
                    <p class="member-email">${member.email}</p>
                    <div class="member-status">
                        <span class="status-badge ${member.status}">${member.status}</span>
                        ${member.last_active ? `<span class="last-active">Last active: ${new Date(member.last_active).toLocaleDateString()}</span>` : ''}
                    </div>
                </div>
                <div class="member-actions">
                    <select class="role-selector" onchange="app.updateMemberRole('${member.code}', this.value)">
                        <option value="heir" ${(member.role || 'heir') === 'heir' ? 'selected' : ''}>Heir</option>
                        <option value="executor" ${member.role === 'executor' ? 'selected' : ''}>Executor</option>
                        <option value="viewer" ${member.role === 'viewer' ? 'selected' : ''}>Viewer</option>
                    </select>
                    <button class="btn small secondary" onclick="app.removeFamilyMember('${member.code}')">
                        <i class="fas fa-trash"></i>
                        Remove
                    </button>
                </div>
            </div>
        `).join('');
    }

    /**
     * Update family stats
     */
    updateFamilyStats() {
        document.getElementById('family-members-count').textContent = this.familyMembers.length;
        
        // Calculate wanted items count (would need API call in real implementation)
        document.getElementById('wanted-items-count').textContent = '0';
        
        // Calculate shared items count based on settings
        const sharedCount = this.sharingSettings.show_for_sale_only
            ? this.inventory.filter(item => item.destination === 'sell' || (!item.destination && item.forSale)).length
            : this.inventory.length;
        document.getElementById('shared-items-count').textContent = sharedCount;

        // Calculate conflict items and show decision making section if there are assignments
        const assignedItems = this.inventory.filter(item =>
            item.destination === 'family' || item.destination === 'charity' ||
            (!item.destination && item.assignedTo)
        );
        const conflictCount = assignedItems.length; // Simplified for now
        document.getElementById('conflict-items-count').textContent = conflictCount;
        
        // Show decision making section if there are assignments
        const decisionSection = document.getElementById('decision-making-section');
        if (assignedItems.length > 0 && decisionSection) {
            decisionSection.style.display = 'block';
        }
    }

    /**
     * Update sharing settings display
     */
    updateSharingSettingsDisplay() {
        document.getElementById('sharing-enabled').checked = this.sharingSettings.enabled;
        document.getElementById('for-sale-only').checked = this.sharingSettings.show_for_sale_only;
        document.getElementById('wanted-tagging').checked = this.sharingSettings.allow_wanted_tagging;
    }

    /**
     * Invite family member
     */
    async inviteFamilyMember() {
        const name = document.getElementById('family-member-name').value.trim();
        const email = document.getElementById('family-member-email').value.trim();
        const role = document.getElementById('family-member-role').value;

        if (!name || !email) {
            this.showMessage('Please enter both name and email', 'error');
            return;
        }

        try {
            const response = await fetch('/api/family/invite', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name, email, role })
            });

            const result = await response.json();

            if (result.success) {
                // Now send the invitation email
                try {
                    const emailResponse = await fetch('/api/notifications/send-invitation', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            email: email,
                            member_code: result.member_code,
                            owner_name: 'Estate Owner' // You could get this from user profile
                        })
                    });

                    const emailResult = await emailResponse.json();

                    if (emailResult.success) {
                        this.showMessage(`Family member invited successfully! Invitation email sent to ${email}`, 'success');
                    } else {
                        // Email failed - show share link to user
                        const shareLink = result.share_link;
                        this.showMessage(`Family member added! Share link copied to clipboard. Send it to ${email}`, 'success');

                        // Copy link to clipboard
                        navigator.clipboard.writeText(shareLink).catch(err => {
                            console.error('Failed to copy to clipboard:', err);
                        });
                    }
                } catch (emailError) {
                    console.error('Email sending error:', emailError);
                    // Show share link to user
                    const shareLink = result.share_link;
                    this.showMessage(`Family member added! Share link copied to clipboard. Send it to ${email}`, 'success');

                    // Copy link to clipboard
                    navigator.clipboard.writeText(shareLink).catch(err => {
                        console.error('Failed to copy to clipboard:', err);
                    });
                }

                this.closeModal('invite-family-modal');
                this.loadFamilyData();
                
                // Clear form
                document.getElementById('family-member-name').value = '';
                document.getElementById('family-member-email').value = '';
            } else {
                throw new Error(result.error || 'Failed to invite family member');
            }
        } catch (error) {
            console.error('Error inviting family member:', error);
            this.showMessage(error.message, 'error');
        }
    }

    /**
     * Generate sharing link
     */
    async generateShareLink() {
        try {
            const response = await fetch('/api/family/share-link', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();

            if (result.success) {
                this.currentShareLink = result.share_link;
                document.getElementById('sharing-link').value = this.currentShareLink;
                this.showMessage('New sharing link generated!', 'success');
            } else {
                throw new Error(result.error || 'Failed to generate sharing link');
            }
        } catch (error) {
            console.error('Error generating sharing link:', error);
            this.showMessage(error.message, 'error');
        }
    }

    /**
     * Copy sharing link to clipboard
     */
    async copyShareLink() {
        const linkInput = document.getElementById('sharing-link');
        
        if (!linkInput.value) {
            this.showMessage('No sharing link to copy. Generate one first.', 'error');
            return;
        }

        try {
            await navigator.clipboard.writeText(linkInput.value);
            this.showMessage('Sharing link copied to clipboard!', 'success');
        } catch (error) {
            // Fallback for older browsers
            linkInput.select();
            document.execCommand('copy');
            this.showMessage('Sharing link copied to clipboard!', 'success');
        }
    }

    /**
     * Update sharing settings
     */
    async updateSharingSettings() {
        const settings = {
            show_for_sale_only: document.getElementById('for-sale-only').checked,
            allow_wanted_tagging: document.getElementById('wanted-tagging').checked
        };

        try {
            const response = await fetch('/api/family/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(settings)
            });

            const result = await response.json();

            if (result.success) {
                this.sharingSettings = result.settings;
                this.updateFamilyStats();
                this.showMessage('Sharing settings updated!', 'success');
            } else {
                throw new Error(result.error || 'Failed to update settings');
            }
        } catch (error) {
            console.error('Error updating sharing settings:', error);
            this.showMessage(error.message, 'error');
        }
    }

    /**
     * Remove family member
     */
    async removeFamilyMember(memberCode) {
        if (!confirm('Are you sure you want to remove this family member?')) {
            return;
        }

        // In a real implementation, this would call an API endpoint
        this.familyMembers = this.familyMembers.filter(member => member.code !== memberCode);
        this.updateFamilyMembersDisplay();
        this.updateFamilyStats();
        this.showMessage('Family member removed', 'success');
    }

    /**
     * Open the authentication modal — used by landing page CTA buttons
     */
    openAuthModal() {
        this.openModal('auth-modal');
    }

    /**
     * Open modal
     */
    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            // Reset QR modal content if it's the QR modal
            if (modalId === 'qr-modal') {
                const qrContainer = document.getElementById('qr-code');
                if (qrContainer) {
                    qrContainer.innerHTML = `
                        <div class="qr-loading">
                            <i class="fas fa-spinner fa-spin"></i>
                            <p>Generating QR Code...</p>
                        </div>
                    `;
                }
            } else if (modalId === 'add-item-modal') {
                this.newItemPhotos = [];
                this.renderNewItemPhotoThumbnails();
            }

            modal.style.display = 'flex';
            modal.style.visibility = 'visible';
            modal.style.pointerEvents = 'auto';
            document.body.style.overflow = 'hidden';
        }
    }

    /**
     * Close modal
     */
    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
            modal.style.visibility = 'hidden';
            modal.style.pointerEvents = 'none';
            document.body.style.overflow = '';
        }
        if (modalId === 'add-item-modal') {
            this.cancelMobilePhotoCapture();
        }
    }

    /**
     * Load legacy/assignment data
     */
    async loadLegacy() {
        try {
            // Fetch inventory items (to show assignments)
            const inventoryResponse = await fetch('/api/items');
            const inventoryData = await inventoryResponse.json();

            // Fetch family members (to populate filters)
            const familyResponse = await fetch('/api/family/members');
            const familyData = await familyResponse.json();

            if (inventoryData.success && familyData.success) {
                this.legacyItems = inventoryData.items || [];
                this.familyMembers = familyData.members || [];

                this.updateLegacyStats();
                this.populateLegacyFilters();
                this.displayLegacyItems();
            }
        } catch (error) {
            console.error('Error loading legacy data:', error);
            this.showMessage('Failed to load legacy data', 'error');
        }
    }

    /**
     * Update legacy statistics
     */
    updateLegacyStats() {
        const totalItems = this.legacyItems.length;
        const assignedItems = this.legacyItems.filter(item => item.assigned_to).length;
        const unassignedItems = totalItems - assignedItems;
        const familyMembers = this.familyMembers.length;

        document.getElementById('legacy-total-items').textContent = totalItems;
        document.getElementById('legacy-assigned-items').textContent = assignedItems;
        document.getElementById('legacy-unassigned-items').textContent = unassignedItems;
        document.getElementById('legacy-family-members').textContent = familyMembers;
    }

    /**
     * Populate filter dropdowns
     */
    populateLegacyFilters() {
        const assigneeFilter = document.getElementById('legacy-filter-assignee');

        // Clear existing options (except "All")
        assigneeFilter.innerHTML = '<option value="all">All Family Members</option>';

        // Add family members
        this.familyMembers.forEach(member => {
            const option = document.createElement('option');
            option.value = member.email;
            option.textContent = member.name;
            assigneeFilter.appendChild(option);
        });
    }

    /**
     * Display legacy items in grid
     */
    displayLegacyItems() {
        const grid = document.getElementById('legacy-items-grid');
        const filteredItems = this.getFilteredLegacyItems();

        if (filteredItems.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-box-open fa-3x"></i>
                    <p>No items match your filters</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = filteredItems.map(item => `
            <div class="assignment-card" data-item-id="${item.id}">
                <div class="assignment-card-image">
                    ${item.photo ? `<img src="${item.photo}" alt="${item.name}">` : '<i class="fas fa-box fa-3x"></i>'}
                </div>
                <div class="assignment-card-content">
                    <h4>${item.name}</h4>
                    <p class="item-category"><i class="fas fa-tag"></i> ${item.category || 'Uncategorized'}</p>
                    <p class="item-value"><i class="fas fa-dollar-sign"></i> ${item.value ? '$' + item.value.toFixed(2) : 'No value'}</p>
                    ${item.assigned_to ? `
                        <div class="assignment-status assigned">
                            <i class="fas fa-user-check"></i> Assigned to ${this.getFamilyMemberName(item.assigned_to)}
                        </div>
                        ${item.assignment_reason ? `<p class="assignment-reason">${item.assignment_reason}</p>` : ''}
                    ` : `
                        <div class="assignment-status unassigned">
                            <i class="fas fa-user-times"></i> Not assigned
                        </div>
                    `}
                </div>
                <div class="assignment-card-actions">
                    ${item.assigned_to ? `
                        <button class="btn btn-sm secondary" onclick="app.reassignItem('${item.id}')">
                            <i class="fas fa-exchange-alt"></i> Reassign
                        </button>
                        <button class="btn btn-sm danger" onclick="app.unassignItem('${item.id}')">
                            <i class="fas fa-times"></i> Unassign
                        </button>
                    ` : `
                        <button class="btn btn-sm primary" onclick="app.assignItem('${item.id}')">
                            <i class="fas fa-user-plus"></i> Assign
                        </button>
                    `}
                    <button class="btn btn-sm secondary" onclick="app.addItemStory('${item.id}')">
                        <i class="fas fa-heart"></i> Add Story
                    </button>
                </div>
            </div>
        `).join('');
    }

    /**
     * Filter legacy items based on search and filters
     */
    getFilteredLegacyItems() {
        let items = [...this.legacyItems];

        // Search filter
        const searchTerm = document.getElementById('legacy-search').value.toLowerCase();
        if (searchTerm) {
            items = items.filter(item =>
                item.name.toLowerCase().includes(searchTerm) ||
                (item.description && item.description.toLowerCase().includes(searchTerm))
            );
        }

        // Status filter
        const statusFilter = document.getElementById('legacy-filter-status').value;
        if (statusFilter === 'assigned') {
            items = items.filter(item => item.assigned_to);
        } else if (statusFilter === 'unassigned') {
            items = items.filter(item => !item.assigned_to);
        }

        // Assignee filter
        const assigneeFilter = document.getElementById('legacy-filter-assignee').value;
        if (assigneeFilter !== 'all') {
            items = items.filter(item => item.assigned_to === assigneeFilter);
        }

        return items;
    }

    /**
     * Filter and redisplay items
     */
    filterLegacyItems() {
        this.displayLegacyItems();
    }

    /**
     * Sort legacy items
     */
    sortLegacyItems() {
        const sortBy = document.getElementById('legacy-sort').value;

        this.legacyItems.sort((a, b) => {
            switch(sortBy) {
                case 'name':
                    return a.name.localeCompare(b.name);
                case 'value':
                    return (b.value || 0) - (a.value || 0);
                case 'assignee':
                    return (a.assigned_to || 'zzz').localeCompare(b.assigned_to || 'zzz');
                case 'date':
                    return new Date(b.created_at || 0) - new Date(a.created_at || 0);
                default:
                    return 0;
            }
        });

        this.displayLegacyItems();
    }

    /**
     * Get family member name by email
     */
    getFamilyMemberName(email) {
        const member = this.familyMembers.find(m => m.email === email);
        return member ? member.name : email;
    }

    /**
     * Assign single item
     */
    async assignItem(itemId) {
        const item = this.legacyItems.find(i => i.id === itemId);
        if (!item) return;

        // Reuse existing showAssignmentModal function
        this.showAssignmentModal(item);
    }

    /**
     * Reassign item
     */
    async reassignItem(itemId) {
        this.assignItem(itemId); // Same as assign, modal will show current assignment
    }

    /**
     * Unassign item
     */
    async unassignItem(itemId) {
        if (!confirm('Remove assignment from this item?')) return;

        try {
            const response = await fetch(`/api/items/${itemId}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    assigned_to: '',
                    assignment_reason: ''
                })
            });

            const data = await response.json();
            if (data.success) {
                this.showMessage('Assignment removed', 'success');
                await this.loadLegacy();
            } else {
                throw new Error(data.error || 'Failed to unassign item');
            }
        } catch (error) {
            console.error('Error unassigning item:', error);
            this.showMessage(error.message, 'error');
        }
    }

    /**
     * Show bulk assignment modal
     */
    showBulkAssignmentModal() {
        // Populate family members dropdown
        const assigneeSelect = document.getElementById('bulk-assignee');
        assigneeSelect.innerHTML = '<option value="">Select family member...</option>';
        this.familyMembers.forEach(member => {
            const option = document.createElement('option');
            option.value = member.email;
            option.textContent = member.name;
            assigneeSelect.appendChild(option);
        });

        // Populate items checklist (only unassigned items)
        const itemsList = document.getElementById('bulk-items-list');
        const unassignedItems = this.legacyItems.filter(item => !item.assigned_to);

        if (unassignedItems.length === 0) {
            itemsList.innerHTML = '<p>All items are already assigned</p>';
        } else {
            itemsList.innerHTML = unassignedItems.map(item => `
                <label class="checkbox-item">
                    <input type="checkbox" value="${item.id}">
                    <span>${item.name} - $${item.value || 0}</span>
                </label>
            `).join('');
        }

        this.openModal('bulk-assignment-modal');
    }

    /**
     * Submit bulk assignment
     */
    async submitBulkAssignment() {
        const assignee = document.getElementById('bulk-assignee').value;
        const reason = document.getElementById('bulk-assignment-reason').value;

        if (!assignee) {
            this.showMessage('Please select a family member', 'error');
            return;
        }

        const selectedItems = Array.from(document.querySelectorAll('#bulk-items-list input:checked'))
            .map(input => input.value);

        if (selectedItems.length === 0) {
            this.showMessage('Please select at least one item', 'error');
            return;
        }

        try {
            // Assign each item
            const promises = selectedItems.map(itemId =>
                fetch(`/api/items/${itemId}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        assigned_to: assignee,
                        assignment_reason: reason
                    })
                })
            );

            await Promise.all(promises);

            this.showMessage(`Assigned ${selectedItems.length} item(s) successfully`, 'success');
            this.closeModal('bulk-assignment-modal');
            await this.loadLegacy();
        } catch (error) {
            console.error('Error in bulk assignment:', error);
            this.showMessage('Failed to assign items', 'error');
        }
    }

    /**
     * Add sentimental story to item
     */
    addItemStory(itemId) {
        // TODO: Implement story/sentimental value modal
        this.showMessage('Story feature coming soon!', 'info');
    }

    /**
     * Show loading overlay
     */
    showLoading(text = 'Loading...') {
        const overlay = document.getElementById('loading-overlay');
        const loadingText = document.getElementById('loading-text');
        
        if (overlay) {
            if (loadingText) loadingText.textContent = text;
            overlay.style.display = 'flex';
        }
    }

    /**
     * Hide loading overlay
     */
    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    }

    /**
     * Show message to user
     */
    showMessage(message, type = 'info') {
        // Create message element
        const messageEl = document.createElement('div');
        messageEl.className = `message message-${type}`;
        messageEl.innerHTML = `
            <div class="message-content">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
            <button class="message-close" onclick="this.parentElement.remove()">&times;</button>
        `;

        // Add to page
        document.body.appendChild(messageEl);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (messageEl.parentElement) {
                messageEl.remove();
            }
        }, 5000);
    }

    /**
     * Add activity to recent activity list
     */
    addActivity(text) {
        const activityList = document.getElementById('activity-list');
        if (!activityList) return;

        const activityItem = document.createElement('div');
        activityItem.className = 'activity-item';
        activityItem.innerHTML = `
            <i class="fas fa-clock"></i>
            <span>${text}</span>
            <small>${new Date().toLocaleTimeString()}</small>
        `;

        activityList.insertBefore(activityItem, activityList.firstChild);

        // Keep only last 5 activities
        while (activityList.children.length > 5) {
            activityList.removeChild(activityList.lastChild);
        }
    }

    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        return this.currentUser !== null;
    }

    /**
     * Update authentication UI based on login status
     */
    updateAuthUI(isAuthenticated) {
        const userMenu = document.getElementById('user-menu');
        const authButtons = document.getElementById('auth-buttons');
        const estateSelector = document.getElementById('estate-selector');

        // Elements may not exist on the landing page — guard against null
        if (isAuthenticated) {
            if (userMenu) userMenu.style.display = 'block';
            if (estateSelector) estateSelector.style.display = 'flex';
            if (authButtons) authButtons.style.display = 'none';

            // Update user name — show first name only + gold initials avatar
            this._updateUserDisplay(this.currentUser);
        } else {
            if (userMenu) userMenu.style.display = 'none';
            if (estateSelector) estateSelector.style.display = 'none';
            if (authButtons) authButtons.style.display = 'flex';
        }
    }

    /**
     * Update header user display — initials avatar + first name only.
     * Keeps full name in the DOM for profile modal but shows compact form in header.
     */
    _updateUserDisplay(user) {
        if (!user || !user.name) return;
        const parts = user.name.trim().split(/\s+/);
        const firstName = parts[0];
        // Build initials: first letter of first name + first letter of last word (if exists)
        const initials = (parts.length > 1)
            ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
            : parts[0].slice(0, 2).toUpperCase();

        const avatar = document.getElementById('user-initials-avatar');
        const nameEl = document.getElementById('user-name');
        if (avatar) avatar.textContent = initials;
        if (nameEl) nameEl.textContent = firstName;
    }

    /**
     * Update estate selector dropdown
     */
    updateEstateSelector(estates, currentEstateId) {
        const select = document.getElementById('estate-select');
        if (!select) return;

        // Clear existing options
        select.innerHTML = '<option value="">Select Estate...</option>';

        // Add estates
        estates.forEach(estate => {
            const option = document.createElement('option');
            option.value = estate.id;
            option.textContent = estate.name;
            if (estate.user_role === 'owner') {
                option.textContent += ' (Owner)';
            }
            if (estate.id === currentEstateId) {
                option.selected = true;
            }
            select.appendChild(option);
        });

        // Also populate mobile estate dropdown
        const mobileDropdown = document.getElementById('mobile-estate-dropdown');
        if (mobileDropdown) {
            mobileDropdown.innerHTML = '<option value="">Select Estate...</option>';
            estates.forEach(estate => {
                const option = document.createElement('option');
                option.value = estate.id;
                option.textContent = estate.name;
                if (estate.user_role === 'owner') {
                    option.textContent += ' (Owner)';
                }
                option.selected = (estate.id === currentEstateId);
                mobileDropdown.appendChild(option);
            });
        }

        // Update mobile estate indicator text and let CSS media query control visibility.
        // Do NOT set display:flex inline — that would override the media query and show
        // the indicator on desktop too, duplicating the estate name from the centre selector.
        const mobileEstateIndicator = document.getElementById('mobile-estate-indicator');
        const estateNameMobile = document.getElementById('estate-name-mobile');
        if (mobileEstateIndicator && estateNameMobile && currentEstateId) {
            const currentEstate = estates.find(e => e.id === currentEstateId);
            if (currentEstate) {
                estateNameMobile.textContent = currentEstate.name;
                // Clear the initial inline display:none so the CSS media query takes over
                mobileEstateIndicator.style.removeProperty('display');
            }
        }

        // Refresh the welcome card subtitle now that we know the estate name
        this.updateWelcomeCard();
    }

    /**
     * Switch to a different estate
     */
    async switchEstate(estateId) {
        if (!estateId) return;
        
        try {
            const response = await fetch('/api/estates/switch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ estate_id: estateId })
            });

            const data = await response.json();

            if (data.success) {
                this.showMessage(`Switched to ${data.estate.name}`, 'success');
                // Reload inventory and other data for the new estate
                this.loadInventory();
                this.loadFamilyData();
                this.updateStats();
                this.loadEstateTimeline();
                this.updateDisposalStats();
            } else {
                throw new Error(data.error || 'Failed to switch estate');
            }
        } catch (error) {
            console.error('Error switching estate:', error);
            this.showMessage(error.message, 'error');
        }
    }

    /**
     * Show welcome modal (first-time users)
     */
    showWelcomeModal() {
        this.openModal('welcome-modal');
    }

    /**
     * Start estate creation from welcome modal
     */
    startEstateCreation() {
        this.closeModal('welcome-modal');
        setTimeout(() => {
            this.showCreateEstateModal();
        }, 300);
    }

    /**
     * Get icon for a role
     */
    getRoleIcon(role) {
        const icons = {
            'owner': 'fa-crown',
            'executor': 'fa-gavel',
            'heir': 'fa-user',
            'viewer': 'fa-eye'
        };
        return icons[role] || icons['heir'];
    }

    /**
     * Get display label for a role
     */
    getRoleLabel(role) {
        const labels = {
            'owner': 'Owner',
            'executor': 'Executor',
            'heir': 'Heir',
            'viewer': 'Viewer'
        };
        return labels[role] || labels['heir'];
    }

    /**
     * Update a family member's role
     */
    async updateMemberRole(memberCode, newRole) {
        try {
            const response = await fetch(`/api/family/members/${memberCode}/role`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ role: newRole })
            });

            const data = await response.json();

            if (data.success) {
                this.showMessage(`Role updated to ${this.getRoleLabel(newRole)}`, 'success');
                this.loadFamilyMembers();
            } else {
                this.showMessage(data.error || 'Failed to update role', 'error');
                this.loadFamilyMembers();
            }
        } catch (error) {
            console.error('Error updating member role:', error);
            this.showMessage('Failed to update role', 'error');
            this.loadFamilyMembers();
        }
    }

    /**
     * Show create estate modal
     */
    showCreateEstateModal() {
        this.openModal('create-estate-modal');
    }

    /**
     * Create a new estate
     */
    async createEstate(event) {
        event.preventDefault();
        
        const estateName = document.getElementById('estate-name').value.trim();
        if (!estateName) {
            this.showMessage('Please enter an estate name', 'error');
            return;
        }

        try {
            const response = await fetch('/api/estates', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name: estateName })
            });

            const data = await response.json();

            if (data.success) {
                this.showMessage('Estate created successfully!', 'success');
                this.closeModal('create-estate-modal');
                this.closeModal('welcome-modal');
                document.getElementById('estate-name').value = '';

                // Re-enable UI for first-time users who just created their first estate
                const mainContent = document.querySelector('.main');
                if (mainContent) {
                    mainContent.style.pointerEvents = 'auto';
                    mainContent.style.opacity = '1';
                }

                // Reload estates
                await this.checkAuthStatus();

                // Reload inventory and other data
                this.loadInventory();
                this.loadFamilyData();
                this.updateStats();
            } else {
                throw new Error(data.error || 'Failed to create estate');
            }
        } catch (error) {
            console.error('Error creating estate:', error);
            this.showMessage(error.message, 'error');
        }
    }

    /**
     * Handle user login
     */
    async login(email, password) {
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (data.success) {
                this.currentUser = data.user;
                this.updateAuthUI(true);
                this.closeModal('auth-modal');
                this.showMessage('Welcome back!', 'success');
                return true;
            } else {
                throw new Error(data.error || 'Login failed');
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showMessage(error.message, 'error');
            return false;
        }
    }

    /**
     * Handle user signup
     */
    async signup(name, email, password) {
        try {
            const response = await fetch('/api/auth/signup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name, email, password })
            });

            const data = await response.json();

            if (data.success) {
                this.currentUser = data.user;
                this.updateAuthUI(true);
                this.closeModal('auth-modal');
                this.showMessage('Account created successfully!', 'success');
                return true;
            } else {
                throw new Error(data.error || 'Signup failed');
            }
        } catch (error) {
            console.error('Signup error:', error);
            this.showMessage(error.message, 'error');
            return false;
        }
    }

    /**
     * Handle user logout
     */
    async logout() {
        try {
            const response = await fetch('/api/auth/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (data.success) {
                this.currentUser = null;
                this.updateAuthUI(false);
                this.showMessage('Logged out successfully', 'success');

                // Open login modal so user can log back in
                this.openModal('auth-modal');

                return true;
            } else {
                throw new Error(data.error || 'Logout failed');
            }
        } catch (error) {
            console.error('Logout error:', error);
            this.showMessage(error.message, 'error');
            return false;
        }
    }

    /**
     * Handle Google OAuth login
     */
    async loginWithGoogle() {
        try {
            console.log('Redirecting to Google OAuth...');
            window.location.href = '/auth/google/login';
        } catch (error) {
            console.error('Google login error:', error);
            this.showMessage('Google login failed', 'error');
        }
    }

    /**
     * Handle Facebook OAuth login
     */
    async loginWithFacebook() {
        try {
            window.location.href = '/auth/facebook/login';
        } catch (error) {
            console.error('Facebook login error:', error);
            this.showMessage('Facebook login failed', 'error');
        }
    }

    /**
     * Handle item assignment
     */
    async handleAssignment() {
        try {
            const itemId = this.currentAssignmentItemId;
            const assignedTo = document.getElementById('assign-to-member').value;
            const reason = document.getElementById('assignment-reason').value;

            if (!assignedTo) {
                this.showMessage('Please select a family member to assign the item to.', 'error');
                return;
            }

            const shareId = this.sharingSettings?.share_id;
            const response = await fetch(`/api/family/assign-item/${shareId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    item_id: itemId,
                    assigned_to: assignedTo,
                    reason: reason
                })
            });

            const result = await response.json();

            if (result.success) {
                this.showMessage('Item assigned successfully!', 'success');
                closeModal('assignment-modal');
                this.loadInventory(); // Refresh inventory to show assignment
            } else {
                throw new Error(result.error || 'Failed to assign item');
            }
        } catch (error) {
            console.error('Error assigning item:', error);
            this.showMessage('Failed to assign item. Please try again.', 'error');
        }
    }

    /**
     * Generate assignment report PDF
     */
    async generateAssignmentReport() {
        try {
            this.showMessage('Generating assignment report...', 'info');
            
            const response = await fetch('/api/reports/assignments');
            const result = await response.json();

            if (result.success) {
                // Create download link
                const downloadUrl = result.download_url;
                const filename = result.filename;
                
                // Create temporary link and trigger download
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                this.showMessage('Assignment report downloaded successfully!', 'success');
            } else {
                throw new Error(result.error || 'Failed to generate report');
            }
        } catch (error) {
            console.error('Error generating assignment report:', error);
            this.showMessage('Failed to generate assignment report. Please try again.', 'error');
        }
    }

    /**
     * Show add task modal
     */
    showAddTaskModal() {
        openModal('add-task-modal');
    }

    /**
     * Show disposal modal for an item
     */
    showDisposalModal(itemId) {
        this.currentDisposalItemId = itemId;
        openModal('disposal-modal');
    }

    /**
     * Show disposal summary
     */
    async showDisposalSummary() {
        try {
            const response = await fetch('/api/estate/disposal-summary');
            const result = await response.json();

            if (result.success) {
                const summary = result.summary;
                alert(`Disposal Summary:\n\nTotal Items: ${summary.total_disposed}\nTotal Value: $${summary.total_value.toFixed(2)}\nTax Deductible: $${summary.tax_deductible.toFixed(2)}\n\nBy Type:\n${Object.entries(summary.by_type).map(([type, data]) => `${type}: ${data.count} items, $${data.value.toFixed(2)}`).join('\n')}`);
            } else {
                throw new Error(result.error || 'Failed to load disposal summary');
            }
        } catch (error) {
            console.error('Error loading disposal summary:', error);
            this.showMessage('Failed to load disposal summary.', 'error');
        }
    }

    /**
     * Load estate timeline
     */
    async loadEstateTimeline() {
        // Skip if not logged in
        if (!this.currentUser) {
            console.log('Skipping estate timeline load - user not logged in');
            return;
        }

        try {
            const response = await fetch('/api/estate/timeline');
            const result = await response.json();

            if (result.success) {
                this.displayEstateTimeline(result.timeline);
            } else {
                throw new Error(result.error || 'Failed to load timeline');
            }
        } catch (error) {
            console.error('Error loading estate timeline:', error);
            // Only show error if user is logged in
            if (this.currentUser) {
                this.showMessage('Failed to load estate timeline.', 'error');
            }
        }
    }

    /**
     * Display estate timeline
     */
    displayEstateTimeline(timeline) {
        const container = document.getElementById('timeline-container');
        if (!container) return;

        if (timeline.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-tasks"></i><p>No tasks yet. Add your first settlement task!</p></div>';
            return;
        }

        const timelineHtml = timeline.map(task => `
            <div class="timeline-item ${task.status}">
                <div class="timeline-marker priority-${task.priority}"></div>
                <div class="timeline-content">
                    <h4>${task.task}</h4>
                    <div class="timeline-meta">
                        <span class="priority priority-${task.priority}">${task.priority}</span>
                        <span class="status status-${task.status}">${task.status}</span>
                        ${task.due_date ? `<span class="due-date">Due: ${new Date(task.due_date).toLocaleDateString()}</span>` : ''}
                    </div>
                </div>
                <div class="timeline-actions">
                    <button class="btn small" onclick="app.updateTaskStatus('${task.id}', '${task.status === 'completed' ? 'pending' : 'completed'}')">
                        <i class="fas fa-${task.status === 'completed' ? 'undo' : 'check'}"></i>
                    </button>
                </div>
            </div>
        `).join('');

        container.innerHTML = timelineHtml;
    }

    /**
     * Update disposal stats
     */
    async updateDisposalStats() {
        // Skip if not logged in
        if (!this.currentUser) {
            console.log('Skipping disposal stats update - user not logged in');
            return;
        }

        try {
            const response = await fetch('/api/estate/disposal-summary');
            const result = await response.json();

            if (result.success) {
                const summary = result.summary;
                document.getElementById('total-disposed').textContent = summary.total_disposed;
                document.getElementById('tax-deductible').textContent = `$${summary.tax_deductible.toFixed(2)}`;
                document.getElementById('total-value-disposed').textContent = `$${summary.total_value.toFixed(2)}`;
            }
        } catch (error) {
            console.error('Error updating disposal stats:', error);
        }
    }

    /**
     * Generate disposal report
     */
    async generateDisposalReport() {
        try {
            this.showMessage('Generating disposal report...', 'info');
            
            // This would generate a PDF report of disposed items
            // For now, show the summary
            this.showDisposalSummary();
        } catch (error) {
            console.error('Error generating disposal report:', error);
            this.showMessage('Failed to generate disposal report.', 'error');
        }
    }

    /**
     * Add estate settlement task
     */
    async addTask() {
        try {
            const task = document.getElementById('task-description').value.trim();
            const dueDate = document.getElementById('task-due-date').value;
            const priority = document.getElementById('task-priority').value;

            if (!task) {
                this.showMessage('Please enter a task description.', 'error');
                return;
            }

            const response = await fetch('/api/estate/timeline', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    task: task,
                    due_date: dueDate,
                    priority: priority
                })
            });

            const result = await response.json();

            if (result.success) {
                this.showMessage('Task added successfully!', 'success');
                closeModal('add-task-modal');
                this.loadEstateTimeline();
                
                // Clear form
                document.getElementById('add-task-form').reset();
            } else {
                throw new Error(result.error || 'Failed to add task');
            }
        } catch (error) {
            console.error('Error adding task:', error);
            this.showMessage('Failed to add task. Please try again.', 'error');
        }
    }

    /**
     * Dispose an item
     */
    async disposeItem() {
        try {
            const disposalType = document.getElementById('disposal-type').value;
            const disposalValue = parseFloat(document.getElementById('disposal-value').value) || 0;
            const disposalNotes = document.getElementById('disposal-notes').value.trim();

            if (!disposalType) {
                this.showMessage('Please select a disposal type.', 'error');
                return;
            }

            const response = await fetch(`/api/items/${this.currentDisposalItemId}/dispose`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    disposal_type: disposalType,
                    disposal_value: disposalValue,
                    disposal_notes: disposalNotes
                })
            });

            const result = await response.json();

            if (result.success) {
                this.showMessage(`Item marked as ${disposalType} successfully!`, 'success');
                closeModal('disposal-modal');
                this.loadInventory();
                this.updateDisposalStats();
                
                // Clear form
                document.getElementById('disposal-form').reset();
            } else {
                throw new Error(result.error || 'Failed to dispose item');
            }
        } catch (error) {
            console.error('Error disposing item:', error);
            this.showMessage('Failed to dispose item. Please try again.', 'error');
        }
    }

    /**
     * Show bulk disposal modal
     */
    showBulkDisposalModal() {
        this.showMessage('Bulk disposal feature coming soon!', 'info');
    }

    /**
     * Show donation tracker
     */
    showDonationTracker() {
        this.showMessage('Donation tracker feature coming soon!', 'info');
    }

    /**
     * Update task status
     */
    async updateTaskStatus(taskId, newStatus) {
        try {
            const response = await fetch(`/api/estate/timeline/${taskId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    status: newStatus
                })
            });

            const result = await response.json();

            if (result.success) {
                this.showMessage('Task status updated!', 'success');
                this.loadEstateTimeline();
            } else {
                throw new Error(result.error || 'Failed to update task');
            }
        } catch (error) {
            console.error('Error updating task status:', error);
            this.showMessage('Failed to update task status.', 'error');
        }
    }

    /**
     * Bulk Operations
     */

    getSelectedItems() {
        const checkboxes = document.querySelectorAll('.item-select-checkbox:checked');
        return Array.from(checkboxes).map(cb => cb.dataset.itemId);
    }

    selectAllItems() {
        const checkboxes = document.querySelectorAll('.item-select-checkbox');
        const allChecked = Array.from(checkboxes).every(cb => cb.checked);
        checkboxes.forEach(cb => cb.checked = !allChecked);
        this.updateBulkActions();
    }

    updateBulkActions() {
        const selectedIds = this.getSelectedItems();
        const toolbar = document.getElementById('bulk-actions-toolbar');
        const count = document.getElementById('selected-count');

        if (!toolbar) return;

        if (selectedIds.length > 0) {
            toolbar.style.display = 'flex';
            if (count) count.textContent = selectedIds.length;
        } else {
            toolbar.style.display = 'none';
        }
    }

    async bulkDelete() {
        const selectedIds = this.getSelectedItems();

        if (selectedIds.length === 0) {
            this.showMessage('No items selected', 'error');
            return;
        }

        if (!confirm(`Delete ${selectedIds.length} selected item(s)? This cannot be undone.`)) {
            return;
        }

        this.showLoading(`Deleting ${selectedIds.length} items...`);

        let successCount = 0;
        let failCount = 0;

        for (const itemId of selectedIds) {
            try {
                const response = await fetch(`/api/items/${itemId}`, {
                    method: 'DELETE'
                });

                const result = await response.json();

                if (result.success) {
                    successCount++;
                } else {
                    failCount++;
                }
            } catch (error) {
                console.error(`Error deleting item ${itemId}:`, error);
                failCount++;
            }
        }

        this.hideLoading();

        if (successCount > 0) {
            this.showMessage(`Deleted ${successCount} item(s)`, 'success');
            await this.loadInventory();
        }

        if (failCount > 0) {
            this.showMessage(`Failed to delete ${failCount} item(s)`, 'error');
        }
    }

    async bulkEdit(field, value) {
        const selectedIds = this.getSelectedItems();

        if (selectedIds.length === 0) {
            this.showMessage('No items selected', 'error');
            return;
        }

        this.showLoading(`Updating ${selectedIds.length} items...`);

        let successCount = 0;
        let failCount = 0;

        for (const itemId of selectedIds) {
            try {
                const item = this.inventory.find(i => i.id === itemId);
                if (!item) continue;

                const updatedItem = { ...item, [field]: value };

                const response = await fetch(`/api/items/${itemId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(updatedItem)
                });

                const result = await response.json();

                if (result.success) {
                    successCount++;
                } else {
                    failCount++;
                }
            } catch (error) {
                console.error(`Error updating item ${itemId}:`, error);
                failCount++;
            }
        }

        this.hideLoading();

        if (successCount > 0) {
            this.showMessage(`Updated ${successCount} item(s)`, 'success');
            await this.loadInventory();
            this.closeBulkEditMenu();
        }

        if (failCount > 0) {
            this.showMessage(`Failed to update ${failCount} item(s)`, 'error');
        }
    }

    showBulkEditMenu() {
        const menu = document.getElementById('bulk-edit-menu');
        if (menu) {
            menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
        }
    }

    closeBulkEditMenu() {
        const menu = document.getElementById('bulk-edit-menu');
        if (menu) {
            menu.style.display = 'none';
        }
    }

    async applyBulkCategory() {
        const category = document.getElementById('bulk-category-select')?.value;
        if (!category) {
            this.showMessage('Please select a category', 'error');
            return;
        }
        await this.bulkEdit('category', category);
    }

    async applyBulkDestination() {
        const destination = document.getElementById('bulk-destination-select')?.value;
        if (!destination) {
            this.showMessage('Please select a destination', 'error');
            return;
        }
        await this.bulkEdit('destination', destination);
    }

    async applyBulkAssign() {
        const assignTo = document.getElementById('bulk-assign-select')?.value;
        if (!assignTo) {
            this.showMessage('Please select a family member', 'error');
            return;
        }
        await this.bulkEdit('assignedTo', assignTo);
    }

    /**
     * Search and Filter Functions
     */

    filterInventory() {
        if (!this.inventory || this.inventory.length === 0) {
            return;
        }

        // Get filter values
        const searchQuery = document.getElementById('search-input')?.value.toLowerCase() || '';
        const categoryFilter = document.getElementById('category-filter')?.value || '';
        const forSaleFilter = document.getElementById('for-sale-filter')?.value || '';
        const minValue = parseFloat(document.getElementById('min-value')?.value) || 0;
        const maxValue = parseFloat(document.getElementById('max-value')?.value) || Infinity;
        const sortFilter = document.getElementById('sort-filter')?.value || 'name';

        // Filter items
        let filtered = this.inventory.filter(item => {
            // Search filter (name or description)
            const matchesSearch = !searchQuery ||
                (item.name && item.name.toLowerCase().includes(searchQuery)) ||
                (item.description && item.description.toLowerCase().includes(searchQuery)) ||
                (item.category && item.category.toLowerCase().includes(searchQuery));

            // Category filter
            const matchesCategory = !categoryFilter || item.category === categoryFilter;

            // Destination filter (with backward compat for legacy forSale/assignedTo)
            const matchesForSale = !forSaleFilter || (() => {
                if (item.destination) return item.destination === forSaleFilter;
                if (forSaleFilter === 'sell') return !!item.forSale;
                if (forSaleFilter === 'family') return !!item.assignedTo;
                if (forSaleFilter === 'keep') return !item.forSale && !item.assignedTo;
                return false;
            })();

            // Value range filter
            const itemValue = parseFloat(item.estimatedValue) || 0;
            const matchesValue = itemValue >= minValue && itemValue <= maxValue;

            return matchesSearch && matchesCategory && matchesForSale && matchesValue;
        });

        // Sort items
        filtered = this.sortItems(filtered, sortFilter);

        // Update display with filtered items
        this.displayFilteredInventory(filtered);
    }

    sortItems(items, sortBy) {
        const sorted = [...items];

        switch(sortBy) {
            case 'name':
                sorted.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
                break;
            case 'value-high':
                sorted.sort((a, b) => (b.estimatedValue || 0) - (a.estimatedValue || 0));
                break;
            case 'value-low':
                sorted.sort((a, b) => (a.estimatedValue || 0) - (b.estimatedValue || 0));
                break;
            case 'date-new':
                sorted.sort((a, b) => new Date(b.dateAdded || 0) - new Date(a.dateAdded || 0));
                break;
            case 'date-old':
                sorted.sort((a, b) => new Date(a.dateAdded || 0) - new Date(b.dateAdded || 0));
                break;
        }

        return sorted;
    }

    displayFilteredInventory(items) {
        const grid = document.getElementById('inventory-grid');
        const empty = document.getElementById('inventory-empty');

        if (!grid) return;

        if (items.length === 0) {
            grid.style.display = 'none';
            if (empty) {
                empty.style.display = 'block';
                empty.querySelector('h3').textContent = 'No items match your filters';
                empty.querySelector('p').textContent = 'Try adjusting your search or filter criteria';
            }
            return;
        }

        if (empty) empty.style.display = 'none';
        grid.style.display = 'grid';

        const htmlContent = items.map(item => `
            <div class="inventory-item" data-item-id="${item.id}">
                <div class="item-checkbox">
                    <input type="checkbox" class="item-select-checkbox" data-item-id="${item.id}" onchange="app.updateBulkActions()">
                </div>
                <div class="item-image">
                    ${item.photo ? `<img src="${item.photo}" alt="${item.name}">` : '<i class="fas fa-image"></i>'}
                </div>
                <div class="item-info">
                    <h4>${item.name || 'Unnamed Item'}</h4>
                    <p class="item-category">${item.category || 'Uncategorized'}</p>
                    <p class="item-description">${item.description || 'No description'}</p>
                    <p class="item-value item-value-editable" onclick="app.quickEditValue('${item.id}', ${item.estimatedValue || 0})" title="Click to edit value">$${(item.estimatedValue || 0).toLocaleString()} <i class="fas fa-pencil-alt item-value-edit-icon"></i></p>
                    ${this.getDestinationBadgeHTML(item)}
                    ${this.getListingBadgeHTML(item)}
                    ${item.familyHistory ? '<span class="family-history-indicator"><i class="fas fa-heart"></i> Story</span>' : ''}
                    <div class="item-actions">
                        <button class="edit-btn" onclick="app.editItem('${item.id}')">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button class="pricing-btn" onclick="app.lookupItemPricing('${item.id}')">
                            <i class="fas fa-search-dollar"></i> Price
                        </button>
                        <button class="sell-btn" onclick="app.openListingAssistant('${item.id}')" title="Sell on Facebook Marketplace, eBay, or Craigslist">
                            <i class="fas fa-store"></i> Sell
                        </button>
                        <button class="disposal-btn" onclick="app.showDisposalModal('${item.id}')" title="Mark as disposed">
                            <i class="fas fa-trash-alt"></i> Dispose
                        </button>
                        <button class="delete-btn" onclick="app.deleteItem('${item.id}')">
                            <i class="fas fa-trash"></i> Delete
                        </button>
                    </div>
                </div>
            </div>
        `).join('');

        grid.innerHTML = htmlContent;
        this.updateBulkActions();
    }

    clearFilters() {
        // Clear all filter inputs
        const searchInput = document.getElementById('search-input');
        const categoryFilter = document.getElementById('category-filter');
        const forSaleFilter = document.getElementById('for-sale-filter');
        const minValue = document.getElementById('min-value');
        const maxValue = document.getElementById('max-value');
        const sortFilter = document.getElementById('sort-filter');

        if (searchInput) searchInput.value = '';
        if (categoryFilter) categoryFilter.value = '';
        if (forSaleFilter) forSaleFilter.value = '';
        if (minValue) minValue.value = '';
        if (maxValue) maxValue.value = '';
        if (sortFilter) sortFilter.value = 'name';

        // Reload full inventory
        this.updateInventoryDisplay();
        this.showMessage('Filters cleared', 'info');
    }
}

// Global functions for modal handling
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
        modal.style.visibility = 'visible';
        modal.style.pointerEvents = 'auto';

        // Reset auth flow to email step when opening auth modal
        if (modalId === 'auth-modal') {
            showAuthStep('email');
            // Clear any previous input
            const emailInput = document.getElementById('auth-email');
            if (emailInput) {
                emailInput.value = '';
                setTimeout(() => emailInput.focus(), 100);
            }
        }
    }
}

function closeModal(modalId) {
    if (window.app) {
        window.app.closeModal(modalId);
    }
}

// Global authentication functions
// Progressive Authentication Flow State
const authState = {
    email: '',
    currentStep: 'email',
    mfaRequired: false,
    mfaSecret: '',
    sessionId: ''
};

// Navigate between auth steps
function showAuthStep(stepName) {
    const steps = document.querySelectorAll('.auth-step');
    steps.forEach(step => step.classList.remove('active'));
    
    const targetStep = document.getElementById(`auth-step-${stepName}`);
    if (targetStep) {
        targetStep.classList.add('active');
        authState.currentStep = stepName;
        
        // Focus first input in the step
        setTimeout(() => {
            const firstInput = targetStep.querySelector('input');
            if (firstInput) firstInput.focus();
        }, 100);
    }
}

function authGoBack() {
    if (authState.currentStep === 'password' || authState.currentStep === 'signup') {
        showAuthStep('email');
        authState.email = '';
    } else if (authState.currentStep === 'mfa' || authState.currentStep === 'mfa-setup') {
        showAuthStep('password');
    }
}

// Email check handler
async function handleEmailCheck(event) {
    event.preventDefault();
    const email = document.getElementById('auth-email').value;
    
    if (!email) return;
    
    authState.email = email;
    
    try {
        // Check if user exists
        const response = await fetch('/api/auth/check-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        
        const data = await response.json();
        
        if (data.exists) {
            // Existing user - show password step
            document.getElementById('auth-user-email').textContent = email;
            showAuthStep('password');
        } else {
            // New user - show signup step
            document.getElementById('auth-signup-email').textContent = email;
            showAuthStep('signup');
        }
    } catch (error) {
        console.error('Email check error:', error);
        // On error, assume new user
        document.getElementById('auth-signup-email').textContent = email;
        showAuthStep('signup');
    }
}

// Password login handler
async function handlePasswordLogin(event) {
    event.preventDefault();
    const password = document.getElementById('auth-password').value;
    const rememberMe = document.getElementById('remember-me').checked;
    
    if (!authState.email || !password) return;
    
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                email: authState.email, 
                password,
                remember_me: rememberMe
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (data.mfa_required) {
                // Show MFA verification
                authState.mfaRequired = true;
                authState.sessionId = data.session_id;
                showAuthStep('mfa');
            } else {
                // Login complete
                app.currentUser = data.user;
                app.updateAuthUI(true);
                closeModal('auth-modal');
                app.showMessage('Welcome back!', 'success');
            }
        } else {
            app.showMessage(data.error || 'Invalid password', 'error');
        }
    } catch (error) {
        console.error('Login error:', error);
        app.showMessage('Login failed. Please try again.', 'error');
    }
}

// Signup handler
async function handleSignup(event) {
    event.preventDefault();
    const name = document.getElementById('signup-name').value;
    const password = document.getElementById('signup-password').value;
    const confirmPassword = document.getElementById('signup-password-confirm').value;
    const enableMfa = document.getElementById('enable-mfa').checked;
    const betaCode = document.getElementById('signup-beta-code')?.value?.trim().toUpperCase() || '';

    if (!authState.email || !name || !password) return;

    if (password !== confirmPassword) {
        app.showMessage('Passwords do not match', 'error');
        return;
    }

    if (password.length < 8) {
        app.showMessage('Password must be at least 8 characters', 'error');
        return;
    }

    try {
        const response = await fetch('/api/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                email: authState.email,
                password,
                enable_mfa: enableMfa,
                beta_code: betaCode
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (enableMfa && data.mfa_secret) {
                // Show MFA setup
                authState.mfaSecret = data.mfa_secret;
                authState.sessionId = data.session_id;
                setupMfaDisplay(data.mfa_secret, authState.email);
                showAuthStep('mfa-setup');
            } else {
                // Signup complete without MFA
                app.currentUser = data.user;
                app.updateAuthUI(true);
                closeModal('auth-modal');
                app.showMessage('Account created successfully!', 'success');
            }
        } else {
            app.showMessage(data.error || 'Signup failed', 'error');
        }
    } catch (error) {
        console.error('Signup error:', error);
        app.showMessage('Signup failed. Please try again.', 'error');
    }
}

// MFA digit input handlers
function setupMfaDigitInputs() {
    const mfaForms = ['mfa-form', 'mfa-setup-verify-form'];
    
    mfaForms.forEach(formId => {
        const form = document.getElementById(formId);
        if (!form) return;
        
        const digits = form.querySelectorAll('.mfa-digit');
        
        digits.forEach((digit, index) => {
            // Handle input
            digit.addEventListener('input', (e) => {
                const value = e.target.value;
                
                if (value && index < digits.length - 1) {
                    digits[index + 1].focus();
                }
                
                // Auto-submit when all filled
                const code = Array.from(digits).map(d => d.value).join('');
                if (code.length === 6) {
                    if (formId === 'mfa-form') {
                        handleMfaVerification(new Event('submit'));
                    } else {
                        handleMfaSetupVerify(new Event('submit'));
                    }
                }
            });
            
            // Handle backspace
            digit.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !e.target.value && index > 0) {
                    digits[index - 1].focus();
                }
            });
            
            // Handle paste
            digit.addEventListener('paste', (e) => {
                e.preventDefault();
                const pastedData = e.clipboardData.getData('text').replace(/\D/g, '');
                
                for (let i = 0; i < Math.min(pastedData.length, 6); i++) {
                    if (digits[i]) {
                        digits[i].value = pastedData[i];
                    }
                }
                
                if (pastedData.length === 6) {
                    if (formId === 'mfa-form') {
                        handleMfaVerification(new Event('submit'));
                    } else {
                        handleMfaSetupVerify(new Event('submit'));
                    }
                }
            });
        });
    });
}

// MFA verification handler
async function handleMfaVerification(event) {
    event.preventDefault();
    const digits = document.querySelectorAll('#mfa-form .mfa-digit');
    const code = Array.from(digits).map(d => d.value).join('');
    const trustDevice = document.getElementById('trust-device').checked;
    
    if (code.length !== 6) {
        app.showMessage('Please enter all 6 digits', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/auth/verify-mfa', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                code,
                session_id: authState.sessionId,
                trust_device: trustDevice
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            app.currentUser = data.user;
            app.updateAuthUI(true);
            closeModal('auth-modal');
            app.showMessage('Successfully authenticated!', 'success');
        } else {
            app.showMessage(data.error || 'Invalid code', 'error');
            // Clear digits
            digits.forEach(d => d.value = '');
            digits[0].focus();
        }
    } catch (error) {
        console.error('MFA verification error:', error);
        app.showMessage('Verification failed. Please try again.', 'error');
    }
}

// MFA setup display
function setupMfaDisplay(secret, email) {
    const qrCodeContainer = document.getElementById('mfa-qr-code');
    const secretCodeEl = document.getElementById('mfa-secret-code');

    // Format secret for display
    const formattedSecret = secret.match(/.{1,4}/g).join(' ');
    secretCodeEl.textContent = formattedSecret;

    // Generate QR code
    const otpauthUrl = `otpauth://totp/MyEstateAlly:${encodeURIComponent(email)}?secret=${secret}&issuer=MyEstateAlly`;

    // Clear container and create QR code
    qrCodeContainer.innerHTML = '';

    // Check if QRCode library is available
    if (typeof QRCode !== 'undefined') {
        try {
            new QRCode(qrCodeContainer, {
                text: otpauthUrl,
                width: 200,
                height: 200,
                colorDark: "#000000",
                colorLight: "#ffffff",
                correctLevel: QRCode.CorrectLevel.H
            });
        } catch (error) {
            console.error('QR code generation error:', error);
            showQRCodeFallback(qrCodeContainer, otpauthUrl);
        }
    } else {
        // Fallback: Use Google Charts API to generate QR code
        showQRCodeFallback(qrCodeContainer, otpauthUrl);
    }
}

function showQRCodeFallback(container, otpauthUrl) {
    // Use Google Charts API as fallback
    const qrUrl = `https://chart.googleapis.com/chart?chs=200x200&cht=qr&chl=${encodeURIComponent(otpauthUrl)}&choe=UTF-8`;
    container.innerHTML = `
        <img src="${qrUrl}" alt="MFA QR Code" style="width: 200px; height: 200px; border: 2px solid #e5e7eb; border-radius: 8px;">
    `;
}

// MFA setup verification handler
async function handleMfaSetupVerify(event) {
    event.preventDefault();
    const digits = document.querySelectorAll('#mfa-setup-verify-form .mfa-digit');
    const code = Array.from(digits).map(d => d.value).join('');
    
    if (code.length !== 6) {
        app.showMessage('Please enter all 6 digits', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/auth/verify-mfa-setup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                code,
                secret: authState.mfaSecret,
                session_id: authState.sessionId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            app.currentUser = data.user;
            app.updateAuthUI(true);
            closeModal('auth-modal');
            app.showMessage('Two-factor authentication enabled!', 'success');
        } else {
            app.showMessage(data.error || 'Invalid code', 'error');
            digits.forEach(d => d.value = '');
            digits[0].focus();
        }
    } catch (error) {
        console.error('MFA setup verification error:', error);
        app.showMessage('Verification failed. Please try again.', 'error');
    }
}

function skipMfaSetup() {
    // Complete signup without MFA
    closeModal('auth-modal');
    app.showMessage('Account created! You can enable 2FA later in settings.', 'success');
    app.loadInventory();
}

function resendMfaCode() {
    app.showMessage('Code resent! Check your authenticator app.', 'info');
}

function showForgotPassword() {
    // Pre-fill email from the auth flow if available
    const emailFromAuth = document.getElementById('auth-email-input');
    if (emailFromAuth && emailFromAuth.value) {
        const forgotEmail = document.getElementById('forgot-email');
        if (forgotEmail) forgotEmail.value = emailFromAuth.value;
    }
    showAuthStep('forgot');
}

async function submitForgotPassword(event) {
    event.preventDefault();
    const email = document.getElementById('forgot-email').value.trim();
    const btn = document.getElementById('forgot-submit-btn');
    const successMsg = document.getElementById('forgot-success-msg');
    const form = document.getElementById('forgot-password-form');

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';

    try {
        const resp = await fetch('/api/auth/forgot-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        // Always show success (backend never reveals if email exists)
        form.style.display = 'none';
        successMsg.style.display = 'flex';
    } catch (err) {
        // Still show success to prevent enumeration
        form.style.display = 'none';
        successMsg.style.display = 'flex';
    }
}

async function submitResetPassword(event) {
    event.preventDefault();
    const newPassword = document.getElementById('reset-new-password').value;
    const confirmPassword = document.getElementById('reset-confirm-password').value;
    const errorDiv = document.getElementById('reset-error-msg');
    const btn = document.getElementById('reset-submit-btn');

    // Client-side validation
    errorDiv.style.display = 'none';
    if (newPassword !== confirmPassword) {
        errorDiv.textContent = 'Passwords do not match.';
        errorDiv.style.display = 'block';
        return;
    }
    if (newPassword.length < 12) {
        errorDiv.textContent = 'Password must be at least 12 characters.';
        errorDiv.style.display = 'block';
        return;
    }

    const token = new URLSearchParams(window.location.search).get('token');
    if (!token) {
        errorDiv.textContent = 'Reset token missing. Please use the link from your email.';
        errorDiv.style.display = 'block';
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Resetting...';

    try {
        const resp = await fetch('/api/auth/reset-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, new_password: newPassword })
        });
        const data = await resp.json();

        if (data.success) {
            // Show success state, hide form
            document.getElementById('reset-form-view').style.display = 'none';
            document.getElementById('reset-success-view').style.display = 'block';
            // Clean token from URL without reload
            window.history.replaceState({}, document.title, '/');
        } else {
            errorDiv.textContent = data.error || 'Reset failed. Please try again.';
            errorDiv.style.display = 'block';
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-check"></i> Reset Password';
        }
    } catch (err) {
        errorDiv.textContent = 'Connection error. Please try again.';
        errorDiv.style.display = 'block';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-check"></i> Reset Password';
    }
}

// Legacy function for compatibility
function switchAuthTab(tab) {
    // Now handled by progressive flow
    showAuthStep(tab === 'login' ? 'password' : 'signup');
}

function loginWithGoogle() {
    console.log('loginWithGoogle() called, window.app exists:', !!window.app);
    if (window.app) {
        window.app.loginWithGoogle();
    } else {
        console.error('App not initialized yet. Trying direct redirect...');
        // Fallback: direct redirect if app not initialized
        window.location.href = '/auth/google/login';
    }
}

function loginWithFacebook() {
    console.log('loginWithFacebook() called, window.app exists:', !!window.app);
    if (window.app) {
        window.app.loginWithFacebook();
    } else {
        console.error('App not initialized yet. Trying direct redirect...');
        // Fallback: direct redirect if app not initialized
        window.location.href = '/auth/facebook/login';
    }
}

function logout() {
    if (window.app) {
        window.app.logout();
    }
}

function showUserProfile() {
    if (window.app) {
        window.app.showUserProfile();
    }
}

function showAccountSettings() {
    if (window.app) {
        window.app.showAccountSettings();
    }
}

// ============================================================================
// USER PROFILE & ACCOUNT SETTINGS METHODS
// ============================================================================

MyEstateAllyApp.prototype.showUserProfile = async function() {
    try {
        const response = await fetch('/api/user/profile');
        const data = await response.json();

        if (data.success && data.user) {
            const user = data.user;

            document.getElementById('profile-name').value = user.name || '';
            document.getElementById('profile-email').value = user.email || '';

            const providerMap = {
                'email': 'Email/Password',
                'google': 'Google OAuth',
                'facebook': 'Facebook',
                'demo': 'Demo Account'
            };
            document.getElementById('profile-provider').value = providerMap[user.provider] || user.provider;

            const accountTypeMap = {
                'free': 'Free',
                'premium': 'Premium',
                'beta': 'Beta Tester'
            };
            let accountType = accountTypeMap[user.account_type] || 'Free';
            if (user.grandfathered) {
                accountType += ' (Grandfathered)';
            }
            document.getElementById('profile-account-type').value = accountType;

            if (user.created_at) {
                const date = new Date(user.created_at);
                document.getElementById('profile-created').value = date.toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                });
            }

            this.openModal('user-profile-modal');
        } else {
            this.showMessage(data.error || 'Failed to load profile', 'error');
        }
    } catch (error) {
        console.error('Error loading profile:', error);
        this.showMessage('Failed to load profile', 'error');
    }
};

MyEstateAllyApp.prototype.saveUserProfile = async function(event) {
    event.preventDefault();

    const name = document.getElementById('profile-name').value.trim();

    if (!name || name.length < 2) {
        this.showMessage('Name must be at least 2 characters', 'error');
        return;
    }

    try {
        const response = await fetch('/api/user/profile', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });

        const data = await response.json();

        if (data.success) {
            if (this.currentUser) {
                this.currentUser.name = data.user.name;
            }

            this._updateUserDisplay(data.user);

            this.showMessage('Profile updated successfully!', 'success');
            this.closeModal('user-profile-modal');
        } else {
            this.showMessage(data.error || 'Failed to update profile', 'error');
        }
    } catch (error) {
        console.error('Error saving profile:', error);
        this.showMessage('Failed to update profile', 'error');
    }
};

MyEstateAllyApp.prototype.showAccountSettings = async function() {
    try {
        const response = await fetch('/api/user/profile');
        const data = await response.json();

        if (data.success && data.user) {
            const user = data.user;

            const accountTypeMap = {
                'free': 'Free',
                'premium': 'Premium',
                'beta': 'Beta Tester'
            };
            let accountType = accountTypeMap[user.account_type] || 'Free';
            if (user.grandfathered) {
                accountType += ' (Grandfathered)';
            }
            document.getElementById('settings-account-type').textContent = accountType;

            if (user.created_at) {
                const date = new Date(user.created_at);
                document.getElementById('settings-created-date').textContent = date.toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                });
            }

            document.getElementById('settings-user-id').textContent = user.id;

            const mfaEnabled = user.mfa_enabled || false;
            const mfaStatusText = document.getElementById('mfa-status-text');
            const mfaToggleBtn = document.getElementById('mfa-toggle-btn');

            if (mfaEnabled) {
                mfaStatusText.innerHTML = '<i class="fas fa-check-circle" style="color: var(--success-color);"></i> Enabled';
                mfaToggleBtn.innerHTML = '<i class="fas fa-times"></i> Disable 2FA';
                mfaToggleBtn.className = 'btn danger';
            } else {
                mfaStatusText.innerHTML = '<i class="fas fa-times-circle" style="color: var(--text-muted);"></i> Not enabled';
                mfaToggleBtn.innerHTML = '<i class="fas fa-mobile-alt"></i> Enable 2FA';
                mfaToggleBtn.className = 'btn secondary';
            }

            const passwordContainer = document.getElementById('password-change-container');
            if (user.provider === 'email') {
                passwordContainer.style.display = 'block';
            } else {
                passwordContainer.style.display = 'none';
            }

            const deleteMfaGroup = document.getElementById('delete-mfa-group');
            if (mfaEnabled) {
                deleteMfaGroup.style.display = 'block';
                document.getElementById('delete-mfa-code').required = true;
            } else {
                deleteMfaGroup.style.display = 'none';
                document.getElementById('delete-mfa-code').required = false;
            }

            const deletePasswordGroup = document.getElementById('delete-password-group');
            if (user.provider === 'email') {
                deletePasswordGroup.style.display = 'block';
                document.getElementById('delete-password').required = true;
            } else {
                deletePasswordGroup.style.display = 'none';
                document.getElementById('delete-password').required = false;
            }

            this.openModal('account-settings-modal');
        } else {
            this.showMessage(data.error || 'Failed to load settings', 'error');
        }
    } catch (error) {
        console.error('Error loading settings:', error);
        this.showMessage('Failed to load settings', 'error');
    }
};

MyEstateAllyApp.prototype.showChangePassword = function() {
    document.getElementById('password-change-form-container').style.display = 'block';
    document.getElementById('password-change-form-container').scrollIntoView({ behavior: 'smooth' });
};

MyEstateAllyApp.prototype.hideChangePassword = function() {
    document.getElementById('password-change-form-container').style.display = 'none';
    document.getElementById('change-password-form').reset();
};

MyEstateAllyApp.prototype.changePassword = async function(event) {
    event.preventDefault();

    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-new-password').value;

    if (newPassword !== confirmPassword) {
        this.showMessage('New passwords do not match', 'error');
        return;
    }

    if (newPassword.length < 8) {
        this.showMessage('Password must be at least 8 characters', 'error');
        return;
    }

    try {
        const response = await fetch('/api/user/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });

        const data = await response.json();

        if (data.success) {
            this.showMessage('Password changed successfully!', 'success');
            this.hideChangePassword();
            document.getElementById('change-password-form').reset();
        } else {
            this.showMessage(data.error || 'Failed to change password', 'error');
        }
    } catch (error) {
        console.error('Error changing password:', error);
        this.showMessage('Failed to change password', 'error');
    }
};

MyEstateAllyApp.prototype.toggleMFA = async function() {
    try {
        const profileResponse = await fetch('/api/user/profile');
        const profileData = await profileResponse.json();

        if (!profileData.success) {
            this.showMessage('Failed to check MFA status', 'error');
            return;
        }

        const mfaEnabled = profileData.user.mfa_enabled || false;

        if (mfaEnabled) {
            this.disableMFA();
        } else {
            this.setupMFA();
        }
    } catch (error) {
        console.error('Error toggling MFA:', error);
        this.showMessage('Failed to toggle MFA', 'error');
    }
};

MyEstateAllyApp.prototype.setupMFA = async function() {
    try {
        const response = await fetch('/api/user/toggle-mfa', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'enable' })
        });

        const data = await response.json();

        if (data.success && data.action === 'setup') {
            this.mfaSetupData = {
                secret: data.mfa_secret
            };

            const qrCodeDiv = document.getElementById('mfa-qr-code');
            qrCodeDiv.innerHTML = `<img src="${data.qr_code}" alt="MFA QR Code" style="max-width: 250px;">`;

            document.getElementById('mfa-secret-display').textContent = data.mfa_secret;

            this.openModal('mfa-setup-modal');
        } else {
            this.showMessage(data.error || 'Failed to setup MFA', 'error');
        }
    } catch (error) {
        console.error('Error setting up MFA:', error);
        this.showMessage('Failed to setup MFA', 'error');
    }
};

MyEstateAllyApp.prototype.verifyMFASetup = async function(event) {
    event.preventDefault();

    const code = document.getElementById('mfa-verification-code').value;

    if (!this.mfaSetupData || !this.mfaSetupData.secret) {
        this.showMessage('MFA setup data not found', 'error');
        return;
    }

    try {
        const response = await fetch('/api/user/toggle-mfa', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action: 'verify_enable',
                mfa_secret: this.mfaSetupData.secret,
                code: code
            })
        });

        const data = await response.json();

        if (data.success) {
            this.showMessage('Two-factor authentication enabled successfully!', 'success');
            this.closeModal('mfa-setup-modal');
            this.closeModal('account-settings-modal');
            delete this.mfaSetupData;
        } else {
            this.showMessage(data.error || 'Invalid verification code', 'error');
        }
    } catch (error) {
        console.error('Error verifying MFA:', error);
        this.showMessage('Failed to verify MFA code', 'error');
    }
};

MyEstateAllyApp.prototype.cancelMFASetup = function() {
    delete this.mfaSetupData;
    this.closeModal('mfa-setup-modal');
    document.getElementById('mfa-verify-form').reset();
};

MyEstateAllyApp.prototype.copyMFASecret = function() {
    const secretText = document.getElementById('mfa-secret-display').textContent;
    navigator.clipboard.writeText(secretText).then(() => {
        this.showMessage('Secret copied to clipboard!', 'success');
    }).catch(() => {
        this.showMessage('Failed to copy secret', 'error');
    });
};

MyEstateAllyApp.prototype.disableMFA = async function() {
    const confirmed = confirm('Are you sure you want to disable two-factor authentication? This will make your account less secure.');

    if (!confirmed) return;

    const verification = prompt('Enter your password or current 2FA code to confirm:');

    if (!verification) return;

    try {
        const isMFACode = /^\d{6}$/.test(verification);

        const payload = {
            action: 'disable'
        };

        if (isMFACode) {
            payload.code = verification;
        } else {
            payload.password = verification;
        }

        const response = await fetch('/api/user/toggle-mfa', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (data.success) {
            this.showMessage('Two-factor authentication disabled', 'success');
            this.closeModal('account-settings-modal');
        } else {
            this.showMessage(data.error || 'Failed to disable MFA', 'error');
        }
    } catch (error) {
        console.error('Error disabling MFA:', error);
        this.showMessage('Failed to disable MFA', 'error');
    }
};

MyEstateAllyApp.prototype.exportAccountData = async function() {
    try {
        this.showMessage('Preparing your data export...', 'info');

        const response = await fetch('/api/user/export-data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.success) {
            const blob = new Blob([data.data], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = data.filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            this.showMessage('Data exported successfully!', 'success');
        } else {
            this.showMessage(data.error || 'Failed to export data', 'error');
        }
    } catch (error) {
        console.error('Error exporting data:', error);
        this.showMessage('Failed to export data', 'error');
    }
};

MyEstateAllyApp.prototype.confirmDeleteAccount = function() {
    this.openModal('delete-account-modal');
    document.getElementById('delete-account-form').reset();
};

MyEstateAllyApp.prototype.deleteAccount = async function(event) {
    event.preventDefault();

    const password = document.getElementById('delete-password').value;
    const mfaCode = document.getElementById('delete-mfa-code').value;
    const confirmation = document.getElementById('delete-confirmation').value;

    if (confirmation.toUpperCase() !== 'DELETE MY ACCOUNT') {
        this.showMessage('Please type "DELETE MY ACCOUNT" exactly to confirm', 'error');
        return;
    }

    const finalConfirm = confirm('This is your last chance. Are you absolutely sure you want to permanently delete your account? This cannot be undone.');

    if (!finalConfirm) return;

    try {
        const response = await fetch('/api/user/account', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                password: password,
                mfa_code: mfaCode,
                confirmation: confirmation
            })
        });

        const data = await response.json();

        if (data.success) {
            this.showMessage('Account deleted successfully. Goodbye.', 'success');

            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
        } else {
            this.showMessage(data.error || 'Failed to delete account', 'error');
        }
    } catch (error) {
        console.error('Error deleting account:', error);
        this.showMessage('Failed to delete account', 'error');
    }
};

// ============================================================================
// DOCUMENT MANAGEMENT METHODS
// ============================================================================

MyEstateAllyApp.prototype.loadDocuments = async function() {
    // Guard: Skip if not authenticated
    if (!this.currentUser) {
        console.log('Skipping documents load - user not authenticated');
        return;
    }

    try {
        const response = await fetch('/api/documents');
        const data = await response.json();

        if (data.success) {
            this.documents = data.documents;
            this.displayDocuments();
        } else {
            // Silently handle "no estate selected" error (happens during initial load)
            if (data.error !== 'No estate selected') {
                console.error('Failed to load documents:', data.error);
            }
        }
    } catch (error) {
        console.error('Error loading documents:', error);
    }
};

MyEstateAllyApp.prototype.displayDocuments = function() {
    const container = document.getElementById('documents-list');
    if (!container) return;

    if (this.documents.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-folder-open"></i>
                <p>No documents yet</p>
                <p class="empty-state-subtitle">Upload legal documents, receipts, appraisals, and more</p>
                <button class="btn primary" onclick="app.showUploadDocumentModal()">
                    <i class="fas fa-upload"></i> Upload First Document
                </button>
            </div>
        `;
        return;
    }

    const htmlContent = this.documents.map(doc => {
        const uploadDate = new Date(doc.uploaded_at).toLocaleDateString();
        const fileSize = this.formatFileSize(doc.file_size);
        const icon = this.getDocumentIcon(doc.content_type);

        return `
            <div class="document-item" data-doc-id="${doc.id}">
                <div class="document-icon">
                    <i class="${icon}"></i>
                </div>
                <div class="document-info">
                    <h4>${doc.filename}</h4>
                    <div class="document-meta">
                        <span class="document-category">
                            <i class="fas fa-tag"></i> ${doc.category}
                        </span>
                        <span class="document-size">
                            <i class="fas fa-file"></i> ${fileSize}
                        </span>
                        <span class="document-date">
                            <i class="fas fa-calendar"></i> ${uploadDate}
                        </span>
                    </div>
                    ${doc.description ? `<p class="document-description">${doc.description}</p>` : ''}
                </div>
                <div class="document-actions">
                    <button class="btn-icon" onclick="app.previewDocument('${doc.id}')" title="Preview">
                        <i class="fas fa-eye"></i><span>Preview</span>
                    </button>
                    <button class="btn-icon" onclick="app.downloadDocument('${doc.id}')" title="Download">
                        <i class="fas fa-download"></i><span>Download</span>
                    </button>
                    <button class="btn-icon danger" onclick="app.deleteDocument('${doc.id}')" title="Delete">
                        <i class="fas fa-trash"></i><span>Delete</span>
                    </button>
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = htmlContent;
};

MyEstateAllyApp.prototype.filterDocuments = function() {
    const categoryFilter = document.getElementById('document-category-filter')?.value || '';
    const searchQuery = document.getElementById('document-search')?.value.toLowerCase() || '';

    let filtered = this.documents.filter(doc => {
        const matchesCategory = !categoryFilter || doc.category === categoryFilter;
        const matchesSearch = !searchQuery ||
            doc.filename.toLowerCase().includes(searchQuery) ||
            (doc.description && doc.description.toLowerCase().includes(searchQuery));

        return matchesCategory && matchesSearch;
    });

    // Temporarily store filtered documents
    const originalDocs = this.documents;
    this.documents = filtered;
    this.displayDocuments();
    this.documents = originalDocs;
};

MyEstateAllyApp.prototype.showUploadDocumentModal = function() {
    const modal = document.getElementById('upload-document-modal');
    if (modal) {
        modal.style.display = 'flex';
        // Reset form
        document.getElementById('upload-document-form')?.reset();
    }
};

MyEstateAllyApp.prototype.uploadDocument = async function(event) {
    event.preventDefault();

    const form = event.target;
    const formData = new FormData(form);

    // Show loading
    this.showLoading('Uploading document...');

    try {
        const response = await fetch('/api/documents/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            this.showMessage('Document uploaded successfully!', 'success');
            this.closeModal('upload-document-modal');
            await this.loadDocuments();
        } else {
            this.showMessage(data.error || 'Failed to upload document', 'error');
        }
    } catch (error) {
        console.error('Error uploading document:', error);
        this.showMessage('Failed to upload document. Please try again.', 'error');
    } finally {
        this.hideLoading();
    }
};

MyEstateAllyApp.prototype.downloadDocument = async function(docId) {
    try {
        this.showLoading('Downloading document...');

        const response = await fetch(`/api/documents/${docId}`);

        if (!response.ok) {
            const data = await response.json();
            this.showMessage(data.error || 'Failed to download document', 'error');
            return;
        }

        // Get filename from Content-Disposition header
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'document';

        if (contentDisposition) {
            const matches = /filename="([^"]+)"/.exec(contentDisposition);
            if (matches && matches[1]) {
                filename = matches[1];
            }
        }

        // Download the file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        this.showMessage('Document downloaded successfully!', 'success');
    } catch (error) {
        console.error('Error downloading document:', error);
        this.showMessage('Failed to download document', 'error');
    } finally {
        this.hideLoading();
    }
};

MyEstateAllyApp.prototype.previewDocument = function(docId) {
    // Find document in current documents list
    const doc = this.documents.find(d => d.id === docId);
    if (!doc) {
        this.showMessage('Document not found', 'error');
        return;
    }

    // Store current document ID for download fallback
    this.currentPreviewDocId = docId;

    // Show modal and loading state
    document.getElementById('preview-document-modal').style.display = 'flex';
    document.getElementById('preview-loading').style.display = 'flex';
    document.getElementById('preview-error').style.display = 'none';
    document.getElementById('preview-iframe').style.display = 'none';
    document.getElementById('preview-image').style.display = 'none';

    // Update modal title
    document.getElementById('preview-document-title').innerHTML =
        `<i class="fas fa-eye"></i> ${doc.filename}`;

    // Set up download button
    const downloadBtn = document.getElementById('preview-download-btn');
    downloadBtn.onclick = () => this.downloadDocument(docId);

    // Set up fallback download button
    const fallbackBtn = document.getElementById('preview-download-fallback');
    fallbackBtn.onclick = () => {
        this.closePreviewModal();
        this.downloadDocument(docId);
    };

    // Determine file type and preview accordingly
    const extension = doc.filename.split('.').pop().toLowerCase();

    if (extension === 'pdf') {
        this.previewPDF(docId, doc.filename);
    } else if (['jpg', 'jpeg', 'png', 'gif'].includes(extension)) {
        this.previewImage(docId, doc.filename);
    } else {
        // Unsupported file type
        this.showPreviewError(
            `Preview not available for ${extension.toUpperCase()} files. Please download to view.`,
            true
        );
    }
};

MyEstateAllyApp.prototype.previewPDF = function(docId, filename) {
    const iframe = document.getElementById('preview-iframe');
    const loading = document.getElementById('preview-loading');

    // Set iframe source
    iframe.src = `/api/documents/${docId}/preview`;

    // Handle iframe load
    iframe.onload = () => {
        loading.style.display = 'none';
        iframe.style.display = 'block';
    };

    // Handle iframe error
    iframe.onerror = () => {
        this.showPreviewError('Failed to load PDF preview. Try downloading instead.', true);
    };

    // Timeout after 30 seconds
    setTimeout(() => {
        if (loading.style.display !== 'none') {
            this.showPreviewError('Preview timed out. Try downloading instead.', true);
        }
    }, 30000);
};

MyEstateAllyApp.prototype.previewImage = function(docId, filename) {
    const img = document.getElementById('preview-image');
    const loading = document.getElementById('preview-loading');

    // Set image source
    img.src = `/api/documents/${docId}/preview`;

    // Handle image load
    img.onload = () => {
        loading.style.display = 'none';
        img.style.display = 'block';
    };

    // Handle image error
    img.onerror = () => {
        this.showPreviewError('Failed to load image preview. Try downloading instead.', true);
    };

    // Timeout after 30 seconds
    setTimeout(() => {
        if (loading.style.display !== 'none') {
            this.showPreviewError('Preview timed out. Try downloading instead.', true);
        }
    }, 30000);
};

MyEstateAllyApp.prototype.showPreviewError = function(message, showDownload = false) {
    document.getElementById('preview-loading').style.display = 'none';
    document.getElementById('preview-iframe').style.display = 'none';
    document.getElementById('preview-image').style.display = 'none';
    document.getElementById('preview-error').style.display = 'flex';
    document.getElementById('preview-error-message').textContent = message;

    const fallbackBtn = document.getElementById('preview-download-fallback');
    fallbackBtn.style.display = showDownload ? 'inline-block' : 'none';
};

MyEstateAllyApp.prototype.closePreviewModal = function() {
    const modal = document.getElementById('preview-document-modal');
    const iframe = document.getElementById('preview-iframe');
    const img = document.getElementById('preview-image');

    // Clear iframe and image sources to stop loading
    iframe.src = '';
    img.src = '';

    // Hide modal
    modal.style.display = 'none';

    // Reset states
    document.getElementById('preview-loading').style.display = 'flex';
    document.getElementById('preview-error').style.display = 'none';
    iframe.style.display = 'none';
    img.style.display = 'none';

    // Clear current preview doc ID
    this.currentPreviewDocId = null;
};

MyEstateAllyApp.prototype.deleteDocument = async function(docId) {
    if (!confirm('Are you sure you want to delete this document? This action cannot be undone.')) {
        return;
    }

    try {
        this.showLoading('Deleting document...');

        const response = await fetch(`/api/documents/${docId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            this.showMessage('Document deleted successfully!', 'success');
            await this.loadDocuments();
        } else {
            this.showMessage(data.error || 'Failed to delete document', 'error');
        }
    } catch (error) {
        console.error('Error deleting document:', error);
        this.showMessage('Failed to delete document', 'error');
    } finally {
        this.hideLoading();
    }
};

MyEstateAllyApp.prototype.getDocumentIcon = function(contentType) {
    if (contentType.includes('pdf')) return 'fas fa-file-pdf';
    if (contentType.includes('word') || contentType.includes('doc')) return 'fas fa-file-word';
    if (contentType.includes('image')) return 'fas fa-file-image';
    if (contentType.includes('text')) return 'fas fa-file-alt';
    return 'fas fa-file';
};

MyEstateAllyApp.prototype.formatFileSize = function(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
};

// ============================================================================
// EXPORT & PRINT FUNCTIONS
// ============================================================================

MyEstateAllyApp.prototype.toggleExportMenu = function(event) {
    event.stopPropagation();
    const menu = document.getElementById('export-menu');
    menu.style.display = menu.style.display === 'block' ? 'none' : 'block';

    // Close menu when clicking outside
    document.addEventListener('click', function closeMenu(e) {
        if (!menu.contains(e.target)) {
            menu.style.display = 'none';
            document.removeEventListener('click', closeMenu);
        }
    });
};

MyEstateAllyApp.prototype.exportInventoryPDF = async function() {
    try {
        this.showLoading('Generating PDF...');

        const response = await fetch('/api/export/inventory/pdf');

        if (!response.ok) {
            const data = await response.json();
            this.showMessage(data.error || 'Failed to export PDF', 'error');
            return;
        }

        // Download the PDF
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `inventory_${new Date().toISOString().split('T')[0]}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        this.showMessage('PDF exported successfully!', 'success');
    } catch (error) {
        console.error('Error exporting PDF:', error);
        this.showMessage('Failed to export PDF', 'error');
    } finally {
        this.hideLoading();
    }
};

MyEstateAllyApp.prototype.exportInventoryCSV = async function() {
    try {
        this.showLoading('Generating CSV...');

        const response = await fetch('/api/export/inventory/csv');

        if (!response.ok) {
            const data = await response.json();
            this.showMessage(data.error || 'Failed to export CSV', 'error');
            return;
        }

        // Download the CSV
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `inventory_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        this.showMessage('CSV exported successfully!', 'success');
    } catch (error) {
        console.error('Error exporting CSV:', error);
        this.showMessage('Failed to export CSV', 'error');
    } finally {
        this.hideLoading();
    }
};

MyEstateAllyApp.prototype.exportDocumentsCSV = async function() {
    try {
        this.showLoading('Generating documents list...');

        const response = await fetch('/api/export/documents/csv');

        if (!response.ok) {
            const data = await response.json();
            this.showMessage(data.error || 'Failed to export documents', 'error');
            return;
        }

        // Download the CSV
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `documents_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        this.showMessage('Documents list exported!', 'success');
    } catch (error) {
        console.error('Error exporting documents:', error);
        this.showMessage('Failed to export documents', 'error');
    } finally {
        this.hideLoading();
    }
};

MyEstateAllyApp.prototype.printInventory = function() {
    // Create print-friendly version
    const printWindow = window.open('', '_blank');
    const doc = printWindow.document;

    // Calculate total value
    const totalValue = this.inventory.reduce((sum, item) => sum + (item.estimated_value || 0), 0);

    // Build HTML
    doc.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Estate Inventory - ${new Date().toLocaleDateString()}</title>
            <style>
                @media print {
                    @page {
                        margin: 0.5in;
                    }
                }
                body {
                    font-family: Arial, sans-serif;
                    padding: 20px;
                    color: #333;
                }
                h1 {
                    color: #4F46E5;
                    border-bottom: 3px solid #4F46E5;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }
                .summary {
                    background: #f9fafb;
                    padding: 15px;
                    border-radius: 8px;
                    margin-bottom: 30px;
                }
                .summary p {
                    margin: 5px 0;
                    font-size: 14px;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }
                th {
                    background: #4F46E5;
                    color: white;
                    padding: 12px;
                    text-align: left;
                    font-weight: 600;
                }
                td {
                    padding: 10px 12px;
                    border-bottom: 1px solid #e5e7eb;
                }
                tr:nth-child(even) {
                    background: #f9fafb;
                }
                .footer {
                    margin-top: 30px;
                    text-align: center;
                    font-size: 12px;
                    color: #6b7280;
                }
            </style>
        </head>
        <body>
            <h1>Estate Inventory Report</h1>

            <div class="summary">
                <p><strong>Total Items:</strong> ${this.inventory.length}</p>
                <p><strong>Total Value:</strong> $${totalValue.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
                <p><strong>Generated:</strong> ${new Date().toLocaleString()}</p>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Item Name</th>
                        <th>Category</th>
                        <th>Value</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${this.inventory.map(item => `
                        <tr>
                            <td>${item.name || ''}</td>
                            <td>${item.category || ''}</td>
                            <td>$${(item.estimated_value || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                            <td>${(item.status || 'active').charAt(0).toUpperCase() + (item.status || 'active').slice(1)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>

            <div class="footer">
                <p>Generated by MyEstateAlly - AI-Powered Estate Management</p>
            </div>

            <script>
                window.onload = function() {
                    window.print();
                };
            </script>
        </body>
        </html>
    `);

    doc.close();
};

/**
 * Load activity log for current estate
 */
MyEstateAllyApp.prototype.loadActivityLog = async function() {
    try {
        const response = await fetch('/api/activity-log?limit=50');
        const data = await response.json();

        if (data.success) {
            this.displayActivityLog(data.activities);
        } else {
            console.error('Failed to load activity log:', data.error);
        }
    } catch (error) {
        console.error('Error loading activity log:', error);
    }
};

/**
 * Display activity log
 */
MyEstateAllyApp.prototype.displayActivityLog = function(activities) {
    const list = document.getElementById('activity-log-list');

    if (!activities || activities.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-history"></i>
                <p>No activity yet</p>
                <p class="empty-state-subtitle">Changes to your inventory will appear here</p>
            </div>
        `;
        return;
    }

    list.innerHTML = activities.map(activity => {
        const actionIcons = {
            'added': 'fa-plus-circle',
            'updated': 'fa-edit',
            'deleted': 'fa-trash',
            'claimed': 'fa-hand-paper',
            'unclaimed': 'fa-hand-point-left'
        };

        const actionColors = {
            'added': '#10b981',
            'updated': '#3b82f6',
            'deleted': '#ef4444',
            'claimed': '#f59e0b',
            'unclaimed': '#6b7280'
        };

        const icon = actionIcons[activity.action] || 'fa-circle';
        const color = actionColors[activity.action] || '#6b7280';
        const timestamp = new Date(activity.timestamp).toLocaleString();

        return `
            <div class="activity-item">
                <div class="activity-icon" style="background-color: ${color}">
                    <i class="fas ${icon}"></i>
                </div>
                <div class="activity-content">
                    <div class="activity-header">
                        <span class="activity-action">${activity.action.charAt(0).toUpperCase() + activity.action.slice(1)}</span>
                        <span class="activity-user">${activity.user_email}</span>
                    </div>
                    <div class="activity-item-name">${activity.item_name || 'Unknown item'}</div>
                    <div class="activity-timestamp">${timestamp}</div>
                </div>
            </div>
        `;
    }).join('');
};

/**
 * Claim an item
 */
MyEstateAllyApp.prototype.claimItem = async function(itemId) {
    try {
        const response = await fetch(`/api/items/${itemId}/claim`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            this.showMessage(data.message, 'success');
            if (data.has_conflict) {
                this.showMessage('Multiple people want this item', 'warning');
            }
            this.loadInventory();
        } else {
            this.showMessage(data.error || 'Failed to claim item', 'error');
        }
    } catch (error) {
        console.error('Error claiming item:', error);
        this.showMessage('Failed to claim item', 'error');
    }
};

/**
 * Unclaim an item
 */
MyEstateAllyApp.prototype.unclaimItem = async function(itemId) {
    try {
        const response = await fetch(`/api/items/${itemId}/unclaim`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            this.showMessage(data.message, 'success');
            this.loadInventory();
        } else {
            this.showMessage(data.error || 'Failed to unclaim item', 'error');
        }
    } catch (error) {
        console.error('Error unclaiming item:', error);
        this.showMessage('Failed to unclaim item', 'error');
    }
};

/**
 * Get current user's role in estate
 */
MyEstateAllyApp.prototype.getUserRole = async function() {
    try {
        const response = await fetch('/api/user/role');
        const data = await response.json();
        return data.role || 'viewer';
    } catch (error) {
        console.error('Error getting user role:', error);
        return 'viewer';
    }
};

/**
 * Show AI search modal
 */
MyEstateAllyApp.prototype.showAISearchModal = function() {
    this.openModal('ai-search-modal');
    document.getElementById('ai-search-query').value = '';
    document.getElementById('ai-search-results').innerHTML = '';
};

/**
 * Perform AI-powered natural language search
 */
MyEstateAllyApp.prototype.performAISearch = async function() {
    try {
        const query = document.getElementById('ai-search-query').value.trim();

        if (!query) {
            this.showMessage('Please enter a search query', 'error');
            return;
        }

        this.showLoading('AI is searching...');

        const response = await fetch('/api/ai/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query })
        });

        const data = await response.json();

        if (data.success) {
            const resultsDiv = document.getElementById('ai-search-results');

            if (data.items.length === 0) {
                resultsDiv.innerHTML = `<div class="ai-no-results"><i class="fas fa-search"></i><p>No items found</p></div>`;
            } else {
                resultsDiv.innerHTML = `
                    <div class="ai-results-header">
                        <h4>Found ${data.items.length} item(s)</h4>
                        <p>${data.explanation}</p>
                    </div>
                `;
            }

            this.showMessage('Search completed!', 'success');
        } else {
            this.showMessage(data.error || 'AI search failed', 'error');
        }
    } catch (error) {
        console.error('Error with AI search:', error);
        this.showMessage('Failed to perform AI search', 'error');
    } finally {
        this.hideLoading();
    }
};

/**
 * Get AI valuation for an item
 */
MyEstateAllyApp.prototype.getAIValuation = async function(itemData) {
    try {
        this.openModal('ai-valuation-modal');
        document.getElementById('ai-valuation-result').style.display = 'none';
        document.getElementById('ai-valuation-loading').style.display = 'block';

        const response = await fetch('/api/ai/value-item', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(itemData)
        });

        const data = await response.json();
        document.getElementById('ai-valuation-loading').style.display = 'none';

        if (data.success) {
            const valuation = data.valuation;
            this.currentAIValuation = valuation.estimated_value;

            document.getElementById('ai-value-range').textContent =
                `$${valuation.min_value.toLocaleString()} - $${valuation.max_value.toLocaleString()}`;
            document.getElementById('ai-estimated-value').textContent =
                `$${valuation.estimated_value.toLocaleString()}`;
            document.getElementById('ai-valuation-explanation').textContent = valuation.explanation;
            document.getElementById('ai-valuation-condition').textContent = valuation.condition;

            document.getElementById('ai-valuation-result').style.display = 'block';
        } else {
            this.showMessage(data.error || 'AI valuation failed', 'error');
            this.closeModal('ai-valuation-modal');
        }
    } catch (error) {
        console.error('Error with AI valuation:', error);
        this.showMessage('Failed to get AI valuation', 'error');
        this.closeModal('ai-valuation-modal');
    }
};

/**
 * Apply AI valuation to current item
 */
MyEstateAllyApp.prototype.applyAIValuation = function() {
    if (this.currentAIValuation) {
        const valueInput = document.getElementById('edit-estimated-value') || document.getElementById('estimated-value');
        if (valueInput) {
            valueInput.value = this.currentAIValuation;
        }
        this.closeModal('ai-valuation-modal');
        this.showMessage('AI valuation applied!', 'success');
    }
};

/**
 * Toggle mobile navigation menu
 */
MyEstateAllyApp.prototype.toggleMobileMenu = function() {
    const navContent = document.getElementById('nav-content');
    const menuBtn = document.getElementById('mobile-menu-btn');
    const isActive = navContent.classList.contains('mobile-active');

    if (isActive) {
        navContent.classList.remove('mobile-active');
        menuBtn.innerHTML = '<i class="fas fa-bars"></i>';
    } else {
        navContent.classList.add('mobile-active');
        menuBtn.innerHTML = '<i class="fas fa-times"></i>';
    }
};

/**
 * Close mobile menu when a nav button is clicked
 */
MyEstateAllyApp.prototype.closeMobileMenu = function() {
    const navContent = document.getElementById('nav-content');
    const menuBtn = document.getElementById('mobile-menu-btn');

    if (navContent.classList.contains('mobile-active')) {
        navContent.classList.remove('mobile-active');
        menuBtn.innerHTML = '<i class="fas fa-bars"></i>';
    }
};

/**
 * Set active state for bottom navigation
 */
MyEstateAllyApp.prototype.setActiveBottomNav = function(clickedBtn) {
    const allBtns = document.querySelectorAll('.bottom-nav-btn');
    allBtns.forEach(btn => btn.classList.remove('active'));

    if (clickedBtn) {
        clickedBtn.classList.add('active');
    }
};

/**
 * Open mobile more menu
 */
MyEstateAllyApp.prototype.openMobileMoreMenu = function() {
    const moreMenu = document.getElementById('mobile-more-menu');
    moreMenu.style.display = 'block';

    // Add backdrop
    const backdrop = document.createElement('div');
    backdrop.id = 'more-menu-backdrop';
    backdrop.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1000;';
    backdrop.onclick = () => this.closeMobileMoreMenu();
    document.body.appendChild(backdrop);

    // Prevent body scroll
    document.body.style.overflow = 'hidden';
};

/**
 * Close mobile more menu
 */
MyEstateAllyApp.prototype.closeMobileMoreMenu = function() {
    const moreMenu = document.getElementById('mobile-more-menu');
    moreMenu.style.display = 'none';

    // Remove backdrop
    const backdrop = document.getElementById('more-menu-backdrop');
    if (backdrop) {
        backdrop.remove();
    }

    // Restore body scroll
    document.body.style.overflow = '';
};

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new MyEstateAllyApp();
    console.log('MyEstateAlly app ready!');

    const urlParams = new URLSearchParams(window.location.search);

    // Check for OAuth error in URL (e.g., mismatching_state after Google callback)
    const oauthError = urlParams.get('error');
    const oauthMessage = urlParams.get('message');
    if (oauthError) {
        // Clean the ugly error params from the URL bar without reloading the page
        window.history.replaceState({}, document.title, window.location.pathname);
        // Show a user-friendly message
        const isStateError = oauthMessage && oauthMessage.toLowerCase().includes('mismatching_state');
        const msg = isStateError
            ? 'Sign-in session expired or interrupted. Please try signing in again.'
            : `Sign-in failed: ${decodeURIComponent(oauthMessage || oauthError)}`;
        setTimeout(() => {
            if (window.app) window.app.showMessage(msg, 'error');
        }, 300); // Small delay to let the app finish initializing
    }

    // Check for password reset token in URL (/reset-password?token=...)
    const resetToken = urlParams.get('token');
    if (resetToken) {
        // Show the reset password modal automatically
        const resetModal = document.getElementById('reset-password-modal');
        if (resetModal) {
            resetModal.style.display = 'flex';
        }
    }

    // Global escape key handler for modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Close preview modal if open
            const previewModal = document.getElementById('preview-document-modal');
            if (previewModal && previewModal.style.display === 'flex') {
                window.app.closePreviewModal();
            }
        }
    });
});

// ============================================================================
// LISTING ASSISTANT — Sell on Facebook Marketplace / eBay / Craigslist
// ============================================================================

/**
 * Open the Listing Assistant modal for an item.
 */
MyEstateAllyApp.prototype.openListingAssistant = function(itemId) {
    const item = this.inventory.find(i => i.id === itemId);
    if (!item) {
        this.showMessage('Item not found', 'error');
        return;
    }
    this.listingItem = item;

    // Item preview
    const photoEl = document.getElementById('listing-item-photo');
    if (photoEl) {
        photoEl.innerHTML = item.photo
            ? `<img src="${item.photo}" alt="">`
            : '<i class="fas fa-image"></i>';
    }
    const nameEl = document.getElementById('listing-item-name');
    if (nameEl) nameEl.textContent = item.name || 'Unnamed Item';
    const metaEl = document.getElementById('listing-item-meta');
    if (metaEl) metaEl.textContent =
        `${item.category || 'Uncategorized'} · Est. value $${(item.estimatedValue || 0).toLocaleString()}`;

    // Prefill editable fields from the item
    const titleEl = document.getElementById('listing-title');
    const priceEl = document.getElementById('listing-price');
    const descEl  = document.getElementById('listing-description');
    if (titleEl) titleEl.value = item.name || '';
    if (priceEl) priceEl.value = item.estimatedValue || '';
    if (descEl)  descEl.value  = item.description || '';

    // Photo download only makes sense if there is a photo
    const dlBtn = document.getElementById('listing-download-photo-btn');
    if (dlBtn) dlBtn.style.display = item.photo ? '' : 'none';

    // Restore listing tracker state
    const listings = item.listings || {};
    const fb = document.getElementById('listed-facebook');
    const eb = document.getElementById('listed-ebay');
    const cl = document.getElementById('listed-craigslist');
    const pm = document.getElementById('listed-poshmark');
    if (fb) fb.checked = !!listings.facebook;
    if (eb) eb.checked = !!listings.ebay;
    if (cl) cl.checked = !!listings.craigslist;
    if (pm) pm.checked = !!listings.poshmark;

    this.openModal('listing-assistant-modal');
};

/**
 * Ask the AI to write marketplace-ready listing copy for the current item.
 */
MyEstateAllyApp.prototype.generateListingCopy = async function() {
    if (!this.listingItem) return;
    const btn = document.getElementById('generate-listing-btn');
    const originalHTML = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Writing your listing…';
    }

    try {
        const response = await fetch('/api/ai/generate-listing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ item_id: this.listingItem.id })
        });
        const data = await response.json();

        if (data.success && data.listing) {
            const l = data.listing;
            const titleEl = document.getElementById('listing-title');
            const priceEl = document.getElementById('listing-price');
            const descEl  = document.getElementById('listing-description');
            if (titleEl && l.title) titleEl.value = String(l.title).slice(0, 80);
            if (priceEl && l.price) priceEl.value = Math.round(Number(l.price)) || '';
            if (descEl && l.description) descEl.value = l.description;
            this.showMessage('Listing written! Review it, then copy and paste.', 'success');
        } else {
            this.showMessage(data.error || 'Could not generate listing', 'error');
        }
    } catch (error) {
        console.error('Error generating listing:', error);
        this.showMessage('Could not generate listing. Please try again.', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalHTML;
        }
    }
};

/**
 * Copy a listing field's text to the clipboard, with visual feedback.
 */
MyEstateAllyApp.prototype.copyListingText = async function(fieldId, btn) {
    const field = document.getElementById(fieldId);
    if (!field || !field.value) {
        this.showMessage('Nothing to copy yet', 'info');
        return;
    }
    try {
        await navigator.clipboard.writeText(field.value);
    } catch (e) {
        // Fallback for older browsers / non-secure contexts
        field.select();
        document.execCommand('copy');
    }
    if (btn) {
        const original = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.innerHTML = original;
            btn.classList.remove('copied');
        }, 1600);
    }
};

/**
 * Download the item's photo so it can be attached to a marketplace listing.
 */
MyEstateAllyApp.prototype.downloadListingPhoto = function() {
    if (!this.listingItem || !this.listingItem.photo) {
        this.showMessage('This item has no photo', 'info');
        return;
    }
    const a = document.createElement('a');
    a.href = this.listingItem.photo;
    const safeName = (this.listingItem.name || 'item')
        .replace(/[^a-z0-9]+/gi, '_').toLowerCase();
    a.download = `${safeName}_photo.jpg`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
};

/**
 * Open a marketplace's "create listing" page in a new tab.
 */
MyEstateAllyApp.prototype.openMarketplace = function(platform) {
    const urls = {
        facebook:  'https://www.facebook.com/marketplace/create/item',
        ebay:      'https://www.ebay.com/sl/sell',
        craigslist:'https://post.craigslist.org/',
        poshmark:  'https://poshmark.com/create-listing'
    };
    const url = urls[platform];
    if (url) window.open(url, '_blank', 'noopener');
};

/**
 * Persist which marketplaces the item is listed on (saved on the item).
 */
MyEstateAllyApp.prototype.saveListingStatus = async function() {
    if (!this.listingItem) return;
    const listings = {
        facebook:   !!document.getElementById('listed-facebook')?.checked,
        ebay:       !!document.getElementById('listed-ebay')?.checked,
        craigslist: !!document.getElementById('listed-craigslist')?.checked,
        poshmark:   !!document.getElementById('listed-poshmark')?.checked
    };
    try {
        const response = await fetch(`/api/items/${this.listingItem.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ listings })
        });
        const data = await response.json();
        if (data.success) {
            this.listingItem.listings = listings;
            // Keep the in-memory inventory in sync and refresh badges
            const idx = this.inventory.findIndex(i => i.id === this.listingItem.id);
            if (idx !== -1) this.inventory[idx].listings = listings;
            this.updateInventoryDisplay();
        } else {
            this.showMessage(data.error || 'Could not save listing status', 'error');
        }
    } catch (error) {
        console.error('Error saving listing status:', error);
        this.showMessage('Could not save listing status', 'error');
    }
};

