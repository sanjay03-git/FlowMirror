# FlowMirror final handoff

## What is included

- Enterprise traffic-command dashboard and a browser traveller-alert view
- Digital-twin road network with live vehicle simulation, congestion, incidents,
  prediction, scenario modelling, route options, emergency dispatch, and adaptive signals
- Multi-camera registry and CCTV analysis pipeline
- Model-backed YOLO + ByteTrack adapter, with a fixed-camera OpenCV fallback
- ESP32 miniature LED signal-controller firmware and wiring instructions
- SQLite operations audit log, API endpoints, backend tests, and container setup

## Run locally

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

For the enterprise React command center, build `web/` with `pnpm install` then
`pnpm build`; FastAPI automatically serves `web/dist`. Until it is built, it
serves the included functional static dashboard in `frontend/`.

## Demonstration scope

This is a deployable software prototype. The ESP32 integration is for a
low-voltage miniature LED intersection only; it must never connect to real
traffic signals or emergency-dispatch systems. Production field use requires
certified controller gateways, approved emergency-service integrations, a
validated local detection model, security controls, and agency authorization.
