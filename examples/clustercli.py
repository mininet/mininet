#!/usr/bin/python

"CLI for Mininet Cluster Edition prototype demo"

from mininet.cli import CLI
from mininet.log import output

import networkx as nx
from networkx import graphviz_layout
import matplotlib.pyplot as plt

class DemoCLI( CLI ):
    "CLI with additional commands for Cluster Edition demo"

    @staticmethod
    def colorsFor( seq ):
        "Return a list of background colors for a sequence"
        colors = [ 'red', 'lightgreen', 'cyan', 'yellow', 'orange',
                  'magenta', 'pink', 'grey', 'brown',
                  'white' ]
        slen, clen = len( seq ), len( colors )
        reps = max( 1, slen / clen )
        colors = colors * reps
        colors = colors[ 0 : slen ]
        return colors
    
    def do_plot( self, line ):
        "Plot topology colored by node placement"
        # Make a networkx Graph
        g = nx.Graph()
        mn = self.mn
        servers, hosts, switches = mn.servers, mn.hosts, mn.switches
        hlen, slen = len( hosts ), len( switches )
        nodes = hosts + switches
        g.add_nodes_from( nodes )
        links = [ ( link.intf1.node, link.intf2.node )
                  for link in self.mn.links ]
        g.add_edges_from( links )
        # Pick some shapes and colors
        shapes = hlen * [ 's' ] + slen * [ 'o' ]
        color = dict( zip( servers, self.colorsFor( servers ) ) )
        # Plot it!
        pos = nx.graphviz_layout( g )
        opts = { 'ax': None, 'font_weight': 'bold',
		 'width': 2, 'edge_color': 'darkblue' }
        hcolors = [ color[ h.server ] for h in hosts ]
        scolors = [ color[ s.server ] for s in switches ]
        nx.draw_networkx( g, pos=pos, nodelist=hosts, node_size=800, label='host',
                          node_color=hcolors, node_shape='s', **opts )
        nx.draw_networkx( g, pos=pos, nodelist=switches, node_size=1000,
                          node_color=scolors, node_shape='o', **opts )
        # Get rid of axes, add title, and show
        fig = plt.gcf()
        ax = plt.gca()
        ax.get_xaxis().set_visible( False )
        ax.get_yaxis().set_visible( False )
        fig.canvas.set_window_title( 'Mininet')
        plt.title( 'Node Placement', fontweight='bold' )
        plt.show()

    def do_placement( self, line ):
        "Describe node placement"
        mn = self.mn
        nodes = mn.hosts + mn.switches + mn.controllers
        for server in mn.servers:
            names = [ n.name for n in nodes if hasattr( n, 'server' )
                      and n.server == server ]
            output( '%s: %s\n' % ( server, ' '.join( names ) ) )