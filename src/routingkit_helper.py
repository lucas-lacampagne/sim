import networkx as nx
import routingkit_cch as rk
import copy
from collections import defaultdict

class rk_helper:
    def __init__(self, graph : nx.MultiDiGraph, trajs, order='inertial'):
        self.nx_graph = graph.copy()
        self.rk_to_nx={k:v for k,v in enumerate(self.nx_graph.nodes)}
        self.nx_to_rk={v:k for k,v in self.rk_to_nx.items()}
        self.edge_nx_to_rk={(u,v,k):i for i,(u,v,k) in enumerate(self.nx_graph.edges)}
        self.edge_rk_to_nx={v:k for k,v in self.edge_nx_to_rk.items()}
        self.nk_graph=nx.relabel_nodes(self.nx_graph, self.nx_to_rk) # NX_G IS LABELED [0, N]
        
        self.node_count=self.nk_graph.number_of_nodes()
        self.tail = [u for u,v,k in self.nk_graph.edges]
        self.head = [v for u,v,k in self.nk_graph.edges]
        self.weights = [self.nk_graph[u][v][k]['weight'] for u,v,k in self.nk_graph.edges]

        if order=='degree':
            order = rk.compute_order_degree(self.node_count, self.tail, self.head)
        elif order=='inertial':
            self.lat=[self.nk_graph.nodes[n_id]['y'] for n_id in self.nk_graph.nodes]
            self.lon=[self.nk_graph.nodes[n_id]['y'] for n_id in self.nk_graph.nodes]
            order = rk.compute_order_inertial(self.node_count, self.tail, self.head, self.lat, self.lon)

        self.cch = rk.CCH(order, self.tail, self.head, False)
        self.metric = rk.CCHMetric(self.cch, self.weights)
        self.updater = rk.CCHMetricPartialUpdater(self.cch)
        self.reset_all_paths()
        for s,t in trajs:
            self.all_paths[s][t]=[self.calculate_shortest_path(s,t)]

    # def add_edge(self, u, v, k, data):
    #     self.tail.append(u)
    #     self.head.append(v)
    #     self.weights.append(data['weight'])

    #     # rx_u, rx_v = self.nx_to_rx[u], self.nx_to_rx[v]
    #     # rx_idx = self.rx_g.add_edge(rx_u, rx_v, data)
    #     # self.edge_nx_to_rx[(u, v, k)] = rx_idx

    # def remove_edge(self, u, v, k):
    #     self.nk_graph.remove_edge(u, v, k)
    #     rx_idx = self.edge_nx_to_rx.pop((u, v, k))
    #     self.rx_g.remove_edge_from_index(rx_idx)

    def reset_all_paths(self):
        self.all_paths=defaultdict(dict)

    def update_edge(self, u, v, k, update_key:str, update_value):
        self.nk_graph[self.nx_to_rk[u]][self.nx_to_rk[v]][k][update_key]=update_value
        rk_idx = self.edge_nx_to_rk[u, v, k]
        if update_key=='weight':
            self.updater.apply(self.metric, {rk_idx:update_value})

    def map_id(self, d:dict|int|list, mapping_dict:dict):
        if type(d)==int:
            return mapping_dict[d]
        elif type(d)==dict:
            return {mapping_dict[k]:[[mapping_dict[node] for node in v]] if v is not None else k for k,v in d.items()}
        elif type(d)==list:
            return [mapping_dict[node] for node in d]
        
    def is_path(self, path):
        return nx.is_path(self.nk_graph, path)

    def calculate_shortest_path(self, nx_source, nx_target, weight='weight'):
        q = rk.CCHQuery(self.metric)
        path = q.run(self.nx_to_rk[nx_source], self.nx_to_rk[nx_target]).node_path
        return self.map_id(path, self.rk_to_nx)
    
    def get_shortest_path(self, nx_source, nx_target, weight='weight'):
        return copy.deepcopy(self.all_paths[nx_source][nx_target][0])