// Node 22 regression test of the actual reconstructed service worker.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const sourceRoot = process.argv[2];
if (!sourceRoot) throw new Error('SOURCE_ROOT_REQUIRED');
const script = fs.readFileSync(path.join(sourceRoot, 'public', 'sw.js'), 'utf8');
const handlers = {};
const removed = [];
const stored = new Map();
let calls = 0;
const cache = {
  match: async request => stored.get(request.url),
  put: async (request, response) => { stored.set(request.url, response); },
};
const caches = {
  keys: async () => ['skyed-growthbridge-shell-v2.3.0', 'another-app'],
  delete: async name => { removed.push(name); return true; },
  open: async () => cache,
};
const self = {
  location: { origin: 'https://growth.skyed.org' },
  skipWaiting: async () => undefined,
  clients: { claim: async () => undefined },
  addEventListener: (name, fn) => { handlers[name] = fn; },
};
const response = {
  ok: true, type: 'basic', headers: { has: () => false },
  clone() { return this; },
};
vm.runInNewContext(script, {
  self, caches, URL, Set,
  fetch: async () => { calls++; return response; },
}, { filename: 'GrowthBridge service worker' });

function intercept(url, mode = 'cors') {
  let captured;
  handlers.fetch({
    request: { url, method: 'GET', mode },
    respondWith(promise) { captured = promise; },
  });
  return captured;
}

(async () => {
  for (const url of ['/parent/', '/teacher/', '/', '/api/v1/parent/children', '/students/child-a/photo.webp']) {
    assert.equal(intercept('https://growth.skyed.org' + url, 'navigate'), undefined);
    assert.equal(intercept('https://growth.skyed.org' + url, 'cors'), undefined);
  }
  const asset = 'https://growth.skyed.org/assets/index-B6rCBfks.js';
  await intercept(asset);
  await intercept(asset);
  assert.equal(calls, 1);
  assert.ok(stored.has(asset));
  let activation;
  handlers.activate({ waitUntil(p) { activation = p; } });
  await activation;
  assert.deepEqual(removed, ['skyed-growthbridge-shell-v2.3.0']);
  console.log('GROWTHBRIDGE_BROWSER_CACHE_PRIVACY=PASS');
})().catch(err => { console.error(err); process.exitCode = 1; });
