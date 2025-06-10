// Service Worker for AI Sales Assistant PWA
const CACHE_NAME = 'ai-sales-assistant-v1';
const urlsToCache = [
  '/',
  '/static/styles.css',
  '/static/script.js',
  '/static/manifest.json',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
];

// Install event - cache resources
self.addEventListener('install', function(event) {
  console.log('[ServiceWorker] Install');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        console.log('[ServiceWorker] Caching app shell');
        return cache.addAll(urlsToCache);
      })
      .catch(function(error) {
        console.log('[ServiceWorker] Cache failed:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', function(event) {
  console.log('[ServiceWorker] Activate');
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(cacheName) {
          if (cacheName !== CACHE_NAME) {
            console.log('[ServiceWorker] Removing old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', function(event) {
  // Skip cross-origin requests
  if (!event.request.url.startsWith(self.location.origin)) {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        // Return cached version or fetch from network
        if (response) {
          console.log('[ServiceWorker] Serving from cache:', event.request.url);
          return response;
        }

        console.log('[ServiceWorker] Fetching from network:', event.request.url);
        return fetch(event.request).then(function(response) {
          // Don't cache if not a valid response
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }

          // Clone the response
          const responseToCache = response.clone();

          // Cache the response for static assets
          if (event.request.url.includes('/static/') || 
              event.request.url.endsWith('.css') || 
              event.request.url.endsWith('.js') ||
              event.request.url.endsWith('.json')) {
            caches.open(CACHE_NAME)
              .then(function(cache) {
                cache.put(event.request, responseToCache);
              });
          }

          return response;
        }).catch(function(error) {
          console.log('[ServiceWorker] Fetch failed:', error);
          
          // Return offline page for navigation requests
          if (event.request.mode === 'navigate') {
            return caches.match('/') || new Response(
              `<!DOCTYPE html>
              <html>
              <head>
                <title>AI Sales Assistant - Offline</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                  body { 
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
                    text-align: center; 
                    padding: 50px; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    flex-direction: column;
                  }
                  .offline-card {
                    background: rgba(255, 255, 255, 0.1);
                    backdrop-filter: blur(10px);
                    border-radius: 20px;
                    padding: 3rem;
                    max-width: 400px;
                    border: 1px solid rgba(255, 255, 255, 0.2);
                  }
                  h1 { margin-bottom: 1rem; }
                  p { margin-bottom: 2rem; line-height: 1.6; }
                  button {
                    background: rgba(255, 255, 255, 0.2);
                    color: white;
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    padding: 0.75rem 1.5rem;
                    border-radius: 10px;
                    cursor: pointer;
                    font-size: 1rem;
                  }
                  button:hover {
                    background: rgba(255, 255, 255, 0.3);
                  }
                </style>
              </head>
              <body>
                <div class="offline-card">
                  <h1>🤖 AI Sales Assistant</h1>
                  <p>You're currently offline. Please check your internet connection and try again.</p>
                  <button onclick="window.location.reload()">Retry</button>
                </div>
              </body>
              </html>`,
              {
                headers: {
                  'Content-Type': 'text/html'
                }
              }
            );
          }
          
          // For other requests, just fail gracefully
          throw error;
        });
      })
  );
});

// Handle messages from the main thread
self.addEventListener('message', function(event) {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// Background sync for offline message queuing (if supported)
self.addEventListener('sync', function(event) {
  if (event.tag === 'background-sync') {
    console.log('[ServiceWorker] Background sync triggered');
    event.waitUntil(doBackgroundSync());
  }
});

function doBackgroundSync() {
  // Handle any queued offline actions here
  return Promise.resolve();
}

// Push notification handling (for future use)
self.addEventListener('push', function(event) {
  if (event.data) {
    const data = event.data.json();
    const options = {
      body: data.body || 'New message from AI Sales Assistant',
      icon: '/static/icon-192x192.png',
      badge: '/static/badge-72x72.png',
      tag: 'ai-sales-notification',
      renotify: true,
      actions: [
        {
          action: 'open',
          title: 'Open Chat'
        },
        {
          action: 'close',
          title: 'Dismiss'
        }
      ]
    };

    event.waitUntil(
      self.registration.showNotification(data.title || 'AI Sales Assistant', options)
    );
  }
});

// Handle notification clicks
self.addEventListener('notificationclick', function(event) {
  event.notification.close();

  if (event.action === 'open') {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});

console.log('[ServiceWorker] Service Worker registered successfully'); 