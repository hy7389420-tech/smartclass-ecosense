# SmartClass EcoSense - Step-by-Step Schedule

Rule: har step ke baad TEST, phir COMMIT. Ek time par ek hi step.
Labels: CORE / IMPORTANT / ADVANCED / OPTIONAL / FUTURE
Time andaza hai (roz 2-3 ghante ke hisaab se). Deadline kam ho to "Week 6 ke baad wale" steps chhod do.

---

## STATUS ABHI

DONE (CV): 4.1 capture, 4.2 detection, 4.3 tracking, 4.4 line crossing, 4.5a events.jsonl, 4.6 manual identity.
Ab: Week 1 se shuru.

---

## WEEK 1: Presence logic (Python, bina server) [CORE]

| Day | Kaam | File | Test |
|---|---|---|---|
| 1 | Backend venv alag banao (`.venv-backend`), folder banao | backend/ | `pytest` chale |
| 2 | `calculate_presence()` | backend/app/services/presence.py | entry 10:02, exit 10:30, return 10:42 -> 48 in, 12 out |
| 3 | Edge-case tests (never exit, never return, multiple exits, absent) | backend/tests/test_presence.py | sab pass |
| 4 | Sustained-presence rule (N second + confidence) | cv/sustained.py + test, config.py mein thresholds | 1-2 second dikhne wale ko present na mane |
| 5 | Sample data generator (8 lectures, 1 mein 10:25-10:40 exit spike) | backend/sample_data/generate_sample.py | file bane |

## WEEK 2: Backend + Database [CORE]

| Day | Kaam | File | Test |
|---|---|---|---|
| 1 | FastAPI + `GET /health` | backend/app/main.py | browser mein OK |
| 2 | SQLite + tables (students, classrooms, lectures, presence_events) | database.py, models.py, schemas.py | tables bane |
| 3 | Create/list APIs: students, classrooms, lectures | routes/ | /docs page se test |
| 4 | `POST /events` + validation (pehla event ENTRY ho, EXIT sirf andar wale ka) | routes/events.py | galat sequence reject ho |
| 5 | **4.5b:** `cv/event_sender.py` ko `POST /events` se jodo (file bhi chalti rahe, backup) | cv/event_sender.py | camera event DB mein dikhe |
| 6 | `GET /dashboard/{lecture_id}` | routes/dashboard.py | inside/outside/absent numbers sahi |

## WEEK 3: Frontend dashboard [CORE]

| Day | Kaam | File | Test |
|---|---|---|---|
| 1 | React (Vite) setup, backend se data fetch | frontend/src/services/api.js | console mein data |
| 2 | Cards: Total, Inside, Outside, Absent, Occupancy | components/StatCards.jsx | numbers backend se match |
| 3 | Student table (Name, Status, Entry, Exit, Return, Inside, Outside) | components/StudentTable.jsx | simulate data dikhe |
| 4 | Auto-refresh (har 3-5 sec) + "Camera Offline" banner | App.jsx | camera band karo, banner aaye |
| 5 | Camera -> backend -> dashboard poora demo chalao | - | line cross karo, dashboard update |

**MVP COMPLETE yahan.** Tag `v0.2-mvp`, 2 minute ka screen recording banao (backup demo).

## WEEK 4: Analytics + Sustainability [IMPORTANT]

| Day | Kaam | File | Test |
|---|---|---|---|
| 1-2 | Occupancy, utilization, peak time | services/analytics.py + test | haath se hisaab match |
| 3 | Anomaly: 5-minute windows, mean + 2xstd, kam se kam 3 exits | services/anomaly.py + test | sample data ka 10:25-10:40 spike pakde |
| 4 | Trend: pichle 3-4 lectures se compare (data kam ho to "data kam hai") | services/trends.py + test | - |
| 5 | Dashboard par utilization chart + insights panel | UtilizationChart.jsx, InsightsPanel.jsx | neutral wording dikhe |
| 5 | Simulated suggestion: "Room utilization 33%, chhota room consider karein" | analytics.py | energy saving ka number NAHI |

## WEEK 5: Engagement estimates (OpenCV + Audio) [ADVANCED]

Kam features lo, par sahi tareeke se. Sab class-level aggregate, individual student ka attention score NAHI.

