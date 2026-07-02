import networkx as nx
import json


def adjacency2networkx(xadj: list, adjncy: list, vwgt: list, adjcwgt: list):
    pass


def networkx2adjacency(
    graph: nx.Graph, default_nweight: int = 1, default_lweight: int = 1
):
    xadj, adjacency, vweights, adjweights, i = [0], [], [], [], 0
    node_weights = nx.get_node_attributes(graph, "weight", default=default_nweight)
    edge_weights = nx.get_edge_attributes(graph, "weight", default=default_lweight)
    for node in graph.nodes:
        xadj.append(xadj[i] + graph.degree[node])
        if len(graph[node]) > 0:
            for neighbor in graph[node]:
                adjacency.append(int(neighbor))
                if (node, neighbor) in edge_weights:
                    adjweights.append(edge_weights[(node, neighbor)])
                else:
                    adjweights.append(edge_weights[(neighbor, node)])
            vweights.append(node_weights[node])
        i += 1
    return xadj, adjacency, vweights, adjweights


def save_attack(attack: list, filename: str):
    with open(filename, encoding="utf-8", mode="w") as wfile:
        json.dump(attack, wfile, indent=4)


def load_attack(filename: str):
    with open(filename, encoding="utf-8", mode="r") as rfile:
        attack = json.load(rfile)
    return attack


def read_gadj(filename: str) -> tuple:
    with open(filename, mode="r", encoding="utf-8") as rfile:
        d = json.load(rfile)
    return d["xadj"], d["adjacency"], d["vweights"], d["adjweights"]


def write_gadj(graph: nx.Graph, filename: str):
    xadj, adjacency, vweights, adjweights = networkx2adjacency(graph)
    graph_dict = {
        "xadj": xadj,
        "adjacency": adjacency,
        "vweights": vweights,
        "adjweights": adjweights,
    }

    with open(filename, mode="w", encoding="utf-8") as wfile:
        json.dump(graph_dict, wfile, indent=4)


def unify_attacks(filenames, new_filename):
    attacks = []
    for filename in filenames:
        attacks.append(load_attack(filename))
    flat_attacks = sum(attacks, [])
    save_attack(flat_attacks, new_filename)
