from __future__ import annotations

import random
from datetime import datetime, timezone

import networkx as nx

from .models import Alert, Incident, ResponseUnit, Road, RouteResult, TrafficSignal, Vehicle
from .network import INTERSECTIONS, ROADS, create_road_graph


class TrafficTwin:
    """In-memory digital twin for the initial prototype."""

    def __init__(self) -> None:
        self.graph: nx.Graph = create_road_graph()
        self.roads: dict[str, Road] = {road.id: road.model_copy(deep=True) for road in ROADS}
        self.incidents: dict[str, Incident] = {}
        self.alerts: dict[str, Alert] = {}
        self.signals: dict[str, TrafficSignal] = self._create_signals()
        self.response_units: dict[str, ResponseUnit] = {}
        self.vehicles: dict[str, Vehicle] = {}
        self._rng = random.Random(7)
        self._incident_counter = 0
        self.history: list[dict] = []
        self._create_vehicles(24)
        self.refresh_road_state()
        self.record_history()

    def _create_signals(self) -> dict[str, TrafficSignal]:
        return {
            "signal-B": TrafficSignal(id="signal-B", intersection_id="B", active_road_id="B-E", phase_label="North-South flow", green_seconds=30, reason="Normal adaptive operation."),
            "signal-E": TrafficSignal(id="signal-E", intersection_id="E", active_road_id="B-E", phase_label="North-South flow", green_seconds=30, reason="Normal adaptive operation."),
            "signal-H": TrafficSignal(id="signal-H", intersection_id="H", active_road_id="E-H", phase_label="North-South flow", green_seconds=30, reason="Normal adaptive operation."),
        }

    def road_between(self, start: str, end: str) -> str:
        return self.graph.edges[start, end]["road_id"]

    def _create_vehicles(self, count: int) -> None:
        nodes = list(self.graph.nodes)
        classes = ["car", "car", "car", "car", "truck", "bus", "motorcycle", "emergency", "bicycle"]
        for number in range(1, count + 1):
            source, destination = self._rng.sample(nodes, 2)
            route = nx.shortest_path(self.graph, source, destination)
            road_id = self.road_between(route[0], route[1])
            start = INTERSECTIONS[route[0]]
            vehicle_class = self._rng.choice(classes)
            self.vehicles[f"vehicle-{number:02d}"] = Vehicle(
                id=f"vehicle-{number:02d}", current_road_id=road_id,
                speed_kmph=self._rng.uniform(20, 38), route=route,
                route_position=0, segment_progress=self._rng.random() * 0.8,
                latitude=start.latitude, longitude=start.longitude,
                vehicle_class=vehicle_class, lane_number=self._rng.randint(1, 3),
                direction=f"{route[0]}→{route[1]}", confidence=round(self._rng.uniform(.86, .99), 2),
                tracking_path=[(start.latitude, start.longitude)],
            )

    def _new_route(self, source: str, avoid_blocked: bool = True) -> list[str]:
        choices = [node for node in self.graph.nodes if node != source]
        destination = self._rng.choice(choices)
        try:
            return self.find_route(source, destination).nodes
        except nx.NetworkXNoPath:
            return nx.shortest_path(self.graph, source, destination)

    def tick(self, seconds: float = 2.0) -> None:
        for vehicle in self.vehicles.values():
            if vehicle.route_position >= len(vehicle.route) - 1:
                vehicle.route = self._new_route(vehicle.route[-1])
                vehicle.route_position = 0
                vehicle.segment_progress = 0.0

            start_id = vehicle.route[vehicle.route_position]
            end_id = vehicle.route[vehicle.route_position + 1]
            road_id = self.road_between(start_id, end_id)
            road = self.roads[road_id]
            vehicle.current_road_id = road_id

            if road.blocked:
                vehicle.speed_kmph = 0
                vehicle.status = "stopped"
                current_node = start_id
                try:
                    vehicle.route = self._new_route(current_node)
                    vehicle.route_position = 0
                    vehicle.segment_progress = 0.0
                    vehicle.status = "rerouted"
                except nx.NetworkXNoPath:
                    continue
            else:
                load = sum(v.current_road_id == road_id for v in self.vehicles.values())
                factor = 1.0 if load <= 3 else 0.65 if load <= 6 else 0.3
                vehicle.speed_kmph = max(5, road.speed_limit_kmph * factor * self._rng.uniform(0.82, 1.0))
                vehicle.status = "slow" if factor < 1 else "moving"
                vehicle.segment_progress += (vehicle.speed_kmph * seconds / 3600) / road.distance_km

            if vehicle.segment_progress >= 1:
                vehicle.route_position += 1
                vehicle.segment_progress = 0.0
                if vehicle.route_position >= len(vehicle.route) - 1:
                    continue
                start_id = vehicle.route[vehicle.route_position]
                end_id = vehicle.route[vehicle.route_position + 1]
                road_id = self.road_between(start_id, end_id)
                vehicle.current_road_id = road_id

            start = INTERSECTIONS[start_id]
            end = INTERSECTIONS[end_id]
            vehicle.latitude = start.latitude + (end.latitude - start.latitude) * vehicle.segment_progress
            vehicle.longitude = start.longitude + (end.longitude - start.longitude) * vehicle.segment_progress
            vehicle.direction = f"{start_id}→{end_id}"
            vehicle.tracking_path = (vehicle.tracking_path + [(vehicle.latitude, vehicle.longitude)])[-12:]
        self.refresh_road_state()
        self.update_signals()
        self.update_response_progress()
        self.record_history()

    def record_history(self) -> None:
        """Keep a small rolling operational history for the dashboard analytics."""
        roads = list(self.roads.values())
        self.history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "average_speed_kmph": round(sum(road.current_speed_kmph for road in roads) / len(roads), 1),
            "high_congestion_roads": sum(road.congestion_level == "high" for road in roads),
            "active_incidents": sum(item.status == "active" for item in self.incidents.values()),
        })
        self.history = self.history[-90:]

    def refresh_road_state(self) -> None:
        for road in self.roads.values():
            occupants = [v.speed_kmph for v in self.vehicles.values() if v.current_road_id == road.id]
            road.vehicle_count = len(occupants)
            road.incident_count = sum(i.status == "active" and i.road_id == road.id for i in self.incidents.values())
            if road.blocked:
                road.current_speed_kmph = 0
                road.congestion_level = "high"
            elif not occupants:
                road.current_speed_kmph = road.speed_limit_kmph
                road.congestion_level = "low"
            else:
                road.current_speed_kmph = round(sum(occupants) / len(occupants), 1)
                ratio = road.current_speed_kmph / road.speed_limit_kmph
                road.congestion_level = "low" if ratio >= 0.70 else "medium" if ratio >= 0.40 else "high"
            future_pressure = road.vehicle_count + road.incident_count * 6
            road.predicted_congestion_5m = "high" if road.congestion_level == "high" or future_pressure >= 7 else "medium" if road.congestion_level == "medium" or future_pressure >= 4 else "low"

    def update_signals(self) -> None:
        """Select the incoming road that receives the next green phase.

        This is a deliberately visible prototype controller: blocked/incident roads
        receive emergency-clearance priority, then the most congested connected road
        receives a longer green phase. Physical signal hardware is not controlled.
        """
        for signal in self.signals.values():
            node = signal.intersection_id
            connected = [data["road_id"] for _, _, data in self.graph.edges(node, data=True)]
            scored: list[tuple[int, str]] = []
            for road_id in connected:
                road = self.roads[road_id]
                score = {"low": 1, "medium": 4, "high": 7}[road.congestion_level]
                if road.blocked:
                    score += 10
                scored.append((score, road_id))
            score, selected = max(scored, key=lambda item: item[0])
            road = self.roads[selected]
            incoming = sum(self.roads[road_id].vehicle_count for road_id in connected)
            outgoing = max(0, int(incoming * .68))
            signal.incoming_vehicle_count = incoming
            signal.outgoing_vehicle_count = outgoing
            signal.queue_length = max(0, incoming - outgoing)
            signal.predicted_wait_seconds = 20 + signal.queue_length * 7
            signal.decision_confidence = .96 if road.blocked else .92 if road.congestion_level == "high" else .88
            if road.blocked:
                signal.mode = "emergency"
                signal.green_seconds = 75
                signal.phase_label = f"Emergency clearance · {selected}"
                signal.reason = "Incident detected: reserve a clearance phase for emergency movement."
            else:
                signal.mode = "adaptive"
                signal.green_seconds = 55 if road.congestion_level == "high" else 42 if road.congestion_level == "medium" else 30
                signal.phase_label = f"Priority flow · {selected}"
                signal.reason = f"{road.congestion_level.title()} congestion has the highest measured demand."
            signal.active_road_id = selected

    def find_route(self, source: str, destination: str) -> RouteResult:
        if source not in self.graph or destination not in self.graph:
            raise ValueError("Source and destination must be valid intersection IDs.")

        def cost(start: str, end: str, data: dict) -> float:
            road = self.roads[data["road_id"]]
            if road.blocked:
                return float("inf")
            speed = max(road.current_speed_kmph, 5)
            multiplier = {"low": 1.0, "medium": 1.5, "high": 3.0}[road.congestion_level]
            return road.distance_km / speed * 60 * multiplier

        nodes = nx.shortest_path(self.graph, source, destination, weight=cost)
        road_ids = [self.road_between(a, b) for a, b in zip(nodes, nodes[1:])]
        minutes = round(sum(cost(a, b, self.graph.edges[a, b]) for a, b in zip(nodes, nodes[1:])), 1)
        return RouteResult(source=source, destination=destination, nodes=nodes, roads=road_ids, estimated_minutes=minutes)

    def route_options(self, source: str, destination: str) -> list[dict]:
        """Compute independently scored route strategies for operator and traveller apps."""
        if source not in self.graph or destination not in self.graph:
            raise ValueError("Source and destination must be valid intersection IDs.")
        profiles = [
            ("fastest", "Fastest route", {"low": 1.0, "medium": 1.35, "high": 2.6}),
            ("least_congested", "Least congested", {"low": 1.0, "medium": 2.2, "high": 4.2}),
            ("fuel_efficient", "Fuel-efficient", {"low": .9, "medium": 1.7, "high": 3.8}),
            ("emergency", "Emergency priority", {"low": .8, "medium": 1.0, "high": 1.8}),
        ]
        output: list[dict] = []
        for key, label, multiplier in profiles:
            def weight(start: str, end: str, data: dict) -> float:
                road = self.roads[data["road_id"]]
                if road.blocked:
                    return float("inf")
                signal_bonus = .7 if key == "emergency" and any(signal.active_road_id == road.id for signal in self.signals.values()) else 1.0
                return road.distance_km / max(road.current_speed_kmph, 5) * 60 * multiplier[road.congestion_level] * signal_bonus
            nodes = nx.shortest_path(self.graph, source, destination, weight=weight)
            roads = [self.road_between(a, b) for a, b in zip(nodes, nodes[1:])]
            eta = round(sum(weight(a, b, self.graph.edges[a, b]) for a, b in zip(nodes, nodes[1:])), 1)
            distance = round(sum(self.roads[road_id].distance_km for road_id in roads), 2)
            average_speed = round(distance / (eta / 60), 1) if eta else 0.0
            traffic_score = round(sum({"low": 95, "medium": 62, "high": 27}[self.roads[road_id].congestion_level] for road_id in roads) / max(len(roads), 1))
            output.append({"strategy": key, "label": label, "nodes": nodes, "roads": roads, "eta_minutes": eta, "distance_km": distance, "delay_minutes": round(max(0, eta - distance / 40 * 60), 1), "traffic_score": traffic_score, "average_speed_kmph": average_speed, "confidence": .94 if key in {"fastest", "least_congested"} else .88})
        return output

    def simulate_scenario(self, event: str, road_id: str, multiplier: float = 2.0) -> dict:
        if road_id not in self.roads:
            raise ValueError("Road ID does not exist.")
        affected = self.roads[road_id]
        baseline = self.predictions(5)
        impacted: list[dict] = []
        for road in self.roads.values():
            adjacent = road.id == road_id or set((road.from_node, road.to_node)) & set((affected.from_node, affected.to_node))
            speed_factor = .12 if event in {"road_closure", "flood"} and road.id == road_id else (1 / multiplier if adjacent else 1.0)
            speed = round(max(3, road.current_speed_kmph * speed_factor), 1)
            level = "high" if speed / road.speed_limit_kmph < .4 else "medium" if speed / road.speed_limit_kmph < .7 else "low"
            impacted.append({"road_id": road.id, "predicted_speed_kmph": speed, "predicted_congestion": level, "affected": bool(adjacent)})
        return {"event": event, "road_id": road_id, "multiplier": multiplier, "baseline": baseline, "impact": impacted, "recommended_action": "Activate adjacent signal priority, publish traveller detours, and reserve emergency route capacity."}

    def create_incident(self, road_id: str, kind: str, severity: str) -> Incident:
        if road_id not in self.roads:
            raise ValueError("Road ID does not exist.")
        active = next((i for i in self.incidents.values() if i.road_id == road_id and i.status == "active"), None)
        if active:
            return active
        self._incident_counter += 1
        incident = Incident(
            id=f"incident-{self._incident_counter:02d}", road_id=road_id, type=kind,
            severity=severity, created_at=datetime.now(timezone.utc),
            message=f"{kind.replace('_', ' ').title()} reported on road {road_id}. Rerouting is active.",
        )
        self.incidents[incident.id] = incident
        self.roads[road_id].blocked = True
        self.refresh_road_state()
        self.update_signals()
        self._create_incident_alerts(incident)
        self._dispatch_response_units(incident)
        incident.response_status = "units_assigned"
        self.record_history()
        return incident

    def _dispatch_response_units(self, incident: Incident) -> None:
        """Prototype dispatch planner. Assigns the nearest virtual emergency units.

        The interface mirrors a real CAD integration: the next adapter would replace
        this simulated registry with trusted emergency-service dispatch APIs.
        """
        units = [("police", "Central Police Station", 4), ("ambulance", "City General Hospital", 6), ("fire", "Station 12", 8)]
        for unit_type, origin, eta in units:
            unit_id = f"{unit_type}-{len(self.response_units) + 1:03d}"
            self.response_units[unit_id] = ResponseUnit(id=unit_id, incident_id=incident.id, unit_type=unit_type, origin=origin, destination_road_id=incident.road_id, eta_minutes=eta, status="units_assigned")

    def update_response_progress(self) -> None:
        for unit in self.response_units.values():
            incident = self.incidents.get(unit.incident_id)
            if not incident or incident.status != "active":
                unit.status = "available"
                continue
            unit.progress_percent = min(100, unit.progress_percent + self._rng.randint(2, 7))
            unit.status = "on_scene" if unit.progress_percent >= 100 else "en_route"
            if unit.status == "on_scene":
                incident.response_status = "on_scene"

    def _create_incident_alerts(self, incident: Incident) -> None:
        existing = [a for a in self.alerts.values() if a.road_id == incident.road_id and not a.acknowledged]
        if existing:
            return
        timestamp = incident.created_at
        alert_data = [
            ("traveller", "warning", "Route updated", f"Incident on {incident.road_id}. Avoid this corridor; a safer route is available."),
            ("police", "critical", "Police response required", f"{incident.type.replace('_', ' ').title()} reported on {incident.road_id}. Dispatch and verify the scene."),
            ("traffic_control", "critical", "Signal priority activated", f"Emergency clearance phase activated around {incident.road_id} to reduce queueing and aid response."),
        ]
        for audience, priority, title, message in alert_data:
            alert_id = f"alert-{len(self.alerts) + 1:03d}"
            self.alerts[alert_id] = Alert(id=alert_id, audience=audience, priority=priority, title=title, message=message, road_id=incident.road_id, created_at=timestamp)

    def clear_incident(self, incident_id: str) -> None:
        incident = self.incidents.get(incident_id)
        if not incident:
            raise KeyError(incident_id)
        incident.status = "cleared"
        self.roads[incident.road_id].blocked = False
        self.refresh_road_state()
        self.update_signals()
        self.update_response_progress()
        self.record_history()

    def acknowledge_alert(self, alert_id: str) -> None:
        if alert_id not in self.alerts:
            raise KeyError(alert_id)
        self.alerts[alert_id].acknowledged = True

    def set_signal_mode(self, signal_id: str, mode: str) -> TrafficSignal:
        if signal_id not in self.signals:
            raise KeyError(signal_id)
        signal = self.signals[signal_id]
        if mode == "adaptive":
            self.update_signals()
        else:
            signal.mode = "emergency"
            signal.green_seconds = 75
            signal.phase_label = f"Manual emergency override · {signal.active_road_id}"
            signal.reason = "Traffic operator activated an emergency clearance phase."
        return signal

    def analytics(self) -> dict:
        return {"samples": self.history, "sample_interval_seconds": 2}

    def predictions(self, minutes: int = 5) -> list[dict]:
        """Returns transparent rule-based forecasts for the prototype horizons."""
        forecast: list[dict] = []
        for road in self.roads.values():
            pressure = road.vehicle_count + road.incident_count * 7
            level = road.predicted_congestion_5m
            if minutes >= 30 and pressure >= 4:
                level = "high" if level != "low" else "medium"
            predicted_speed = max(5, road.speed_limit_kmph * ({"low": .80, "medium": .52, "high": .26}[level]))
            forecast.append({"road_id": road.id, "horizon_minutes": minutes, "predicted_congestion": level, "predicted_speed_kmph": round(predicted_speed, 1), "confidence": round(.76 + min(pressure, 8) * .02, 2), "basis": "current volume, incident state, signal queue, and rolling speed"})
        return forecast

    def apply_camera_observation(self, vehicle_count: int, average_speed: float, congestion: str, stopped_risk: bool) -> None:
        """Synchronise the monitored CCTV corridor (B-E) with camera observations."""
        road = self.roads["B-E"]
        road.current_speed_kmph = max(0.0, round(average_speed, 1))
        road.congestion_level = congestion if congestion in {"low", "medium", "high"} else "low"
        if stopped_risk and not road.blocked:
            self.create_incident("B-E", "suspected_accident", "high")
        else:
            self.update_signals()

    def snapshot(self) -> dict:
        roads = list(self.roads.values())
        return {
            "intersections": [item.model_dump(mode="json") for item in INTERSECTIONS.values()],
            "roads": [item.model_dump(mode="json") for item in roads],
            "vehicles": [item.model_dump(mode="json") for item in self.vehicles.values()],
            "incidents": [item.model_dump(mode="json") for item in self.incidents.values() if item.status == "active"],
            "alerts": [item.model_dump(mode="json") for item in self.alerts.values() if not item.acknowledged],
            "signals": [item.model_dump(mode="json") for item in self.signals.values()],
            "responders": [item.model_dump(mode="json") for item in self.response_units.values()],
            "summary": {
                "active_vehicles": len(self.vehicles),
                "high_congestion_roads": sum(r.congestion_level == "high" for r in roads),
                "active_incidents": sum(i.status == "active" for i in self.incidents.values()),
                "average_network_speed_kmph": round(sum(r.current_speed_kmph for r in roads) / len(roads), 1),
            },
        }
