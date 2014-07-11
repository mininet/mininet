"Library of potentially useful topologies for Mininet"

from csv import DictReader
from mininet.topo import Topo
from mininet.net import Mininet

class TreeTopo( Topo ):
    "Topology for a tree network with a given depth and fanout."

    def __init__( self, depth=1, fanout=2 ):
        super( TreeTopo, self ).__init__()
        # Numbering:  h1..N, s1..M
        self.hostNum = 1
        self.switchNum = 1
        # Build topology
        self.addTree( depth, fanout )

    def addTree( self, depth, fanout ):
        """Add a subtree starting with node n.
           returns: last node added"""
        isSwitch = depth > 0
        if isSwitch:
            node = self.addSwitch( 's%s' % self.switchNum )
            self.switchNum += 1
            for _ in range( fanout ):
                child = self.addTree( depth - 1, fanout )
                self.addLink( node, child )
        else:
            node = self.addHost( 'h%s' % self.hostNum )
            self.hostNum += 1
        return node


def TreeNet( depth=1, fanout=2, **kwargs ):
    "Convenience function for creating tree networks."
    topo = TreeTopo( depth, fanout )
    return Mininet( topo, **kwargs )


class CsvTopo( Topo ):
    """Create a topology from CSV (comma-separated values) files.

       The two CSV files can have arbitrary number of columns, but
       'name' is mandatory in the 'nodes.csv' file and 'name_a' and
       'name_b' is mandatory in the 'links.csv' file.

       @param path Filenames are prepended with 'path'.

       A node is created as switch and not as host if it has more than
       one links.  CsvTopo automatically converts string values to
       float and integer when possible.

       Example.  Having the following two files, you can start mininet as:
       mn --topo=csv,path=exp1. --link=tc --host=rt  

       ,---[ exp1.nodes.csv ]
       |name,cpu
       |h1,0.1
       |h2,0.2
       |s3,0.5
       `---

       ,---[ exp1.links.csv ]
       |name_a,name_b,delay,bw
       |h1,s3,20,2
       |h2,s3,30,5
       `---
    """

    def __init__( self, path='', **opts ):
        "Create the topo."

        def convert(x):
            try:
                r = x
                r = float(x)
                r = int(x)
            except (ValueError, TypeError):
                pass
            return r

        # Add default members to class.
        super( CsvTopo, self ).__init__(**opts)

        # Load nodes from file
        f = open( path + 'nodes.csv' )
        reader = DictReader( f )
        nodes = {}
        for r in reader:
            for k,v in r.iteritems():
                r[k] = convert(v)
            nodes[ r['name'] ] = r
        f.close()

        # Load links from file
        f = open( path + 'links.csv' )
        reader = DictReader( f )
        links = {}
        for r in reader:
            for k,v in r.iteritems():
                r[k] = convert(v)

            name_a = r[ 'name_a' ]
            name_b = r[ 'name_b' ]

            try:
                links[ name_a ][ name_b ] = r
            except KeyError:
                links[ name_a ] = { name_b: r }
            try:
                links[ name_b ][ name_a ] = r
            except KeyError:
                links[ name_b ] = { name_a: r }
        f.close()

        # Add nodes
        node_names = nodes.keys()
        node_names.sort()
        for node_name in node_names:
            ports = links[ node_name ]
            opts = nodes[ node_name ]
            del(opts['name'])
            if len(ports) > 1:
                self.addSwitch( node_name, **opts )
            else:
                self.addHost( node_name, **opts )

        # Add links
        for node_a in node_names:
            neighbors = links[ node_a ].keys()
            neighbors.sort()
            for node_b in neighbors:
                if node_a < node_b:
                    lopts = links[ node_a ][ node_b ]
                    self.addLink( node_a, node_b, **lopts )
