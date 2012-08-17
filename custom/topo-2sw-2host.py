"""Custom topology example

author: Brandon Heller (brandonh@stanford.edu)

Two directly connected switches plus a host for each switch:

   host --- switch --- switch --- host

Adding the 'topos' dict with a key/value pair to generate our newly defined
topology enables one to pass in '--topo=mytopo' from the command line.
"""

from mininet.topo import Topo, Node

class MyTopo( Topo ):
    "Simple topology example."

    def __init__( self, enable_all = True ):
        "Create custom topo."

        # Add default members to class.
        super( MyTopo, self ).__init__()

        # Set Node IDs for hosts and switches
        leftHost = 1
        leftSwitch = 2
        rightSwitch = 3
        rightHost = 4

        # Add nodes
        self.addNode( leftSwitch, Node( isSwitch=True ) )
        self.addNode( rightSwitch, Node( isSwitch=True ) )
        self.addNode( leftHost, Node( isSwitch=False ) )
        self.addNode( rightHost, Node( isSwitch=False ) )

        # Add edges
        self.add_edge( leftHost, leftSwitch )
        self.add_edge( leftSwitch, rightSwitch )
        self.add_edge( rightSwitch, rightHost )

        # Consider all switches and hosts 'on'
        self.enable_all()


topos = { 'mytopo': ( lambda: MyTopo() ) }
