#!/usr/bin/python

"Create a 64-node tree network, and test connectivity using ping."


from mininet.log import setLogLevel, info
from mininet.node import UserSwitch, OVSKernelSwitch  # , KernelSwitch
from mininet.topolib import TreeNet

def treePing64():
    "Run ping test on 64-node tree networks."

    results = {}
    switches = {  # 'reference kernel': KernelSwitch,
                  'reference user': UserSwitch,
                  'Open vSwitch kernel': OVSKernelSwitch }

    for name in switches:
        info( "*** Testing", name, "datapath\n" )
        switch = switches[ name ]
        network = TreeNet( depth=2, fanout=8, switch=switch )
        result = network.run( network.pingAll )
        results[ name ] = result

    info( "\n*** Tree network ping results:\n" )
    for name in switches:
        info( "%s: %d%% packet loss\n" % ( name, results[ name ] ) )
    info( '\n' )

if __name__ == '__main__':
    setLogLevel( 'info' )
    treePing64()
