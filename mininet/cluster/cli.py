#!/usr/bin/python

"CLI for Mininet Cluster Edition prototype demo"

from mininet.cli import CLI
from mininet.log import output, error

# pylint: disable=global-statement
nx, graphviz_layout, plt = None, None, None  # Will be imported on demand


class ClusterCLI( CLI ):
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

    def do_plot( self, _line ):
        "Plot topology colored by node placement"
        # Import networkx if needed
        global nx, plt
        if not nx:
            try:
                # pylint: disable=import-error
                import networkx
                nx = networkx  # satisfy pylint
                from matplotlib import pyplot
                plt = pyplot   # satisfiy pylint
                import pygraphviz
                assert pygraphviz  # silence pyflakes
                # pylint: enable=import-error
            except ImportError:
                error( 'plot requires networkx, matplotlib and pygraphviz - '
                       'please install them and try again\n' )
                return
        # Make a networkx Graph
        g = nx.Graph()
        mn = self.mn
        servers, hosts, switches = mn.servers, mn.hosts, mn.switches
        nodes = hosts + switches
        g.add_nodes_from( nodes )
        links = [ ( link.intf1.node, link.intf2.node )
                  for link in self.mn.links ]
        g.add_edges_from( links )
        # Pick some shapes and colors
        # shapes = hlen * [ 's' ] + slen * [ 'o' ]
        color = dict( zip( servers, self.colorsFor( servers ) ) )
        # Plot it!
        pos = nx.graphviz_layout( g )
        opts = { 'ax': None, 'font_weight': 'bold',
                 'width': 2, 'edge_color': 'darkblue' }
        hcolors = [ color[ getattr( h, 'server', 'localhost' ) ]
                    for h in hosts ]
        scolors = [ color[ getattr( s, 'server', 'localhost' ) ]
                    for s in switches ]
        nx.draw_networkx( g, pos=pos, nodelist=hosts, node_size=800,
                          label='host', node_color=hcolors, node_shape='s',
                          **opts )
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

    def do_status( self, _line ):
        "Report on node shell status"
        nodes = self.mn.hosts + self.mn.switches
        for node in nodes:
            node.shell.poll()
        exited = [ node for node in nodes
                   if node.shell.returncode is not None ]
        if exited:
            for node in exited:
                output( '%s has exited with code %d\n'
                        % ( node, node.shell.returncode ) )
        else:
            output( 'All nodes are still running.\n' )

    def do_placement( self, _line ):
        "Describe node placement"
        mn = self.mn
        nodes = mn.hosts + mn.switches + mn.controllers
        for server in mn.servers:
            names = [ n.name for n in nodes if hasattr( n, 'server' )
                      and n.server == server ]
            output( '%s: %s\n' % ( server, ' '.join( names ) ) )
