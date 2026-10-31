import { useCallback, useEffect, useRef, useState } from 'react'
import {
  correctReviewEvent,
  decideSuggestion,
  getCurrentUser,
  getDashboard,
  getAlerts,
  getEngagement,
  getLectures,
  getReviewEvents,
  getSuggestionHistory,
  getSuggestions,
  login,
  resolveReviewEvent,
} from './services/api'
import './App.css'

const statusLabels = {
  INSIDE: 'Inside',
  OUTSIDE: 'Outside',
  ABSENT: 'Absent',
  PARTIAL: 'Partial',
}

function formatTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function formatLocalTimestamp(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (part) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function localTimestampToUtc(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toISOString()
}

function readSavedLectureId() {
  try {
    return localStorage.getItem('ecosense_selected_lecture_id') || ''
  } catch {
    return ''
  }
}

function saveSelectedLectureId(lectureId) {
  try {
    localStorage.setItem('ecosense_selected_lecture_id', lectureId)
  } catch {
    // Lecture selection still works when browser storage is unavailable.
  }
}

function formatAlertTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString([], {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDecisionTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString([], {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatLectureWindow(lecture) {
  if (!lecture?.start_time || !lecture?.end_time) return ''
  const start = new Date(lecture.start_time)
  const end = new Date(lecture.end_time)
  const date = start.toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })
  const startTime = start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const endTime = end.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return `${date} · ${startTime}–${endTime}`
}

function App() {
  const [token] = useState(() => localStorage.getItem('ecosense_token'))
  const [user, setUser] = useState(null)
  const [lectures, setLectures] = useState([])
  const [lectureId, setLectureId] = useState('')
  const [dashboard, setDashboard] = useState(null)
  const [engagement, setEngagement] = useState(null)
  const [suggestions, setSuggestions] = useState([])
  const [suggestionsState, setSuggestionsState] = useState('loading')
  const [suggestionHistory, setSuggestionHistory] = useState([])
  const [suggestionHistoryState, setSuggestionHistoryState] = useState('loading')
  const [alerts, setAlerts] = useState([])
  const [alertsState, setAlertsState] = useState('loading')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [engagementState, setEngagementState] = useState('loading')
  const [reviewEvents, setReviewEvents] = useState([])
  const [reviewState, setReviewState] = useState('loading')
  const [reviewReason, setReviewReason] = useState({})
  const dashboardRequestRef = useRef(false)

  const loadDashboard = useCallback(async (selectedId) => {
    if (!selectedId || dashboardRequestRef.current) return
    dashboardRequestRef.current = true
    setLoading(true)
    setError('')
    setEngagement(null)
    setEngagementState('loading')
    setSuggestionHistory([])
    setSuggestionHistoryState('loading')
    setSuggestions([])
    setSuggestionsState('loading')
    setAlerts([])
    setAlertsState('loading')
    setReviewEvents([])
    setReviewState('loading')
    try {
      const [dashboardData, engagementData, suggestionData, suggestionHistoryData, reviewEventsData, alertsData] = await Promise.all([
        getDashboard(selectedId).catch((dashboardError) => ({
          __error: dashboardError,
        })),
        getEngagement(selectedId).catch((engagementError) => ({
          __error: engagementError,
        })),
        getSuggestions(selectedId).catch((suggestionsError) => ({
          __error: suggestionsError,
        })),
        getSuggestionHistory(selectedId).catch((historyError) => ({
          __error: historyError,
        })),
        getReviewEvents(selectedId).catch((reviewError) => ({
          __error: reviewError,
        })),
        getAlerts().catch((alertsError) => ({
          __error: alertsError,
        })),
      ])
      if (dashboardData.__error) {
        if (dashboardData.__error.status === 401) {
          localStorage.removeItem('ecosense_token')
          window.location.reload()
          return
        }
        setError(dashboardData.__error.message)
      } else {
        setDashboard(dashboardData)
      }
      if (engagementData.__error) {
        setEngagement(null)
        setEngagementState(engagementData.__error.status === 404 ? 'no_data' : 'error')
      } else {
        setEngagement(engagementData)
        setEngagementState(engagementData.windows?.length ? 'ready' : 'no_data')
      }
      if (suggestionData.__error) {
        setSuggestions([])
        setSuggestionsState('error')
      } else {
        setSuggestions(suggestionData)
        setSuggestionsState(suggestionData.length ? 'ready' : 'no_data')
      }
      if (suggestionHistoryData.__error) {
        setSuggestionHistory([])
        setSuggestionHistoryState('error')
      } else {
        setSuggestionHistory(suggestionHistoryData)
        setSuggestionHistoryState(suggestionHistoryData.length ? 'ready' : 'no_data')
      }
      if (reviewEventsData.__error) {
        setReviewEvents([])
        setReviewState('error')
      } else {
        setReviewEvents(reviewEventsData.items)
        setReviewState(reviewEventsData.items.length ? 'ready' : 'no_data')
      }
      if (alertsData.__error) {
        setAlerts([])
        setAlertsState('error')
      } else {
        setAlerts(alertsData.items)
        setAlertsState(alertsData.items.length ? 'ready' : 'no_data')
      }
    } catch (err) {
      if (err.status === 401) {
        localStorage.removeItem('ecosense_token')
        window.location.reload()
        return
      }
      setError(err.message)
    } finally {
      setLoading(false)
      dashboardRequestRef.current = false
    }
  }, [])

  useEffect(() => {
    if (!token) return
    Promise.all([getCurrentUser(), getLectures()])
      .then(([userData, lectureData]) => {
        setUser(userData)
        setLectures(lectureData.items)
        const savedLectureId = readSavedLectureId()
        const savedLecture = lectureData.items.find(
          (lecture) => String(lecture.id) === savedLectureId,
        )
        const selected = savedLecture
          || lectureData.items.find((lecture) => lecture.status === 'live')
          || lectureData.items[0]
        if (selected) {
          setLectureId(String(selected.id))
          saveSelectedLectureId(String(selected.id))
          loadDashboard(selected.id)
        }
      })
      .catch((err) => {
        if (err.status === 401) {
          localStorage.removeItem('ecosense_token')
          window.location.reload()
          return
        }
        setError(err.message)
      })
  }, [token, loadDashboard])

  useEffect(() => {
    if (!lectureId) return undefined
    const interval = window.setInterval(() => loadDashboard(lectureId), 5000)
    return () => window.clearInterval(interval)
  }, [lectureId, loadDashboard])

  async function handleLogin(event) {
    event.preventDefault()
    setError('')
    const form = new FormData(event.currentTarget)
    try {
      const result = await login(form.get('email'), form.get('password'))
      localStorage.setItem('ecosense_token', result.access_token)
      window.location.reload()
    } catch (err) {
      setError(err.message)
    }
  }

  function handleLogout() {
    localStorage.removeItem('ecosense_token')
    window.location.reload()
  }

  async function handleDecision(suggestionId, decision) {
    try {
      await decideSuggestion(suggestionId, decision)
      await loadDashboard(lectureId)
    } catch (err) {
      setError(err.message)
    }
  }

    async function handleResolveReview(eventId) {
      const reason = reviewReason[eventId]?.trim()
      if (!reason) {
        setError('Human review reason is required.')
        return
      }
      try {
        await resolveReviewEvent(eventId, reason)
        await loadDashboard(lectureId)
      } catch (err) {
        setError(err.message)
      }
    }

    async function handleCorrectReview(eventId) {
      const form = document.querySelector(`[data-review-form="${eventId}"]`)
      const formData = new FormData(form)
      const reason = String(formData.get('reason') || '').trim()
      const timestamp = String(formData.get('timestamp') || '')
      if (!reason || !timestamp) {
        setError('Correction timestamp and human review reason are required.')
        return
      }
      try {
        await correctReviewEvent(eventId, {
          student_id: formData.get('student_id') ? Number(formData.get('student_id')) : null,
          event_type: formData.get('event_type'),
          timestamp: localTimestampToUtc(timestamp),
          reason,
        })
        await loadDashboard(lectureId)
      } catch (err) {
        setError(err.message)
      }
    }

  if (!token) {
    return (
      <main className="login-page">
        <form className="login-card" onSubmit={handleLogin}>
          <div className="brand-mark">SE</div>
          <p className="eyebrow">SmartClass EcoSense</p>
          <h1>Classroom presence</h1>
          <p className="login-copy">Monitor attendance and observable class activity.</p>
          <label>Email<input name="email" type="email" required /></label>
          <label>Password<input name="password" type="password" required /></label>
          {error && (
            <p className="error">
              {error}
              {error.includes('Email or password') && (
                <> <span>Use the configured account password.</span></>
              )}
            </p>
          )}
          <button className="primary-button" type="submit">Sign in</button>
        </form>
      </main>
    )
  }

  const cards = dashboard?.cards
  const selectedLecture = lectures.find((lecture) => String(lecture.id) === String(lectureId))
  const estimates = engagement?.windows || []
  const validEstimates = estimates.filter((window) => window.estimate !== null)
  const chartPoints = validEstimates.map((window, index) => {
    const x = validEstimates.length === 1 ? 50 : index * 100 / (validEstimates.length - 1)
    const y = 110 - window.estimate * 100
    return `${x},${y}`
  }).join(' ')

  return (
    <div className="app-shell">
      <header>
        <div>
          <p className="eyebrow">SmartClass EcoSense</p>
          <h1>Presence dashboard</h1>
        </div>
        <div className="header-actions">
          <span>{user?.email}</span>
          <button className="text-button" onClick={handleLogout}>Sign out</button>
        </div>
      </header>

      <section className="toolbar">
        <label>
          Lecture
          <select value={lectureId} onChange={(event) => {
            setLectureId(event.target.value)
            saveSelectedLectureId(event.target.value)
            loadDashboard(event.target.value)
          }}>
            {lectures.map((lecture) => (
              <option key={lecture.id} value={lecture.id}>
                {lecture.subject} · #{lecture.id} · {lecture.status}
              </option>
            ))}
          </select>
        </label>
        <div className="refresh-state">{loading ? 'Updating...' : 'Auto-refresh: 5 seconds'}</div>
      </section>
      {selectedLecture && (
        <div className="lecture-context">
          <span className={`lecture-status lecture-status-${selectedLecture.status}`}>
            {selectedLecture.status}
          </span>
          <span>{formatLectureWindow(selectedLecture)}</span>
        </div>
      )}

      {error && <p className="error banner">{error}</p>}
      {dashboard?.camera_status === 'Camera Offline' && (
        <p className="camera-alert">Camera Offline — no new presence events are being confirmed.</p>
      )}

      {cards && (
        <>
          <section className="stats-grid">
            {[
              ['Total', cards.total_students], ['Present', cards.present],
              ['Inside', cards.inside], ['Outside', cards.outside],
              ['Absent', cards.absent], ['Occupancy', `${cards.occupancy_percent.toFixed(1)}%`],
            ].map(([label, value]) => (
              <article className="stat-card" key={label}><span>{label}</span><strong>{value}</strong></article>
            ))}
          </section>

          <section className="camera-panel-grid">
            <article className="panel camera-details-panel">
              <div className="panel-heading">
                <div><p className="eyebrow">Camera status</p><h2>Connection details</h2></div>
                <span className={`camera-status camera-status-${dashboard.camera_status === 'Online' ? 'online' : 'offline'}`}>
                  {dashboard.camera_status}
                </span>
              </div>
              <dl className="camera-details">
                <div><dt>Classroom ID</dt><dd>{selectedLecture?.classroom_id ?? '-'}</dd></div>
                <div><dt>Lecture ID</dt><dd>{dashboard.lecture_id}</dd></div>
                <div><dt>Video display</dt><dd>Not available; metadata only</dd></div>
              </dl>
              <p className="metadata-note">
                Camera status describes recent system activity, not detection accuracy.
              </p>
            </article>

            <article className="panel camera-alerts-panel">
              <div className="panel-heading">
                <div><p className="eyebrow">Operational monitoring</p><h2>Camera alerts</h2></div>
              </div>
              {alertsState === 'loading' && (
                <p className="empty-state">Loading camera alerts...</p>
              )}
              {alertsState === 'no_data' && (
                <p className="empty-state">No unresolved camera alerts.</p>
              )}
              {alertsState === 'error' && (
                <p className="empty-state error-state">Camera alerts could not be loaded. The dashboard will retry automatically.</p>
              )}
              {alertsState === 'ready' && alerts.map((alert) => (
                <div className="camera-alert-item" key={alert.id}>
                  <div>
                    <strong>{alert.kind.replaceAll('_', ' ')}</strong>
                    <span>{alert.severity} · {formatAlertTime(alert.created_at)}</span>
                  </div>
                  <p>{alert.message}</p>
                </div>
              ))}
            </article>
          </section>

          <section className="content-grid">
            <article className="panel">
              <div className="panel-heading">
                <div><p className="eyebrow">Observable activity</p><h2>Activity estimate</h2></div>
                {engagement?.average_estimate != null && <strong>{engagement.average_estimate.toFixed(2)}</strong>}
              </div>
              {engagementState === 'loading' && !engagement && (
                <p className="empty-state">Loading activity estimate...</p>
              )}
              {engagementState === 'error' && (
                <p className="empty-state error-state">Activity estimate could not be loaded. The dashboard will retry automatically.</p>
              )}
              {chartPoints ? (
                <svg className="activity-chart" viewBox="0 0 100 120" preserveAspectRatio="none" aria-label="Observable activity chart">
                  <polyline points={chartPoints} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
                </svg>
              ) : engagementState === 'no_data' ? (
                <p className="empty-state">No activity windows available.</p>
              ) : null}
              <p className="estimate-note">
                {engagement?.estimate_note || 'Activity estimates are indicators, not proof of attention or engagement.'}
              </p>
            </article>

            <article className="panel suggestions-panel">
              <div className="panel-heading">
                <div><p className="eyebrow">Teaching support</p><h2>Neutral suggestions</h2></div>
              </div>
              {suggestionsState === 'loading' && <p className="empty-state">Loading neutral suggestions...</p>}
              {suggestionsState === 'error' && <p className="empty-state error-state">Neutral suggestions could not be loaded. Try refreshing.</p>}
              {suggestionsState === 'no_data' && <p className="empty-state">No suggestions for this lecture.</p>}
              {suggestions.map((suggestion) => (
                <div className="suggestion" key={suggestion.id}>
                  <strong>{suggestion.title}</strong>
                  <p>{suggestion.text}</p>
                  <div className="decision-actions">
                    <button onClick={() => handleDecision(suggestion.id, 'accepted')}>Accept</button>
                    <button onClick={() => handleDecision(suggestion.id, 'rejected')}>Reject</button>
                    <button onClick={() => handleDecision(suggestion.id, 'ignored')}>Ignore</button>
                  </div>
                </div>
              ))}
              <div className="suggestion-history">
                <h3>Decision history</h3>
                {suggestionHistoryState === 'loading' && (
                  <p className="empty-state">Loading suggestion decisions...</p>
                )}
                {suggestionHistoryState === 'no_data' && (
                  <p className="empty-state">No suggestion decisions recorded yet.</p>
                )}
                {suggestionHistoryState === 'error' && (
                  <p className="empty-state error-state">Decision history could not be loaded. Try refreshing.</p>
                )}
                {suggestionHistoryState === 'ready' && suggestionHistory.map((decision) => (
                  <div className="suggestion-history-item" key={decision.id}>
                    <div>
                      <strong>Suggestion {decision.suggestion_id}</strong>
                      <span>{formatDecisionTime(decision.decided_at)} · Actor {decision.decided_by}</span>
                    </div>
                    <span className={`decision-badge decision-${decision.decision}`}>
                      {decision.decision}
                    </span>
                    {decision.note && <p>{decision.note}</p>}
                  </div>
                ))}
              </div>
            </article>
          </section>

          <article className="panel table-panel">
            <div className="panel-heading">
              <div><p className="eyebrow">Lecture {dashboard.lecture_id}</p><h2>Student presence</h2></div>
              <span className="review-count">{reviewEvents.length} pending review</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Student</th><th>Status</th><th>Entry</th><th>Exit</th><th>Inside</th><th>Outside</th><th>Review</th></tr></thead>
                <tbody>
                  {dashboard.students.map((student) => (
                    <tr key={student.student_id}>
                      <td><strong>{student.name}</strong><small>{student.student_code}</small></td>
                      <td><span className={`status status-${student.status.toLowerCase()}`}>{statusLabels[student.status]}</span></td>
                      <td>{formatTime(student.first_entry)}</td>
                      <td>{formatTime(student.last_exit)}</td>
                      <td>{student.inside_minutes.toFixed(1)} min</td>
                      <td>{student.outside_minutes.toFixed(1)} min</td>
                      <td>{student.flagged ? 'Required' : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </>
      )}
      <article className="panel review-panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Human review</p><h2>Events needing verification</h2></div>
          {reviewState === 'ready' && <span className="review-count">{reviewEvents.length} event(s)</span>}
        </div>
        <p className="review-note">
          Review observable camera data only. Correct or resolve an event with a clear reason;
          do not use this workflow to accuse or rank a student.
        </p>
        {reviewState === 'loading' && <p className="empty-state">Loading review events...</p>}
        {reviewState === 'error' && <p className="empty-state error-state">Review events could not be loaded. Try refreshing.</p>}
        {reviewState === 'no_data' && <p className="empty-state">No events flagged for review</p>}
        {reviewEvents.map((event) => (
          <form className="review-item" data-review-form={event.id} key={event.id}>
            <div className="review-summary">
              <strong>{event.student_code_raw || event.student_id || 'Unknown student identity'}</strong>
              <span>{event.event_type} · {formatTime(event.timestamp_utc)}</span>
            </div>
            <div className="review-fields">
              <label>Event type
                <select name="event_type" defaultValue="ENTRY">
                  <option value="ENTRY">ENTRY</option>
                  <option value="EXIT">EXIT</option>
                </select>
              </label>
              <label>Timestamp
                <input name="timestamp" type="datetime-local" defaultValue={formatLocalTimestamp(event.timestamp_utc)} />
              </label>
              {!event.student_id && (
                <label>Student ID
                  <input name="student_id" type="number" min="1" required />
                </label>
              )}
              <label className="review-reason">Review reason
                <input
                  name="reason"
                  value={reviewReason[event.id] || ''}
                  onChange={(change) => setReviewReason((current) => ({
                    ...current,
                    [event.id]: change.target.value,
                  }))}
                  maxLength="1000"
                  required
                />
              </label>
            </div>
            <div className="decision-actions">
              <button type="button" onClick={() => handleCorrectReview(event.id)}>Save human correction</button>
              <button type="button" className="secondary-button" onClick={() => handleResolveReview(event.id)}>Resolve without correction</button>
            </div>
          </form>
        ))}
      </article>
    </div>
  )
}

export default App
