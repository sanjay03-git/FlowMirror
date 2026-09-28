# FlowMirror Project Guide

## What is implemented

The application is a camera-first prototype of a traffic digital twin. A fixed CCTV video or local webcam is analysed in OpenCV using background segmentation and contour filtering. The backend derives vehicle counts, a movement-based speed estimate, congestion state, and stopped-traffic risk; it synchronises that state to corridor B-E, manages incidents, calculates traffic-aware alternative routes, and broadcasts state to the dashboard.

## Architecture

`CCTV video/webcam -> OpenCV vehicle-motion analysis -> Twin state -> FastAPI/WebSocket API -> Command Center dashboard`

## Core functional requirements covered

1. CCTV video upload and local-webcam ingestion.
2. Moving vehicle-sized-object detection and annotated camera stream.
3. Congestion classification (low, medium, high) from camera density and movement.
4. Rule-based stopped-traffic risk and duplicate-safe incident reporting.
5. Dynamic route calculation using a congestion-weighted shortest path.
6. Live alerts, route visualisation, rolling performance analytics, and priority-corridor health.
7. Audience-specific in-app alerts for travellers, police, and traffic-control operators.
8. Adaptive signal-phase prototype: the highest-demand connected corridor receives the green phase; incidents trigger emergency-clearance priority.

## Run and validate

From `backend`, activate `.venv`, then run `uvicorn app.main:app --reload`. Open the dashboard at `http://127.0.0.1:8000`.

Upload a fixed-camera traffic video, wait for vehicle boxes, and check that the camera status and vehicle-detection card update. Use origin `B`, destination `H`, calculate the route, create the test accident, then calculate again. The original path uses `B-E`; the second path must avoid `B-E`.

After the incident, verify three linked outcomes: the traveller app displays a route alert, the police/control-room panel displays two critical messages that can be acknowledged, and signals connected to the affected road switch to an emergency-clearance phase. This demonstrates the full accident-to-response workflow.

## Extensions for Phase II

- Replace simulated telemetry with a controlled GPS/MQTT adapter.
- Persist snapshots and incident history in PostgreSQL/PostGIS.
- Add authenticated operator accounts and audit logging.
- Use validated video analytics or prediction models only with suitable data and consent.
