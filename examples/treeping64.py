#!/usr/bin/env python

"Create a 64-node tree network, and test connectivity using ping."


from mininet.log import setLogLevel, info
from mininet.node import UserSwitch, OVSKernelSwitch, Host
from mininet.topolib import TreeNet


class HostV4( Host ):
    "Try to IPv6 and its awful neighbor discovery"
    def __init__( self, *args, **kwargs ):
        super( HostV4, self ).__init__( *args, **kwargs )
        cfgs = [ 'all.disable_ipv6=1', 'default.disable_ipv6=1',
                 'default.autoconf=0', 'lo.autoconf=0' ]
        for cfg in cfgs:
            self.cmd( 'sysctl -w net.ipv6.conf.' + cfg )


def treePing64():
    "Run ping test on 64-node tree networks."

    results = {}
    switches = { 'reference user': UserSwitch,
                 'Open vSwitch kernel': OVSKernelSwitch }

    for name, switch in switches.items():
        info( "*** Testing", name, "datapath\n" )
        network = TreeNet( depth=2, fanout=8, switch=switch,
                           waitConnected=True )
        result = network.run( network.pingAll )
        results[ name ] = result

    info( "\n*** Tree network ping results:\n" )
    for name in switches:
        info( "%s: %d%% packet loss\n" % ( name, results[ name ] ) )
    info( '\n' )


if __name__ == '__main__':
    setLogLevel( 'info' )
    treePing64()
