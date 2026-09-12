// Thin wrapper around the browser fetch() for every call to the eProcure API.
//
// The backend now authenticates requests with a session cookie rather than
// the old (client-trusted, therefore meaningless) X-User-Role header, so every
// API call must carry credentials for the cookie to be sent/received - see
// `credentials: 'include'` below. It also centralizes the one bit of shared
// behavior every caller needs: a 401 (no valid session) means the user is
// logged out as far as the server is concerned, so the stale client-side
// session is cleared and the user is sent back to /login. A 403 (wrong role /
// not the resource's owner) is left to each caller's existing `!response.ok`
// handling, since that already surfaces the server's error message.
const AUTH_STORAGE_KEYS = ['eProcureUser', 'supplier_id', 'supplier_status']

const clearStoredAuth = () => {
  try {
    AUTH_STORAGE_KEYS.forEach((key) => window.sessionStorage.removeItem(key))
  } catch {
    // Storage may be unavailable (private mode / disabled cookies) - ignore.
  }
}

export async function apiFetch(input, init = {}) {
  const response = await fetch(input, { ...init, credentials: 'include' })

  const url = typeof input === 'string' ? input : (input && input.url) || ''
  const isLoginRequest = url.includes('/api/login')
  if (response.status === 401 && !isLoginRequest) {
    clearStoredAuth()
    if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
      window.location.assign('/login')
    }
  }

  return response
}
