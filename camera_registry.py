from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .camera import TrafficCameraService
from .twin import TrafficTwin


@dataclass(frozen=True)
class CameraSite:
    id: str
    name: str
    intersection_id: str
    corridor: str
    location: str


class CameraRegistry:
    """City-scale camera service registry.

    Each site owns an independent analysis service, source, status, and stream. The
    current prototype shares the twin but production deployments can distribute sites
    across GPU workers without changing this API boundary.
    """
    sites = (
        CameraSite("cam-01", "Civic Square North", "B", "A-B", "Civic Square / North approach"),
        CameraSite("cam-02", "Central Junction", "E", "B-E", "Central Junction / inbound"),
        CameraSite("cam-03", "Transit Exchange", "H", "E-H", "Transit Exchange / northbound"),
        CameraSite("cam-04", "East Ring Corridor", "F", "C-F", "East Ring / feeder road"),
    )

    def __init__(self, twin: TrafficTwin, video_directory: Path) -> None:
        self.twin = twin
        self.video_directory = video_directory
        self.services = {site.id: TrafficCameraService(twin) for site in self.sites}

    def site(self, camera_id: str) -> CameraSite:
        for site in self.sites:
            if site.id == camera_id:
                return site
        raise KeyError(camera_id)

    def status(self, camera_id: str) -> dict:
        site = self.site(camera_id)
        return {"id": site.id, "name": site.name, "intersection_id": site.intersection_id, "corridor": site.corridor, "location": site.location, **self.services[camera_id].status()}

    def all_status(self) -> list[dict]:
        return [self.status(site.id) for site in self.sites]

    def primary_status(self) -> dict:
        active = next((site.id for site in self.sites if self.services[site.id].status()["state"] == "running"), self.sites[0].id)
        return self.status(active)

    def start_video(self, camera_id: str, suffix: str, data: bytes) -> str:
        self.site(camera_id)
        target = self.video_directory / f"{camera_id}-input{suffix}"
        target.write_bytes(data)
        self.services[camera_id].start(str(target))
        return target.name

    def start_webcam(self, camera_id: str, device_index: int = 0) -> None:
        self.site(camera_id)
        self.services[camera_id].start(device_index)

    def stop(self, camera_id: str) -> None:
        self.site(camera_id)
        self.services[camera_id].stop()

    def shutdown(self) -> None:
        for service in self.services.values():
            service.stop()
