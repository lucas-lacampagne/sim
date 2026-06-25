import networkx as nx

import copy
from shapely.geometry import Point

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.INFO)

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
        return f'(({self.dep},{self.arr}), {self.last_true_node}, {self.next_true_node}, {self.cost})'