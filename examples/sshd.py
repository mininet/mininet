#!/usr/bin/python

"""
Create a network and start sshd(8) on each host.

While something like rshd(8) would be lighter and faster,
(and perfectly adequate on an in-machine network)
the advantage of running sshd is that scripts can work
unchanged on mininet and hardware.
"""

import sys ; readline = sys.stdin.readline
from mininet import init, Node, createLink, TreeNet, Cli

def nets( hosts ):
   "Return list of networks (/24) for hosts."
   nets = {}
   for host in hosts:
      net = host.IP().split( '.' )[ : -1 ]
      net = '.'.join( net ) + '.0/24'
      nets[ net ] = True
   return nets.keys()
   
def connectToRootNS( network, switch ):
   "Connect hosts to root namespace via switch. Starts network."
   # Create a node in root namespace and link to switch 0
   root = Node( 'root', inNamespace=False )
   createLink( root, switch )
   ip = '10.0.123.1'
   root.setIP( root.intfs[ 0 ], ip, '/24' )
   # Start network that now includes link to root namespace
   network.start()
   # Add routes
   routes = nets( network.hosts )
   intf = root.intfs[ 0 ]
   for net in routes:
      root.cmdPrint( 'route add -net ' + net + ' dev ' + intf )

def sshd( network ):
   "Start a network, connect it to root ns, and run sshd on all hosts."
   connectToRootNS( network, network.switches[ 0 ] )
   for host in network.hosts: host.cmd( 'sshd -D &' )
   print
   print "*** Hosts are running sshd at the following addresses:"
   print
   for host in network.hosts: print host.name, host.IP()
   print
   print "*** Press return to shut down network: ",
   readline()
   for host in network.hosts: host.cmd( 'kill %sshd')
   network.stop()
   
if __name__ == '__main__':
   init()
   network = TreeNet( depth=1, fanout=4, kernel=True )
   sshd( network )