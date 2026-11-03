import numpy as np
import networkx as nx

def trajs_rdm(graph:nx.MultiDiGraph, size:int):
    nodes_list=list(graph.nodes)
    return [np.random.choice(nodes_list, 2, False) for _ in range(size)]