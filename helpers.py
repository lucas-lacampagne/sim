from collections import Counter
import time
import rustworkx as rx
import networkx as nx
import numpy as np
import itertools as it
import osmnx as ox
import matplotlib

import copy
import base64
import folium
from IPython.display import IFrame, display
import base64
from shapely.geometry import LineString, Point
from attack.attack import feature_based_attack

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

def select_min_weight_lane(graph, node1, node2, weight):
    """
In MultiDiGraph, selects the path with minimum weight.
    """   
    lanes=graph[node1][node2]

    if type(graph)==nx.MultiDiGraph:
        selected_id=min(lanes, key=lambda k : lanes[k].get(weight))
        return selected_id, lanes[selected_id]
    else:
        return None, lanes

def show_folium_safe(m : folium.Map, height=500):
    """
    Displays a Folium map in a safe IFrame using Base64 encoding.
    This avoids "Trusted" errors, file path issues, and CSS leakage.
    """
    html_content = m.get_root().render()
    encoded = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
    data_uri = f"data:text/html;charset=utf-8;base64,{encoded}"
    display(IFrame(src=data_uri, width="100%", height=height), clear=True)

def display_graph(graph, demand=None, show=True):
    nodes, edges = ox.convert.graph_to_gdfs(graph)

    m = edges.explore(
        tiles="cartodbdarkmatter"
    )
    map=nodes.explore(
        m=m, 
        marker_kwds={"radius": 3}
    )
    if demand and demand.log_trajs:
        colors = [
            'red',
            'gray',
            'darkred',
            'lightred',
            'orange',
            'beige',
            'green',
            'darkgreen',
            'lightgreen',
            'lightblue',
            'purple',
            'darkpurple',
            'pink',
            'lightgray',
            'black'
        ]
        np.random.shuffle(colors)
        for k,(car,color) in enumerate(zip(demand.fleet, colors)):
            for point in car.traj:
                point_geom_proj, crs = (
                    ox.projection.project_geometry(
                        point, 
                        crs=demand.graph.graph['crs'], 
                        to_latlong=True
                        )
                )

                folium.Marker(
                    location=[point_geom_proj.y, point_geom_proj.x],
                    tooltip=f"{car.arr}",
                    popup=car.__repr__(),
                    icon=folium.Icon(color=color,icon=f"{k}", prefix='fa'),
                ).add_to(map)
    if show:
        show_folium_safe(map)
    return map

class rx_helper:
    def __init__(self, graph : nx.MultiDiGraph):
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

    def add_edge(self, u, v, k, data):
        self.nx_graph.add_edge(u, v, k, **data)
        rx_u, rx_v = self.nx_to_rx[u], self.nx_to_rx[v]
        rx_idx = self.rx_g.add_edge(rx_u, rx_v, data)
        self.edge_nx_to_rx[(u, v, k)] = rx_idx

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

    def get_all_shortest_paths(self, weight:str='weight'):
        rx_paths={k:dict(v) for k,v in dict(rx.all_pairs_dijkstra_shortest_paths(
            self.rx_g,
            edge_cost_fn=lambda x:x.get(weight))).items()
            }
        nx_rx_paths={self.map_id(k, self.rx_to_nx): self.map_id(v, self.rx_to_nx) for k,v in rx_paths.items()}
        return nx_rx_paths

    def get_shortest_path(self, nx_source, nx_target, weight='weight'):
        path = rx.dijkstra_shortest_paths(self.rx_g, self.nx_to_rx[nx_source], self.nx_to_rx[nx_target],weight_fn=lambda x:x.get(weight))
        return self.map_id(list(list(dict(path).values())[0]), self.rx_to_nx)

