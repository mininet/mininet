#!/usr/bin/python

"""
controlnet.py: Mininet with a custom control network

We create two Mininet() networks, a control network
and a data network, running four DataControllers on the
control network to control the data network.

Since we're using UserSwitch on the data network,
it should correctly fail over to a backup controller.

We also use a Mininet Facade to talk to both the
control and data networks from a single CLI.
"""

from functools import partial

from mininet.net import Mininet
from mininet.node import Controller, UserSwitch
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.topolib import TreeTopo
from mininet.log import setLogLevel, info

# Some minor hacks

class DataController( Controller ):
    """Data Network Controller.
       patched to avoid checkListening error and to delete intfs"""

    def checkListening( self ):
        "Ignore spurious error"
        pass

    def stop( self, *args, **kwargs ):
        "Make sure intfs are deleted"
        kwargs.update( deleteIntfs=True )
        super( DataController, self ).stop( *args, **kwargs )


class MininetFacade( object ):
    """Mininet object facade that allows a single CLI to
       talk to one or more networks"""

    def __init__( self, net, *args, **kwargs ):
        """Create MininetFacade object.
           net: Primary Mininet object
           args: unnamed networks passed as arguments
           kwargs: named networks passed as arguments"""
        self.net = net
        self.nets = [ net ] + list( args ) + kwargs.values()
        self.nameToNet = kwargs
        self.nameToNet['net'] = net

    def __getattr__( self, name ):
        "returns attribute from Primary Mininet object"
        return getattr( self.net, name )

    def __getitem__( self, key ):
        "returns primary/named networks or node from any net"
        #search kwargs for net named key
        if key in self.nameToNet:
            return self.nameToNet[ key ]
        #search each net for node named key
        for net in self.nets:
            if key in net:
                return net[ key ]

    def __iter__( self ):
        "Iterate through all nodes in all Mininet objects"
        for net in self.nets:
            for node in net:
                yield node

    def __len__( self ):
        "returns aggregate number of nodes in all nets"
        count = 0
        for net in self.nets:
            count += len(net)
        return count

    def __contains__( self, key ):
        "returns True if node is a member of any net"
        return key in self.keys()

    def keys( self ):
        "returns a list of all node names in all networks"
        return list( self )

    def values( self ):
        "returns a list of all nodes in all networks"
        return [ self[ key ] for key in self ]

    def items( self ):
        "returns (key,value) tuple list for every node in all networks"
        return zip( self.keys(), self.values() )

# A real control network!

class ControlNetwork( Topo ):
    "Control Network Topology"
    def __init__( self, n, dataController=DataController, **kwargs ):
        """n: number of data network controller nodes
           dataController: class for data network controllers"""
        Topo.__init__( self, **kwargs )
        # Connect everything to a single switch
        cs0 = self.addSwitch( 'cs0' )
        # Add hosts which will serve as data network controllers
        for i in range( 0, n ):
            c = self.addHost( 'c%s' % i, cls=dataController,
                              inNamespace=True )
            self.addLink( c, cs0 )
        # Connect switch to root namespace so that data network
        # switches will be able to talk to us
        root = self.addHost( 'root', inNamespace=False )
        self.addLink( root, cs0 )


# Make it Happen!!

def run():
    "Create control and data networks, and invoke the CLI"

    info( '* Creating Control Network\n' )
    ctopo = ControlNetwork( n=4, dataController=DataController )
    cnet = Mininet( topo=ctopo, ipBase='192.168.123.0/24', controller=None )
    info( '* Adding Control Network Controller\n')
    cnet.addController( 'cc0', controller=Controller )
    info( '* Starting Control Network\n')
    cnet.start()

    info( '* Creating Data Network\n' )
    topo = TreeTopo( depth=2, fanout=2 )
    # UserSwitch so we can easily test failover
    sw = partial( UserSwitch, opts='--inactivity-probe=1 --max-backoff=1' )
    net = Mininet( topo=topo, switch=sw, controller=None )
    info( '* Adding Controllers to Data Network\n' )
    for host in cnet.hosts:
        if isinstance(host, Controller):
            net.addController( host )
    info( '* Starting Data Network\n')
    net.start()

    mn = MininetFacade( net, cnet=cnet )

    CLI( mn )

    info( '* Stopping Data Network\n' )
    net.stop()

    info( '* Stopping Control Network\n' )
    cnet.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    run()
