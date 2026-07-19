# import kahip
import igraph as ig
import networkx as nx
import rustworkx as rx
import random as rd
from math import inf
from src.attack.utils import networkx2adjacency


def edge_betweenness_centrality_ig(igraph: ig.Graph, approx: int, weight: bool):
    if approx == -1:
        ebc = (
            igraph.edge_betweenness(weights="length")
            if weight
            else igraph.edge_betweenness()
        )
    else:
        sources = rd.sample(igraph.vs, approx)
        ebc = (
            igraph.edge_betweenness(weights="length", sources=sources)
            if weight
            else igraph.edge_betweenness()
        )
    max_ebc, edge = ebc[0], igraph.es[0]
    for i in range(1, len(ebc)):
        if ebc[i] > max_ebc:
            max_ebc = ebc[i]
            edge = igraph.es[i]
    return edge

def edge_betweenness_centrality_nx(graph: nx.MultiDiGraph, approx: int, weight: bool):
    if approx == -1:
        ebc = (
            nx.edge_betweenness_centrality(graph, weight="length")
            if weight
            else nx.edge_betweenness_centrality(graph)
        )
    edge=max(ebc, key=ebc.get)
    return edge
    
def edge_betweenness_centrality_rx(rx_graph:rx.PyDiGraph, approx: int):
    if approx == -1:
        ebc = dict(
            rx.edge_betweenness_centrality(rx_graph)
        )
    rx_edge=max(ebc, key=ebc.get)
    return rx_edge


def degree(graph, f):
    max_deg = 0
    chosen_edge = None
    for edge in graph.edges:
        edegree = f(graph.degree[edge[0]], graph.degree[edge[1]])
        if edegree > max_deg:
            chosen_edge = edge
            max_deg = edegree
    return chosen_edge


def random(graph):
    return rd.choice(list(graph.edges))


def mindegree(graph, f):
    min_deg = inf
    chosen_edge = None
    for edge in graph.edges:
        edegree = f(graph.degree[edge[0]], graph.degree[edge[1]])
        if edegree < min_deg:
            chosen_edge = edge
            min_deg = edegree
    return chosen_edge





def feature_based_attack(
    graph: nx.MultiDiGraph|rx.PyDiGraph,
    l: int,
    attack_name: str,
    igraph: ig.Graph = None,
    approx: int = -1,
    weight: bool = True,
):
    """Simple feature-based attacks
   Attacks based on features that can be computed directly on the graph at each step
   without further objects
   Accepted features are:
        * 'ebc' for edge betweenness centrality
        * 'rd' for random
        * 'deg' for max degree computed by extremities sum
        * 'xdeg' for max degree computed by extremities product
        * 'mindeg' for min degree computed by extremities sum
        * 'minxdeg' for min degree computed by extremities product

    Parameters
    ----------
    graph: nx.Graph
        graph in networkx format, needed for 'deg' and 'rd' attacks
    l: int
        size of the attack (number of edges to remove)
    attack_name: str
        see features above
    igraph: ig.Graph=None
        graph in igraph format, needed for 'ebc' attack
    approx: int=-1
        number of edges to sample if ebc approx is wanted
        
    Returns
    -------
    list
        list of chosen edges
"""
    attack = []
    match attack_name:
        case "ebc":
            if igraph:
                parameters = [igraph, approx, weight]
                feature = edge_betweenness_centrality_ig
            elif type(graph)==nx.MultiDiGraph:
                parameters = [graph, approx, weight]
                feature = edge_betweenness_centrality_nx
            elif type(graph)==rx.PyDiGraph:
                parameters = [graph, approx]
                feature = edge_betweenness_centrality_rx

        case "deg":
            parameters = [graph, lambda x, y: x + y]
            feature = degree
        case "xdeg":
            parameters = [graph, lambda x, y: x * y]
            feature = degree
        case "rd":
            parameters = [graph]
            feature = random
        case "mindeg":
            parameters = [graph, lambda x, y: x + y]
            feature = mindegree
        case "minxdeg":
            parameters = [graph, lambda x, y: x * y]
            feature = mindegree
        case _:
            raise ValueError(
                "attack_name invalid, please choose between 'ebc', 'rd', 'deg', 'xdeg', 'mindeg' and minxdeg."
            )
    if attack_name == "ebc" :
        for i in range(1,l+1):
            print(f"{i} edge removals done over {l}, hence {i*100 / l:.2f}%", end='\r')
            chosen_edge = feature(*parameters)
            # print(chosen_edge["former_name"])
            # print(chosen_edge.attributes())
            # print(chosen_edge.tuple)
            # print(chosen_edge.vertex_tuple)
            if igraph:
                attack.append(chosen_edge.tuple)
                igraph.delete_edges(chosen_edge)
            elif type(graph)==rx.PyDiGraph:
                attack.append(chosen_edge)
                graph.remove_edge_from_index(chosen_edge)
            elif type(graph)==nx.MultiDiGraph:
                attack.append(chosen_edge)
                graph.remove_edge(chosen_edge)
    else:
        for i in range(1,l+1):
            print(f"{i} edge removals done over {l}, hence {i*100 / l:.2f}%", end='\r')
            chosen_edge = feature(*parameters)
            attack.append(chosen_edge)
            graph.remove_edge(*chosen_edge)
    return attack

