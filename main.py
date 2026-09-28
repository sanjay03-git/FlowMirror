from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse

from .models import CreateIncidentRequest, ScenarioRequest, SignalModeRequest
from .camera_registry import CameraRegistry
from .twin import TrafficTwin
from .websocket_manager import ConnectionManager
from .operations_store import OperationsStore

twin = TrafficTwin()
manager = ConnectionManager()
video_directory = Path(__file__).resolve().parents[2] / "data" / "videos"
video_directory.mkdir(parents=True, exist_ok=True)
camera_registry = CameraRegistry(twin, video_directory)
operations_store = OperationsStore(Path(__file__).resolve().parents[2] / "data" / "flowmirror-operations.db")


async def simulation_loop() -> None:
    while True:
        twin.tick()
        state = twin.snapshot()
        state["camera"] = camera_registry.primary_status()
        state["cameras"] = camera_registry.all_status()
        await manager.broadcast(state)
        await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(simulation_loop())
    yield
    task.cancel()
    camera_registry.shutdown()


app = FastAPI(title="FlowMirror API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/state")
def get_state():
    state = twin.snapshot()
    state["camera"] = camera_registry.primary_status()
    state["cameras"] = camera_registry.all_status()
    return state


@app.get("/api/roads")
def get_roads():
    return list(twin.roads.values())


@app.get("/api/vehicles")
def get_vehicles():
    return list(twin.vehicles.values())


@app.get("/api/incidents")
def get_incidents():
    return [incident for incident in twin.incidents.values() if incident.status == "active"]


@app.get("/api/alerts")
def get_alerts(audience: str | None = None):
    alerts = [alert for alert in twin.alerts.values() if not alert.acknowledged]
    if audience:
        alerts = [alert for alert in alerts if alert.audience == audience]
    return alerts


@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    try:
        twin.acknowledge_alert(alert_id)
        operations_store.record("alert.acknowledged", {"alert_id": alert_id}, actor="traffic-operator")
        return {"message": "Alert acknowledged."}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Alert not found.") from exc


@app.get("/api/signals")
def get_signals():
    return list(twin.signals.values())


@app.get("/api/signals/{signal_id}/hardware")
def get_signal_hardware_state(signal_id: str):
    """Small, read-only contract for the ESP32 miniature-intersection controller."""
    signal = twin.signals.get(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found.")
    return {
        "signal_id": signal.id,
        "intersection_id": signal.intersection_id,
        "mode": signal.mode,
        "phase": "green" if signal.mode in {"adaptive", "emergency"} else "red",
        "remaining_seconds": signal.green_seconds,
        "reason": signal.reason,
        "emergency_priority": signal.mode == "emergency",
        "prototype_only": True,
    }


@app.post("/api/signals/{signal_id}/mode")
def set_signal_mode(signal_id: str, request: SignalModeRequest):
    try:
        signal = twin.set_signal_mode(signal_id, request.mode)
        operations_store.record("signal.mode_changed", signal.model_dump(mode="json"), actor="traffic-operator", severity="warning" if request.mode == "emergency" else "info")
        return signal
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Signal not found.") from exc


@app.get("/api/route")
def get_route(source: str, destination: str):
    try:
        return twin.find_route(source.upper(), destination.upper())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail="No available route.") from exc


@app.get("/api/routes/options")
def get_route_options(source: str, destination: str):
    try:
        return twin.route_options(source.upper(), destination.upper())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail="No available route options.") from exc


@app.post("/api/twin/simulate")
def simulate_twin_scenario(request: ScenarioRequest):
    try:
        result = twin.simulate_scenario(request.event, request.road_id, request.multiplier)
        operations_store.record("twin.scenario_simulated", result, actor="traffic-operator")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analytics")
def get_analytics():
    return twin.analytics()


