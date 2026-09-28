from __future__ import annotations

import networkx as nx

from .models import Intersection, Road

# These coordinates form a compact fictional road grid near Bengaluru. Replace them with
# real permitted road data only after the prototype is working.
INTERSECTIONS: dict[str, Intersection] = {
    "A": Intersection(id="A", name="North West", latitude=12.9750, longitude=77.5900),
    "B": Intersection(id="B", name="North Centre", latitude=12.9750, longitude=77.5950),
    "C": Intersection(id="C", name="North East", latitude=12.9750, longitude=77.6000),
    "D": Intersection(id="D", name="Central West", latitude=12.9700, longitude=77.5900),
    "E": Intersection(id="E", name="Central Junction", latitude=12.9700, longitude=77.5950),
    "F": Intersection(id="F", name="Central East", latitude=12.9700, longitude=77.6000),
    "G": Intersection(id="G", name="South West", latitude=12.9650, longitude=77.5900),
    "H": Intersection(id="H", name="South Centre", latitude=12.9650, longitude=77.5950),
    "I": Intersection(id="I", name="South East", latitude=12.9650, longitude=77.6000),
}


def _road(road_id: str, start: str, end: str) -> Road:
    return Road(
        id=road_id,
        from_node=start,
        to_node=end,
        distance_km=0.56,
        speed_limit_kmph=40,
        current_speed_kmph=35,
        congestion_level="low",
    )


ROADS: list[Road] = [
    _road("A-B", "A", "B"), _road("B-C", "B", "C"),
    _road("D-E", "D", "E"), _road("E-F", "E", "F"),
    _road("G-H", "G", "H"), _road("H-I", "H", "I"),
    _road("A-D", "A", "D"), _road("D-G", "D", "G"),
    _road("B-E", "B", "E"), _road("E-H", "E", "H"),
    _road("C-F", "C", "F"), _road("F-I", "F", "I"),
]


def create_road_graph() -> nx.Graph:
    graph = nx.Graph()
    for node in INTERSECTIONS.values():
        graph.add_node(node.id, **node.model_dump())
    for road in ROADS:
        graph.add_edge(road.from_node, road.to_node, road_id=road.id)
    return graph
