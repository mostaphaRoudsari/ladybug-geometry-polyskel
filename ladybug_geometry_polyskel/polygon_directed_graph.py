# coding=utf-8
"""
Implementation of a Directed Graph.
"""

from __future__ import division

# Geometry classes
from ladybug_geometry.geometry2d.line import LineSegment2D
from ladybug_geometry import intersection2d
from math import log10


def _vector2hash(vector, tol):
    """ Hashes spatial coordinates for use in dictionary.

    Args:
        vector: A Vector2D object.
        tol: floating point precision tolerance.

    Returns:
        Hash of vector as a string of rounded coordinates.
    """
    try:
        rtol = int(log10(tol)) * -1
    except ValueError:
        rtol = 0

    return str((round(vector.x, rtol), round(vector.y, rtol)))


class _Node(object):
    """Private class to handle nodes in PolygonDirectedGraph.

        Args:
            val: Any python object
            key: Hash of passed object
            order: integer counting order of Node (based on dg propagation)
            adj_lst: list of keys: ['key1', 'key2' ....  'keyn']
            exterior: Allows user to pass node boundary condition. None if not
                set by user, else True or False according to user.
    """
    __slots__ = ('key', 'pt', '_order', 'adj_lst', 'exterior')

    def __init__(self, key, val, order, adj_lst, exterior):
        """Initialize _Node"""

        self.key = key
        self.pt = val
        self._order = order
        self.adj_lst = adj_lst
        # IDEA: Change exterior to data (similar to networkX)
        # and pass conditional function to get_exterior
        # this resolves redundancy between unidirect and exterior
        # node/edge properties.
        self.exterior = exterior

    def __repr__(self):
        return '{}: {}'.format(self._order, self.key)

    @property
    def adj_count(self):
        """Number of adjacent nodes"""
        return len(self.adj_lst)