class Car:
    def __init__(self, graph:nx.MultiDiGraph, departure_node:int, arrival_node:int, path:list[int], cost:int):
        self.dep=departure_node
        self.arr=arrival_node
        self.completed=(departure_node==arrival_node)

        self.path=copy.deepcopy(path) #list of following true nodes - begins with next_true_node
        self.cost=cost

        self.last_true_node=self.path.pop(0)
        self.next_true_node=self.path[0]
        self.check_next_edge=True
        self.next_edge_key=0

        self.loc=graph.nodes[departure_node]['x'], graph.nodes[departure_node]['y']
        self.loc=Point(self.loc)
        self.traj=[self.loc]

    def go_to_next_true_node(self, graph:nx.MultiDiGraph, next_weight:int):
        self.last_true_node=self.path.pop(0)
        self.loc=Point(graph.nodes[self.last_true_node]['x'], graph.nodes[self.last_true_node]['y'])
        self.cost-=next_weight
        self.next_true_node=self.path[0] if len(self.path)>0 else None
        self.completed=(self.last_true_node==self.arr)
        return self

    
    def __repr__(self):
        return f'({self.dep}, {self.last_true_node}, {self.loc}, {self.next_true_node}, {self.arr}, {self.completed})'

class Base_car_fleet:
    ## INIT METHODS
    def __init__(self, graph, size=50, log_trajs=False):
        self.graph: nx.MultiDiGraph | nx.DiGraph = graph
        self.is_multi = type(graph)==nx.MultiDiGraph
        self.rx_helper=rx_helper(self.graph)
        self.all_paths = self.rx_helper.get_all_shortest_paths()

        cnt=0
        while True:
            trajs = self.init_trajs(size)
            if all(nx.has_path(graph, s, t) for s, t in trajs):
                break
            cnt+=1
            print(f"{cnt}th time regenerating trajectories: some nodes were disconnected.", end='\r')
        self.trajs = trajs
        self.log_trajs=log_trajs

        self.fleet = [Car(self.graph, s, t, self.all_paths[s][t][0], nx.path_weight(self.graph, self.all_paths[s][t][0], 'weight')) for s, t in self.trajs]
        self.num_cars = len(trajs)
        self.edges_state = {(car.dep, car.arr) :
            self.check_edges_along_path(car.path) for car in self.fleet
        }
        self.step=0
        self.info=[]

    def init_trajs(self, size):
        nodes_list=list(self.graph.nodes)
        return [np.random.choice(nodes_list, 2, False) for _ in range(size)]

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
        
    def get_last_nodes_visited(self, include_completed=True):
        if include_completed:
            return [car.last_true_node for car in self.fleet]
        else:
            return [car.last_true_node for car in self.fleet if not car.completed]
        
    def get_arr(self, include_completed=True):
        if include_completed:
            return [car.arr for car in self.fleet]
        else:
            return [car.arr for car in self.fleet if not car.completed]
        
    def get_completed(self):
        return [car.completed for car in self.fleet]
    def all_completed(self):
        return all(self.get_completed())
    
    def get_paths(self): # change to calculate paths from next_true node
        return {(car.next_true_node, car.arr):car.path for car in self.fleet if not car.completed}

    def get_edge_blocked(self):
        return {(u,v):edge_data['weight']>2 for u,v,edge_data in list(self.rx_helper.nx_graph.edges(data=True))}
        
    def get_path(self, node1, node2, weight) -> list: #Jamais None pck on bosse sur une seule composante
        if nx.has_path(self.rx_helper.nx_graph, node1, node2):
            return self.rx_helper.get_shortest_path(node1, node2, weight)
        elif nx.has_path(self.graph, node1, node2):
            path=nx.shortest_path(self.graph, node1, node2, weight)
            for k,u in enumerate(path, start=1):
                if not nx.is_path(self.rx_helper.nx_graph, path[:k]): #Oriented ?
                    break
            return path[:k-1]
    
    def get_cost(self, path, weight):
        return nx.path_weight(self.rx_helper.nx_graph, path, weight)
    
    ## LOGIC METHODS    
    def check_edges_along_path(self, path, dist=3):
        edges = []
        for k, (u, v) in enumerate(it.pairwise(path), start=1):
            if u == v:
                edges.append(0)
                continue
            
            if k<=dist: 
                _, edge=select_min_weight_lane(self.rx_helper.nx_graph, u,v,'weight')
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
            if s!=t:
                if (s,t) in edges_state.keys():
                    edge_state=edges_state[(s,t)]
                    # Si on a cassé l'ancien chemin OU les arêtes ont changé d'état OU (path est vide ???)
                    if not self.rx_helper.is_path(path) or self.check_edges_along_path(path, dist)!=edge_state[:dist] or all(path):
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
        return self.all_paths

    def handle_interactions(self, node1, node2, edge_id, demand_delta, new_weight, op):
        if node1!=node2 and self.rx_helper.nx_graph.has_edge(node1,node2): # Prevent self-loops from interacting (arrival node for example)
            edge=self.rx_helper.nx_graph[node1][node2][edge_id]
            edge['load']+=demand_delta
            if op(edge['load'], edge['capacity']):
                self.rx_helper.update_edge(node1, node2, edge_id, 'weight', new_weight) # WORKS for DiGraph ?

    #HANDLE ATTACK
    def prepare_attack(self, attack='deg', batch_size=5, number_steps=30):
        """
        * 'ebc' for edge betweenness centrality
        * 'rd' for random
        * 'deg' for max degree computed by extremities sum
        * 'xdeg' for max degree computed by extremities product
        * 'mindeg' for min degree computed by extremities sum
        * 'minxdeg' for min degree computed by extremities product
        """
        print ("Preparing attack...", end="\r")
        if attack=='ebc':
            rx_edges = feature_based_attack(self.rx_helper.rx_g.copy(), l=number_steps*batch_size, attack_name=attack)
            edges=[self.rx_helper.edge_rx_to_nx[rx_edge] for rx_edge in rx_edges]
        else:
            edges = feature_based_attack(self.graph.copy(), l=number_steps*batch_size, attack_name=attack, 
                                    #  igraph=ig.Graph.from_networkx(self.graph.copy())
                                    )
        self.rmvd_edges=[]
        self.to_rmv_edges = edges
        self.to_rmv_edges = list(it.batched(self.to_rmv_edges, n=batch_size))
        print ("Launching simulation", end="\r")


    def launch_attack(self, end_step=30):
        def _attack(u,v,k):
            if self.rx_helper.nx_graph.has_edge(u,v,k):
                edge_data=self.rx_helper.nx_graph[u][v][k]
                self.reset_edge(edge_data)
                edges_rmvd.append([(u,v,k), edge_data])
                self.rx_helper.remove_edge(u,v,k)
                
        if self.to_rmv_edges:
            if self.step<end_step:
                edges=self.to_rmv_edges.pop(0)
                edges_rmvd=[]
                for (u,v,k) in edges:
                    _attack(u,v,k)
                    _attack(v,u,k)
                self.rmvd_edges.append(edges_rmvd)

    def repair_attack(self, launch_step=30):
        if self.rmvd_edges:
            if self.step>launch_step:
                edges=self.rmvd_edges.pop(0)
                for (u,v,k), data in edges:
                    self.rx_helper.add_edge(u,v,k,data)

class UnitTest:
    def __init__(self, demand:Base_car_fleet):
        self.demand=demand

    def short_trajs(self):
        self.demand
        graph=self.demand.graph
        dep_node=np.random.choice(list(graph.nodes), 1)[0]
        next_node=list(graph.neighbors(dep_node))[0]
        self.demand.fleet=[Car(self.demand.graph, dep_node, next_node, [dep_node, next_node], 0)]
        self.demand.run(attack=False, repair=False)
        
        ## END TEST
    def end_test_load(self):
        for u,v,k in self.demand.graph.edges:
            assert self.demand.graph[u][v][k]['load']==0

    def run(self):
        self.end_test_load()