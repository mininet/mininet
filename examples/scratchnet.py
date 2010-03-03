#!/usr/bin/python

"""
Build a simple network from scratch, using mininet primitives.
This is more complicated than using the higher-level classes,
but it exposes the configuration details and allows customization.
"""

import logging

from mininet.net import init
from mininet.node import Node
from mininet.util import createLink
from mininet.log import info

# print out info() messages, including cmdPrint
logging.LOGLEVELDEFAULT = logging.INFO

def scratchNet( cname='controller', cargs='ptcp:'):
    # Create Network
    print "*** creating Nodes"
    controller = Node( 'c0', inNamespace=False )
    switch = Node( 's0', inNamespace=False )
    h0 = Node( 'h0' )
    h1 = Node( 'h1' )
    print "*** creating links"
    createLink( node1=h0, port1=0, node2=switch, port2=0 )
    createLink( node1=h1, port1=0, node2=switch, port2=1 )
    # Configure hosts
    print "*** configuring hosts"
    h0.setIP( h0.intfs[ 0 ], '192.168.123.1', '/24' )
    h1.setIP( h1.intfs[ 0 ], '192.168.123.2', '/24' )
    print h0
    print h1
    # Start network using kernel datapath
    controller.cmdPrint( cname + ' ' + cargs + '&' )
    switch.cmdPrint( 'dpctl deldp nl:0' )
    switch.cmdPrint( 'dpctl adddp nl:0' )
    for intf in switch.intfs.values():
      switch.cmdPrint( 'dpctl addif nl:0 ' + intf )
    switch.cmdPrint( 'ofprotocol nl:0 tcp:localhost &')
    # Run test
    print h0.cmd( 'ping -c1 ' + h1.IP() )
    # Stop network
    controller.cmdPrint( 'kill %' + cname)
    switch.cmdPrint( 'dpctl deldp nl:0' )
    switch.cmdPrint( 'kill %ofprotocol' )
    switch.stop()
    controller.stop()
   
if __name__ == '__main__':
    info( '*** Scratch network demo\n' )
    init()   
    scratchNet()
