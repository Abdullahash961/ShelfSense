/**
 * ShelfSense API Client
 *
 * Thin fetch wrappers for every backend endpoint.
 * All functions return parsed JSON or throw on error.
 */

const BASE = '/api';

async function request(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Accept': 'application/json', ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

// ── Analysis ──────────────────────────────────────────────────────────

export async function getStatus() {
  return request(`${BASE}/status`);
}

export async function getAlerts(statuses = 'LOW,EMPTY') {
  return request(`${BASE}/alerts?statuses=${statuses}`);
}

export async function getZoneHistory(zoneId, limit = 50) {
  return request(`${BASE}/zones/${zoneId}/history?limit=${limit}`);
}

export async function analyzeShelf(imageFile) {
  const form = new FormData();
  form.append('image', imageFile);

  const res = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Analysis failed: ${res.status}`);
  }

  return res.json();
}

// ── Zones CRUD ────────────────────────────────────────────────────────

export async function getZones() {
  return request(`${BASE}/zones`);
}

export async function getZone(zoneId) {
  return request(`${BASE}/zones/${zoneId}`);
}

export async function createZone(data) {
  return request(`${BASE}/zones`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function updateZone(zoneId, data) {
  return request(`${BASE}/zones/${zoneId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export async function deleteZone(zoneId) {
  return request(`${BASE}/zones/${zoneId}`, { method: 'DELETE' });
}

// ── References ────────────────────────────────────────────────────────

export async function getReferences() {
  return request(`${BASE}/references`);
}

export async function uploadReference(imageFile) {
  const form = new FormData();
  form.append('image', imageFile);

  const res = await fetch(`${BASE}/references`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed: ${res.status}`);
  }

  return res.json();
}

export async function deleteReference(filename) {
  return request(`${BASE}/references/${filename}`, { method: 'DELETE' });
}

// ── Camera ────────────────────────────────────────────────────────────

export async function getCameraStatus() {
  return request(`${BASE}/camera/status`);
}

export async function connectCamera(source = 0) {
  return request(`${BASE}/camera/connect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source }),
  });
}

export async function disconnectCamera() {
  return request(`${BASE}/camera/disconnect`, { method: 'POST' });
}

/**
 * Returns the URL for the live MJPEG camera feed.
 * Use directly in an <img> src attribute.
 */
export function getCameraFeedUrl() {
  return `${BASE}/camera/feed`;
}

/**
 * Returns the URL for a single camera snapshot (JPEG image).
 * Append a cache-busting query param to force refresh.
 */
export function getSnapshotUrl() {
  return `${BASE}/camera/snapshot?t=${Date.now()}`;
}

// ── Scheduler ─────────────────────────────────────────────────────────

export async function getSchedulerStatus() {
  return request(`${BASE}/scheduler/status`);
}

export async function startScheduler(intervalMinutes = null) {
  const body = intervalMinutes ? { interval_minutes: intervalMinutes } : {};
  return request(`${BASE}/scheduler/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function stopScheduler() {
  return request(`${BASE}/scheduler/stop`, { method: 'POST' });
}

export async function triggerAnalysis() {
  return request(`${BASE}/scheduler/trigger`, { method: 'POST' });
}
