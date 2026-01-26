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
        this.sharingSettings = {
            enabled: true,
            show_for_sale_only: false,
            allow_wanted_tagging: true
        };
        this.currentShareLink = null;

        this.init();
    }

    /**
     * Initialize the application
     */
    init() {
        console.log('MyEstateAlly app initializing...');
        
        // Check for existing session or set up demo user
        this.checkAuthStatus();
        
        this.setupEventListeners();
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
                
                // If no estates exist, show welcome modal
                if (!data.estates || data.estates.length === 0) {
                    // Show welcome modal for first-time users
                    setTimeout(() => {
                        this.showWelcomeModal();
                    }, 500);
                }
                
                return;
            }
            
            // No valid session, show auth modal
            this.updateAuthUI(false);
            
        } catch (error) {
            console.error('Auth check failed:', error);
            // Fallback to showing auth UI
            this.updateAuthUI(false);
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
                this.showMessage('Photo analyzed successfully!', 'success');
                this.displayAIAnalysis(result.analysis);
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
        // Create a simple display of the analysis
        const message = `AI identified: ${analysis.item_name} (${analysis.category})\nEstimated value: $${analysis.estimated_value_min}-$${analysis.estimated_value_max}\nConfidence: ${Math.round(analysis.confidence * 100)}%`;
        this.showMessage(message, 'success');
        
        // Add to activity
        this.addActivity(`AI analyzed new item: ${analysis.item_name}`);
    }

    /**
     * Load inventory data
     */
    async loadInventory() {
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
                    <p class="item-value">$${item.estimatedValue || 0}</p>
                    ${item.forSale ? '<span class="for-sale-badge">For Sale</span>' : ''}
                    ${item.assignedTo ? `<span class="assigned-badge">Assigned to ${item.assignedTo}</span>` : ''}
                    <div class="item-actions">
                        <button class="edit-btn" onclick="app.editItem('${item.id}')">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button class="pricing-btn" onclick="app.lookupItemPricing('${item.id}')">
                            <i class="fas fa-search-dollar"></i> Price
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
     * Edit an inventory item
     */
    editItem(itemId) {
        const item = this.inventory.find(i => i.id === itemId);
        if (!item) {
            this.showMessage('Item not found', 'error');
            return;
        }

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
                            <label for="editValue">Estimated Value ($):</label>
                            <input type="number" id="editValue" value="${item.estimatedValue || 0}" min="0" step="0.01">
                        </div>
                        <div class="form-group">
                            <label for="editAssignedTo">Assigned To:</label>
                            <input type="text" id="editAssignedTo" value="${item.assignedTo || ''}" placeholder="Leave empty if unassigned">
                        </div>
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="editForSale" ${item.forSale ? 'checked' : ''}>
                                For Sale
                            </label>
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
            estimatedValue: parseFloat(document.getElementById('editValue').value) || 0,
            assignedTo: document.getElementById('editAssignedTo').value,
            forSale: document.getElementById('editForSale').checked
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
        const forSale = document.getElementById('item-for-sale').checked;

        if (!name || !category) {
            this.showMessage('Please fill in item name and category', 'error');
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
                    estimatedValue,
                    forSale,
                    photo: '/static/placeholder-image.png'  // Placeholder for manual entries
                })
            });

            const result = await response.json();

            if (result.success) {
                this.showMessage('Item added successfully!', 'success');
                this.closeModal('add-item-modal');
                document.getElementById('add-item-form').reset();
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
     * Update statistics
     */
    updateStats() {
        const totalItems = this.inventory.length;
        const totalValue = this.inventory.reduce((sum, item) => sum + (item.estimatedValue || 0), 0);
        const forSaleItems = this.inventory.filter(item => item.forSale).length;
        const assignedItems = this.inventory.filter(item => item.assignedTo).length;

        document.getElementById('total-items').textContent = totalItems;
        document.getElementById('total-value').textContent = `$${totalValue.toLocaleString()}`;
        document.getElementById('for-sale-items').textContent = forSaleItems;
        document.getElementById('assigned-items').textContent = assignedItems;
    }

    /**
     * Load family data
     */
    async loadFamilyData() {
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
            ? this.inventory.filter(item => item.forSale).length 
            : this.inventory.length;
        document.getElementById('shared-items-count').textContent = sharedCount;
        
        // Calculate conflict items and show decision making section if there are assignments
        const assignedItems = this.inventory.filter(item => item.assignedTo);
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
            }
            
            modal.style.display = 'flex';
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
            document.body.style.overflow = '';
        }
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
        
        if (isAuthenticated) {
            // Show user menu and estate selector, hide auth buttons
            userMenu.style.display = 'block';
            estateSelector.style.display = 'flex';
            authButtons.style.display = 'none';
            
            // Update user name
            const userName = document.getElementById('user-name');
            if (userName && this.currentUser) {
                userName.textContent = this.currentUser.name;
            }
        } else {
            // Hide user menu and estate selector, show auth buttons
            userMenu.style.display = 'none';
            estateSelector.style.display = 'none';
            authButtons.style.display = 'flex';
        }
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
                document.getElementById('estate-name').value = '';
                
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

    async applyBulkForSale() {
        const forSale = document.getElementById('bulk-for-sale-select')?.value === 'true';
        await this.bulkEdit('forSale', forSale);
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

            // For sale filter
            const matchesForSale = !forSaleFilter ||
                (forSaleFilter === 'true' && item.forSale) ||
                (forSaleFilter === 'false' && !item.forSale);

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
                    <p class="item-value">$${item.estimatedValue || 0}</p>
                    ${item.forSale ? '<span class="for-sale-badge">For Sale</span>' : ''}
                    ${item.assignedTo ? `<span class="assigned-badge">Assigned to ${item.assignedTo}</span>` : ''}
                    <div class="item-actions">
                        <button class="edit-btn" onclick="app.editItem('${item.id}')">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button class="pricing-btn" onclick="app.lookupItemPricing('${item.id}')">
                            <i class="fas fa-search-dollar"></i> Price
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
    app.showMessage('Password reset feature coming soon!', 'info');
}

// Legacy function for compatibility
function switchAuthTab(tab) {
    // Now handled by progressive flow
    showAuthStep(tab === 'login' ? 'password' : 'signup');
}

function loginWithGoogle() {
    if (window.app) {
        window.app.loginWithGoogle();
    }
}

function loginWithFacebook() {
    if (window.app) {
        window.app.loginWithFacebook();
    }
}

function logout() {
    if (window.app) {
        window.app.logout();
    }
}

function showUserProfile() {
    // TODO: Implement user profile modal
    app.showMessage('User profile coming soon!', 'info');
}

function showAccountSettings() {
    // TODO: Implement account settings modal
    app.showMessage('Account settings coming soon!', 'info');
}

// ============================================================================
// DOCUMENT MANAGEMENT METHODS
// ============================================================================

MyEstateAllyApp.prototype.loadDocuments = async function() {
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
                    <button class="btn-icon" onclick="app.downloadDocument('${doc.id}')" title="Download">
                        <i class="fas fa-download"></i>
                    </button>
                    <button class="btn-icon danger" onclick="app.deleteDocument('${doc.id}')" title="Delete">
                        <i class="fas fa-trash"></i>
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

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new MyEstateAllyApp();
    console.log('MyEstateAlly app ready!');
});

