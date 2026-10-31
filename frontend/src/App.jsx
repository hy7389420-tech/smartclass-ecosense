import { useCallback, useEffect, useRef, useState } from 'react'
import {
  correctReviewEvent,
  decideSuggestion,
  getCurrentUser,
  getDashboard,
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
  const [suggestionHistory, setSuggestionHistory] = useState([])
  const [suggestionHistoryState, setSuggestionHistoryState] = useState('loading')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [engagementState, setEngagementState] = useState('loading')
  const [reviewEvents, setReviewEvents] = useState([])
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
    try {
      const [dashboardData, engagementData, suggestionData, suggestionHistoryData, reviewEventsData] = await Promise.all([
        getDashboard(selectedId),
        getEngagement(selectedId).catch((engagementError) => ({
          __error: engagementError,
        })),
        getSuggestions(selectedId).catch(() => []),
        getSuggestionHistory(selectedId).catch((historyError) => ({
          __error: historyError,
        })),
        getReviewEvents(selectedId).catch(() => ({ items: [] })),
      ])
      setDashboard(dashboardData)
      if (engagementData.__error) {
        setEngagement(null)
        setEngagementState(engagementData.__error.status === 404 ? 'no_data' : 'error')
      } else {
        setEngagement(engagementData)
        setEngagementState(engagementData.windows?.length ? 'ready' : 'no_data')
      }
      setSuggestions(suggestionData)
      if (suggestionHistoryData.__error) {
        setSuggestionHistory([])
        setSuggestionHistoryState('error')
      } else {
        setSuggestionHistory(suggestionHistoryData)
        setSuggestionHistoryState(suggestionHistoryData.length ? 'ready' : 'no_data')
      }
      setReviewEvents(reviewEventsData.items)
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
        const selected = lectureData.items.find((lecture) => lecture.status === 'live')
          || lectureData.items[0]
        if (selected) {
          setLectureId(String(selected.id))
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
          timestamp,
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
              {suggestions.length === 0 && <p className="empty-state">No suggestions for this lecture.</p>}
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

          {reviewEvents.length > 0 && (
            <article className="panel review-panel">
              <div className="panel-heading">
                <div><p className="eyebrow">Human review</p><h2>Events needing verification</h2></div>
                <span className="review-count">{reviewEvents.length} event(s)</span>
              </div>
              <p className="review-note">
                Review observable camera data only. Correct or resolve an event with a clear reason;
                do not use this workflow to accuse or rank a student.
              </p>
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
                      <input name="timestamp" type="datetime-local" defaultValue={event.timestamp_utc.slice(0, 16)} />
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
          )}

          <article className="panel table-panel">
            <div className="panel-heading">
              <div><p className="eyebrow">Lecture {dashboard.lecture_id}</p><h2>Student presence</h2></div>
              <span className="review-count">{dashboard.pending_review_count} pending review</span>
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
    </div>
  )
}

export default App
