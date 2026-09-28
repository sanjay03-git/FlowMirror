from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Intersection(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float


class Road(BaseModel):
    id: str
    from_node: str
    to_node: str
    distance_km: float
    speed_limit_kmph: float
    current_speed_kmph: float
    congestion_level: Literal["low", "medium", "high"]
    blocked: bool = False
    vehicle_count: int = 0
    incident_count: int = 0
    predicted_congestion_5m: Literal["low", "medium", "high"] = "low"


class Vehicle(BaseModel):
    id: str
    current_road_id: str
    speed_kmph: float
    route: list[str]
    route_position: int
    segment_progress: float
    latitude: float
    longitude: float
    status: Literal["moving", "slow", "stopped", "rerouted"] = "moving"
    vehicle_class: Literal["car", "truck", "bus", "motorcycle", "emergency", "bicycle"] = "car"
    direction: str = "northbound"
    lane_number: int = 1
    confidence: float = 0.94
    tracking_path: list[tuple[float, float]] = []


class Incident(BaseModel):
    id: str
    road_id: str
    type: Literal["vehicle_collision", "vehicle_overturned", "broken_vehicle", "road_block", "pedestrian_accident", "fire", "flooded_road", "fallen_tree", "construction", "suspected_accident"]
    severity: Literal["medium", "high"]
    status: Literal["active", "cleared"] = "active"
    created_at: datetime
    message: str
    affected_lanes: int = 1
    estimated_clearance_minutes: int = 20
    response_status: Literal["detected", "confirmed", "units_assigned", "en_route", "on_scene", "road_cleared", "resolved"] = "detected"


class RouteResult(BaseModel):
    source: str
    destination: str
    nodes: list[str]
    roads: list[str]
    estimated_minutes: float


class CreateIncidentRequest(BaseModel):
    road_id: str = "B-E"
    type: Literal["vehicle_collision", "vehicle_overturned", "broken_vehicle", "road_block", "pedestrian_accident", "fire", "flooded_road", "fallen_tree", "construction", "suspected_accident"] = "suspected_accident"
    severity: Literal["medium", "high"] = "high"


class Alert(BaseModel):
    id: str
    audience: Literal["traveller", "police", "traffic_control"]
    priority: Literal["info", "warning", "critical"]
    title: str
    message: str
    road_id: str
    created_at: datetime
    acknowledged: bool = False


class TrafficSignal(BaseModel):
    id: str
    intersection_id: str
    mode: Literal["adaptive", "emergency"] = "adaptive"
    active_road_id: str
    phase_label: str
    green_seconds: int
    reason: str
    incoming_vehicle_count: int = 0
    outgoing_vehicle_count: int = 0
    queue_length: int = 0
    predicted_wait_seconds: int = 0
    decision_confidence: float = 0.90


class ResponseUnit(BaseModel):
    id: str
    incident_id: str
    unit_type: Literal["police", "ambulance", "fire"]
    origin: str
    destination_road_id: str
    eta_minutes: int
    progress_percent: int = 0
    status: Literal["units_assigned", "en_route", "on_scene", "available"] = "units_assigned"


class SignalModeRequest(BaseModel):
    mode: Literal["adaptive", "emergency"]


class ScenarioRequest(BaseModel):
    event: Literal["road_closure", "traffic_surge", "flood", "construction", "signal_failure"]
    road_id: str
    multiplier: float = 2.0
