# FlowMirror Production Deployment Profile

## High-performance runtime

Use a GPU-capable deployment host for model-backed surveillance. The repository supports a model path through `FLOWMIRROR_YOLO_MODEL` and uses Ultralytics tracking with `bytetrack.yaml` when that variable is configured.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install ultralytics
export FLOWMIRROR_YOLO_MODEL=/absolute/path/to/validated-traffic-model.pt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

On macOS, use a current Python environment with PyTorch MPS support where suitable. For sustained multi-camera operations, use a CUDA-capable Linux GPU server and a locally validated detection model.

## Container deployment

The included container profile starts the FastAPI service and its dashboard on
port 8000. From the project root:

```bash
docker compose up --build -d
docker compose ps
```

Confirm the service at `http://localhost:8000/api/health`. The compose volume
preserves uploaded CCTV videos and the operations audit database between
container restarts. For GPU surveillance, use a CUDA-enabled base image and
install the matching PyTorch/Ultralytics runtime in a separately tested image;
do not assume a CPU image can provide production camera throughput.

## Detection model policy

The fallback motion detector is only for a fixed-camera demo. A real deployment must configure a validated model that identifies the required classes: car, truck, bus, motorcycle, bicycle, pedestrian, and emergency vehicle. Standard COCO weights cover all except emergency vehicle; use a city-specific custom model for that class.

## Frontend

The enterprise command-center frontend is in `web/`.

```bash
cd web
pnpm install
pnpm build
```

FastAPI automatically serves `web/dist` when it exists. It otherwise serves the legacy static dashboard, so the production command-center bundle must be built before deployment.

## Integration boundaries

- CCTV/RTSP adapters: feed camera frames into `TrafficCameraService`.
- CAD/dispatch: replace `_dispatch_response_units` with an authenticated emergency-service adapter.
- Signal controllers: replace the prototype `update_signals` output with a vendor gateway protected by approval, audit, and fail-safe rules.
- Maps/routing: supply authoritative road geometry and traffic feeds; retain the route-options API contract.

Never connect physical traffic signals or emergency-dispatch systems without certified integrations, access controls, audit trails, operator approval, and jurisdictional authorization.
