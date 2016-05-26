#!/usr/bin/python

"""
Build a simple network from scratch, using mininet primitives.
This is more complicated than using the higher-level classes,
but it exposes the configuration details and allows customization.

For most tasks, the higher-level API will be preferable.

This version uses the user datapath and an explicit control network.
"""

from mininet.net import Mininet
from mininet.node import Node
from mininet.link import Link
from mininet.log import setLogLevel, info

def linkIntfs( node1, node2 ):
    "Create link from node1 to node2 and return intfs"
    link = Link( node1, node2 )
    return link.intf1, link.intf2

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
    cintf, sintf = linkIntfs( controller, switch )
    h0intf, sintf1 = linkIntfs( h0, switch )
    h1intf, sintf2 = linkIntfs( h1, switch )

    info( '*** Configuring control network\n' )
    controller.setIP( '10.0.123.1/24', intf=cintf )
    switch.setIP( '10.0.123.2/24', intf=sintf)

    info( '*** Configuring hosts\n' )
    h0.setIP( '192.168.123.1/24', intf=h0intf )
    h1.setIP( '192.168.123.2/24', intf=h1intf )

    info( '*** Network state:\n' )
    for node in controller, switch, h0, h1:
        info( str( node ) + '\n' )

    info( '*** Starting controller and user datapath\n' )
    controller.cmd( cname + ' ' + cargs + '&' )
    switch.cmd( 'ifconfig lo 127.0.0.1' )
    intfs = str( sintf1 ), str( sintf2 )
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
    setLogLevel( 'info' )
    info( '*** Scratch network demo (user datapath)\n' )
    Mininet.init()
    scratchNetUser()
