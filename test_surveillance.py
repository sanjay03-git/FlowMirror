import unittest

from app.surveillance import Detection, MultiObjectTracker


class MultiObjectTrackerTests(unittest.TestCase):
    def test_external_tracker_id_is_preserved_across_large_motion(self):
        tracker = MultiObjectTracker()
        first = tracker.update([Detection((10, 20, 40, 30), object_class="bus", external_track_id="77")])
        second = tracker.update([Detection((300, 200, 40, 30), object_class="bus", external_track_id="77")])

        self.assertEqual("OBJ-77", first[0].track_id)
        self.assertEqual("OBJ-77", second[0].track_id)
        self.assertEqual(2, len(second[0].path))


if __name__ == "__main__":
    unittest.main()
