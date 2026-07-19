import time
import datetime

import numpy as np
import pandas as pd
import geopandas as gpd
import networkx as nx
from shapely import LineString

import operator
import itertools as it

from src.display import Display
from src.rustworkx_helper import rx_helper
from src.routingkit_helper import rk_helper
from src.car import Car
from src.attack_helper import attack_helper
from src.utils import select_min_weight_lane, timeit

class Sim:
    ## INIT METHODS
    @timeit
    def __init__(self, graph, helper:rx_helper|rk_helper, size=50, log_trajs:int=0):
        self.graph: nx.MultiDiGraph | nx.DiGraph = graph
        self.is_multi = type(graph)==nx.MultiDiGraph
        self.display_h=Display()

        cnt=0
        while True:
            trajs = self.init_trajs(size)
            if all(nx.has_path(graph, s, t) for s, t in trajs):
                break
            cnt+=1
            print(f"{cnt}th time regenerating trajectories: some nodes were disconnected.", end='\r')
        self.clock=datetime.datetime.now()
        self.log_trajs=log_trajs

        self.calc_helper:rx_helper|rk_helper=helper(self.graph, trajs)
        self.fleet = [Car(self.graph, id, s, t, path:=self.calc_helper.get_shortest_path(s, t), nx.path_weight(self.graph, path, 'weight')) for id, (s, t) in enumerate(trajs)]
        self.trajs = gpd.GeoDataFrame([(self.clock, car.loc, car.id) for car in self.fleet[:log_trajs]], columns=['t', 'geometry', 'trajectory_id'], crs=self.graph.graph['crs'])
        self.edges_state = {(car.dep, car.arr) :
            self.check_edges_along_path(car.path) for car in self.fleet
        }

        self.attack_helper=attack_helper(self.calc_helper)

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
    
    def get_paths(self):
        return {(car.next_true_node, car.arr):car.path for car in self.fleet if not car.completed}

    def get_edge_blocked(self):
        return {(u,v):edge_data['weight']>2 for u,v,edge_data in list(self.calc_helper.nx_graph.edges(data=True))}
    
    def log_info(self, car):
        if car.cost>1000:
            self.info.append((car.last_true_node, car.next_true_node))
    
    def save_trajs(self, filename):
        trajs=self.trajs.to_crs('epsg:4326')
        trajs['t']=pd.to_datetime(trajs['t'])
        trajs.to_file(filename)
    
    def format_trajs_step(self):
        l=[]
        for car in self.get_fleet(include_completed=False)[:self.log_trajs]:
            for t, geom in car.traj:
                l.append((t, geom, car.id))
        return gpd.GeoDataFrame(l, columns=['t', 'geometry', 'trajectory_id'], crs=self.graph.graph['crs'])

    
    ## LOGIC METHODS    
    def check_edges_along_path(self, path, dist=3):
        edges = []
        for k, (u, v) in enumerate(it.pairwise(path), start=1):
            if u == v:
                edges.append(0)
                continue
            
            if k<=dist: 
                _, edge=select_min_weight_lane(self.calc_helper.nx_graph, u,v,'weight')
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
                    if not self.calc_helper.is_path(path) or self.check_edges_along_path(path, dist)!=edge_state[:dist] or all(path):
                        to_calculate.append((s, t))
                else:
                    to_calculate.append((s, t))
        return to_calculate
    
    def get_path(self, node1, node2, weight) -> list: #Jamais None pck on bosse sur une seule composante
        if nx.has_path(self.calc_helper.nx_graph, node1, node2):
            return self.calc_helper.calculate_shortest_path(node1, node2, weight)
        elif nx.has_path(self.graph, node1, node2):
            path=nx.shortest_path(self.graph, node1, node2, weight)
            for k,u in enumerate(path, start=1):
                if not nx.is_path(self.calc_helper.nx_graph, path[:k]): #Oriented ?
                    break
            return path[:k-1]
    
    def get_cost(self, path, weight):
        return nx.path_weight(self.calc_helper.nx_graph, path, weight)
    
    @timeit
    def calculate_paths(self, dist):
        """
    Recomputes car paths if their state within a certain radius have changed.
        """
        to_calculate=self.get_paths_to_calculate(self.get_paths(), self.edges_state, dist)
        for s,t in to_calculate:
            path = self.get_path(s, t, weight='weight')
            self.edges_state[(s,t)] = self.check_edges_along_path(path)
            self.calc_helper.all_paths[s][t] = [path]
        return self.calc_helper.all_paths

    def handle_interactions(self, node1, node2, edge_id, demand_delta, new_weight, op)->False:
        edge=self.calc_helper.nx_graph[node1][node2][edge_id]
        edge['load']+=demand_delta
        if op(edge['load'], edge['capacity']):
            self.calc_helper.update_edge(node1, node2, edge_id, 'weight', new_weight) # WORKS for DiGraph ?
        return False
    
    def move(self, car: Car, time_step: float = 20):
        """
    Moves a car along its path for a given time step.
    Handles edge transitions, interaction updates (load increments/decrements),
    and path completion.
        """
        time_remaining = time_step
        speed = 50 / 3.6  # m/s

        while time_remaining > 0 :

            # Si l'arête E_k sur laquelle t'étais censée passer existe plus, arrête toi
            if not self.calc_helper.nx_graph.has_edge(car.last_true_node, car.next_true_node, car.next_edge_key):
                break

            edge = self.calc_helper.nx_graph[car.last_true_node][car.next_true_node][car.next_edge_key]
            geom: LineString = edge['geometry']
            
            dist_from_start = geom.project(car.loc)
            dist_to_go = speed * time_remaining
            new_dist = dist_from_start + dist_to_go

            # Si tu vas aller plus loin que le prochain noeud
            if new_dist >= geom.length:
                time_used = (geom.length - dist_from_start) / speed
                time_remaining -= time_used

                # Si tu sais où aller après le prochain noeud, check quelle arête E_k+1 tu vas prendre
                if len(car.path)>1: 
                    next_edge_key, _ = select_min_weight_lane(
                                self.calc_helper.nx_graph, car.next_true_node, car.path[1], 'weight' 
                            )
                    
                # Si ton prochain noeud c'est l'arrivée, y a pas de prochaine arête, vas-y
                elif car.next_true_node==car.arr: 
                    if not car.first_step:
                        self.handle_interactions(car.last_true_node, car.next_true_node,
                            car.next_edge_key, -1, 1, op=operator.lt)
                    car.go_to_next_true_node(self.calc_helper.nx_graph)
                    car.log_traj(self.log_trajs, self.clock+datetime.timedelta(seconds=time_step-time_remaining))
                    break

                # Si l'arête E_k+1 n'existe pas car bloquée, arrête toi au bout de la route
                else:
                    car.loc = geom.interpolate(geom.length)
                    car.log_traj(self.log_trajs, self.clock+datetime.timedelta(seconds=time_step-time_remaining))
                    break

                if not car.first_step:
                    car.first_step=self.handle_interactions(car.last_true_node, car.next_true_node,
                                            car.next_edge_key, -1, 1, op=operator.lt)
                
                road = car.go_to_next_true_node(self.calc_helper.nx_graph)
                car.log_traj(self.log_trajs, self.clock+datetime.timedelta(seconds=time_step-time_remaining))
                car.first_step=False
                
                car.next_edge_key = next_edge_key
                self.handle_interactions(car.last_true_node, car.next_true_node,
                                        car.next_edge_key, 1, 10000, op=operator.ge)
            # Si tu vas pas plus loin que le prochain noeud, avance sur l'arête E_k
            else:
                if car.first_step:
                    car.first_step=self.handle_interactions(car.last_true_node, car.next_true_node, car.next_edge_key, 1, 10000, op=operator.ge)
                car.loc = geom.interpolate(new_dist)
                car.log_traj(self.log_trajs, self.clock+datetime.timedelta(seconds=time_step-time_remaining))
                time_remaining = 0

        return car.loc
    
    @timeit
    def update_fleet(self, time_step):
        """
    Updates car states and handles interactions during displacement.
        """
        for car in self.get_fleet(include_completed=False):
            car.reset_traj()
            # On recalcule pas le chemin à un pas de l'arrivée si on sait où on va
            if car.next_true_node!=car.arr:
                path = self.calc_helper.get_shortest_path(car.next_true_node, car.arr)
                car.path=path
                car.cost=self.get_cost(path, 'weight')
                self.log_info(car)
            
            # Bouge
            point=self.move(car, time_step)

            # On supprime pas l'ancien état puisque deux voitures peuvent se suivre
            self.edges_state[(car.next_true_node, car.arr)]=self.check_edges_along_path(car.path)