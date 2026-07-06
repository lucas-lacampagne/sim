from collections import Counter
import networkx as nx
import numpy as np
import osmnx as ox
from matplotlib import colormaps

import folium
from IPython.display import IFrame, display
import base64
import time
import copy
import pandas as pd
import movingpandas as mpd

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

class Display:
    def __init__(self, shuffle=True):
        self.colors = [
                'red',
                'gray',
                'darkred',
                # 'lightred',
                'orange',
                'beige',
                'green',
                'darkgreen',
                'lightgreen',
                'lightblue',
                'purple',
                # 'darkpurple',
                'pink',
                'lightgray',
                # 'black'
            ]
        if shuffle:
            np.random.shuffle(self.colors)
        pass

    def get_edge_c(self, graph, cmap='RdYlGn_r'):
        cmap=colormaps[cmap]
        edge_load = {(u,v,k):edge_data['load']/edge_data['capacity'] for u,v,k,edge_data in list(graph.edges(keys=True,data=True))}
        edge_c=sorted(list(set(edge_load.values())))
        edge_c={load:color for load,color in zip(edge_c, cmap(edge_c))}
        return {k:edge_c[load] for k,load in edge_load.items()}
    
    def transform_df(self, df):
        df_copy=copy.deepcopy(df)
        df_copy=df_copy.to_crs('epsg:4326')
        df_copy['t']=pd.to_datetime(df_copy['t'])
        df_copy['trajectory_id']=df_copy['trajectory_id'].astype('str')
        return df_copy
    
    @timeit
    def display(self, demand, ax):
        """
        Displays city (self.graph) and traffic (self.fleet).
        """
        node_c = get_dict(list(demand.graph.nodes), demand.get_last_nodes_visited(include_completed=False), 
                          [], #demand.get_arr(include_completed=False), 
                          'r', 'g', 'grey')
        node_size = {node:Count(demand.get_last_nodes_visited(include_completed=False))[node]**0.5*15 for node in list(demand.graph.nodes)}
        if demand.is_multi:
            edge_c = {(u,v,k):'y' if edge_data['load']>0 else 'grey' for u,v,k,edge_data in list(demand.graph.edges(keys=True,data=True))}
            for u,v,k in edge_c.keys():
                if edge_c[(u,v,k)]=='y':
                    try:
                        edge_c[(v,u,k)]=='y'
                    except:
                        pass
        else:
            edge_c = {(u,v):'y' if edge_data['weight']>2 else 'grey' for u,v,edge_data in list(demand.graph.edges(data=True))}
        for edge in demand.info:
            edge_c[edge]='r'
        edge_alpha = {(u,v,k):1 if demand.rx_helper.nx_graph.has_edge(u,v,k) else 0. for u,v,k,edge_data in list(demand.graph.edges(keys=True,data=True))}
        
        # print(edge_c)
        ox.plot.plot_graph(
                nx.MultiDiGraph(demand.graph),
                ax=ax,          # Use the animation's axis
                show=False,     # Don't open a new window now
                close=False,    # Don't close the plot
                node_color=list(node_c.values()),
                node_size=list(node_size.values()),
                edge_alpha=list(edge_alpha.values()),
                edge_color=list(edge_c.values())
            )

    @timeit
    def display_huge(self, demand, ax=None, cmap='RdYlGn_r'):
        """
    Displays city (demand.graph) and traffic (demand.fleet).
        """
        
        node_c = get_dict(list(demand.graph.nodes), demand.get_last_nodes_visited(include_completed=False), 
                          [], #demand.get_arr(include_completed=False), 
                          'grey', 'grey', 'grey')
        node_size = {node:Count(demand.get_last_nodes_visited(include_completed=False))[node]**0.5*15 for node in list(demand.graph.nodes)}
        edge_c=self.get_edge_c(demand.rx_helper.nx_graph, cmap)
        edge_alpha = {(u,v,k):1 if demand.rx_helper.nx_graph.has_edge(u,v,k) else 0. for u,v,k,edge_data in list(demand.graph.edges(keys=True,data=True))}
        
        ox.plot.plot_graph(
                nx.MultiDiGraph(demand.rx_helper.nx_graph),
                ax=ax if ax else None,          # Use the animation's axis
                show=False,     # Don't open a new window now
                close=False,    # Don't close the plot
                node_color=list(node_c.values()),
                node_size=list(node_size.values()),
                edge_alpha=list(edge_alpha.values()),
                edge_color=list(edge_c.values())
            )


    def show_folium_safe(self, m : folium.Map, height=500):
        """
        Displays a Folium map in a safe IFrame using Base64 encoding.
        This avoids "Trusted" errors, file path issues, and CSS leakage.
        """
        html_content = m.get_root().render()
        encoded = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
        data_uri = f"data:text/html;charset=utf-8;base64,{encoded}"
        display(IFrame(src=data_uri, width="100%", height=height), clear=True)

    @timeit
    def display_graph(self, graph, demand=None, include_trajs=False, include_markers=False, show=True, m=None):
        nodes, edges = ox.convert.graph_to_gdfs(graph)
        if demand:
            edges['color']=self.get_edge_c(demand.rx_helper.nx_graph)
        m = edges.explore(
            tiles="cartodbdarkmatter",
            m=m if m else None,
            color='color' if demand else None
        )
        map=nodes.explore(
            m=m,
            marker_kwds={"radius": 3}
        )
        if demand:
            if include_trajs:
                self.tc = mpd.TrajectoryCollection(self.transform_df(demand.trajs), "trajectory_id", t="t")
                m=self.tc.explore(column="trajectory_id", cmap=self.colors[:demand.log_trajs], style_kwds={"weight": 4}, m=m)

            if include_markers and demand.log_trajs:
                for _, row in demand.trajs.to_crs('epsg:4326').iterrows():
                    car=demand.fleet[row['trajectory_id']]
                    folium.Marker(
                        location=[row['geometry'].y, row['geometry'].x],
                        tooltip=f"{car.arr}",
                        popup=car.__repr__(),
                        icon=folium.Icon(color=self.colors[row['trajectory_id']],icon=f"{row['trajectory_id']}", prefix='fa'),
                    ).add_to(map)

        if show:
            self.show_folium_safe(map)
        return map
    

    def highlight_node(self, graph, node, markers=None):
        nodes, edges = ox.convert.graph_to_gdfs(nx.ego_graph(graph, node, radius=2))

        m = edges.explore(
            tiles="cartodbdarkmatter",
        )
        map=nodes.explore(
            m=m, 
            marker_kwds={"radius": 3}
        )
        if markers:
            for k,marker in enumerate(markers):
                point_geom_proj, crs = (
                    ox.projection.project_geometry(
                        marker, 
                        crs=graph.graph['crs'], 
                        to_latlong=True
                        )
                )
                folium.Marker(
                    location=[point_geom_proj.y, point_geom_proj.x],
                    icon=folium.Icon(icon=f"{k}", prefix='fa'),
                ).add_to(map)
        self.show_folium_safe(map)
        return map