| Day | Kaam | File | Test |
|---|---|---|---|
| 1-2 | Movement level (frame differencing, 5-min window) | cv/motion.py + test (fake frames) | hilne par level badhe |
| 3 | Inactivity duration (kam movement wale windows) | cv/motion.py | still video par inactivity dikhe |
| 4 | Head orientation estimate (MediaPipe, front ki taraf wale % ) | cv/headpose.py | docs check karke; sirf aggregate |
| 5-6 | Audio activity: level + voice-activity per window, sirf numbers save, raw audio nahi | audio/audio_features.py + test | chup/bolne par alag number |
| 7 | `activity_windows` table + `POST /activity` + API | backend | DB mein windows dikhe |

## WEEK 6: Fusion + Agent suggestions [ADVANCED]

| Day | Kaam | File | Test |
|---|---|---|---|
| 1-2 | Fusion: movement + head + audio ko ek "observable activity level" timeline mein jodo (simple weighted average, weights config mein) | backend/app/services/fusion.py + test | timeline banti hai |
| 3 | Decline detection (last windows ka average pehle se kam) | services/fusion.py | fake data mein decline pakde |
| 4 | Rule-based suggestions: quiz, discussion, question, example (neutral wording) | services/suggestions.py | har rule ka test |
| 5 | Teacher Accept / Reject buttons, decision log | frontend + backend | choice save ho |
| 6 | Dashboard: engagement graph + "estimate, not proof" label | frontend | label hamesha dikhe |
| 7 | Optional: LLM sirf wording ke liye (local model ya fixed template default; aggregate numbers hi bhejo) | services/ai_summary.py | API fail ho to template chale |

## WEEK 7: Login, correction, reports, security [IMPORTANT / ADVANCED]

| Day | Kaam | Test |
|---|---|---|
| 1-2 | Login (JWT, password hashing), roles HOD / FACULTY | galat role par 403 |
| 3 | Manual correction + audit_logs (original, correction, kisne, kab, reason) | audit entry bane |
| 4 | Reports: session summary (PDF ya CSV) | file download ho |
| 5 | Retention: purana data auto-delete script, README mein likho | script test |
| 6-7 | Security checks: .env, input validation, rate limit, unauthorized access test | sab pass |

## WEEK 8: Testing, accuracy, demo [CORE]

| Day | Kaam |
|---|---|
| 1-2 | Real test: alag roshni, alag camera angle, 2-3 log. 20 baar line cross karo, kitne sahi event bane note karo (entry/exit accuracy, false positive/negative). Sirf MEASURE kiya hua number hi likhna. |
| 3 | `pytest` poora chalao, test count note karo |
| 4 | README + screenshots + architecture diagram + limitations section |
| 5 | Demo script rehearse: enter -> dashboard -> exit -> return -> duration -> insight -> utilization -> suggestion |
| 6 | Slides (14 slides, MASTER_PROMPT.md Section 67 jaisa), viva Q&A practice |
| 7 | Buffer / bug fix. Repo public karne se pehle secrets check |

---

## Technology-wise summary (kaun si cheez kahan)

**OpenCV / CV (cv/):** capture, YOLO detection, tracking, line crossing (done); sustained presence, motion/inactivity, head orientation (Week 1, 5).
**Audio (audio/):** level + voice activity per window, sirf numbers (Week 5).
**Backend (FastAPI):** DB, events API, dashboard API, analytics, anomaly, trend, fusion, suggestions, auth, audit (Week 2, 4, 6, 7).
**Frontend (React):** cards, table, charts, insights, engagement graph, accept/reject, login (Week 3, 4, 6, 7).
**Database:** SQLite pehle, PostgreSQL optional baad mein.
**AI:** pehle rules/statistics; LLM sirf text likhne ke liye, optional.
**Git:** har step ke baad commit; week ke end par push + tag.

## Agar time kam hai (minimum demo)

Week 1 + 2 + 3 + Week 4 ka analytics + Week 8. Engagement (Week 5-6) ko "Future scope / proposed" bolo.
Jo bana nahi, use "implemented" mat bolo.

## Build this first / next / later

- **First:** Week 1 (presence.py + tests + sustained presence)
- **Next:** Week 2 aur 3 (backend + dashboard = MVP)
- **Later:** Week 4 se 8 (analytics, engagement estimates, agent, security, demo)
