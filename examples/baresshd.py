#!/usr/bin/python

"This example doesn't use OpenFlow, but attempts to run sshd in a namespace."

import sys

from mininet.node import Host
from mininet.util import ensureRoot, waitListening
from mininet.log import info, warn, output


ensureRoot()
timeout = 5

info( "*** Creating nodes\n" )
h1 = Host( 'h1' )

root = Host( 'root', inNamespace=False )

info( "*** Creating link\n" )
h1.linkTo( root )

info( h1 )

info( "*** Configuring nodes\n" )
h1.setIP( '10.0.0.1', 8 )
root.setIP( '10.0.0.2', 8 )

info( "*** Creating banner file\n" )
f = open( '/tmp/%s.banner' % h1.name, 'w' )
f.write( 'Welcome to %s at %s\n' % ( h1.name, h1.IP() ) )
f.close()

info( "*** Running sshd\n" )
cmd = '/usr/sbin/sshd -o UseDNS=no -u0 -o "Banner /tmp/%s.banner"' % h1.name
# add arguments from the command line
if len( sys.argv ) > 1:
    cmd += ' ' + ' '.join( sys.argv[ 1: ] )
h1.cmd( cmd )
listening = waitListening( server=h1, port=22, timeout=timeout )

if listening:
    output( "*** You may now ssh into", h1.name, "at", h1.IP(), '\n' )
else:
    warn( "*** Warning: after %s seconds, %s is not listening on port 22"
            % ( timeout, h1.name ), '\n' )
