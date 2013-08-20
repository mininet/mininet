#!/usr/bin/python

"""
controlnet.py: Mininet with a custom control network

We create two Mininet() networks, a control network
and a data network, running four DataControllers on the
control network to control the data network.

Since we're using UserSwitch on the data network,
it should correctly fail over to a backup controller.

We also hack/subclass the CLI slightly so it can talk to
both the control and data networks.
"""

from mininet.net import Mininet
from mininet.node import Controller, UserSwitch
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.topolib import TreeTopo
from mininet.log import setLogLevel, info

# Some minor hacks

class DataController( Controller ):
    """Data Network Controller.
       patched to avoid checkListening error"""
    def checkListening( self ):
        "Ignore spurious error"
        pass


class MininetFacade:
    "TODO: CLI that can talk to two or more networks"
    
    def __init__( self, *args ):
        self.nets = args

    # default is first net
    def __getattr__( self, name ):
        return getattr( self.nets[ 0 ], name )

    def __getitem__( self, key ):
        for net in self.nets:
            if key in net:
                return net[ key ]

    def __iter__( self ):
        for net in self.nets:
            for node in net:
                yield node

    def __len__( self ):
        count = 0
        for net in self.nets:
            count += len(net)
        return count

    def __contains__( self, key ):
        return key in self.keys()

    def keys( self ):
        return list( self )

    def values( self ):
        return [ self[ key ] for key in self ]

    def items( self ):
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

setLogLevel( 'info' )

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
net = Mininet( topo=topo, switch=UserSwitch, controller=None )
info( '* Adding Controllers to Data Network\n' )
for host in cnet.hosts:
    if isinstance(host, Controller):
        net.addController( host )
info( '* Starting Data Network\n')
net.start()

mn = MininetFacade( net, cnet )
mn.keys()
CLI( mn )

info( '* Stopping Data Network\n' )
net.stop()

info( '* Stopping Control Network\n' )
# dataControllers have already been stopped -- now terminate is idempotent
#cnet.hosts = list( set( cnet.hosts ) - set( dataControllers ) )
cnet.stop()