@app.get("/api/predictions")
def get_predictions(minutes: int = 5):
    if minutes not in {5, 10, 30, 60}:
        raise HTTPException(status_code=400, detail="Prediction horizon must be 5, 10, 30, or 60 minutes.")
    return twin.predictions(minutes)


@app.get("/api/responders")
def get_responders():
    return list(twin.response_units.values())


@app.get("/api/audit-events")
def audit_events(limit: int = 100):
    return operations_store.recent(min(max(limit, 1), 500))


@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "flowmirror", "simulation": "running"}


@app.get("/api/camera/status")
def camera_status():
    return camera_registry.primary_status()


@app.get("/api/cameras")
def cameras_status():
    return camera_registry.all_status()


@app.get("/api/cameras/{camera_id}")
def camera_site_status(camera_id: str):
    try:
        return camera_registry.status(camera_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Camera not found.") from exc


@app.post("/api/cameras/{camera_id}/video")
async def upload_camera_video(camera_id: str, video: UploadFile = File(...)):
    suffix = Path(video.filename or "traffic-video.mp4").suffix.lower()
    if suffix not in {".mp4", ".avi", ".mov", ".mkv"}:
        raise HTTPException(status_code=400, detail="Upload an MP4, AVI, MOV, or MKV video file.")
    try:
        filename = camera_registry.start_video(camera_id, suffix, await video.read())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Camera not found.") from exc
    return {"message": "Video uploaded. CCTV analysis is starting.", "camera_id": camera_id, "filename": filename}


@app.post("/api/cameras/{camera_id}/webcam")
def start_webcam(camera_id: str, device_index: int = 0):
    try:
        camera_registry.start_webcam(camera_id, device_index)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Camera not found.") from exc
    return {"message": "Webcam analysis is starting.", "camera_id": camera_id}


@app.post("/api/cameras/{camera_id}/stop")
def stop_camera(camera_id: str):
    try:
        camera_registry.stop(camera_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Camera not found.") from exc
    return {"message": "Camera analysis stopped.", "camera_id": camera_id}


@app.get("/api/cameras/{camera_id}/stream")
def camera_stream(camera_id: str):
    try:
        return StreamingResponse(camera_registry.services[camera_id].mjpeg_frames(), media_type="multipart/x-mixed-replace; boundary=frame")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Camera not found.") from exc


# Backwards-compatible aliases for the first camera.
@app.post("/api/camera/video")
async def upload_primary_camera_video(video: UploadFile = File(...)):
    return await upload_camera_video("cam-01", video)

@app.post("/api/camera/webcam")
def start_primary_webcam():
    return start_webcam("cam-01")

@app.post("/api/camera/stop")
def stop_primary_camera():
    return stop_camera("cam-01")

@app.get("/api/camera/stream")
def primary_camera_stream():
    return camera_stream("cam-01")


@app.post("/api/incidents")
def create_incident(request: CreateIncidentRequest):
    try:
        incident = twin.create_incident(request.road_id, request.type, request.severity)
        operations_store.record("incident.created", incident.model_dump(mode="json"), severity=incident.severity)
        return incident
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/incidents/{incident_id}")
def clear_incident(incident_id: str):
    try:
        twin.clear_incident(incident_id)
        operations_store.record("incident.cleared", {"incident_id": incident_id}, actor="traffic-operator")
        return {"message": "Incident cleared."}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Incident not found.") from exc


@app.websocket("/ws/live")
async def live_updates(websocket: WebSocket):
    await manager.connect(websocket)
    initial_state = twin.snapshot()
    initial_state["camera"] = camera_registry.primary_status()
    initial_state["cameras"] = camera_registry.all_status()
    await websocket.send_json(initial_state)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


project_root = Path(__file__).resolve().parents[2]
compiled_command_center = project_root / "web" / "dist"
frontend_directory = compiled_command_center if compiled_command_center.exists() else project_root / "frontend"
app.mount("/", StaticFiles(directory=frontend_directory, html=True), name="dashboard")
