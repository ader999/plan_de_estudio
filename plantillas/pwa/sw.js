{% load static %}const SW_VERSION = 'planeauml-v11';
const STATIC_CACHE = `static-${SW_VERSION}`;
const PAGES_CACHE = `pages-${SW_VERSION}`;
const OFFLINE_URL = "{% url 'pwa_offline' %}";

const PRECACHE_ASSETS = [
    OFFLINE_URL,
    "{% static 'css/base.css' %}",
    "{% static 'css/shared_styles.css' %}",
    "{% static 'css/blog_style.css' %}",
    "{% static 'css/detalle_silabo_styles.css' %}",
    "{% static 'css/login.css' %}",
    "{% static 'css/planestudio.css' %}",
    "{% static 'img/logouml.png' %}",
    "{% static 'img/logouml.ico' %}",
    "{% static 'img/pwa-icon-192.png' %}",
    "{% static 'img/pwa-icon-512.png' %}",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/css/bootstrap.min.css",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.1/dist/js/bootstrap.bundle.min.js",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/js/all.min.js",
    "https://code.jquery.com/jquery-3.5.1.min.js"
];

const CDN_HOSTS = new Set([
    'cdn.jsdelivr.net',
    'cdnjs.cloudflare.com',
    'code.jquery.com',
    'fonts.googleapis.com',
    'fonts.gstatic.com'
]);

const BYPASS_PREFIXES = [
    '/admin/',
    '/app/',
    '/login/',
    '/logout/',
    '/google/',
    '/oauth2callback/',
    '/api/',
    '/generar_docx/',
    '/generar_excel/',
    '/generar_excel2/',
    '/descargar-secuencia-didactica/',
    '/generar-silabo/',
    '/generar-estudio-independiente/',
    '/sw.js',
    '/manifest.json',
    '/.well-known/'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then(async (cache) => {
            await Promise.allSettled(
                PRECACHE_ASSETS.map((url) =>
                    cache.add(new Request(url, { cache: 'reload' })).catch(() => null)
                )
            );
        }).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((key) => key !== STATIC_CACHE && key !== PAGES_CACHE)
                    .map((key) => caches.delete(key))
            )
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'CLEAR_PAGES_CACHE') {
        event.waitUntil(caches.delete(PAGES_CACHE));
    }
});

function isBypassPath(pathname) {
    return BYPASS_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

function fetchWithTimeout(request, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    return fetch(request, { signal: controller.signal }).finally(() => clearTimeout(timer));
}

async function cacheFirst(request) {
    const cache = await caches.open(STATIC_CACHE);
    const cached = await cache.match(request);
    if (cached) {
        return cached;
    }
    const response = await fetch(request);
    if (response && (response.ok || response.type === 'opaque')) {
        cache.put(request, response.clone()).catch(() => null);
    }
    return response;
}

async function staleWhileRevalidate(request) {
    const cache = await caches.open(STATIC_CACHE);
    const cached = await cache.match(request);
    const networkPromise = fetch(request)
        .then((response) => {
            if (response && response.ok) {
                cache.put(request, response.clone()).catch(() => null);
            }
            return response;
        })
        .catch(() => null);

    if (cached) {
        return cached;
    }
    const networkResponse = await networkPromise;
    return networkResponse || Response.error();
}

async function handleNavigation(request, url) {
    if (url.pathname.startsWith('/logout/')) {
        await caches.delete(PAGES_CACHE);
        return fetch(request);
    }

    if (isBypassPath(url.pathname)) {
        if (typeof navigator !== 'undefined' && navigator.onLine === false) {
            const offline = await caches.match(OFFLINE_URL);
            return offline || Response.error();
        }
        try {
            return await fetchWithTimeout(request, 45000);
        } catch (err) {
            const offline = await caches.match(OFFLINE_URL);
            return offline || Response.error();
        }
    }

    const pagesCache = await caches.open(PAGES_CACHE);
    const cachedPage = await pagesCache.match(request);
    const timeoutMs = cachedPage ? 4500 : 12000;

    try {
        const networkResponse = await fetchWithTimeout(request, timeoutMs);
        if (
            networkResponse &&
            networkResponse.ok &&
            !networkResponse.redirected &&
            !new URL(networkResponse.url).pathname.startsWith('/login/')
        ) {
            pagesCache.put(request, networkResponse.clone()).catch(() => null);
        }
        return networkResponse;
    } catch (err) {
        if (cachedPage) {
            return cachedPage;
        }
        const offline = await caches.match(OFFLINE_URL);
        return offline || Response.error();
    }
}

self.addEventListener('fetch', (event) => {
    const { request } = event;
    if (request.method !== 'GET') {
        return;
    }

    const url = new URL(request.url);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') {
        return;
    }

    if (request.mode === 'navigate') {
        event.respondWith(handleNavigation(request, url));
        return;
    }

    if (url.origin === self.location.origin && url.pathname.startsWith('/static/')) {
        event.respondWith(staleWhileRevalidate(request));
        return;
    }

    if (CDN_HOSTS.has(url.hostname)) {
        event.respondWith(cacheFirst(request));
    }
});
