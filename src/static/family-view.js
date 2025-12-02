/**
 * MyEstateAlly - Family View JavaScript
 * Interface for family members to view and interact with shared inventory
 */

class FamilyViewApp {
    constructor() {
        this.shareId = null;
        this.memberCode = null;
        this.inventory = [];
        this.wantedItems = [];
        this.currentView = 'all';
        this.filters = {
            category: '',
            sort: 'name'
        };
        
        this.init();
    }

    /**
     * Initialize the family view application
     */
    init() {
        console.log('MyEstateAlly Family View initializing...');
        
        // Get share ID from URL
        const urlParams = new URLSearchParams(window.location.search);
        this.shareId = urlParams.get('share');
        
        if (!this.shareId) {
            this.showError('Invalid sharing link. Please check the URL.');
            return;
        }

        // Check for stored member code
        this.memberCode = localStorage.getItem(`family_member_code_${this.shareId}`);
        
        if (!this.memberCode) {
            this.showMemberSetup();
        } else {
            this.displayMemberCode();
            this.loadInventory();
        }

        this.setupEventListeners();
        console.log('MyEstateAlly Family View initialized');
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Navigation buttons
        document.querySelectorAll('.family-nav-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const view = e.target.closest('.family-nav-btn').dataset.view;
                this.switchView(view);
            });
        });

        // Filters
        document.getElementById('category-filter')?.addEventListener('change', (e) => {
            this.filters.category = e.target.value;
            this.applyFilters();
        });

        document.getElementById('sort-filter')?.addEventListener('change', (e) => {
            this.filters.sort = e.target.value;
            this.applyFilters();
        });

        // Modal close
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.closeModal();
            }
        });
    }

    /**
     * Show member setup modal
     */
    showMemberSetup() {
        const modal = document.getElementById('member-setup-modal');
        if (modal) {
            modal.style.display = 'flex';
        }
    }

    /**
     * Set member code
     */
    setMemberCode() {
        const input = document.getElementById('member-code-input');
        const code = input.value.trim().toUpperCase();
        
        if (!code || !code.match(/^FM\d{3}$/)) {
            this.showMessage('Please enter a valid member code (e.g., FM001)', 'error');
            return;
        }

        this.memberCode = code;
        localStorage.setItem(`family_member_code_${this.shareId}`, code);
        
        this.displayMemberCode();
        this.closeModal('member-setup-modal');
        this.loadInventory();
    }

    /**
     * Display member code in UI
     */
    displayMemberCode() {
        document.getElementById('member-code-display').textContent = this.memberCode || '--';
        document.getElementById('current-member-code').textContent = this.memberCode || '--';
    }

    /**
     * Switch between views
     */
    switchView(view) {
        this.currentView = view;
        
        // Update navigation
        document.querySelectorAll('.family-nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-view="${view}"]`)?.classList.add('active');

        // Show/hide sections
        if (view === 'my-wanted') {
            document.getElementById('family-items-grid').style.display = 'none';
            document.getElementById('my-wanted-list').style.display = 'block';
            this.loadWantedItems();
        } else {
            document.getElementById('family-items-grid').style.display = 'grid';
            document.getElementById('my-wanted-list').style.display = 'none';
            this.applyFilters();
        }
    }

    /**
     * Load shared inventory
     */
    async loadInventory() {
        this.showLoading();
        
        try {
            const response = await fetch(`/api/family/shared-inventory/${this.shareId}`);
            const result = await response.json();

            if (result.success) {
                this.inventory = result.inventory;
                this.displayInventory();
            } else {
                throw new Error(result.error || 'Failed to load inventory');
            }
        } catch (error) {
            console.error('Error loading inventory:', error);
            this.showError('Failed to load inventory. Please check your connection and try again.');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Load wanted items for current member
     */
    async loadWantedItems() {
        if (!this.memberCode) return;

        try {
            const response = await fetch(`/api/family/wanted-items/${this.shareId}/${this.memberCode}`);
            const result = await response.json();

            if (result.success) {
                this.wantedItems = result.wanted_items;
                this.displayWantedItems();
            } else {
                throw new Error(result.error || 'Failed to load wanted items');
            }
        } catch (error) {
            console.error('Error loading wanted items:', error);
            this.showMessage('Failed to load wanted items', 'error');
        }
    }

    /**
     * Display inventory items
     */
    displayInventory() {
        const grid = document.getElementById('family-items-grid');
        const emptyState = document.getElementById('family-empty-state');

        if (!grid) return;

        let items = this.inventory;

        // Filter by view
        if (this.currentView === 'for-sale') {
            items = items.filter(item => item.forSale);
        }

        if (items.length === 0) {
            grid.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        if (emptyState) emptyState.style.display = 'none';
        grid.style.display = 'grid';

        grid.innerHTML = items.map(item => this.createItemCard(item)).join('');
    }

    /**
     * Create item card HTML
     */
    createItemCard(item) {
        const isWanted = this.wantedItems.some(w => w.item_id === item.id);
        
        return `
            <div class="family-item-card" data-item-id="${item.id}">
                <div class="family-item-image">
                    ${item.photo ? `<img src="${item.photo}" alt="${item.name}">` : '<i class="fas fa-image"></i>'}
                    ${item.forSale ? '<span class="for-sale-badge">For Sale</span>' : ''}
                </div>
                <div class="family-item-info">
                    <h4>${item.name || 'Unnamed Item'}</h4>
                    <p class="family-item-category">${item.category || 'Uncategorized'}</p>
                    <p class="family-item-description">${item.description || 'No description available'}</p>
                    <div class="family-item-value">$${item.estimatedValue || 0}</div>
                    ${item.assignedTo ? `<div class="assigned-info">Assigned to: ${item.assignedTo}</div>` : ''}
                </div>
                <div class="family-item-actions">
                    <button class="btn ${isWanted ? 'secondary' : 'primary'} want-btn" 
                            onclick="familyApp.toggleWantItem('${item.id}', ${isWanted})">
                        <i class="fas fa-heart${isWanted ? '' : '-o'}"></i>
                        ${isWanted ? 'Wanted' : 'Want This'}
                    </button>
                    <button class="btn secondary" onclick="familyApp.showItemDetails('${item.id}')">
                        <i class="fas fa-info-circle"></i>
                        Details
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Display wanted items
     */
    displayWantedItems() {
        const grid = document.getElementById('wanted-items-grid');
        const emptyState = document.getElementById('wanted-empty-state');

        if (!grid) return;

        if (this.wantedItems.length === 0) {
            grid.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
            return;
        }

        if (emptyState) emptyState.style.display = 'none';
        grid.style.display = 'grid';

        // Get full item details for wanted items
        const wantedItemsWithDetails = this.wantedItems.map(wanted => {
            const item = this.inventory.find(inv => inv.id === wanted.item_id);
            return { ...wanted, ...item };
        }).filter(item => item.name); // Filter out items that don't exist anymore

        // Group by priority
        const priorities = ['high', 'medium', 'low'];
        let html = '';

        priorities.forEach(priority => {
            const items = wantedItemsWithDetails.filter(item => item.priority === priority);
            if (items.length > 0) {
                html += `
                    <div class="wanted-priority-section">
                        <h4 class="priority-header priority-${priority}">
                            <i class="fas fa-flag"></i>
                            ${priority.charAt(0).toUpperCase() + priority.slice(1)} Priority (${items.length})
                        </h4>
                        <div class="wanted-items-list">
                            ${items.map(item => this.createWantedItemCard(item)).join('')}
                        </div>
                    </div>
                `;
            }
        });

        grid.innerHTML = html;
    }

    /**
     * Create wanted item card HTML
     */
    createWantedItemCard(item) {
        return `
            <div class="wanted-item-card">
                <div class="wanted-item-image">
                    ${item.photo ? `<img src="${item.photo}" alt="${item.name}">` : '<i class="fas fa-image"></i>'}
                </div>
                <div class="wanted-item-info">
                    <h5>${item.name}</h5>
                    <p class="wanted-item-category">${item.category}</p>
                    <p class="wanted-item-value">$${item.estimatedValue || 0}</p>
                    <p class="wanted-date">Wanted: ${new Date(item.wanted_at).toLocaleDateString()}</p>
                </div>
                <div class="wanted-item-actions">
                    <button class="btn small secondary" onclick="familyApp.toggleWantItem('${item.item_id}', true)">
                        <i class="fas fa-heart-broken"></i>
                        Remove
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Apply filters to inventory
     */
    applyFilters() {
        let items = this.inventory;

        // Filter by view
        if (this.currentView === 'for-sale') {
            items = items.filter(item => item.forSale);
        }

        // Filter by category
        if (this.filters.category) {
            items = items.filter(item => item.category === this.filters.category);
        }

        // Sort items
        switch (this.filters.sort) {
            case 'name':
                items.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
                break;
            case 'value-high':
                items.sort((a, b) => (b.estimatedValue || 0) - (a.estimatedValue || 0));
                break;
            case 'value-low':
                items.sort((a, b) => (a.estimatedValue || 0) - (b.estimatedValue || 0));
                break;
            case 'date-new':
                items.sort((a, b) => new Date(b.dateAdded || 0) - new Date(a.dateAdded || 0));
                break;
            case 'date-old':
                items.sort((a, b) => new Date(a.dateAdded || 0) - new Date(b.dateAdded || 0));
                break;
        }

        // Update display
        const grid = document.getElementById('family-items-grid');
        const emptyState = document.getElementById('family-empty-state');

        if (items.length === 0) {
            grid.style.display = 'none';
            if (emptyState) emptyState.style.display = 'block';
        } else {
            if (emptyState) emptyState.style.display = 'none';
            grid.style.display = 'grid';
            grid.innerHTML = items.map(item => this.createItemCard(item)).join('');
        }
    }

    /**
     * Toggle want status for an item
     */
    async toggleWantItem(itemId, isCurrentlyWanted) {
        if (!this.memberCode) {
            this.showMessage('Please set your member code first', 'error');
            return;
        }

        // If adding, show desire level selection
        if (!isCurrentlyWanted) {
            this.showDesireLevelModal(itemId);
            return;
        }

        try {
            const response = await fetch(`/api/family/want-item/${this.shareId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    item_id: itemId,
                    member_code: this.memberCode,
                    action: 'remove'
                })
            });

            const result = await response.json();

            if (result.success) {
                this.showMessage(result.message, 'success');
                
                // Update local wanted items
                this.wantedItems = this.wantedItems.filter(w => w.item_id !== itemId);

                // Refresh display
                if (this.currentView === 'my-wanted') {
                    this.displayWantedItems();
                } else {
                    this.displayInventory();
                }
            } else {
                throw new Error(result.error || 'Failed to update wanted status');
            }
        } catch (error) {
            console.error('Error toggling want status:', error);
            this.showMessage(error.message, 'error');
        }
    }

    /**
     * Show desire level selection modal
     */
    showDesireLevelModal(itemId) {
        const item = this.inventory.find(inv => inv.id === itemId);
        if (!item) return;

        // Create modal HTML
        const modalHtml = `
            <div id="desire-modal" class="modal" style="display: block;">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>How much do you want this item?</h3>
                        <button class="modal-close" onclick="this.closest('.modal').remove()">&times;</button>
                    </div>
                    <div class="modal-body">
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
                        
                        <div class="desire-level-selection">
                            <h4>Select your desire level:</h4>
                            <div class="desire-levels">
                                <label class="desire-level-option">
                                    <input type="radio" name="desire_level" value="1">
                                    <div class="desire-level-content">
                                        <span class="desire-level-number">1</span>
                                        <span class="desire-level-label">Not really interested</span>
                                        <span class="desire-level-desc">Would take it if no one else wants it</span>
                                    </div>
                                </label>
                                
                                <label class="desire-level-option">
                                    <input type="radio" name="desire_level" value="2">
                                    <div class="desire-level-content">
                                        <span class="desire-level-number">2</span>
                                        <span class="desire-level-label">Somewhat interested</span>
                                        <span class="desire-level-desc">Would like it but not a priority</span>
                                    </div>
                                </label>
                                
                                <label class="desire-level-option">
                                    <input type="radio" name="desire_level" value="3" checked>
                                    <div class="desire-level-content">
                                        <span class="desire-level-number">3</span>
                                        <span class="desire-level-label">Interested</span>
                                        <span class="desire-level-desc">Would like to have it</span>
                                    </div>
                                </label>
                                
                                <label class="desire-level-option">
                                    <input type="radio" name="desire_level" value="4">
                                    <div class="desire-level-content">
                                        <span class="desire-level-number">4</span>
                                        <span class="desire-level-label">Really want it</span>
                                        <span class="desire-level-desc">Would be disappointed to not get it</span>
                                    </div>
                                </label>
                                
                                <label class="desire-level-option">
                                    <input type="radio" name="desire_level" value="5">
                                    <div class="desire-level-content">
                                        <span class="desire-level-number">5</span>
                                        <span class="desire-level-label">Must have!</span>
                                        <span class="desire-level-desc">This item is very important to me</span>
                                    </div>
                                </label>
                            </div>
                        </div>
                        
                        <div class="modal-actions">
                            <button class="btn secondary" onclick="this.closest('.modal').remove()">Cancel</button>
                            <button class="btn primary" onclick="familyApp.submitDesireLevel('${itemId}')">Add to My Wanted List</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    /**
     * Submit desire level selection
     */
    async submitDesireLevel(itemId) {
        const modal = document.getElementById('desire-modal');
        const selectedLevel = modal.querySelector('input[name="desire_level"]:checked');
        
        if (!selectedLevel) {
            this.showMessage('Please select a desire level', 'error');
            return;
        }

        const desireLevel = parseInt(selectedLevel.value);
        
        try {
            const response = await fetch(`/api/family/want-item/${this.shareId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    item_id: itemId,
                    member_code: this.memberCode,
                    action: 'add',
                    priority: 'medium',
                    desire_level: desireLevel
                })
            });

            const result = await response.json();

            if (result.success) {
                this.showMessage(result.message, 'success');
                
                // Update local wanted items
                this.wantedItems.push({
                    item_id: itemId,
                    priority: 'medium',
                    desire_level: desireLevel,
                    wanted_at: new Date().toISOString()
                });

                // Remove modal
                modal.remove();

                // Refresh display
                if (this.currentView === 'my-wanted') {
                    this.displayWantedItems();
                } else {
                    this.displayInventory();
                }
            } else {
                throw new Error(result.error || 'Failed to add item to wanted list');
            }
        } catch (error) {
            console.error('Error adding item to wanted list:', error);
            this.showMessage(error.message, 'error');
        }
    }

    /**
     * Show item details modal
     */
    showItemDetails(itemId) {
        const item = this.inventory.find(inv => inv.id === itemId);
        if (!item) return;

        const modal = document.getElementById('family-item-modal');
        const nameEl = document.getElementById('family-item-name');
        const contentEl = document.getElementById('family-item-content');
        const wantBtn = document.getElementById('want-item-btn');

        if (!modal || !nameEl || !contentEl || !wantBtn) return;

        nameEl.textContent = item.name || 'Unnamed Item';
        
        contentEl.innerHTML = `
            <div class="item-detail-image">
                ${item.photo ? `<img src="${item.photo}" alt="${item.name}">` : '<i class="fas fa-image"></i>'}
            </div>
            <div class="item-detail-info">
                <div class="detail-row">
                    <strong>Category:</strong> ${item.category || 'Uncategorized'}
                </div>
                <div class="detail-row">
                    <strong>Estimated Value:</strong> $${item.estimatedValue || 0}
                </div>
                <div class="detail-row">
                    <strong>Description:</strong> ${item.description || 'No description available'}
                </div>
                ${item.forSale ? '<div class="detail-row"><strong>Status:</strong> <span class="for-sale-badge">For Sale</span></div>' : ''}
                ${item.assignedTo ? `<div class="detail-row"><strong>Assigned to:</strong> ${item.assignedTo}</div>` : ''}
                <div class="detail-row">
                    <strong>Added:</strong> ${item.dateAdded ? new Date(item.dateAdded).toLocaleDateString() : 'Unknown'}
                </div>
            </div>
        `;

        const isWanted = this.wantedItems.some(w => w.item_id === itemId);
        wantBtn.innerHTML = `
            <i class="fas fa-heart${isWanted ? '' : '-o'}"></i>
            ${isWanted ? 'Remove from Wanted' : 'Add to Wanted'}
        `;
        wantBtn.onclick = () => {
            this.toggleWantItem(itemId, isWanted);
            this.closeModal();
        };

        modal.style.display = 'flex';
    }

    /**
     * Close modal
     */
    closeModal() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.style.display = 'none';
        });
    }

    /**
     * Show loading state
     */
    showLoading() {
        document.getElementById('family-loading').style.display = 'block';
        document.getElementById('family-items-grid').style.display = 'none';
        document.getElementById('family-empty-state').style.display = 'none';
        document.getElementById('family-error-state').style.display = 'none';
    }

    /**
     * Hide loading state
     */
    hideLoading() {
        document.getElementById('family-loading').style.display = 'none';
    }

    /**
     * Show error state
     */
    showError(message) {
        document.getElementById('family-error-state').style.display = 'block';
        document.getElementById('family-loading').style.display = 'none';
        document.getElementById('family-items-grid').style.display = 'none';
        document.getElementById('family-empty-state').style.display = 'none';
        
        const errorEl = document.getElementById('family-error-state');
        if (errorEl) {
            errorEl.querySelector('p').textContent = message;
        }
    }

    /**
     * Show message to user
     */
    showMessage(message, type = 'info') {
        const messageEl = document.getElementById('family-message');
        if (!messageEl) return;

        messageEl.className = `family-message family-message-${type}`;
        messageEl.innerHTML = `
            <div class="family-message-content">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
            <button class="family-message-close" onclick="this.parentElement.style.display='none'">&times;</button>
        `;
        
        messageEl.style.display = 'block';

        // Auto hide after 5 seconds
        setTimeout(() => {
            messageEl.style.display = 'none';
        }, 5000);
    }
}

// Global functions
function setMemberCode() {
    if (window.familyApp) {
        window.familyApp.setMemberCode();
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.familyApp = new FamilyViewApp();
    console.log('MyEstateAlly Family View ready!');
});

