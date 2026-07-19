import numpy as np
from src.car import Car

class UnitTest:
    def __init__(self, demand):
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
            for u,v,k in self.demand.calc_helper.nx_graph.edges:
                assert self.demand.calc_helper.nx_graph[u][v][k]['load']==0
        except Exception as e:
            self.demand.display_h.display_huge(self.demand, cmap='prism')
            raise e
    
    def test_graph(self):
        try:
            assert self.demand.calc_helper.nx_graph.number_of_edges()==self.demand.graph.number_of_edges()
            assert self.demand.calc_helper.nx_graph.number_of_nodes()==self.demand.graph.number_of_nodes()
        except Exception as e:
            print(self.demand.calc_helper.nx_graph.number_of_edges(), self.demand.graph.number_of_edges())
            print(self.demand.calc_helper.nx_graph.number_of_nodes(), self.demand.graph.number_of_nodes())
            raise e


    def run(self):
        self.test_load()
        self.test_graph()