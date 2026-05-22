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

def get_all_shortest_paths(graph : nx.DiGraph, weight:str='weight'):
    def map_id(d:dict|int, mapping_dict:dict):
        if type(d)==int:
            return mapping_dict[d]
        elif type(d)==dict:
            return {mapping_dict[k]:[[mapping_dict[node] for node in v]] if v is not None else k for k,v in d.items()}
        elif type(d)==list:
            return {mapping_dict[k]:[[mapping_dict[node] for node in v]] if v is not None else k for k,v in enumerate(d)}

    rx_g:rx.PyDiGraph = rx.networkx_converter(graph, keep_attributes=True)
    rx_to_nx={}
    for node_id, node in zip(rx_g.node_indices(), rx_g.nodes()):
        rx_to_nx[node_id] = node['__networkx_node__']
    # nx_to_rx = {v:k for k,v in rx_to_nx.items()}

    rx_paths={k:dict(v) for k,v in dict(rx.all_pairs_dijkstra_shortest_paths(
        rx_g, 
        edge_cost_fn=lambda x:x.get(weight))).items()
        }
    nx_rx_paths={map_id(k, rx_to_nx): map_id(v, rx_to_nx) for k,v in rx_paths.items()}
    return nx_rx_paths