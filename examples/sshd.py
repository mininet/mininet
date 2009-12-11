#!/usr/bin/python

"""Create a network and start sshd(8) on the hosts.
   While something like rshd(8) would be lighter and faster,
   (and perfectly adequate on an in-machine network)
   the advantage of running sshd is that scripts can work
   unchanged on mininet and hardware."""

from mininet import init, Node, createLink, TreeNet, Cli

def nets( hosts ):
   "Return list of networks (/24) for hosts."
   nets = {}
   for host in hosts:
      net = host.IP().split( '.' )[ : -1 ]
      net = '.'.join( net ) + '.0/24'
      nets[ net ] = True
   return nets.keys()
   
def addRoutes( node, nets, intf ):
   "Add routes from node to nets through intf."
   for net in nets:
      node.cmdPrint( 'route add -net ' + net + ' dev ' + intf )

def removeRoutes( node, nets ):
   "Remove routes to nets from node."
   for net in nets:
      node.cmdPrint( 'route del -net ' + net )
   
def sshd( network ):
   "Start sshd up on each host, routing appropriately."
   controllers, switches, hosts = (
      network.controllers, network.switches, network.hosts )
   # Create a node in root ns and link to switch 0
   root = Node( 'root', inNamespace=False )
   createLink( root, switches[ 0 ] )
   ip = '10.0.123.1'
   root.setIP( root.intfs[ 0 ], ip, '/24' )
   network.start()
   # Add routes
   routes = nets( hosts )
   addRoutes( root, routes, root.intfs[ 0 ] )
   # Start up sshd on each host
   for host in hosts: host.cmdPrint( '/usr/sbin/sshd' )
   # Dump out IP addresses and run CLI
   print
   print "*** Hosts are running sshd at the following addresses:"
   for host in hosts: print host.name, host.IP()
   print
   print "*** Starting Mininet CLI - type 'exit' or ^D to exit"
   network.runTest( Cli )
   network.stop()
   removeRoutes( root, routes )
   
if __name__ == '__main__':
   init()
   network = TreeNet( depth=1, fanout=2, kernel=True )
   sshd( network )
