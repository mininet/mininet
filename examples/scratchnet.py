#!/usr/bin/python

"""
Build a simple network from scratch, using mininet primitives.
This is more complicated than using the higher-level classes,
but it exposes the configuration details and allows customization.
"""

from mininet.net import init
from mininet.node import Node
from mininet.util import createLink
from mininet.log import lg, info

def scratchNet( cname='controller', cargs='ptcp:' ):
    "Create network from scratch using kernel switch."

    info( "*** Creating nodes\n" )
    controller = Node( 'c0', inNamespace=False )
    switch = Node( 's0', inNamespace=False )
    h0 = Node( 'h0' )
    h1 = Node( 'h1' )

    info( "*** Creating links\n" )
    createLink( node1=h0, node2=switch, port1=0, port2=0 )
    createLink( node1=h1, node2=switch, port1=0, port2=1 )

    info( "*** Configuring hosts\n" )
    h0.setIP( h0.intfs[ 0 ], '192.168.123.1', 24 )
    h1.setIP( h1.intfs[ 0 ], '192.168.123.2', 24 )
    info( str( h0 ) + '\n' )
    info( str( h1 ) + '\n' )

    info( "*** Starting network using kernel datapath\n" )
    controller.cmd( cname + ' ' + cargs + '&' )
    switch.cmd( 'dpctl deldp nl:0' )
    switch.cmd( 'dpctl adddp nl:0' )
    for intf in switch.intfs.values():
        switch.cmd( 'dpctl addif nl:0 ' + intf )
    switch.cmd( 'ofprotocol nl:0 tcp:localhost &' )

    info( "*** Running test\n" )
    h0.cmdPrint( 'ping -c1 ' + h1.IP() )

    info( "*** Stopping network\n" )
    controller.cmd( 'kill %' + cname )
    switch.cmd( 'dpctl deldp nl:0' )
    switch.cmd( 'kill %ofprotocol' )
    switch.deleteIntfs()
    info( '\n' )

if __name__ == '__main__':
    lg.setLogLevel( 'info' )
    info( '*** Scratch network demo (kernel datapath)\n' )
    init()
    scratchNet()
