#!/usr/bin/python

"""
Build a simple network from scratch, using mininet primitives.
This is more complicated than using the higher-level classes,
but it exposes the configuration details and allows customization.
"""

from mininet.mininet import init, Node, createLink

def scratchNet( cname='controller', cargs='ptcp:'):
   # Create Network
   controller = Node( 'c0', inNamespace=False )
   switch = Node( 's0', inNamespace=False )
   h0 = Node( 'h0' )
   h1 = Node( 'h1' )
   createLink( h0, switch )
   createLink( h1, switch )
   # Configure hosts
   h0.setIP( h0.intfs[ 0 ], '192.168.123.1', '/24' )
   h1.setIP( h1.intfs[ 0 ], '192.168.123.2', '/24' )
   # Start network using kernel datapath
   controller.cmdPrint( cname + ' ' + cargs + '&' )
   switch.cmdPrint( 'dpctl deldp nl:0' )
   switch.cmdPrint( 'dpctl adddp nl:0' )
   for intf in switch.intfs:
      switch.cmdPrint( 'dpctl addif nl:0 ' + intf )
   switch.cmdPrint( 'ofprotocol nl:0 tcp:localhost &')
   # Run test
   h0.cmdPrint( 'ping -c1 ' + h1.IP() )
   # Stop network
   controller.cmdPrint( 'kill %' + cname)
   switch.cmdPrint( 'dpctl deldp nl:0' )
   switch.cmdPrint( 'kill %ofprotocol' )
   switch.stop()
   controller.stop()
   
if __name__ == '__main__':
   init()   
   scratchNet()
