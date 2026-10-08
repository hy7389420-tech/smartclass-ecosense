# SmartClass EcoSense - Project Context

> Condensed master context. If you have the original long "Master Project Context"
> document, you can paste it below the "Extra detail" heading at the end of this file.

## 1. Role of the AI assistant
Act as senior software architect, AI/computer-vision engineer, backend + frontend developer,
database architect, cybersecurity advisor, UI/UX designer, tester, mentor and documentation helper.
The user is a beginner/intermediate student. Explain difficult ideas in very simple language:
what we are doing, why, how it works, what technology, what to do next.
Always prefer: SIMPLE -> WORKING -> TESTED -> SECURE -> SCALABLE -> ADVANCED.

## 2. Project overview
**Name:** SmartClass EcoSense
**Full title:** AI-Powered Sustainable Classroom Presence, Analytics & Resource Optimization System

Traditional attendance answers only "present or absent?".
EcoSense answers "how long was the student actually inside the classroom during the lecture?"

Events recorded: ENTRY, EXIT, RETURN, LECTURE_START, LECTURE_END, MANUAL_CORRECTION.
Derived values: inside duration, outside duration, number of exits, number of returns.

Concept flow:
Student presence -> entry/exit detection -> presence duration -> classroom occupancy analytics
-> AI pattern/trend/anomaly insights -> admin dashboard -> resource optimization -> sustainable campus.

**Positioning:** "An AI-powered classroom presence, analytics, and sustainable resource optimization
platform." Do NOT call it "just an AI attendance system" or "just face recognition".
Innovation = Presence + Duration + Analytics + AI + Privacy + Sustainability + Resource Optimization.

**Competition:** NIRMAAN (theme: Sustainable Engineering, includes "Any other innovative ideas"),
also hackathons, innovation and smart-campus competitions, college exhibitions.

## 3. Example (used for tests and demo)
Lecture 10:00-11:00. Student A: entry 10:02, exit 10:30, return 10:42, lecture end 11:00.
- Inside = 48 min, Outside = 12 min, Exits = 1, Returns = 1.
- Formula: Presence Duration = Lecture End - Entry Time - Outside Duration.

Classroom example: 60 students, 55 inside, 3 outside, 2 absent -> occupancy about 91.7%.
Utilization = average occupied / capacity x 100 (e.g. 42/60 = 70%).

## 4. Users and roles
- **ADMIN:** manages users, roles, classes, students, faculty, classrooms, cameras, settings, retention, audit logs.
- **HOD:** department-level analytics, occupancy, student presence, trends, reports, AI insights, alerts.
- **FACULTY:** only assigned classes: presence, entry/exit events, reports.
- **STUDENT:** only own attendance, presence %, entry/exit history, outside duration. Never other students' data.

## 5. Core features
1. Smart attendance (foundation only)
2. Entry, exit, return detection with timestamp + confidence
3. Presence duration and outside duration (per lecture, day, week, month)
4. Exit frequency per lecture
5. Classroom occupancy (inside, outside, absent, capacity, occupancy %)
6. Classroom utilization (underutilized / overutilized rooms)
7. Reports: daily, weekly, monthly

## 6. AI features (use only where it adds real value)
- Pattern detection, anomaly detection, trend analysis, behavioral pattern summary (no judging the reason)
- AI summary in plain language
- Later: natural-language HOD assistant that queries only authorized structured data
- Simple calculations use normal programming, NOT AI.

**AI must NOT:** punish or accuse students, make disciplinary decisions, assume why a student left,
publicly rank students, generate sensitive personal judgments, or treat computer-vision output as 100% accurate.
Say: "Unusual activity detected. Please verify."

## 7. Architecture (high level)
Camera/Webcam -> Computer Vision -> Person Detection -> Tracking -> Identity Association (if approved)
-> Entry/Exit Event Detection -> Backend API (FastAPI) -> Database -> Analytics Engine + AI Engine -> React Dashboard.

Keep three layers separate: PERSON DETECTION, PERSON IDENTITY, EVENT TRACKING.
Identity layer must be replaceable (face recognition is NOT always required; QR/RFID or other options possible).
Future edge AI: process video locally, send only event data to server.

## 8. Privacy and security (core requirements, not optional)
- Collect minimum data. No continuous raw video storage. Prefer local/edge processing.
- Store only required events. Encrypt sensitive data. Role-based access. Audit logs.
- Data retention policy with automatic deletion. Manual correction and review.
- Inform users about monitoring. Avoid unnecessary biometric storage. No public rankings.
- Security: authentication, authorization, RBAC, encrypted communication, secure passwords,
  session management, API security, input validation, rate limiting, secret management.
- Get institutional approval before real deployment. Do not claim legal compliance unless professionally verified.
- This is a technical prototype until all deployment requirements are formally satisfied.

## 9. Accuracy, manual correction, failure handling
- Computer vision is imperfect: lighting, occlusion, camera angle, similar faces, network or camera failure.
- Use confidence scores, event validation, manual correction, error logging, fallback states.
- Low confidence -> "Low confidence event detected - manual verification required."
- Faculty/HOD can correct events. Keep audit log: original event, correction, who, when, reason.
- Camera offline -> show "Camera Offline". Never silently generate fake attendance.
- Network failure -> store events locally, sync later. Database down -> fail safely.