class PolygonDirectedGraph(object):
    """A directed graph for point and edge adjacency relationships.

    This class assumes that exterior edges are naked (unidirectional) and interior
    edges are bidirectional.

    Args:
        tol: floating point precision used for hashing points.

    Properties:
        * num_nodes
    """

    def __init__(self, tol=1e-5):
        """Initialize a PolygonDirectedGraph."""
        self._directed_graph = {}
        self._root = None
        self._tol = tol
        self.num_nodes = 0

    def __repr__(self):
        s = ''
        for n in self.ordered_nodes:
            s += '{}, [{}]\n'.format(
                n.pt.to_array(),
                ', '.join([str(_n.pt.to_array()) for _n in n.adj_lst]))
        return s

    @classmethod
    def from_polygon(cls, polygon):
        """Generate a directed graph from a polygon.

        Args:
            polygon: A Polygon2D object.
        """
        return cls.from_point_array(polygon.vertices, loop=True)

    @classmethod
    def from_point_array(cls, point_array, loop=True):
        """Generate a directed graph from a 1-dimensional array of points.

        Args:
            point_array: Array of Point2D objects.
            loop: Optional parameter to connect 1d array
        """

        dg = cls()
        for i in range(len(point_array) - 1):
            dg.add_node(point_array[i], [point_array[i+1]], exterior=True)

        if loop:
            dg.add_node(point_array[-1], [point_array[0]], exterior=True)

        return dg

    @property
    def root(self):
        """Get the root node, used for traversal of directed graph."""

        if self._root is None:
            self._root = self.ordered_nodes[0]
        return self._root

    def node(self, key):
        """Retrieves the node based on passed value.

        Args:
            val: The key for a node in the directed graph.

        Returns:
            The node for the passed key.
        """

        try:
            return self._directed_graph[key]
        except KeyError:
            return None

    def _check_and_make_node(self, key, val, exterior=None):
        # If key doesn't exist, add to dg
        if key not in self._directed_graph:
            self.num_nodes += 1
            self._directed_graph[key] = _Node(key, val, self.num_nodes - 1, [], exterior)
        return self._directed_graph[key]

    def add_adj(self, node, adj_val_lst):
        """Adds nodes to node.adj_lst.

        This method will ensure no repetitions will occur in adj_lst.

        Args:
            node: _Node to add adjacencies to.
            adj_val_lst: List of Point2D objects to add as adjacent nodes.
        """
        adj_keys = {n.key: None for n in node.adj_lst}
        adj_keys[node.key] = None
        for adj_val in adj_val_lst:
            adj_key = _vector2hash(adj_val, self._tol)
            if adj_key in adj_keys:
                continue

            self._check_and_make_node(adj_key, adj_val, exterior=None)
            adj_keys[adj_key] = None
            node.adj_lst.append(self.node(adj_key))

    def remove_adj(self, node, adj_key_lst):
        """Removes nodes in node.adj_lst.

        Args:
            node: _Node to remove adjacencies to.
            adj_val_lst: List of adjacency keys to remove as adjacent nodes.
        """
        node.adj_lst = [n for n in node.adj_lst if n.key not in set(adj_key_lst)]

    def add_node(self, val, adj_lst, exterior=None):
        """Consumes a polygon point, and computes its key value, and adds it in the
        graph if it doesn't exist. If it does exist it appends adj_lst to existing pt.

        Args:
            val: A Point2D object
            adj_lst: A list of Point2D objects

        Returns:
            The hashed key from the existing or new node.
        """

        # Get key
        key = _vector2hash(val, self._tol)

        # Get node if it exists
        self._check_and_make_node(key, val, exterior)

        node = self._directed_graph[key]

        # Add the adj_lst to dg, and leave exterior None
        self.add_adj(node, adj_lst)

        # If pass exterior boolean, change node attribute
        if exterior is not None:
            node.exterior = exterior

        return node.key

    def insert_node(self, node, new_val, next_node, exterior=None):
        """Insert node in the middle of an edge defined by node and next_node.

        Args:
            node: _Node to left.
            new_val: Value for middle node.
            next_node: _Node to right.
            exterior: Optional boolean for exterior attribute.

        Returns:
            key of new_val node.
        """
        # Add new_val as a node, with next_node as an adjacency
        new_key = self.add_node(new_val, [next_node.pt], exterior=exterior)

        # Update parent by adding new adjacency, and removing old adjacency
        self.add_adj(node, [self.node(new_key).pt])

        # Edge case where the new point is coincident to parent or next_point.
        # This occurs when intersection passes through a corner.
        if (new_key == next_node.key) or (new_key == node.key):
            return new_key

        self.remove_adj(node, [next_node.key])

        return new_key

    def node_exists(self, key):
        """True if node in directed graph else False"""
        return key in self._directed_graph

    @property
    def nodes(self):
        """Get an iterable of pt nodes"""
        return self._directed_graph.values()

    @property
    def ordered_nodes(self):
        """Get an iterable of pt nodes in order of addition"""
        nodes = list(self.nodes)
        nodes.sort(key=lambda v: v._order)
        return nodes

    def adj_matrix(self):
        """Gets an adjacency matrix of the directed graph where:

        * 1 = adjacency from row node to col node.
        * 0 = no adjacency.

        Returns:
            N x N square matrix where N is number of nodes.
        """
        nodes = self.ordered_nodes

        # Initialize amtx with no adjacencies
        amtx = [[0 for i in range(self.num_nodes)]
                for j in range(self.num_nodes)]

        for i in range(self.num_nodes):
            adj_indices = [adj._order for adj in nodes[i].adj_lst]
            for adj_idx in adj_indices:
                amtx[i][adj_idx] = 1

        return amtx

    def adj_matrix_labels(self):
        """Returns a dictionary where label key corresponds to index in adj_matrix
        and value is node key"""
        return {i: node.key for i, node in enumerate(self.ordered_nodes)}

    @staticmethod
    def is_edge_bidirect(node1, node2):
        """Are two nodes bidirectional.

        Args:
            node1: _Node object
            node2: _Node object

        Returns:
            True if node1 and node2 are in each other's adjacency list,
            else False.
        """
        return node1.key in (n.key for n in node2.adj_lst) and \
            node2.key in (n.key for n in node1.adj_lst)

    @staticmethod
    def next_unidirect_node(node):
        """Retrieves the first unidirectional point adjacent
        to consumed point. They define an exterior or naked edge.

        Args:
            node: _Node

        Returns:
            Next node that defines unidirectional edge, or None if all
            adjacencies are bidirectional.
        """
        # Check bidirectionality
        next_node = None
        for _next_node in node.adj_lst:
            if not PolygonDirectedGraph.is_edge_bidirect(node, _next_node):
                next_node = _next_node
                break

        return next_node

    @staticmethod
    def next_exterior_node(node):
        """Retrieves the first exterior node adjacent
        to consumed node. They define an exterior or naked edge.

        Args:
            node: _Node

        Returns:
            Next node that defines exterior edge, or None if all
            adjacencies are bidirectional.
        """

        # Check bidirectionality
        next_node = None
        for _next_node in node.adj_lst:

            if _next_node.exterior is None:
                # If user-assigned attribute isn't defined, check bidirectionality.
                if not PolygonDirectedGraph.is_edge_bidirect(node, _next_node):
                    next_node = _next_node
                    break
            elif _next_node.exterior is True:
                next_node = _next_node
                break

        return next_node

    @staticmethod
    def exterior_cycle(cycle_root):
        """Computes exterior boundary from a given node.

        This method assumes that exterior edges are naked (unidirectional) and
        interior edges are bidirectional.

        Args:
            cycle_root: Starting _Node in exterior cycle.
        Returns:
            List of nodes on exterior if a cycle exists, else None.
        """

        # Get the first exterior edge
        curr_node = cycle_root
        next_node = PolygonDirectedGraph.next_exterior_node(curr_node)
        if not next_node:
            return None

        ext_cycle = [curr_node]
        while next_node.key != cycle_root.key:
            ext_cycle.append(next_node)
            next_node = PolygonDirectedGraph.next_exterior_node(next_node)
            if not next_node:
                return None

        return ext_cycle

    @property
    def exterior_cycles(self):
        """Computes all exterior boundaries.

        Returns:
            List of boundaries as list of nodes. The first polygon will
            be the outer exterior edge (in counter-clockwise order), and
            subsequent edges will be the edges of the holes in the graph
            (in clockwise order).
        """

        exterior_poly_lst = []
        exterior_check = {}

        for root_node in self.ordered_nodes:

            # Store node in check
            exterior_check[root_node.key] = None

            # Get next exterior adjacent node
            next_node = self.next_exterior_node(root_node)
            is_valid = (next_node is not None) and \
                (next_node.key not in exterior_check)

            if not is_valid:
                continue

            # Create list of exterior points
            # and add to dict to prevent repetition
            exterior_poly = [root_node]
            exterior_check[next_node.key] = None

            while next_node.key != root_node.key:
                exterior_poly.append(next_node)
                exterior_check[next_node.key] = None
                next_node = self.next_exterior_node(next_node)

            exterior_poly_lst.append(exterior_poly)

        return exterior_poly_lst

    def smallest_closed_cycles(self, recurse_limit=None):
        """Gets a list of the smallest individual polygons defined by the edges.

        This is achieved by looping through the exterior edges of the directed graph, and
        identifying the closed loop with the smallest counter-clockwise angle of rotation
        between edges. Since the exterior edges of a polygon split by a straight skeleton
        will always result in either a split or edge event, of the interior skeleton,
        this will identify the smallest polygon nested in the directed graph.

        Returns:
            A list of polygon point arrays.
        """

        polygon_node_lst = []

        # Get continous exterior nodes list.
        for node in self.ordered_nodes:
            ext_nodes = self.exterior_cycle(node)
            if ext_nodes is not None:
                break

        # Add first node to ensure complete cycle
        ext_nodes += [ext_nodes[0]]
        for i, ext_node in enumerate(ext_nodes[:-1]):
            next_node = ext_nodes[i + 1]
            cycle = self.min_ccw_cycle(ext_node, next_node,
                                       recurse_limit=recurse_limit, count=0)
            polygon_node_lst.append(cycle)

        return polygon_node_lst

    @staticmethod
    def min_ccw_cycle(ref_node, next_node, cycle=None, recurse_limit=None, count=0):
        """Recursively identifes most counter-clockwise adjacent node and returns closed loop.

        Args:
            ref_node: The first node, for first edge.
            next_node: The node next to ref_node that constitues a polygon edge.
            cycle: Current list of nodes that will form a polygon.
            recurse_limit: optional parameter to limit recursion for debugging.
            count: optional paramter to limit recursion for debugging.

        Returns:
            A list of nodes that form a polygon.
        """
        # Base case 1: recursion limit is hit
        if recurse_limit and count >= recurse_limit:
            raise RecursionError

        # Base case 2: loop is completed
        if cycle and (next_node.key == cycle[0].key):
            return cycle

        # Set parameters
        if cycle is None:
            cycle = [ref_node]

        cycle.append(next_node)
        # Get current edge direction vector
        # Point subtraction or addition results in Vector2D
        edge_dir = next_node.pt - ref_node.pt

        # Initialize values for comparison
        min_theta = float("inf")
        min_node = None

        # Identify the node with the smallest ccw angle
        for adj_node in next_node.adj_lst:
            # Make sure this node isn't backtracking by checking
            # new node isn't parent of next_node
            if adj_node.key == cycle[-2].key:
                continue

            # Get next edge direction vector
            next_edge_dir = adj_node.pt - next_node.pt
            theta = edge_dir.angle_clockwise(next_edge_dir * -1)

            if theta < min_theta:
                min_theta = theta
                min_node = adj_node

        return PolygonDirectedGraph.min_ccw_cycle(next_node, min_node, cycle,
                                                  recurse_limit=recurse_limit,
                                                  count=count+1)

    def intersect_graph_with_segment(self, segment):
        """Update graph with intersection of partial segment that crosses through polygon.

        Args:
            segment: LineSegment2D to intersect. Does not need to be contained within
            polygon.
        """
        int_key_lst = []

        for node in self.ordered_nodes:

            # Convert graph edge to trimming segment
            next_node = node.adj_lst[0]
            trim_seg = LineSegment2D.from_end_points(node.pt, next_node.pt)
            int_pt = intersection2d.intersect_line2d_infinite(trim_seg, segment)

            # Add intersection point as new node in graph
            if int_pt:
                int_key = self.insert_node(node, int_pt, next_node,
                                           exterior=False)
                int_key_lst.append(int_key)

        # Add intersection edges
        if len(int_key_lst) == 2:
            # Typical case with convex cases
            # Make edge between intersection nodes
            n1, n2 = self.node(int_key_lst[0]), self.node(int_key_lst[1])
            self.add_node(n1.pt, [n2.pt], exterior=False)
            self.add_node(n2.pt, [n1.pt], exterior=False)

        elif len(int_key_lst) > 2:
            # Edge case with concave geometry creates multiple intersections
            # Sort distance and add adjacency
            n = self.node(int_key_lst[0])
            distances = [(0, 0.0)]

            for i, k in enumerate(int_key_lst[1:]):
                distance = LineSegment2D.from_end_points(n.pt, self.node(k).pt).length
                distances.append((i + 1, distance))

            distances = sorted(distances, key=lambda t: t[1])

            for i in range(len(distances)-1):
                k1, k2 = distances[i][0], distances[i+1][0]
                n1, n2 = self.node(int_key_lst[k1]), self.node(int_key_lst[k2])

                # Add bidirection so the min cycle works
                self.add_node(n1.pt, [n2.pt], exterior=False)
                self.add_node(n2.pt, [n1.pt], exterior=False)
