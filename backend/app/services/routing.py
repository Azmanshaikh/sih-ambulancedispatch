import heapq
import math
from typing import Dict, List, Tuple

def heuristic(node_a: Tuple[float, float], node_b: Tuple[float, float]) -> float:
    """
    Calculate the Euclidean distance between two nodes to serve as the heuristic.
    In a real geographic system, the Haversine formula would be used here.
    """
    return math.sqrt((node_a[0] - node_b[0])**2 + (node_a[1] - node_b[1])**2)

def a_star_search(
    start: str, 
    goal: str, 
    graph: Dict[str, Dict[str, float]], 
    node_coordinates: Dict[str, Tuple[float, float]]
) -> Tuple[List[str], float]:
    """
    Finds the shortest and fastest path from start to goal using the A* (A-star) algorithm.
    It combines Dijkstra's algorithm logic with a heuristic to cut down search time.
    
    :param start: Starting node ID in the graph.
    :param goal: Goal node ID in the graph.
    :param graph: Adjacency list representing the road network {node: {neighbor: cost/time}}.
    :param node_coordinates: Coordinates of each node for the heuristic {node: (lat, lng)}.
    :return: A tuple of (path, total_cost). If no path is found, returns ([], float('inf')).
    """
    if start not in graph or goal not in graph:
        return [], float('inf')

    # Priority queue to store nodes to explore: (f_score, node)
    open_set = []
    heapq.heappush(open_set, (0, start))
    
    # Cost from start to a node (g-score)
    g_score = {node: float('inf') for node in graph}
    g_score[start] = 0
    
    # Came from map to reconstruct the final path
    came_from = {}
    
    while open_set:
        current_f_score, current = heapq.heappop(open_set)
        
        # If we reached the goal, reconstruct and return the path
        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path, g_score[goal]
            
        # Explore neighbors
        for neighbor, cost in graph.get(current, {}).items():
            tentative_g_score = g_score[current] + cost
            
            # If a shorter path to the neighbor is found
            if tentative_g_score < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                
                # f = g + h
                h = heuristic(node_coordinates[neighbor], node_coordinates[goal])
                f_score = tentative_g_score + h
                
                heapq.heappush(open_set, (f_score, neighbor))
                
    # If open set is empty and goal was never reached, no path exists
    return [], float('inf')
