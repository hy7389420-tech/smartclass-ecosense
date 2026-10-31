# SmartClass EcoSense Demo Script

The demo takes approximately three minutes and uses demo data only. Do not
describe simulated values as measured camera accuracy.

## Before the demo

1. Start the FastAPI backend on port 8000.
2. Start the React frontend on port 5173.
3. Sign in with a locally provisioned demo account.
4. Select the live demo lecture.
5. Confirm that the backend and demo data are available.

## 0:00-0:30 - Lecture and dashboard

Show the lecture selector and lecture status/time context. Explain that the
dashboard is scoped to the selected lecture, including status, local start and
end time, and presence cards.

- Total and Present describe the current lecture population.
- Inside, Outside, and Absent show derived presence states.
- Occupancy is a calculated dashboard value, not an energy or accuracy claim.

## 0:30-1:00 - Camera and operational alerts

Show camera connection details, classroom ID, lecture ID, video-display status,
and operational alerts.

If the camera is offline, explain that the UI reports `Camera Offline` and does
not invent presence confirmation. Camera status is operational metadata, not
detection accuracy.

## 1:00-1:30 - Student presence and engagement

Show the student presence table, entry and exit information, inside and outside
duration, and the aggregate observable activity panel. Describe aggregate
activity estimates as indicators from available signals, not proof of
attention, behavior, or individual intent.

## 1:30-2:15 - Human review

Open the human-review panel. Choose a flagged event and show:

1. Empty reason submission is blocked.
2. Human correction requires a reason and saves an audited correction.
3. Resolve without correction requires a reason and removes the event from the
   active flagged queue.
4. A refresh does not restore a correctly persisted resolved event.

Explain that review supports a human correction. It must not accuse, blame,
rank, or punish any student or faculty member.

## 2:15-2:45 - Teaching suggestions and history

Open the neutral teaching suggestions panel. Present a suggestion only as
advisory aggregate support for teacher judgment. Accept, reject, or ignore it
and show the decision in history.

Do not claim that the suggestion is proven, accurate, or energy-saving.

## 2:45-3:00 - Close and known limitations

Close with the implemented demo scope:

- FastAPI presence and review APIs.
- React lecture dashboard and audit-aware review workflow.
- Synthetic simulator and optional aggregate CV/audio inputs.

State honestly:

- Live camera and microphone validation remains pending unless a documented test
  has been completed.
- Detection accuracy has not been measured.
- Energy savings have not been measured.
- Raw video is not continuously stored.
- AI output is advisory and remains subject to human review.
