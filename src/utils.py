import networkx as nx
import time
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