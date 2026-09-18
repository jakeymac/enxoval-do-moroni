// Mesma origem em produção; o servidor do Vite encaminha /api para o Django.
const BASE = '/api'

const ACCESS = 'enxoval.access'
const REFRESH = 'enxoval.refresh'

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS)
  },
  get refresh() {
    return localStorage.getItem(REFRESH)
  },
  set({ access, refresh }) {
    if (access) localStorage.setItem(ACCESS, access)
    if (refresh) localStorage.setItem(REFRESH, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS)
    localStorage.removeItem(REFRESH)
  },
}

export class ApiError extends Error {
  constructor(status, data) {
    super(typeof data === 'string' ? data : 'Não foi possível completar a ação.')
    this.status = status
    this.data = data
  }

  /** Achata o {campo: [mensagens]} do DRF em algo exibível. */
  get detail() {
    const d = this.data
    if (!d) return this.message
    if (typeof d === 'string') return d
    if (d.detail) return d.detail
    return Object.entries(d)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : v}`)
      .join('\n')
  }
}

async function parse(res) {
  const text = await res.text()
  try {
    return text ? JSON.parse(text) : null
  } catch {
    return text
  }
}

async function rawRequest(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new ApiError(res.status, await parse(res))
  return res.status === 204 ? null : parse(res)
}

async function refreshAccess() {
  if (!tokens.refresh) return false
  try {
    const data = await rawRequest('/auth/refresh/', {
      method: 'POST',
      body: { refresh: tokens.refresh },
      auth: false,
    })
    tokens.set(data)
    return true
  } catch {
    tokens.clear()
    return false
  }
}

export async function request(path, options = {}) {
  try {
    return await rawRequest(path, options)
  } catch (err) {
    // Uma segunda tentativa depois de renovar o token expirado em silêncio.
    if (err.status === 401 && options.auth !== false && (await refreshAccess())) {
      return rawRequest(path, options)
    }
    throw err
  }
}

export const api = {
  login: (username, password) =>
    request('/auth/login/', { method: 'POST', body: { username, password }, auth: false }),

  // --- dono: um único enxoval, sem id na URL ---
  getRegistry: () => request('/registry/'),
  updateRegistry: (body) => request('/registry/', { method: 'PATCH', body }),

  createItem: (body) => request('/items/', { method: 'POST', body }),
  updateItem: (id, body) => request(`/items/${id}/`, { method: 'PATCH', body }),
  deleteItem: (id) => request(`/items/${id}/`, { method: 'DELETE' }),

  listClaims: () => request('/claims/'),
  updateClaim: (id, body) => request(`/claims/${id}/`, { method: 'PATCH', body }),

  // --- público, sem login ---
  publicRegistry: () => request('/public/', { auth: false }),
  claimItem: (itemId, body) =>
    request(`/public/items/${itemId}/claim/`, { method: 'POST', body, auth: false }),
}
