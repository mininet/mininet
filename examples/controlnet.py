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


class CLI2( CLI ):
    "CLI that can talk to two networks"
    
    def __init__( self, *args, **kwargs ):
        "cnet: second network"
        self.cnet = kwargs.pop( 'cnet' )
        CLI.__init__( self, *args, **kwargs )

    def updateVars( self ):
        "Update variables to include cnet"
        cnet = self.cnet
        nodes2 = cnet.controllers + cnet.switches + cnet.hosts
        self.nodelist += nodes2
        for node in nodes2:
            self.nodemap[ node.name ] = node
        self.locals[ 'cnet' ] = cnet
        self.locals.update( self.nodemap )
    
    def cmdloop( self, *args, **kwargs ):
        "Patch to add cnet if needed"
        if 'cnet' not in self.locals:
            self.updateVars()
        CLI.cmdloop( self, *args, **kwargs )


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
cnet = Mininet( topo=ctopo, ipBase='192.168.123.0/24', build=False )
info( '* Adding Control Network Controller\n')
cnet.addController( 'cc0' )
info( '* Starting Control Network\n')
cnet.build()
cnet.start()
dataControllers = cnet.hosts[ : -1 ]  # ignore 'root' node

info( '* Creating Data Network\n' )
topo = TreeTopo( depth=2, fanout=2 )
# UserSwitch so we can easily test failover
net = Mininet( topo=topo, switch=UserSwitch, build=False )
info( '* Adding Controllers to Data Network\n' )
net.controllers = dataControllers
net.build()
info( '* Starting Data Network\n')
net.start()

CLI2( net, cnet=cnet )

info( '* Stopping Data Network\n' )
net.stop()

info( '* Stopping Control Network\n' )
# dataControllers have already been stopped
cnet.hosts = list( set( cnet.hosts ) - set( dataControllers ) )
cnet.stop()






