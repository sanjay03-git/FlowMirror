import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.camera_registry import CameraRegistry
from app.operations_store import OperationsStore
from app.twin import TrafficTwin


class FlowMirrorOperationsTests(unittest.TestCase):
    def setUp(self):
        self.twin = TrafficTwin()

    def test_incident_dispatches_units_alerts_and_emergency_signals(self):
        incident = self.twin.create_incident("B-E", "vehicle_collision", "high")
        snapshot = self.twin.snapshot()
        self.assertEqual(3, len([unit for unit in snapshot["responders"] if unit["incident_id"] == incident.id]))
        self.assertEqual({"traveller", "police", "traffic_control"}, {alert["audience"] for alert in snapshot["alerts"]})
        self.assertTrue(any(signal["mode"] == "emergency" for signal in snapshot["signals"]))

    def test_route_options_avoid_closed_corridor(self):
        self.twin.create_incident("B-E", "road_block", "high")
        options = self.twin.route_options("B", "H")
        self.assertEqual(4, len(options))
        self.assertTrue(all("B-E" not in option["roads"] for option in options))

    def test_scenario_is_non_destructive(self):
        before = self.twin.roads["B-E"].blocked
        result = self.twin.simulate_scenario("flood", "B-E")
        self.assertFalse(before)
        self.assertFalse(self.twin.roads["B-E"].blocked)
        self.assertTrue(any(item["affected"] for item in result["impact"]))

    def test_camera_registry_has_four_independent_sites(self):
        with TemporaryDirectory() as temp_dir:
            registry = CameraRegistry(self.twin, Path(temp_dir))
            statuses = registry.all_status()
            self.assertEqual(4, len(statuses))
            self.assertEqual({"cam-01", "cam-02", "cam-03", "cam-04"}, {status["id"] for status in statuses})

    def test_audit_store_retains_event_payload(self):
        with TemporaryDirectory() as temp_dir:
            store = OperationsStore(Path(temp_dir) / "audit.db")
            store.record("signal.mode_changed", {"signal_id": "signal-E", "mode": "emergency"}, actor="operator", severity="warning")
            event = store.recent(1)[0]
            self.assertEqual("signal.mode_changed", event["event_type"])
            self.assertEqual("signal-E", event["payload"]["signal_id"])


if __name__ == "__main__":
    unittest.main()
