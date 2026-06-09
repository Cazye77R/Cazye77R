const BASE_URL = import.meta.env.DEV ? 'http://localhost:8000' : ''

function getToken() {
  return localStorage.getItem('token')
}

async function apiFetch(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Anfrage fehlgeschlagen')
  }
  if (res.status === 204) return null
  return res.json()
}

// ── Auth ─────────────────────────────────────────────────────────

export async function login(username, password) {
  const body = new URLSearchParams({ username, password })
  const res = await fetch(`${BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Anmeldung fehlgeschlagen')
  }
  return res.json()
}

// ── Users ─────────────────────────────────────────────────────────

export const getMe = () => apiFetch('/api/users/me')
export const getUsers = () => apiFetch('/api/users/')
export const createUser = (data) => apiFetch('/api/users/', { method: 'POST', body: JSON.stringify(data) })
export const updateUser = (id, data) => apiFetch(`/api/users/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteUser = (id) => apiFetch(`/api/users/${id}`, { method: 'DELETE' })
export const changePassword = (data) => apiFetch('/api/users/me/password', { method: 'PUT', body: JSON.stringify(data) })

// ── Settings: Branding ────────────────────────────────────────────

export const getBranding = () => apiFetch('/api/settings/branding')
export const updateBranding = (data) => apiFetch('/api/settings/branding', { method: 'PUT', body: JSON.stringify(data) })

// ── Module ────────────────────────────────────────────────────────

export const getMyModules = () => apiFetch('/api/modules')
export const getUserModules = (id) => apiFetch(`/api/modules/users/${id}`)
export const setUserModules = (id, keys) => apiFetch(`/api/modules/users/${id}`, { method: 'PUT', body: JSON.stringify({ module_keys: keys }) })

// ── Reittagebuch: Tiertypen ──────────────────────────────────────

export const getTierTypen = () => apiFetch('/api/reittagebuch/tiertypen')
export const updateTierTypen = (typen) => apiFetch('/api/reittagebuch/tiertypen', { method: 'PUT', body: JSON.stringify({ typen }) })

// ── Reittagebuch: Tiere ───────────────────────────────────────────

export const getTiere = () => apiFetch('/api/reittagebuch/tiere')
export const createTier = (data) => apiFetch('/api/reittagebuch/tiere', { method: 'POST', body: JSON.stringify(data) })
export const updateTier = (id, data) => apiFetch(`/api/reittagebuch/tiere/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteTier = (id) => apiFetch(`/api/reittagebuch/tiere/${id}`, { method: 'DELETE' })

// ── Reittagebuch: Einträge ────────────────────────────────────────

function buildQs(params) {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) })
  const s = q.toString()
  return s ? `?${s}` : ''
}

export const getEintraege = (params = {}) => apiFetch(`/api/reittagebuch/eintraege${buildQs(params)}`)
export const getEintrag = (id) => apiFetch(`/api/reittagebuch/eintraege/${id}`)
export const createEintrag = (data) => apiFetch('/api/reittagebuch/eintraege', { method: 'POST', body: JSON.stringify(data) })
export const updateEintrag = (id, data) => apiFetch(`/api/reittagebuch/eintraege/${id}`, { method: 'PUT', body: JSON.stringify(data) })
export const deleteEintrag = (id) => apiFetch(`/api/reittagebuch/eintraege/${id}`, { method: 'DELETE' })

// ── Reittagebuch: Stats ───────────────────────────────────────────

export const getStats = (params = {}) => apiFetch(`/api/reittagebuch/stats${buildQs(params)}`)

// ── Reittagebuch: Downloads ───────────────────────────────────────

async function downloadBlob(url, filename) {
  const token = getToken()
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error('Download fehlgeschlagen')
  const blob = await res.blob()
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}

export const downloadExport = (params = {}) =>
  downloadBlob(
    `/api/reittagebuch/export${buildQs(params)}`,
    `hoftagebuch_${params.von || 'alle'}_${params.bis || 'alle'}.xlsx`,
  )

export const downloadBackup = () =>
  downloadBlob('/api/reittagebuch/backup', 'toolbox.db')
