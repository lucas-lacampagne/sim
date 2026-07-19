import rustworkx as rx
import networkx as nx
import itertools as it
import copy

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.INFO)

class rx_helper:
    def __init__(self, graph : nx.MultiDiGraph, trajs):
        self.nx_graph = graph.copy()
        self.rx_g:rx.PyDiGraph = rx.networkx_converter(graph, keep_attributes=True)
        self.rx_to_nx={node_id : node['__networkx_node__']
            for node_id, node in zip(self.rx_g.node_indices(), self.rx_g.nodes())
        }
        self.nx_to_rx = {v:k for k,v in self.rx_to_nx.items()}

        self.edge_nx_to_rx = {}
        for u, v, k, data in self.nx_graph.edges(keys=True, data=True):
            rx_u, rx_v = self.nx_to_rx[u], self.nx_to_rx[v]
            indices = self.rx_g.edge_indices_from_endpoints(rx_u, rx_v)
            for idx in indices:
                if self.rx_g.get_edge_data_by_index(idx) == data:
                    self.edge_nx_to_rx[(u, v, k)] = idx
                    break
        self.edge_rx_to_nx={v:k for k,v in self.edge_nx_to_rx.items()}
        self.all_paths = self.calculate_all_shortest_paths()

    def add_back_edge(self, u, v, k, data):
        self.nx_graph.add_edge(u, v, k, **data)
        rx_u, rx_v = self.nx_to_rx[u], self.nx_to_rx[v]
        rx_idx = self.rx_g.add_edge(rx_u, rx_v, data)
        self.edge_nx_to_rx[(u, v, k)] = rx_idx
        self.edge_rx_to_nx[rx_idx]=(u,v,k)

    def remove_edge(self, u, v, k):
        self.nx_graph.remove_edge(u, v, k)
        rx_idx = self.edge_nx_to_rx.pop((u, v, k))
        self.rx_g.remove_edge_from_index(rx_idx)

    def update_edge(self, u, v, k, update_key:str, update_value):
        self.nx_graph[u][v][k][update_key]=update_value
        rx_idx = self.edge_nx_to_rx[u, v, k]
        edge=self.rx_g.get_edge_data_by_index(rx_idx)
        edge[update_key]=update_value
        self.rx_g.update_edge_by_index(rx_idx, edge)

    def map_id(self, d:dict|int|list, mapping_dict:dict):
        if type(d)==int:
            return mapping_dict[d]
        elif type(d)==dict:
            return {mapping_dict[k]:[[mapping_dict[node] for node in v]] if v is not None else k for k,v in d.items()}
        elif type(d)==list:
            return [mapping_dict[node] for node in d]
        
    def is_path(self, path):
        """Returns whether or not the specified path exists.

        For it to return True, every node on the path must exist and
        each consecutive pair must be connected via one or more edges.

        Parameters
        ----------
        path : list
            A list of nodes which defines the path to traverse

        Returns
        -------
        bool
            True if `path` is a valid path in `G`

        """
        try:
            return all(nbr in rx.graph_adjacency_matrix(self.rx_g)[node] for node, nbr in it.pairwise(path))
        except (KeyError, TypeError):
            return False

    def calculate_all_shortest_paths(self, weight:str='weight'):
        rx_paths={k:dict(v) for k,v in dict(rx.all_pairs_dijkstra_shortest_paths(
            self.rx_g,
            edge_cost_fn=lambda x:x.get(weight))).items()
            }
        nx_rx_paths={self.map_id(k, self.rx_to_nx): self.map_id(v, self.rx_to_nx) for k,v in rx_paths.items()}
        return nx_rx_paths

    def calculate_shortest_path(self, nx_source, nx_target, weight='weight'):
        path = rx.dijkstra_shortest_paths(self.rx_g, self.nx_to_rx[nx_source], self.nx_to_rx[nx_target],weight_fn=lambda x:x.get(weight))
        return self.map_id(list(list(dict(path).values())[0]), self.rx_to_nx)
    
    def get_shortest_path(self, nx_source, nx_target, weight='weight'):
        return copy.deepcopy(self.all_paths[nx_source][nx_target][0])
