from collections import Counter
import networkx as nx
import numpy as np
import osmnx as ox
from matplotlib import colormaps
from matplotlib import colors

import folium
from IPython.display import IFrame, display
import base64
import time
import copy
import pandas as pd
import movingpandas as mpd
from folium.plugins import HeatMapWithTime
import itertools as it

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

    def get_edge_c(self, graph, values:pd.Series=False, cmap='RdYlGn_r', norm_func=colors.Normalize):
        cmap=colormaps[cmap]
        if type(values)==bool and values==False:
            edge_values = {(u,v,k):edge_data['load']/edge_data['capacity'] for u,v,k,edge_data in list(graph.edges(keys=True,data=True))}
            norm_edge_values = edge_values
        else:
            norm = norm_func(vmin=0, vmax=values.max())
            edge_values = {(u,v,k):values[(u,v,k)] if (u,v,k) in values.keys() else 0 for u,v,k,edge_data in list(graph.edges(keys=True,data=True))}
            norm_edge_values = {(u,v,k):norm(values[(u,v,k)]) if (u,v,k) in values.keys() else 0 for u,v,k,edge_data in list(graph.edges(keys=True,data=True))}
        
        edge_unique_values=sorted(list(set(norm_edge_values.values())))
        value_to_color={load:color for load, color in zip(edge_unique_values, cmap(edge_unique_values))}
        return {k:colors.to_hex(value_to_color[load]) for k,load in norm_edge_values.items()}, edge_values

    def trajs_to_count(self, trajs):
        df=trajs.sort_values(by='trajectory_id').reset_index(drop=True)
        df=df.loc[df['edge'].shift(-1) != df['edge']]
        return df['edge'].value_counts()
    
    def transform_df(self, df):
        df_copy=copy.deepcopy(df)
        df_copy=df_copy.to_crs('epsg:4326')
        df_copy['t']=pd.to_datetime(df_copy['t'])
        df_copy['trajectory_id']=df_copy['trajectory_id'].astype('str')
        return df_copy
    
    def format_string(self, demand):
        string=f'''
Completed: {sum(demand.get_completed())} of {len(demand.fleet)}
Blocked by traffic: {sum(demand.get_edge_blocked().values())} of {demand.graph.number_of_edges()}
'''
        if demand.attack:
            string+=f'Blocked by attack: {len(list(it.chain.from_iterable(demand.attack_helper.rmvd_edges)))}'
        string+=f'High cost paths: {len(demand.info)}'
        return string
    
    @timeit
    def display(self, demand, ax):
        """
        Displays city (self.graph) and traffic (self.fleet).
        """
        node_c = get_dict(list(demand.graph.nodes), demand.get_last_nodes_visited(include_completed=False), 
                          [], #demand.get_arr(include_completed=False), 
                          'r', 'g', 'grey')
        node_size = {node:Count(demand.get_last_nodes_visited(include_completed=False))[node]**0.5*15 for node in list(demand.graph.nodes)}
        edge_c = {(u,v,k):'y' if edge_data['load']>0 else 'grey' for u,v,k,edge_data in list(demand.graph.edges(keys=True,data=True))}
        for u,v,k in edge_c.keys():
            if edge_c[(u,v,k)]=='y':
                try:
                    edge_c[(v,u,k)]=='y'
                except:
                    pass
        for edge in demand.info:
            edge_c[edge]='r'
        edge_alpha = {(u,v,k):1 if demand.calc_helper.nx_graph.has_edge(u,v,k) else 0. for u,v,k,edge_data in list(demand.graph.edges(keys=True,data=True))}
        
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
        edge_c=self.get_edge_c(demand.calc_helper.nx_graph, cmap)
        edge_alpha = {(u,v,k):1 if demand.calc_helper.nx_graph.has_edge(u,v,k) else 0. for u,v,k,edge_data in list(demand.graph.edges(keys=True,data=True))}
        
        ox.plot.plot_graph(
                nx.MultiDiGraph(demand.calc_helper.nx_graph),
                ax=ax if ax else None,          # Use the animation's axis
                show=False,     # Don't open a new window now
                close=False,    # Don't close the plot
                node_color=list(node_c.values()),
                # node_size=list(node_size.values()),
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
    def display_graph(self, graph, demand=None, values:pd.Series=False, norm_func=colors.Normalize, include_trajs=False, include_markers=False, show=True, m=None):
        """
        values : Series with (u,v,k) as keys and edge value (for example vehicle count)
        """
        nodes, edges = ox.convert.graph_to_gdfs(graph)
        if demand:
            edges['color'], edges['value_displayed']=self.get_edge_c(demand.calc_helper.nx_graph, values, norm_func=norm_func)
        m = edges.explore(
                m=m if m else None,
                style_kwds={
                    'style_function': lambda x: {"color":x['properties']['color']}
                    } if demand else None
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

    def display_heatmap(self, demand, show=True):
        df=demand.trajs.rename(columns={'load':'weight'}).sort_values(by=['t', 'trajectory_id'])
        df['t']=pd.to_datetime(df['t'])
        df=df.to_crs('4326')

        times=sorted(list(set(df['t'])))
        data=[]
        for t in times:
            t_list=[]
            for id, row in df[df['t']==t].iterrows():
                t_list.append([row['geometry'].y, row['geometry'].x, row['weight']])
            data.append(t_list)

        times=[time.strftime("%H:%M:%S") for time in times]
        m = folium.Map(
                [data[0][0][0], data[0][0][1]], 
                zoom_start=14, 
                tiles='OpenStreetMap'
            )

        hm = HeatMapWithTime(data, 
                            times,
                            radius = 6,
                            blur = 0.7,
                            min_speed= 2,
                            ).add_to(m)
        if show:
            self.show_folium_safe(m)
        return m