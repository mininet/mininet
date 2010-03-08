#!/usr/bin/python

"""
Build a simple network from scratch, using mininet primitives.
This is more complicated than using the higher-level classes,
but it exposes the configuration details and allows customization.

This version uses the user datapath and an explicit control network.
"""

from mininet.net import init
from mininet.node import Node
from mininet.util import createLink
from mininet.log import lg, info

def scratchNetUser( cname='controller', cargs='ptcp:' ):
    "Create network from scratch using user switch."

    # It's not strictly necessary for the controller and switches
    # to be in separate namespaces. For performance, they probably
    # should be in the root namespace. However, it's interesting to
    # see how they could work even if they are in separate namespaces.

    info( '*** Creating Network\n' )
    controller = Node( 'c0' )
    switch = Node( 's0')
    h0 = Node( 'h0' )
    h1 = Node( 'h1' )
    createLink( controller, 0, switch, 0 )
    createLink( h0, 0, switch, 1 )
    createLink( h1, 0, switch, 2 )

    info( '*** Configuring control network\n' )
    controller.setIP( controller.intfs[ 0 ], '10.0.123.1', 24 )
    switch.setIP( switch.intfs[ 0 ], '10.0.123.2', 24 )

    info( '*** Configuring hosts\n' )
    h0.setIP( h0.intfs[ 0 ], '192.168.123.1', 24 )
    h1.setIP( h1.intfs[ 0 ], '192.168.123.2', 24 )

    info( '*** Network state:\n' )
    for node in controller, switch, h0, h1:
        info( str( node ) + '\n' )

    info( '*** Starting controller and user datapath\n' )
    controller.cmd( cname + ' ' + cargs + '&' )
    switch.cmd( 'ifconfig lo 127.0.0.1' )
    intfs = [ switch.intfs[ port ] for port in ( 1, 2 ) ]
    switch.cmd( 'ofdatapath -i ' + ','.join( intfs ) + ' ptcp: &' )
    switch.cmd( 'ofprotocol tcp:' + controller.IP() + ' tcp:localhost &' )

    info( '*** Running test\n' )
    h0.cmdPrint( 'ping -c1 ' + h1.IP() )

    info( '*** Stopping network\n' )
    controller.cmd( 'kill %' + cname )
    switch.cmd( 'kill %ofdatapath' )
    switch.cmd( 'kill %ofprotocol' )
    switch.deleteIntfs()
    info( '\n' )

if __name__ == '__main__':
    lg.setLogLevel( 'info' )
    info( '*** Scratch network demo (user datapath)\n' )
    init()
    scratchNetUser()
