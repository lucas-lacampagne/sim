import numpy as np
import networkx as nx
import itertools as it

def trajs_rdm(graph:nx.MultiDiGraph, args:dict):
    nodes_list=list(graph.nodes)
    return [np.random.choice(nodes_list, 2, False) for _ in range(args['size'])]

def trajs_bc_test(graph:nx.MultiDiGraph, args:dict):
    nodes_list=list(graph.nodes)
    return list(it.permutations(nodes_list, 2))