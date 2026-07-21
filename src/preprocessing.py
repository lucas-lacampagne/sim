import networkx as nx
import osmnx as ox
import numpy as np

from shapely.geometry import LineString

class preprocessing:
    def __init__(self):
        self.graph=None
    
    def get_graph(self, city="Piedmont, California, USA", network_type="drive", show=True):
        self.graph = ox.graph.graph_from_place(city, network_type="drive")
        if show:
            ox.plot.plot_graph(self.graph, show=show)
        return self.graph
    
    def add_attributes(self, show=False):
        for u,v,k in self.graph.edges:
            if 'geometry' not in self.graph.edges[u,v,k]:
                self.graph[u][v][k]['geometry']=LineString([[self.graph.nodes[u]['x'], self.graph.nodes[u]['y']], [self.graph.nodes[v]['x'], self.graph.nodes[v]['y']]])
            
            attrs_e = {(u, v, k): {
                'load': 0, 
                'weight': 1, 
                'capacity': 10
                }
            }
            nx.set_edge_attributes(self.graph, attrs_e)
        if show:
            for u,v,k in self.graph.edges:
                print(self.graph[u][v][k])
                break
    
    def get_lscc(self):
        return max(list(nx.strongly_connected_components(self.graph)), key=len)

    def get_lscc_size(self, prop=False):
        if prop:
            return len(self.get_lscc())/self.graph.number_of_nodes()
        else:
            return len(self.get_lscc())