"""Returns list of lists of edges. Each list of edges corresponds to the smallest cut

    Parameters:
    -----------
    graph: nx.Graph
        graph in networkx format
    k: int
        number of partitions to cut into
    eps:
        imbalance parameter for cuts
    l: int
        the number of iterations
    nbcuts: int
        number of cuts from which choose the smallest
    weighted: bool=True
        whether set edge weights or not

    Returns
    -------
    list
        a list of list of edges
"""


def iterated_cut_attack(
    init_graph: nx.Graph,
    k: int,
    eps: float,
    l: int,  # deprecated
    nbcuts: int = 1000,
    weighted: bool = True,
):
    res = []
    current_graph = init_graph
    v_map = {node: node for node in init_graph.nodes}
    # for i in range(l): # old way of stopping the ica, now stops by itself
    n = len(init_graph.nodes)
    i = 0
    while len(current_graph.nodes) * 10 >= n:
        xadj, adjncy, vwgt, adjcwgt = networkx2adjacency(current_graph)
        best_blocks, best_cost = None, inf
        print(
            f"Starting cut sequence {i+1} over {l}, graph has size {len(current_graph.nodes)}"
        )
        for _ in range(nbcuts):
            seed = int(rd.random() * 2**31)
            cut_cost, blocks = kahip.kaffpa(
                vwgt, xadj, adjcwgt, adjncy, k, eps, 0, seed, 2
            )
            if cut_cost < best_cost:
                best_blocks = blocks
        best_cut, best_cut_old = [], []
        for u, v in current_graph.edges:
            if best_blocks[u] != best_blocks[v]:
                best_cut_old.append((v_map[u], v_map[v]))
                best_cut.append((u, v))
        res.append(best_cut_old)
        for u, v in best_cut_old:
            if (u, v) in init_graph.edges:
                init_graph.remove_edge(u, v)
            else:
                init_graph.remove_edge(v, u)
        largest_cc = max(nx.connected_components(init_graph), key=len)
        current_graph = init_graph.subgraph(largest_cc)
        current_graph = nx.convert_node_labels_to_integers(
            current_graph, label_attribute="old_label"
        )
        v_map = {
            node: old_node for node, old_node in current_graph.nodes(data="old_label")
        }
        # for node, old_node in current_graph.nodes(data='old_label'):
        #     v_map[node] = v_map.pop(old_node)
        i += 1
    return res


def attack_cost(graph: nx.Graph, cut: list):
    cost = 0
    edge_weights = nx.get_edge_attributes("weight")
    for u, v in cut:
        if (u, v) in edge_weights:
            cost += edge_weights[(u, v)]
        else:
            cost += edge_weights[(v, u)]
    return cost
