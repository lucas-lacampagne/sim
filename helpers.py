from collections import Counter
import time
import rustworkx as rx
import networkx as nx
import numpy as np

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
        return self.map_id(list(list(dict(path).values())[0]), self.rx_to_nx)

class Car:
    def __init__(self, departure_node, arrival_node, path):
        self.dep=departure_node
        self.old_loc=departure_node
        self.path=path
        self.loc=departure_node
        self.arr=arrival_node
        self.completed=(departure_node==arrival_node)
    
    def update_loc_and_path(self):
        new_loc=self.path[1]
        self.path=self.path[1:]
        self.old_loc=self.loc
        self.loc=new_loc
        self.completed=(self.loc==self.arr)
        return self
    
    def __repr__(self):
        return f'({self.dep}, {self.loc}, {self.arr}, {self.completed})'

class Base_car_fleet:
    def __init__(self, graph, size=2*50, replace=False):
        self.graph: nx.MultiDiGraph | nx.DiGraph = graph
        self.is_multi = type(graph)==nx.MultiDiGraph
        self.rx_helper=rx_helper(self.graph)
        self.all_paths = self.rx_helper.get_all_shortest_paths()

        cnt=0
        while True:
            trajs = self.init_trajs(size, replace)
            if all(nx.has_path(graph, s, t) for s, t in trajs):
                break
            cnt+=1
            print(f"{cnt}th time regenerating trajectories: some nodes were disconnected.", end='\r')
        self.trajs = trajs

        self.fleet = [Car(s, t, self.all_paths[s][t][0]) for s, t in self.trajs]
        self.num_cars = len(trajs)
        self.edges_state = {(car.dep, car.arr) :
            self.check_edges_along_path(car.path) for car in self.fleet
        }
        self.step=0
        self.info=[]

    def init_trajs(self, size, replace):
        nodes_list=list(self.graph.nodes)
        chosen=np.random.choice(self.graph.number_of_nodes(), size, replace)
        sources = [nodes_list[k] for k in chosen[:size//2]]
        targets = [nodes_list[k] for k in chosen[size//2:size]]
        return list(zip(sources, targets))

    def __repr__(self):
        return f'{self.fleet}'

    def get_loc(self, include_completed=True):
        if include_completed:
            return [car.loc for car in self.fleet]
        else:
            return [car.loc for car in self.fleet if not car.completed]
    def get_arr(self, include_completed=True):
        if include_completed:
            return [car.arr for car in self.fleet]
        else:
            return [car.arr for car in self.fleet if not car.completed]
    def get_completed(self):
        return [car.completed for car in self.fleet]
    def all_completed(self):
        return all(self.get_completed())
    
    def get_paths(self):
        return [car.path for car in self.fleet if not car.completed]

    def get_edge_blocked(self):
        return {(u,v):edge_data['weight']>2 for u,v,edge_data in list(self.graph.edges(data=True))}
    
    def get_path(self, node1, node2, weight):
        return self.rx_helper.get_shortest_path(node1, node2, weight)
    
    def get_cost(self, path, weight):
        return nx.path_weight(self.graph, path, weight)

    def get_path_and_cost(self, node1, node2, weight):
        path = self.rx_helper.get_shortest_path(node1, node2, weight)
        cost = nx.path_weight(self.graph, path, weight)
        return path, cost