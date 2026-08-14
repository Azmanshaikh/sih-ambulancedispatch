/// <reference types="@sveltejs/kit" />
import { build, files, version } from '$service-worker';

const CACHE = `jeevan-${version}`;
const ASSETS = [...build, ...files];

function isSkippable(request, url) {
	if (request.method !== 'GET') return true;
	if (url.protocol !== 'http:' && url.protocol !== 'https:') return true;
	if (request.headers.get('upgrade') === 'websocket') return true;
	if (url.pathname.startsWith('/tracking') || url.pathname.startsWith('/accounts')) return true;
	if (url.pathname.startsWith('/ai') || url.pathname.startsWith('/hospitals')) return true;
	if (url.hostname.includes('supabase')) return true;
	if (url.hostname.includes('googleapis') || url.hostname.includes('gstatic')) return true;
	if (url.hostname.includes('openstreetmap') || url.hostname.includes('tile.openstreetmap')) return true;
	if (url.hostname.includes('tomtom') || url.hostname.includes('project-osrm')) return true;
	return false;
}

self.addEventListener('install', (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) => cache.addAll(ASSETS))
			.then(() => self.skipWaiting())
	);
});

self.addEventListener('activate', (event) => {
	event.waitUntil(
		caches.keys().then(async (keys) => {
			for (const key of keys) {
				if (key !== CACHE) await caches.delete(key);
			}
			await self.clients.claim();
		})
	);
});

self.addEventListener('fetch', (event) => {
	const request = event.request;
	const url = new URL(request.url);
	if (isSkippable(request, url)) return;

	event.respondWith(
		(async () => {
			const cached = await caches.match(request);
			if (ASSETS.includes(url.pathname) && cached) return cached;

			try {
				const response = await fetch(request);
				if (response.ok && url.origin === self.location.origin) {
					const copy = response.clone();
					const cache = await caches.open(CACHE);
					await cache.put(request, copy);
				}
				return response;
			} catch {
				if (cached) return cached;
				if (request.mode === 'navigate') {
					const shell = await caches.match('/');
					if (shell) return shell;
				}
				return new Response('Offline', { status: 503, statusText: 'Offline' });
			}
		})()
	);
});
