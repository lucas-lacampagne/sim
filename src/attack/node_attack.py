import igraph as ig
import networkx as nx
import random as rd
from math import inf
import numpy as np


def node_betweenness_centrality(igraph: ig.Graph):
    current_id = np.argmax(igraph.betweenness())
    return True, int(current_id), igraph.vs[int(current_id)]["id"]


def degree(graph):
    return max(graph.degree(graph.nodes), key=lambda x: x[1])[0]


def random(graph):
    return rd.choice(list(graph.nodes))


def mindegree(graph):
    return min(graph.degree(graph.nodes), key=lambda x: x[1])[0]


""" Naive implementation, see "An efficient parallel biconnectivity algorithm"
    for optimized version.
    Returns the node id
"""


def articulation_point(igraph: ig.Graph):
    def cc_without(vid):
        newgraph = igraph.copy()
        newgraph.delete_vertices(vid)
        return len(newgraph.connected_components(mode="weak"))

    ncc = len(igraph.connected_components(mode="weak"))
    cc_list = [cc_without(v) for v in igraph.vs]
    current_id, max_cc = 0, ncc
    for v in range(igraph.vcount()):
        new_cc = cc_without(v)
        if new_cc > max_cc:
            max_cc = new_cc
            current_id = v
    if max_cc == ncc:
        return False, current_id, igraph.vs[current_id]["id"]
    return True, current_id, igraph.vs[current_id]["id"]


"""Simple node feature-based attacks
   Attacks based on features that can be computed directly on the graph at each step
   without further objects
   Accepted features are:
        * 'ebc' for edge betweenness centrality
        * 'rd' for random
        * 'deg' for max degree
        * 'mindeg' for min degree
        * 'ap' for articulation point greedy attack
        
    Returns
    -------
    list
        list of chosen nodes
"""


def feature_based_attack(
    graph: nx.Graph,
    attack_name: str,
    igraph: ig.Graph = None,
):
    attack = []
    match attack_name:
        case "ebc":
            if not igraph:
                raise ValueError("For ebc feature, igraph graph format is needed.")
            parameters = [igraph]
            feature = node_betweenness_centrality
        case "deg":
            parameters = [graph]
            feature = degree
        case "rd":
            parameters = [graph]
            feature = random
        case "mindeg":
            parameters = [graph]
            feature = mindegree
        case "ap":
            if not igraph:
                raise ValueError("For ap feature, igraph graph format is needed.")
            parameters = [igraph]
            feature = articulation_point
        case _:
            raise ValueError(
                "attack_name invalid, please choose between 'ebc', 'rd', 'deg' and 'mindeg'."
            )
    if attack_name in ["ebc", "ap"]:
        initial_n, flag = igraph.vcount(), True
        while igraph.vcount() > 0:
            print(
                f"{initial_n - igraph.vcount()} node processed, {(initial_n - igraph.vcount()) * 100 / igraph.vcount()}% done"
            )
            flag, current_node, node_id = feature(*parameters)
            # sub_attack = []
            # sub_attack.append([igraph.es[edge].tuple for edge in igraph.incident(chosen_node)])
            # igraph.delete_edges(igraph.incident(chosen_node))
            # attack.append(sub_attack)
            if flag:
                igraph.delete_vertices(current_node)
                attack.append(node_id)
            else:
                break
    else:
        while len(graph.nodes) > 0:
            # sub_attack = []
            chosen_node = feature(*parameters)
            # for neighbor in graph[chosen_node]:
            #     sub_attack.append((chosen_node, neighbor))
            #     graph.remove_edge(chosen_node, neighbor)
            # attack.append(sub_attack)
            graph.remove_node(chosen_node)
            attack.append(chosen_node)
    return attack
