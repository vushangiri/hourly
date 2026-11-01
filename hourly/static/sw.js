// Cache only public assets and an account-free shell. Never cache API/auth responses.
const VERSION='hourly-shell-v2';
const ASSETS=['/offline','/static/app.css','/static/app.js','/static/icon-192.png','/static/icon-512.png','/static/manifest.webmanifest'];
self.addEventListener('install',e=>e.waitUntil(caches.open(VERSION).then(c=>c.addAll(ASSETS))));
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('hourly-shell-')&&k!==VERSION).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('message',e=>{if(e.data?.type==='ACTIVATE')self.skipWaiting();});
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(u.origin!==self.location.origin||e.request.method!=='GET')return;
 if(e.request.mode==='navigate'&&u.pathname==='/'){e.respondWith(fetch(e.request).catch(()=>caches.match('/offline')));return;}
 if(ASSETS.includes(u.pathname)){e.respondWith(caches.match(e.request).then(c=>c||fetch(e.request)));}
});
