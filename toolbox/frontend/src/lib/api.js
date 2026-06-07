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

export const getMe = () => apiFetch('/api/users/me')

export const getUsers = () => apiFetch('/api/users/')

export const createUser = (data) =>
  apiFetch('/api/users/', { method: 'POST', body: JSON.stringify(data) })

export const updateUser = (id, data) =>
  apiFetch(`/api/users/${id}`, { method: 'PUT', body: JSON.stringify(data) })

export const deleteUser = (id) =>
  apiFetch(`/api/users/${id}`, { method: 'DELETE' })
