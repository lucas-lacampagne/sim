from collections import Counter
import time
import rustworkx as rx
import networkx as nx
import numpy as np
import itertools as it

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
    def __init__(self, graph : nx.MultiDiGraph):
        self.nx_graph = graph.copy()
        self.rx_g:rx.PyDiGraph = rx.networkx_converter(graph, keep_attributes=True)
        self.rx_to_nx={node_id : node['__networkx_node__']
            for node_id, node in zip(self.rx_g.node_indices(), self.rx_g.nodes())
        }
        self.nx_to_rx = {v:k for k,v in self.rx_to_nx.items()}

        self.edge_map = {}
        for u, v, k, data in self.nx_graph.edges(keys=True, data=True):
            rx_u, rx_v = self.nx_to_rx[u], self.nx_to_rx[v]
            indices = self.rx_g.edge_indices_from_endpoints(rx_u, rx_v)
            for idx in indices:
                if self.rx_g.get_edge_data_by_index(idx) == data:
                    self.edge_map[(u, v, k)] = idx
                    break

    def add_edge(self, u, v, k, data):
        self.nx_graph.add_edge(u, v, k, **data)
        rx_u, rx_v = self.nx_to_rx[u], self.nx_to_rx[v]
        rx_idx = self.rx_g.add_edge(rx_u, rx_v, data)
        self.edge_map[(u, v, k)] = rx_idx

    def remove_edge(self, u, v, k):
        self.nx_graph.remove_edge(u, v, k)
        rx_idx = self.edge_map.pop((u, v, k))
        self.rx_g.remove_edge_from_index(rx_idx)

    def update_edge(self, u, v, k, update_key:str, update_value):
        self.nx_graph[u][v][k][update_key]=update_value
        rx_idx = self.edge_map[u, v, k]
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
    def __init__(self, departure_node, arrival_node, path, cost):
        self.dep=departure_node
        self.old_loc=departure_node
        self.path=path
        self.cost=cost
        self.loc=departure_node
        self.arr=arrival_node
        self.completed=(departure_node==arrival_node)
    
    def update_loc_and_path(self, next_weight):
        new_loc=self.path[1]
        self.path=self.path[1:]
        self.cost-=next_weight
        self.old_loc=self.loc
        self.loc=new_loc
        self.completed=(self.loc==self.arr)
        return self
    
    def __repr__(self):
        return f'({self.dep}, {self.loc}, {self.arr}, {self.completed})'

class Base_car_fleet:
    ## INIT METHODS
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

        self.fleet = [Car(s, t, self.all_paths[s][t][0], nx.path_weight(self.graph, self.all_paths[s][t][0], 'weight')) for s, t in self.trajs]
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
    
    def reset_edge(self, edge_data):
        edge_data['load']=0
        return edge_data
    
    ## GET METHODS
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
        return {(car.loc, car.arr):car.path for car in self.fleet if not car.completed}

    def get_edge_blocked(self):
        return {(u,v):edge_data['weight']>2 for u,v,edge_data in list(self.rx_helper.nx_graph.edges(data=True))}
        
    def get_cost(self, path, weight):
        return nx.path_weight(self.rx_helper.nx_graph, path, weight)

    def get_path_and_cost(self, node1, node2, weight):
        path = self.rx_helper.get_shortest_path(node1, node2, weight)
        cost = nx.path_weight(self.rx_helper.nx_graph, path, weight)
        return path, cost
    
    ## LOGIC METHODS    
    def select_min_weight_lane(self, node1, node2, weight):
        """
    In MultiDiGraph, selects the path with minimum weight.
        """   
        lanes=self.rx_helper.nx_graph[node1][node2]

        if self.is_multi:
            selected_id=min(lanes, key=lambda k : lanes[k].get(weight))
            return selected_id, lanes[selected_id]
        else:
            return None, lanes

    def check_edges_along_path(self, path, dist=3):
        edges = []
        for k, (u, v) in enumerate(it.pairwise(path), start=1):
            if u == v:
                edges.append(0)
                continue
            
            if k<=dist: 
                _, edge=self.select_min_weight_lane(u,v,'weight')
                edges.append(edge['weight'])
        return edges
    
    def get_paths_to_calculate(self, paths:dict, edges_state:dict, dist=3):
        """
    Returns the paths to recompute, in the form of a tuple (source, target)
    The newly blocked roads within a certain radius are chosen to be recomputed.
        """
        to_calculate=[]
        if dist>len(edges_state):
            dist=len(edges_state)

        for k, ((s,t), path) in enumerate(paths.items()):
            if (s,t) in edges_state.keys():
                edge_state=edges_state[(s,t)]
                # Si on a cassé l'ancien chemin OU les arêtes ont changé d'état OU (path est vide ???)
                if not nx.is_path(self.rx_helper.nx_graph, path) or self.check_edges_along_path(path, dist)!=edge_state[:dist] or all(path):
                    to_calculate.append((s, t))
            else:
                to_calculate.append((s, t))
        return to_calculate

    @timeit
    def calculate_paths(self, dist):
        """
    Recomputes car paths if their state within a certain radius have changed.
        """
        to_calculate=self.get_paths_to_calculate(self.get_paths(), self.edges_state, dist)
        for s,t in to_calculate:
            path = self.get_path(s, t, weight='weight')
            self.edges_state[(s,t)] = self.check_edges_along_path(path)
            self.all_paths[s][t] = [path]

    def handle_interactions(self, node1, node2, demand_delta, new_weight, op):
        if node1!=node2 and self.rx_helper.nx_graph.has_edge(node1,node2): # Prevent self-loops from interacting (arrival node for example)
            edge_id, edge=self.select_min_weight_lane(node1, node2, 'weight')
            edge['load']+=demand_delta
            if op(edge['load'], edge['capacity']):
                self.rx_helper.update_edge(node1, node2, edge_id, 'weight', new_weight) # WORKS for DiGraph ?