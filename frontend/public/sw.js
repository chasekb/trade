// Service Worker for Trading Dashboard - Caching and Offline Support
const CACHE_NAME = 'trading-dashboard-v1';
const STATIC_CACHE = 'trading-static-v1';
const API_CACHE = 'trading-api-v1';

// Static assets to cache immediately
const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/favicon.ico',
  '/offline.html', // Create this file for offline fallback
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('Service Worker: Installing');

  event.waitUntil(
    (async () => {
      const staticCache = await caches.open(STATIC_CACHE);
      await staticCache.addAll(STATIC_ASSETS);

      // Skip waiting to activate immediately
      await self.skipWaiting();
    })()
  );
});

// Activate event - clean up old caches and claim clients
self.addEventListener('activate', (event) => {
  console.log('Service Worker: Activating');

  event.waitUntil(
    (async () => {
      // Clean up old caches
      const cacheNames = await caches.keys();
      await Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== STATIC_CACHE && cacheName !== API_CACHE && cacheName !== CACHE_NAME) {
            console.log('Service Worker: Deleting old cache', cacheName);
            return caches.delete(cacheName);
          }
        })
      );

      // Take control of all pages under this scope
      await self.clients.claim();
    })()
  );
});

// Fetch event - serve from cache or network with strategies
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests and chrome-extension requests
  if (request.method !== 'GET' || url.protocol === 'chrome-extension:') {
    return;
  }

  // Handle API requests - Network first with cache fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      (async () => {
        try {
          // Try network first
          const response = await fetch(request);

          // Cache successful responses
          if (response.ok) {
            const responseClone = response.clone();
            const apiCache = await caches.open(API_CACHE);
            apiCache.put(request, responseClone);
          }

          return response;
        } catch (error) {
          console.log('Network failed, trying cache for:', request.url);

          // Fallback to cache
          const cachedResponse = await caches.match(request);
          if (cachedResponse) {
            return cachedResponse;
          }

          // Return offline API response
          return new Response(
            JSON.stringify({
              error: 'offline',
              message: 'You appear to be offline. Please check your connection.'
            }),
            {
              status: 503,
              statusText: 'Service Unavailable',
              headers: { 'Content-Type': 'application/json' }
            }
          );
        }
      })()
    );
  }
  // Handle static assets and Next.js assets - Cache first
  else if (
    STATIC_ASSETS.some(asset => url.pathname === asset) ||
    url.pathname.startsWith('/_next/static/') ||
    url.pathname.startsWith('/fonts/') ||
    url.pathname.includes('.')
  ) {
    event.respondWith(
      (async () => {
        // Try cache first
        const cachedResponse = await caches.match(request);

        if (cachedResponse) {
          // Check if cache is still fresh (7 days for static assets)
          const cacheTime = new Date(cachedResponse.headers.get('sw-cache-time') || 0);
          const now = new Date();
          const age = now - cacheTime;

          if (age < 7 * 24 * 60 * 60 * 1000) { // 7 days
            return cachedResponse;
          }
        }

        try {
          // Fetch from network and cache
          const response = await fetch(request);
          if (response.ok) {
            const responseClone = response.clone();
            const headers = new Headers(responseClone.headers);
            headers.set('sw-cache-time', new Date().toISOString());

            const cachedResponse = new Response(responseClone.body, {
              status: responseClone.status,
              statusText: responseClone.statusText,
              headers
            });

            const staticCache = await caches.open(STATIC_CACHE);
            staticCache.put(request, cachedResponse);
          }

          return response;
        } catch (error) {
          // If both cache and network fail, serve offline page for HTML requests
          if (request.headers.get('accept').includes('text/html')) {
            const offlineResponse = await caches.match('/offline.html');
            if (offlineResponse) {
              return offlineResponse;
            }
          }

          // Return cache if available, otherwise network error
          return cachedResponse || fetch(request);
        }
      })()
    );
  }
  // Default: Network first for HTML pages
  else {
    event.respondWith(
      (async () => {
        try {
          const response = await fetch(request);
          return response;
        } catch (error) {
          // Try cache fallback for HTML pages
          if (request.headers.get('accept').includes('text/html')) {
            const cachedResponse = await caches.match(request);
            if (cachedResponse) {
              return cachedResponse;
            }

            // Show offline page
            const offlineResponse = await caches.match('/offline.html');
            return offlineResponse || new Response(
              '<h1>Offline</h1><p>You appear to be offline. Please check your connection.</p>',
              {
                headers: { 'Content-Type': 'text/html' }
              }
            );
          }

          throw error;
        }
      })()
    );
  }
});

// Background sync for failed requests (when online again)
self.addEventListener('sync', (event) => {
  if (event.tag === 'background-sync') {
    event.waitUntil(doBackgroundSync());
  }
});

// Push notifications for trading alerts
self.addEventListener('push', (event) => {
  if (event.data) {
    const data = event.data.json();

    const options = {
      body: data.body,
      icon: '/icon-192x192.png',
      badge: '/badge-72x72.png',
      vibrate: [100, 50, 100],
      data: data.url,
      requireInteraction: true,
      actions: [
        {
          action: 'view',
          title: 'View Details'
        },
        {
          action: 'dismiss',
          title: 'Dismiss'
        }
      ]
    };

    event.waitUntil(
      self.registration.showNotification(data.title, options)
    );
  }
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'view') {
    event.waitUntil(
      clients.openWindow(event.notification.data)
    );
  }
});

// Background sync implementation
async function doBackgroundSync() {
  try {
    const cache = await caches.open(API_CACHE);
    const keys = await cache.keys();

    // Retry failed API requests from cache
    for (const request of keys) {
      try {
        const cachedResponse = await cache.match(request);
        if (cachedResponse && !cachedResponse.ok) {
          await fetchAndCache(request);
        }
      } catch (error) {
        console.log('Background sync failed for:', request.url);
      }
    }
  } catch (error) {
    console.log('Background sync error:', error);
  }
}

async function fetchAndCache(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    console.log('Fetch and cache failed:', error);
    throw error;
  }
}

// Periodic cleanup of old cache entries
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'CLEAN_CACHE') {
    event.waitUntil(cleanOldCacheEntries());
  }
});

async function cleanOldCacheEntries() {
  try {
    const cache = await caches.open(API_CACHE);
    const keys = await cache.keys();

    for (const request of keys) {
      const response = await cache.match(request);
      if (response) {
        const cacheTime = new Date(response.headers.get('sw-cache-time') || 0);
        const now = new Date();
        const age = now - cacheTime;

        // Remove entries older than 24 hours
        if (age > 24 * 60 * 60 * 1000) {
          await cache.delete(request);
        }
      }
    }
  } catch (error) {
    console.log('Cache cleanup error:', error);
  }
}
