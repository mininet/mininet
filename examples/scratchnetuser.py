#!/usr/bin/python

"""
Build a simple network from scratch, using mininet primitives.
This is more complicated than using the higher-level classes,
but it exposes the configuration details and allows customization.

This version uses the user datapath.
"""

from mininet.mininet import init, Node, createLink

def scratchNetUser( cname='controller', cargs='ptcp:'):
   # Create Network
   # It's not strictly necessary for the controller and switches
   # to be in separate namespaces. For performance, they probably
   # should be in the root namespace. However, it's interesting to
   # see how they could work even if they are in separate namespaces.
   controller = Node( 'c0' )
   switch = Node( 's0')
   h0 = Node( 'h0' )
   h1 = Node( 'h1' )
   createLink( controller, switch )
   createLink( h0, switch )
   createLink( h1, switch )
   # Configure control network
   controller.setIP( controller.intfs[ 0 ], '10.0.123.1', '/24' )
   switch.setIP( switch.intfs[ 0 ], '10.0.123.2', '/24' )
   # Configure hosts
   h0.setIP( h0.intfs[ 0 ], '192.168.123.1', '/24' )
   h1.setIP( h1.intfs[ 0 ], '192.168.123.2', '/24' )
   # Start network using user datapath
   controller.cmdPrint( cname + ' ' + cargs + '&' )
   switch.cmdPrint( 'ifconfig lo 127.0.0.1' )
   switch.cmdPrint( 'ofdatapath -i ' + ','.join( switch.intfs[ 1: ]) 
      + ' ptcp: &' )
   switch.cmdPrint( 'ofprotocol tcp:' + controller.IP() + ' tcp:localhost &' )
   # Run test
   h0.cmdPrint( 'ping -c1 ' + h1.IP() )
   # Stop network
   controller.cmdPrint( 'kill %' + cname)
   switch.cmdPrint( 'kill %ofdatapath' )
   switch.cmdPrint( 'kill %ofprotocol' )
   
if __name__ == '__main__':
   init()   
   scratchNetUser()
