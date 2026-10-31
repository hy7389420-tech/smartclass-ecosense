const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export async function apiRequest(path, options = {}) {
  const token = localStorage.getItem('ecosense_token')
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    let code = null
    try {
      const body = await response.json()
      message = body?.error?.message || body?.detail || message
      code = body?.error?.code || null
    } catch {
      // Keep the status-based message when the response is not JSON.
    }
    const requestError = new Error(message)
    requestError.status = response.status
    requestError.code = code
    requestError.retryAfter = response.headers.get('Retry-After')
    throw requestError
  }

  if (response.status === 204) return null
  return response.json()
}

export function login(email, password) {
  return apiRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export function getCurrentUser() {
  return apiRequest('/auth/me')
}

export function getLectures() {
  return apiRequest('/lectures?limit=100&offset=0')
}

export function getDashboard(lectureId) {
  return apiRequest(`/dashboard/${lectureId}`)
}

export function getAlerts() {
  const params = new URLSearchParams({ unresolved_only: 'true', limit: '100', offset: '0' })
  return apiRequest(`/alerts?${params}`)
}

export function getEngagement(lectureId) {
  return apiRequest(`/lectures/${lectureId}/engagement`)
}

export function getSuggestions(lectureId) {
  return apiRequest(`/lectures/${lectureId}/suggestions`)
}

export function getSuggestionHistory(lectureId) {
  return apiRequest(`/lectures/${lectureId}/suggestions/log`)
}

export function decideSuggestion(suggestionId, decision) {
  return apiRequest(`/suggestions/${suggestionId}/decision`, {
    method: 'POST',
    body: JSON.stringify({ decision }),
  })
}

export function getReviewEvents(lectureId) {
  const params = new URLSearchParams({ limit: '100', offset: '0' })
  return apiRequest(`/review/events?${params}`).then((queue) => ({
    ...queue,
    items: queue.items.filter((event) => String(event.lecture_id) === String(lectureId)),
  }))
}

export function correctReviewEvent(eventId, payload) {
  return apiRequest(`/events/${eventId}/correct`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function resolveReviewEvent(eventId, reason) {
  return apiRequest(`/review/events/${eventId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}
