/**
 * MyEstateAlly Service Worker
 * Provides offline functionality and background sync
 */

const CACHE_NAME = 'myestateally-v1.1.0';
const STATIC_CACHE = 'myestateally-static-v1.1.0';
const DYNAMIC_CACHE = 'myestateally-dynamic-v1.1.0';

// Files to cache for offline functionality
const STATIC_FILES = [
    '/',
    '/static/styles.css',
    '/static/script.js',
    '/static/family-view.js',
    '/static/manifest.json',
    '/static/offline.html',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
    'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
];

// Install event - cache static files
self.addEventListener('install', event => {
    console.log('MyEstateAlly Service Worker installing...');
    
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('MyEstateAlly Service Worker caching static files');
                return cache.addAll(STATIC_FILES);
            })
            .then(() => {
                console.log('MyEstateAlly Service Worker installed successfully');
                return self.skipWaiting();
            })
            .catch(error => {
                console.error('MyEstateAlly Service Worker installation failed:', error);
            })
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    console.log('MyEstateAlly Service Worker activating...');
    
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
                            console.log('MyEstateAlly Service Worker deleting old cache:', cacheName);
                            return caches.delete(cacheName);
                        }
                    })
                );
            })
            .then(() => {
                console.log('MyEstateAlly Service Worker activated successfully');
                return self.clients.claim();
            })
    );
});

// Fetch event - serve cached files or fetch from network
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }
    
    // Skip chrome-extension and other non-http(s) requests
    if (!url.protocol.startsWith('http')) {
        return;
    }
    
    // Handle API requests differently
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleApiRequest(request));
        return;
    }
    
    // Handle static files and pages
    event.respondWith(
        caches.match(request)
            .then(cachedResponse => {
                if (cachedResponse) {
                    // Return cached version
                    return cachedResponse;
                }
                
                // Fetch from network and cache
                return fetch(request)
                    .then(response => {
                        // Don't cache non-successful responses
                        if (!response || response.status !== 200 || response.type !== 'basic') {
                            return response;
                        }
                        
                        // Clone response for caching
                        const responseToCache = response.clone();
                        
                        caches.open(DYNAMIC_CACHE)
                            .then(cache => {
                                cache.put(request, responseToCache);
                            });
                        
                        return response;
                    })
                    .catch(() => {
                        // Return offline page for navigation requests
                        if (request.mode === 'navigate') {
                            return caches.match('/static/offline.html');
                        }
                        
                        // Return empty response for other requests
                        return new Response('', {
                            status: 408,
                            statusText: 'Request Timeout'
                        });
                    });
            })
    );
});

// Handle API requests with network-first strategy
async function handleApiRequest(request) {
    try {
        // Try network first
        const response = await fetch(request);
        
        // Cache successful GET requests
        if (response.status === 200 && request.method === 'GET') {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, response.clone());
        }
        
        return response;
    } catch (error) {
        // Try cache for GET requests
        if (request.method === 'GET') {
            const cachedResponse = await caches.match(request);
            if (cachedResponse) {
                return cachedResponse;
            }
        }
        
        // Return error response
        return new Response(JSON.stringify({
            success: false,
            error: 'Network unavailable. Please check your connection.',
            offline: true
        }), {
            status: 503,
            statusText: 'Service Unavailable',
            headers: {
                'Content-Type': 'application/json'
            }
        });
    }
}

// Background sync for offline actions
self.addEventListener('sync', event => {
    console.log('MyEstateAlly Service Worker background sync:', event.tag);
    
    if (event.tag === 'background-sync-inventory') {
        event.waitUntil(syncInventoryData());
    } else if (event.tag === 'background-sync-family') {
        event.waitUntil(syncFamilyData());
    }
});

// Sync inventory data when back online
async function syncInventoryData() {
    try {
        console.log('MyEstateAlly Service Worker syncing inventory data...');
        
        // Get pending inventory updates from IndexedDB
        const pendingUpdates = await getPendingInventoryUpdates();
        
        for (const update of pendingUpdates) {
            try {
                const response = await fetch('/api/inventory/sync', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(update)
                });
                
                if (response.ok) {
                    await removePendingUpdate(update.id);
                    console.log('MyEstateAlly Service Worker synced inventory update:', update.id);
                }
            } catch (error) {
                console.error('MyEstateAlly Service Worker failed to sync update:', update.id, error);
            }
        }
        
        console.log('MyEstateAlly Service Worker inventory sync completed');
    } catch (error) {
        console.error('MyEstateAlly Service Worker inventory sync failed:', error);
    }
}

// Sync family data when back online
async function syncFamilyData() {
    try {
        console.log('MyEstateAlly Service Worker syncing family data...');
        
        // Get pending family updates from IndexedDB
        const pendingUpdates = await getPendingFamilyUpdates();
        
        for (const update of pendingUpdates) {
            try {
                const response = await fetch('/api/family/sync', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(update)
                });
                
                if (response.ok) {
                    await removePendingFamilyUpdate(update.id);
                    console.log('MyEstateAlly Service Worker synced family update:', update.id);
                }
            } catch (error) {
                console.error('MyEstateAlly Service Worker failed to sync family update:', update.id, error);
            }
        }
        
        console.log('MyEstateAlly Service Worker family sync completed');
    } catch (error) {
        console.error('MyEstateAlly Service Worker family sync failed:', error);
    }
}

// Push notification handling
self.addEventListener('push', event => {
    console.log('MyEstateAlly Service Worker received push notification');
    
    const options = {
        body: 'You have new activity in MyEstateAlly',
        icon: '/static/icons/icon-192x192.png',
        badge: '/static/icons/badge-72x72.png',
        vibrate: [100, 50, 100],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1
        },
        actions: [
            {
                action: 'explore',
                title: 'Open MyEstateAlly',
                icon: '/static/icons/action-explore.png'
            },
            {
                action: 'close',
                title: 'Close',
                icon: '/static/icons/action-close.png'
            }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification('MyEstateAlly', options)
    );
});

// Notification click handling
self.addEventListener('notificationclick', event => {
    console.log('MyEstateAlly Service Worker notification clicked:', event.action);
    
    event.notification.close();
    
    if (event.action === 'explore') {
        event.waitUntil(
            clients.openWindow('/')
        );
    } else if (event.action === 'close') {
        // Just close the notification
        return;
    } else {
        // Default action - open the app
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});

// Message handling from main thread
self.addEventListener('message', event => {
    console.log('MyEstateAlly Service Worker received message:', event.data);
    
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    } else if (event.data && event.data.type === 'GET_VERSION') {
        event.ports[0].postMessage({ version: CACHE_NAME });
    }
});

// Utility functions for IndexedDB operations
async function getPendingInventoryUpdates() {
    // Implementation would use IndexedDB to store/retrieve pending updates
    // For now, return empty array
    return [];
}

async function removePendingUpdate(id) {
    // Implementation would remove the update from IndexedDB
    console.log('Removing pending update:', id);
}

async function getPendingFamilyUpdates() {
    // Implementation would use IndexedDB to store/retrieve pending family updates
    // For now, return empty array
    return [];
}

async function removePendingFamilyUpdate(id) {
    // Implementation would remove the family update from IndexedDB
    console.log('Removing pending family update:', id);
}

// Error handling
self.addEventListener('error', event => {
    console.error('MyEstateAlly Service Worker error:', event.error);
});

self.addEventListener('unhandledrejection', event => {
    console.error('MyEstateAlly Service Worker unhandled rejection:', event.reason);
});

console.log('MyEstateAlly Service Worker loaded successfully');

