const CACHE_NAME = 'pose-analysis-v1';
const urlsToCache = [
  '/',
  '/history',
  '/static/manifest.json'
  // 여기에 추가적인 CSS나 JS 파일이 있다면 추가합니다.
];

// 서비스 워커 설치
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

// 요청에 대한 응답
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // 캐시에 있으면 캐시에서, 없으면 네트워크에서 가져옴
        return response || fetch(event.request);
      })
  );
});
