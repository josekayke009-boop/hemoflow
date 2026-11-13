/* HemoFlow — service worker (PWA).
 *
 * O que ele faz:
 *  - guarda a "casca" do sistema (HTML, CSS, JS, ícones) para o app abrir mesmo sem internet;
 *  - sempre tenta a rede primeiro: online, o usuário vê sempre a versão mais nova;
 *  - NUNCA guarda respostas da API (/api/...): dados de doadores, contas etc. não ficam
 *    neste cache. O modo offline (só consulta do estoque) é tratado no app.js, com
 *    dados sem informação pessoal.
 */
const VERSION = "hemoflow-v3";
const SHELL = [
  "/",
  "/app.js",
  "/login-bg.js",
  "/login/h-simbolo-3d.webp",
  "/login/h-mascara.webp",
  "/styles.css",
  "/hemoflow-icon.png",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(VERSION).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== VERSION).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  // Só arquivos do próprio HemoFlow; API e sites externos (fontes) seguem direto para a rede.
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/") || url.pathname === "/healthz") return;

  const isPage = request.mode === "navigate";
  event.respondWith(
    fetch(request)
      .then(response => {
        if (response.ok) {
          const copy = response.clone();
          // Páginas são guardadas como "/" (a casca é a mesma para qualquer endereço).
          caches.open(VERSION).then(cache => cache.put(isPage ? "/" : request, copy));
        }
        return response;
      })
      .catch(() => caches.match(isPage ? "/" : request).then(cached => cached || Response.error()))
  );
});
