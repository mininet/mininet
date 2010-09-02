#!/usr/bin/python

"This example doesn't use OpenFlow, but attempts to run sshd in a namespace."

from mininet.node import Host

print "*** Creating nodes"
h1 = Host( 'h1' )
root = Host( 'root', inNamespace=False )

print "*** Creating links"
h1.linkTo( root )

print "*** Configuring nodes"
h1.setIP( h1.intfs[ 0 ], '10.0.0.1', 8 )
root.setIP( root.intfs[ 0 ], '10.0.0.2', 8 )

print "*** Creating banner file"
f = open( '/tmp/%s.banner' % h1.name, 'w' )
f.write( 'Welcome to %s at %s\n' % ( h1.name, h1.IP() ) )
f.close()

print "*** Running sshd"
h1.cmd( '/usr/sbin/sshd -o "Banner /tmp/%s.banner"' % h1.name )

print "*** You may now ssh into", h1.name, "at", h1.IP()
