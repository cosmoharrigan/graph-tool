#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# graph_tool -- a general graph manipulation python module
#
# Copyright (C) 2007-2011 Tiago de Paula Peixoto <tiago@skewed.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
``graph_tool.draw`` - Graph drawing and layout
----------------------------------------------

Summary
+++++++

Layout algorithms
=================

.. autosummary::
   :nosignatures:

   sfdp_layout
   fruchterman_reingold_layout
   arf_layout
   random_layout


Graph drawing
=============

.. autosummary::
   :nosignatures:

   graph_draw
   graphviz_draw


Low-level graph drawing
^^^^^^^^^^^^^^^^^^^^^^^

.. autosummary::
   :nosignatures:

   cairo_draw
   interactive_window
   GraphWidget
   GraphWindow

Contents
++++++++
"""

from .. import GraphView, _check_prop_vector, group_vector_property, \
     ungroup_vector_property, infect_vertex_property, _prop
from .. topology import max_cardinality_matching, max_independent_vertex_set, \
    label_components,  pseudo_diameter
from .. community import condensation_graph
from .. stats import label_parallel_edges
import numpy.random
from numpy import sqrt
import sys
import warnings

from .. dl_import import dl_import
dl_import("import libgraph_tool_layout")


__all__ = ["graph_draw", "graphviz_draw", "fruchterman_reingold_layout",
           "arf_layout", "sfdp_layout", "random_layout",
           "interactive_window", "cairo_draw", "GraphWidget",
           "GraphWindow"]


def random_layout(g, shape=None, pos=None, dim=2):
    r"""Performs a random layout of the graph.

    Parameters
    ----------
    g : :class:`~graph_tool.Graph`
        Graph to be used.
    shape : tuple or list (optional, default: ``None``)
        Rectangular shape of the bounding area. The size of this parameter must
        match `dim`, and each element can be either a pair specifying a range,
        or a single value specifying a range starting from zero. If None is
        passed, a square of linear size :math:`\sqrt{N}` is used.
    pos : :class:`~graph_tool.PropertyMap` (optional, default: ``None``)
        Vector vertex property maps where the coordinates should be stored.
    dim : int (optional, default: ``2``)
        Number of coordinates per vertex.

    Returns
    -------
    pos : :class:`~graph_tool.PropertyMap`
        A vector-valued vertex property map with the coordinates of the
        vertices.

    Notes
    -----
    This algorithm has complexity :math:`O(V)`.

    Examples
    --------
    >>> from numpy.random import seed
    >>> seed(42)
    >>> g = gt.random_graph(100, lambda: (3, 3))
    >>> shape = [[50, 100], [1, 2], 4]
    >>> pos = gt.random_layout(g, shape=shape, dim=3)
    >>> pos[g.vertex(0)].a
    array([ 86.59969709,   1.31435598,   0.64651486])

    """

    if pos == None:
        pos = g.new_vertex_property("vector<double>")
    _check_prop_vector(pos, name="pos")

    pos = ungroup_vector_property(pos, range(0, dim))

    if shape == None:
        shape = [sqrt(g.num_vertices())] * dim

    for i in xrange(dim):
        if hasattr(shape[i], "__len__"):
            if len(shape[i]) != 2:
                raise ValueError("The elements of 'shape' must have size 2.")
            r = [min(shape[i]), max(shape[i])]
        else:
            r = [min(shape[i], 0), max(shape[i], 0)]
        d = r[1] - r[0]

        # deal with filtering
        p = pos[i].ma
        p[:] = numpy.random.random(len(p)) * d + r[0]

    pos = group_vector_property(pos)
    return pos


def fruchterman_reingold_layout(g, weight=None, a=None, r=1., scale=None,
                                circular=False, grid=True, t_range=None,
                                n_iter=100, pos=None):
    r"""Calculate the Fruchterman-Reingold spring-block layout of the graph.

    Parameters
    ----------
    g : :class:`~graph_tool.Graph`
        Graph to be used.
    weight : :class:`PropertyMap` (optional, default: ``None``)
        An edge property map with the respective weights.
    a : float (optional, default: :math:`V`)
        Attracting force between adjacent vertices.
    r : float (optional, default: 1.0)
        Repulsive force between vertices.
    scale : float (optional, default: :math:`\sqrt{V}`)
        Total scale of the layout (either square side or radius).
    circular : bool (optional, default: ``False``)
        If ``True``, the layout will have a circular shape. Otherwise the shape
        will be a square.
    grid : bool (optional, default: ``True``)
        If ``True``, the repulsive forces will only act on vertices which are on
        the same site on a grid. Otherwise they will act on all vertex pairs.
    t_range : tuple of floats (optional, default: ``(scale / 10, scale / 1000)``)
        Temperature range used in annealing. The temperature limits the
        displacement at each iteration.
    n_iter : int (optional, default: ``100``)
        Total number of iterations.
    pos : :class:`PropertyMap` (optional, default: ``None``)
        Vector vertex property maps where the coordinates should be stored. If
        provided, this will also be used as the initial position of the
        vertices.

    Returns
    -------
    pos : :class:`~graph_tool.PropertyMap`
        A vector-valued vertex property map with the coordinates of the
        vertices.

    Notes
    -----
    This algorithm is defined in [fruchterman-reingold]_, and has
    complexity :math:`O(\text{n-iter}\times V^2)` if `grid=False` or
    :math:`O(\text{n-iter}\times (V + E))` otherwise.

    Examples
    --------
    >>> from numpy.random import seed, zipf
    >>> seed(42)
    >>> g = gt.price_network(300)
    >>> pos = gt.fruchterman_reingold_layout(g, n_iter=1000)
    >>> gt.graph_draw(g, pos=pos, output="graph-draw-fr.pdf")
    <...>

    .. figure:: graph-draw-fr.*
        :align: center

        Fruchterman-Reingold layout of a Price network.

    References
    ----------
    .. [fruchterman-reingold] Fruchterman, Thomas M. J.; Reingold, Edward M.
       "Graph Drawing by Force-Directed Placement". Software – Practice & Experience
       (Wiley) 21 (11): 1129–1164. (1991) :doi:`10.1002/spe.4380211102`
    """

    if pos == None:
        pos = random_layout(g, dim=2)
    _check_prop_vector(pos, name="pos", floating=True)

    if a is None:
        a = float(g.num_vertices())

    if scale is None:
        scale = sqrt(g.num_vertices())

    if t_range is None:
        t_range = (scale / 10, scale / 1000)

    ug = GraphView(g, directed=False)
    libgraph_tool_layout.fruchterman_reingold_layout(ug._Graph__graph,
                                                     _prop("v", g, pos),
                                                     _prop("e", g, weight),
                                                     a, r, not circular, scale,
                                                     grid, t_range[0],
                                                     t_range[1], n_iter)
    return pos


def arf_layout(g, weight=None, d=0.5, a=10, dt=0.001, epsilon=1e-6,
               max_iter=1000, pos=None, dim=2):
    r"""Calculate the ARF spring-block layout of the graph.

    Parameters
    ----------
    g : :class:`~graph_tool.Graph`
        Graph to be used.
    weight : :class:`~graph_tool.PropertyMap` (optional, default: ``None``)
        An edge property map with the respective weights.
    d : float (optional, default: ``0.5``)
        Opposing force between vertices.
    a : float (optional, default: ``10``)
        Attracting force between adjacent vertices.
    dt : float (optional, default: ``0.001``)
        Iteration step size.
    epsilon : float (optional, default: ``1e-6``)
        Convergence criterion.
    max_iter : int (optional, default: ``1000``)
        Maximum number of iterations. If this value is ``0``, it runs until
        convergence.
    pos : :class:`~graph_tool.PropertyMap` (optional, default: ``None``)
        Vector vertex property maps where the coordinates should be stored.
    dim : int (optional, default: ``2``)
        Number of coordinates per vertex.

    Returns
    -------
    pos : :class:`~graph_tool.PropertyMap`
        A vector-valued vertex property map with the coordinates of the
        vertices.

    Notes
    -----
    This algorithm is defined in [geipel-self-organization-2007]_, and has
    complexity :math:`O(V^2)`.

    Examples
    --------
    >>> from numpy.random import seed, zipf
    >>> seed(42)
    >>> g = gt.price_network(300)
    >>> pos = gt.arf_layout(g, max_iter=0)
    >>> gt.graph_draw(g, pos=pos, output="graph-draw-arf.pdf")
    <...>

    .. figure:: graph-draw-arf.*
        :align: center

        ARF layout of a Price network.

    References
    ----------
    .. [geipel-self-organization-2007] Markus M. Geipel, "Self-Organization
       applied to Dynamic Network Layout", International Journal of Modern
       Physics C vol. 18, no. 10 (2007), pp. 1537-1549,
       :doi:`10.1142/S0129183107011558`, :arxiv:`0704.1748v5`
    .. _arf: http://www.sg.ethz.ch/research/graphlayout
    """

    if pos is None:
        if dim != 2:
            pos = random_layout(g, dim=dim)
        else:
            pos = graph_draw(g, output=None)
    _check_prop_vector(pos, name="pos", floating=True)

    ug = GraphView(g, directed=False)
    libgraph_tool_layout.arf_layout(ug._Graph__graph, _prop("v", g, pos),
                                    _prop("e", g, weight), d, a, dt, max_iter,
                                    epsilon, dim)
    return pos


def _coarse_graph(g, vweight, eweight, mivs=False):
    if mivs:
        mivs = max_independent_vertex_set(g, high_deg=True)
        u = GraphView(g, vfilt=mivs, directed=False)
        c = label_components(u)[0]
        c.fa += 1
        u = GraphView(g, directed=False)
        infect_vertex_property(u, c,
                               range(1, c.fa.max() + 1))
        c = g.own_property(c)
    else:
        mivs = None
        m = max_cardinality_matching(GraphView(g, directed=False),
                                     heuristic=True, weight=eweight,
                                     minimize=False)
        u = GraphView(g, efilt=m, directed=False)
        c = label_components(u)[0]
        c = g.own_property(c)
        u = GraphView(g, directed=False)
    cg, cc, vcount, ecount = condensation_graph(u, c, vweight, eweight)
    return cg, cc, vcount, ecount, c, mivs


def _propagate_pos(g, cg, c, cc, cpos, delta, mivs):
    seed = numpy.random.randint(sys.maxint)
    pos = g.new_vertex_property(cpos.value_type())

    if mivs is not None:
        g = GraphView(g, vfilt=mivs)
    libgraph_tool_layout.propagate_pos(g._Graph__graph,
                                       cg._Graph__graph,
                                       _prop("v", g, c),
                                       _prop("v", cg, cc),
                                       _prop("v", g, pos),
                                       _prop("v", cg, cpos),
                                       delta if mivs is None else 0,
                                       seed)
    if mivs is not None:
        g = g.base
        u = GraphView(g, directed=False)
        try:
            libgraph_tool_layout.propagate_pos_mivs(u._Graph__graph,
                                                    _prop("v", u, mivs),
                                                    _prop("v", u, pos),
                                                    delta, seed)
        except ValueError:
            graph_draw(u, mivs, vertex_fillcolor=mivs)
    return pos


def _avg_edge_distance(g, pos):
    return libgraph_tool_layout.avg_dist(g._Graph__graph, _prop("v", g, pos))


def coarse_graphs(g, method="hybrid", mivs_thres=0.9, ec_thres=0.75,
                  weighted_coarse=False, verbose=False):
    cg = [[g, None, None, None, None, None]]
    mivs = not (method in ["hybrid", "ec"])
    while True:
        u = _coarse_graph(cg[-1][0], cg[-1][2], cg[-1][3], mivs)
        if (mivs and
            u[0].num_vertices() > mivs_thres * cg[-1][0].num_vertices()):
            break
        if u[0].num_vertices() > ec_thres * cg[-1][0].num_vertices():
            if method == "hybrid":
                mivs = True
            else:
                break
        if u[0].num_vertices() <= 2:
            break
        cg.append(u)
        if verbose:
            print "Coarse level (%s):" % ("MIVS" if mivs else "EC"),
            print len(cg), " num vertices:",
            print u[0].num_vertices()
    cg.reverse()
    Ks = []
    pos = random_layout(cg[0][0], dim=2)
    for i in xrange(len(cg)):
        if i == 0:
            u = cg[i][0]
            K = _avg_edge_distance(u, pos)
            Ks.append(K)
            continue
        if weighted_coarse:
            gamma = 1.
        else:
            #u = cg[i - 1][0]
            #w = cg[i][0]
            #du = pseudo_diameter(u)[0]
            #dw = pseudo_diameter(w)[0]
            #gamma = du / float(max(dw, du))
            gamma = 0.75
        Ks.append(Ks[-1] * gamma)

    for i in xrange(len(cg)):
        u, cc, vcount, ecount, c, mivs = cg[i]
        yield u, pos, Ks[i], vcount, ecount

        if verbose:
            print "avg edge distance:", _avg_edge_distance(u, pos)

        if i < len(cg) - 1:
            if verbose:
                print "propagating...",
                print mivs.a.sum() if mivs is not None else ""
            pos = _propagate_pos(cg[i + 1][0], u, c, cc, pos,
                                 Ks[i] / 1000, mivs)


def sfdp_layout(g, vweight=None, eweight=None, pin=None, C=0.2, K=None, p=2.,
                theta=0.6, init_step=None, cooling_step=0.9,
                adaptive_cooling=True, max_level=11, epsilon=1e-1, max_iter=0,
                pos=None, multilevel=None, coarse_method="hybrid",
                mivs_thres=0.9, ec_thres=0.75,
                weighted_coarse=False, verbose=False):
    r"""Calculate the sfdp spring-block layout of the graph.

    Parameters
    ----------
    g : :class:`~graph_tool.Graph`
        Graph to be used.
    weight : :class:`~graph_tool.PropertyMap` (optional, default: ``None``)
        An edge property map with the respective weights.
    epsilon : float (optional, default: ``1e-6``)
        Convergence criterion.
    max_iter : int (optional, default: ``1000``)
        Maximum number of iterations. If this value is ``0``, it runs until
        convergence.
    pos : :class:`~graph_tool.PropertyMap` (optional, default: ``None``)
        Vector vertex property maps where the coordinates should be stored.

    Returns
    -------
    pos : :class:`~graph_tool.PropertyMap`
        A vector-valued vertex property map with the coordinates of the
        vertices.

    Notes
    -----
    This algorithm is defined in [geipel-self-organization-2007]_, and has
    complexity :math:`O(V^2)`.

    Examples
    --------
    >>> from numpy.random import seed, zipf
    >>> seed(42)
    >>> g = gt.price_network(300)
    >>> pos = gt.arf_layout(g, max_iter=0)
    >>> gt.graph_draw(g, pos=pos, pin=True, output="graph-draw-arf.pdf")
    <...>

    .. figure:: graph-draw-arf.*
        :align: center

        ARF layout of a Price network.

    References
    ----------
    .. [geipel-self-organization-2007] Markus M. Geipel, "Self-Organization
       applied to Dynamic Network Layout", International Journal of Modern
       Physics C vol. 18, no. 10 (2007), pp. 1537-1549,
       :doi:`10.1142/S0129183107011558`, :arxiv:`0704.1748v5`
    .. _arf: http://www.sg.ethz.ch/research/graphlayout
    """

    if pos is None:
        pos = random_layout(g, dim=2)
    _check_prop_vector(pos, name="pos", floating=True)

    g = GraphView(g, directed=False)

    if pin is not None and pin.value_type() != "bool":
        raise ValueError("'pin' property must be of type 'bool'.")

    if K is None:
        K = _avg_edge_distance(g, pos)

    if init_step is None:
        init_step = 10 * max(_avg_edge_distance(g, pos), K)

    if multilevel is None:
        multilevel = g.num_vertices() > 1000

    if multilevel:
        cgs = coarse_graphs(g, method=coarse_method,
                            mivs_thres=mivs_thres,
                            ec_thres=ec_thres,
                            weighted_coarse=weighted_coarse,
                            verbose=verbose)
        count = 0
        for u, pos, K, vcount, ecount in cgs:
            if verbose:
                print "Positioning level:", count, u.num_vertices(),
                print "with K =", K, "..."
                count += 1
            #graph_draw(u, pos)
            pos = sfdp_layout(u, pos=pos,
                              vweight=vcount if weighted_coarse else None,
                              eweight=ecount if weighted_coarse else None,
                              C=C, K=K, p=p,
                              theta=theta, epsilon=epsilon,
                              max_iter=max_iter,
                              cooling_step=cooling_step,
                              adaptive_cooling=False,
                              init_step=max(2 * K,
                                            _avg_edge_distance(u, pos) / 10),
                              multilevel=False,
                              verbose=False)
            #graph_draw(u, pos)
        return pos

    if g.num_vertices() <= 1:
        return pos
    if g.num_vertices() == 2:
        vs = [g.vertex(0, False), g.vertex(1, False)]
        pos[vs[0]] = [0, 0]
        pos[vs[1]] = [1, 1]
        return pos
    if g.num_vertices() <= 50:
        max_level = 0
    libgraph_tool_layout.sfdp_layout(g._Graph__graph, _prop("v", g, pos),
                                     _prop("v", g, vweight),
                                     _prop("e", g, eweight),
                                     _prop("v", g, pin), (C, K, p), theta,
                                     init_step, cooling_step, max_level,
                                     epsilon, max_iter, not adaptive_cooling,
                                     verbose)
    return pos

from cairo_draw import graph_draw, GraphWidget, GraphWindow, \
     interactive_window, cairo_draw

from graphviz_draw import graphviz_draw
