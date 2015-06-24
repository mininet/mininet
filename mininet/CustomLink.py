"""
CustomLink.py: interface and link abstractions for mininet

It seems useful to bundle functionality for interfaces into a single
class.

Also it seems useful to enable the possibility of multiple flavors of
links, including:

- simple veth pairs
- tunneled links
- patchable links (which can be disconnected and reconnected via a patchbay)
- link simulators (e.g. wireless)

Basic division of labor:

  Nodes: know how to execute commands
  Intfs: know how to configure themselves
  Links: know how to connect nodes together

Intf: basic interface object that can configure itself
TCIntf: interface with bandwidth limiting and delay via tc

Link: basic link class for creating veth pairs
"""

from mininet.log import info, error, debug
from mininet.util import makeIntfPair, quietRun
import re

class CustomLink( object ):

    """A basic link is just a veth pair.
       Other types of links could be tunnels, link emulators, etc.."""

    def __init__( self, node1, port1=None, intfName1=None, name=None, destAddr=None, localAddr=None ):
        """Create veth link to another node, making two new interfaces.
           node1: first node
           port1: node1 port number (optional)
           intfName1: node1 interface name (optional)
        # This is a bit awkward; it seems that having everything in
        # params is more orthogonal, but being able to specify
        # in-line arguments is more convenient! So we support both.
        """

        self.name  = name
        self.node1 = node1
        self.intfName1= intfName1
        self.port1 = port1
        self.dstAddr = destAddr
        self.localAddr = localAddr

        intf1 = Intf( name=intfName1, node=node1,
                      link=self, mac=addr1, **params1 )

        self.intf1 = intf1
        self.makeTunnel()

    def makeTunnel( self ):
        dst = "%s@%s" % ( self.dstUser, self.dstAddr)
        
        #lets delete it if it already exists
        node.rcmd ('ip link del %s' % self.intf1.br_name)
        
        cmd = 'ip link add %s type gretap local %s remote %s' % (self.intf1.br_name,self.localAddr, self.dstAddr)
        node.rcmd(cmd)


    def intfName( self, node, n ):
        "Construct a canonical interface name node-ethN for interface n."
        # Leave this as an instance method for now
        assert self
        return node.name + '-eth' + repr( n )

    def delete( self ):
        "Delete this link"
        self.intf1.delete()

    def stop( self ):
        "Override to stop and clean up link as needed"
        pass

    def status( self ):
        "Return link status as a string"
        return "(%s %s)" % ( self.intf1.status() )

    def __str__( self ):
	if(self.name):
	    return self.name
        else:
            return '{0}-{1}<->{2}'.format( self.node1, self.intf1, self.dest )
