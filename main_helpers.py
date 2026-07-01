import time
import networkx as nx
import numpy as np
import itertools as it
from display import Display
from rustworkx_helper import rx_helper
from car import Car

from attack.attack import feature_based_attack

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.INFO)

def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        logging.info(f'{method.__name__} {(te - ts) * 1000 :.2f}')

        return result
    return timed

def select_min_weight_lane(graph, node1, node2, weight='weight'):
    """
In MultiDiGraph, selects the path with minimum weight.
    """   
    lanes=graph[node1][node2]

    if type(graph)==nx.MultiDiGraph:
        selected_id=min(lanes, key=lambda k : lanes[k].get(weight))
        return selected_id, lanes[selected_id]
    else:
        return None, lanes

class Base_car_fleet:
    ## INIT METHODS
    def __init__(self, graph, size=50, log_trajs:int=0):
        self.graph: nx.MultiDiGraph | nx.DiGraph = graph
        self.is_multi = type(graph)==nx.MultiDiGraph
        self.rx_helper=rx_helper(self.graph)
        self.display_h=Display()
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

        self.fleet = [Car(self.graph, id, s, t, self.all_paths[s][t][0], nx.path_weight(self.graph, self.all_paths[s][t][0], 'weight')) for id, (s, t) in enumerate(self.trajs)]
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
    
    def get_fleet(self,include_completed=True):
        if include_completed:
            return [car for car in self.fleet]
        else:
            return [car for car in self.fleet if not car.completed]
        
    def all_completed(self):
        return all(self.get_completed())
    
    def get_paths(self): # change to calculate paths from next_true node
        def get_s_t(car):
            # return (car.next_true_node, car.arr)
            if car.next_true_node:
                return (car.next_true_node, car.arr)
            else:
                return (car.last_true_node, car.arr)
        return {get_s_t(car):car.path for car in self.fleet if not car.completed}

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
    
    def log_info(self, car):
        if car.cost>1000:
            self.info.append((car.last_true_node, car.next_true_node))
    
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

    def handle_interactions(self, node1, node2, edge_id, demand_delta, new_weight, op)->False:
        edge=self.rx_helper.nx_graph[node1][node2][edge_id]
        edge['load']+=demand_delta
        if op(edge['load'], edge['capacity']):
            self.rx_helper.update_edge(node1, node2, edge_id, 'weight', new_weight) # WORKS for DiGraph ?
        return False

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
            edges = feature_based_attack(self.rx_helper.nx_graph.copy(), l=number_steps*batch_size, attack_name=attack, 
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
    def test_load(self):
        try:
            for u,v,k in self.demand.rx_helper.nx_graph.edges:
                assert self.demand.rx_helper.nx_graph[u][v][k]['load']==0
        except Exception as e:
            self.demand.display_h.display_huge(self.demand, cmap='prism')
            raise e
    
    def test_graph(self):
        try:
            assert self.demand.rx_helper.nx_graph.number_of_edges()==self.demand.graph.number_of_edges()
            assert self.demand.rx_helper.nx_graph.number_of_nodes()==self.demand.graph.number_of_nodes()
        except Exception as e:
            print(self.demand.rx_helper.nx_graph.number_of_edges(), self.demand.graph.number_of_edges())
            print(self.demand.rx_helper.nx_graph.number_of_nodes(), self.demand.graph.number_of_nodes())
            raise e


    def run(self):
        self.test_load()
        self.test_graph()