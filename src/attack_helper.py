from src.rustworkx_helper import rx_helper
from src.attack.attack import feature_based_attack
from src.utils import timeit
import itertools as it

class attack_helper:
    def __init__(self, calc_helper):
         self.calc_helper=calc_helper

    @timeit
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
        if attack=='ebc' and type(self.calc_helper)==rx_helper:
            rx_edges = feature_based_attack(self.calc_helper.rx_g.copy(), l=number_steps*batch_size, attack_name=attack)
            edges=[self.calc_helper.edge_rx_to_nx[rx_edge] for rx_edge in rx_edges]
        else:
            edges = feature_based_attack(self.calc_helper.nx_graph.copy(), l=number_steps*batch_size, attack_name=attack, 
                                    #  igraph=ig.Graph.from_networkx(self.graph.copy())
                                    )
        self.rmvd_edges=[]
        self.to_rmv_edges = edges
        self.to_rmv_edges = list(it.batched(self.to_rmv_edges, n=batch_size))
        print ("Launching simulation", end="\r")

    def launch_attack(self, step, end_step=30):
        def _attack(u,v,k):
            if self.calc_helper.nx_graph.has_edge(u,v,k):
                edge_data=self.calc_helper.nx_graph[u][v][k]
                edges_rmvd.append([(u,v,k), edge_data])
                self.calc_helper.remove_edge(u,v,k)
                
        if self.to_rmv_edges:
            if step<end_step:
                edges=self.to_rmv_edges.pop(0)
                edges_rmvd=[]
                for (u,v,k) in edges:
                    _attack(u,v,k)
                    _attack(v,u,k)
                self.rmvd_edges.append(edges_rmvd)

    def repair_attack(self, step, launch_step=30):
        if self.rmvd_edges:
            if step>launch_step:
                edges=self.rmvd_edges.pop(0)
                for (u,v,k), data in edges:
                    self.calc_helper.add_back_edge(u,v,k,data)