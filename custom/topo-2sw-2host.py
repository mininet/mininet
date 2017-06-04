"""Custom topology example
Two directly connected switches plus a host for each switch:
   host --- switch --- switch --- host
Adding the 'topos' dict with a key/value pair to generate our newly defined
topology enables one to pass in '--topo=mytopo' from the command line.
"""

from mininet.topo import Topo

class MyTopo( Topo ):
    "Simple topology example."

    def __init__( self ):
        "Create custom topo."

        # Initialize topology
        Topo.__init__( self )

        # Add hosts and switches
        Host1 = self.addHost( 'h1' )
        Host2 = self.addHost( 'h2' )
        Host3 = self.addHost( 'h3' )
        Host4 = self.addHost( 'h4' )
        Host5 = self.addHost( 'h5' )
        Host6 = self.addHost( 'h6' )
        Host7 = self.addHost( 'h7' )
        Host8 = self.addHost( 'h8' )
        Switch1 = self.addSwitch( 's1' )
        Switch2 = self.addSwitch( 's2' )
        Switch3 = self.addSwitch( 'c1' )
        Switch4 = self.addSwitch( 'c2' )
        Switch5 = self.addSwitch( 'c3' )
        Switch6 = self.addSwitch( 'c4' )
        Switch7 = self.addSwitch( 'c5' )
        Switch8 = self.addSwitch( 'c6' )
        Switch9 = self.addSwitch( 'c7' )
        Switch10 = self.addSwitch( 'c8' )

        # Add links
        self.addLink( Host1 , Switch1 )
        self.addLink( Host2 , Switch1 )
        self.addLink( Host3 , Switch1 )
        self.addLink( Host4 , Switch1 )
        self.addLink( Switch1, Switch3 )
        self.addLink( Switch1, Switch4 )
        self.addLink( Switch1, Switch5 )
        self.addLink( Switch1, Switch6 )
        self.addLink( Switch1, Switch7 )
        self.addLink( Switch1, Switch8 )
        self.addLink( Switch1, Switch9 )
        self.addLink( Switch1, Switch10 )
        self.addLink( Switch3, Switch2 )
        self.addLink( Switch4, Switch2 )
        self.addLink( Switch5, Switch2 )
        self.addLink( Switch6, Switch2 )
        self.addLink( Switch7, Switch2 )
        self.addLink( Switch8, Switch2 )
        self.addLink( Switch9, Switch2 )
        self.addLink( Switch10, Switch2 )
        self.addLink( Switch2, Host5 )
        self.addLink( Switch2, Host6 )
        self.addLink( Switch2, Host7 )
        self.addLink( Switch2, Host8 )


topos = { 'mytopo': ( lambda: MyTopo() ) }