## 10. Sustainability
- Show classroom capacity, average and peak occupancy, utilization, underutilized and overutilized rooms,
  unused periods. Helps room allocation, scheduling, reducing unnecessary room usage.
- Smart energy optimization (lights, fans, HVAC, IoT) is FUTURE and can be SIMULATED in the prototype.
- Do NOT claim real energy savings unless measured. Say "occupancy data can support resource optimization."

## 11. Technology stack
Python, FastAPI, SQLite (MVP) then PostgreSQL, React, OpenCV + object detection + tracking (later),
LLM API where useful, VS Code, Git, GitHub, Docker (later).
Future: Kotlin + Jetpack Compose mobile app, IoT, edge AI, n8n for automation (n8n must NOT replace core backend).

## 12. MVP definition
1. User login
2. Classroom
3. Student list
4. Lecture creation
5. Simulated/real presence events (ENTRY, EXIT, RETURN)
6. Presence duration
7. Outside duration
8. Dashboard
9. Basic reports

Prove first: ONE classroom + ONE lecture + presence + entry/exit + duration + dashboard.

**Do NOT build first:** mobile app, complex AI agent, IoT hardware, multiple cameras, multi-campus,
advanced LLM assistant, complex cloud, real-time energy control, huge database architecture.

## 13. Database (possible tables)
users, students, faculty, departments, classes, classrooms, lectures, cameras, presence_events,
attendance_records, presence_sessions, analytics, alerts, audit_logs, system_settings.

presence_event fields: event_id, student_id, classroom_id, lecture_id, event_type, timestamp,
confidence, source, created_at.

## 14. Backend and frontend
- Backend: Python + FastAPI. Responsibilities: auth, authorization, APIs, DB, event processing,
  analytics, reports, AI integration, alerts, security.
- Frontend: React. Simple, modern, professional, responsive, accessible. Avoid clutter and unnecessary animation.
- HOD dashboard: cards (Total, Inside, Outside, Absent, Occupancy, Utilization), charts (occupancy over time,
  presence trends, outside duration, room utilization), student table
  (Name, Status, Entry, Exit, Return, Inside time, Outside time), AI insights, reports.

## 15. Testing and metrics
Test: unit (duration, occupancy, utilization), integration, API, UI, security (unauthorized access, role escalation),
performance, real-world (lighting, angles, crowding).
Measure: detection/tracking/identity accuracy, entry/exit accuracy, false positive/negative rate,
processing time, API response time, uptime. Do not claim accuracy without testing.

## 16. Development phases (summary; details in ROADMAP.md)
0 Requirements, 1 System design, 2 Simulated MVP, 3 Computer vision, 4 Identity, 5 Backend, 6 Dashboard,
7 Analytics, 8 AI, 9 Security and privacy, 10 Sustainability, 11 Testing, 12 Demo, 13 Pilot.
(The practical build order used for this repo is in ROADMAP.md.)

## 17. Demo story
Student enters -> dashboard updates -> student exits -> shows outside -> student returns -> duration updates
-> analytics update -> AI insight -> utilization appears -> sustainability note appears.
Be honest about what is simulated and what is real.

## 18. Limitations (be honest)
Camera accuracy, occlusion, lighting, identity errors, privacy concerns, network failure, hardware limits,
false detection, institutional approval, deployment cost.

## 19. Pitch lines
**One-line:** "SmartClass EcoSense is an AI-powered, privacy-first smart classroom platform that analyzes actual
student presence, classroom occupancy and utilization to generate actionable insights and support sustainable
resource optimization."

**Problem statement:** Traditional attendance gives only present/absent and cannot show actual presence throughout
a lecture. Institutions also lack detail on occupancy, utilization, entry/exit patterns, presence and outside
duration, and unusual activity.

## 20. Product roadmap (long term)
V1 attendance + presence + entry/exit + duration + dashboard
V2 AI analytics, anomaly detection, trends, reports
V3 privacy-first edge AI, multiple classrooms, advanced security
V4 sustainability analytics, classroom and resource optimization
V5 IoT: smart lighting, HVAC, energy analytics
V6 AI campus assistant, predictive analytics, smart scheduling
V7 commercial SaaS, multi-campus
Do NOT try to build V7 now. Build one classroom, one lecture, one working flow, test, improve, scale.

## 21. Instructions for any AI assistant
- Use this document as permanent context. Do not change architecture unnecessarily. Keep the MVP simple.
- Give step-by-step instructions and say exactly which file to create or modify.
- Do not generate unnecessary code. Do not add unnecessary AI.
- Keep privacy, security, sustainability, competition needs and scalability in mind.
- Test every important feature. Explain errors simply.
- Never claim something works unless tested. Never claim energy savings without measurement.
- Never claim legal compliance without verification. Never treat AI predictions as absolute truth.
- Never automatically punish or accuse students. Prefer human review for sensitive decisions.
- Classify new features: CORE / IMPORTANT / ADVANCED / OPTIONAL / FUTURE.
- Always say: "Build this first", then "Build this next", then "Build this later".

---

## Extra detail
(Paste the original full Master Project Context here if you want the complete version.)
