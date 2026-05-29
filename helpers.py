from collections import Counter
import time
import rustworkx as rx
import networkx as nx

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.INFO)

def get_dict(nodes, nodes_pos, nodes_neg, pos_val, neg_val, null_val):
    out={node:null_val for node in nodes}
    for node in nodes:
        if node in nodes_neg:
            out[node]=neg_val
        elif node in nodes_pos:
            out[node]=pos_val
    return out

class Count(Counter):
    def __missing__(self, key):
        'The count of elements not in the Counter is one.'
        # Needed so that self[missing_item] does not raise KeyError
        return 1

def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        logging.info(f'{method.__name__} {(te - ts) * 1000 :.2f}')

        return result
    return timed

class rx_helper:
    def __init__(self, graph : nx.DiGraph):
        self.nx_graph = graph
        self.rx_g:rx.PyDiGraph = rx.networkx_converter(graph, keep_attributes=True)
        self.rx_to_nx={node_id : node['__networkx_node__']
            for node_id, node in zip(self.rx_g.node_indices(), self.rx_g.nodes())
        }
        self.nx_to_rx = {v:k for k,v in self.rx_to_nx.items()}

    def map_id(self, d:dict|int|list, mapping_dict:dict):
        if type(d)==int:
            return mapping_dict[d]
        elif type(d)==dict:
            return {mapping_dict[k]:[[mapping_dict[node] for node in v]] if v is not None else k for k,v in d.items()}
        elif type(d)==list:
            return [mapping_dict[node] for node in d]

    def get_all_shortest_paths(self, weight:str='weight'):
        rx_paths={k:dict(v) for k,v in dict(rx.all_pairs_dijkstra_shortest_paths(
            self.rx_g,
            edge_cost_fn=lambda x:x.get(weight))).items()
            }
        nx_rx_paths={self.map_id(k, self.rx_to_nx): self.map_id(v, self.rx_to_nx) for k,v in rx_paths.items()}
        for node in nx_rx_paths.keys():
            nx_rx_paths[node][node]=[[node]]
        return nx_rx_paths

    def get_shortest_path(self, nx_source, nx_target, weight='weight'):
        path = rx.dijkstra_shortest_paths(self.rx_g, self.nx_to_rx[nx_source], self.nx_to_rx[nx_target],weight_fn=lambda x:x.get(weight))
        # print(list(dict(path).values()))
        # if not rx.has_path(self.rx_g, self.nx_to_rx[nx_source], self.nx_to_rx[nx_target]):
        #     print('Ah bon ?!')
        #     print(nx_source, nx_target)
        #     print(self.nx_to_rx[nx_source], self.nx_to_rx[nx_target])
        return self.map_id(list(list(dict(path).values())[0]), self.rx_to_nx)