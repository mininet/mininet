#!/usr/bin/python

"This example doesn't use OpenFlow, but attempts to run sshd in a namespace."

import sys
from mininet.node import Host
from mininet.util import ensureRoot

ensureRoot()

print "*** Creating nodes"
h1 = Host( 'h1' )

root = Host( 'root', inNamespace=False )

print "*** Creating links"
h1.linkTo( root )

print h1

print "*** Configuring nodes"
h1.setIP( '10.0.0.1', 8 )
root.setIP( '10.0.0.2', 8 )

print "*** Creating banner file"
f = open( '/tmp/%s.banner' % h1.name, 'w' )
f.write( 'Welcome to %s at %s\n' % ( h1.name, h1.IP() ) )
f.close()

print "*** Running sshd"
cmd = '/usr/sbin/sshd -o UseDNS=no -u0 -o "Banner /tmp/%s.banner"' % h1.name
# add arguments from the command line
if len( sys.argv ) > 1:
    cmd += ' ' + ' '.join( sys.argv[ 1: ] )
h1.cmd( cmd )

print "*** You may now ssh into", h1.name, "at", h1.IP()
