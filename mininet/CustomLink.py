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

from mininet.link import Intf
from mininet.log import info, error, debug
from mininet.util import makeIntfPair, quietRun
import re

class CustomLink( object ):

    """A basic link is just a veth pair.
       Other types of links could be tunnels, link emulators, etc.."""

    def __init__( self, node, port=None, intfName=None, name=None, destAddr=None, localAddr=None, addr=None ):
        """Create veth link to another node, making two new interfaces.
           node1: first node
           port1: node1 port number (optional)
           intfName1: node1 interface name (optional)
        # This is a bit awkward; it seems that having everything in
        # params is more orthogonal, but being able to specify
        # in-line arguments is more convenient! So we support both.
        """

        self.name  = name
        self.node = node
        self.intfName= intfName
        self.port = port
        self.dstAddr = destAddr
        self.localAddr = localAddr

        intf = Intf( name=intfName, node=node, port=port,
                      link=self, mac=addr )

        self.intf = intf
        self.makeTunnel()
        self.node.addIntf(intf, port=port)
        
    def makeTunnel( self ):
        #lets delete it if it already exists
        print "Making tunnel!\n"
        quietRun('ip link del %s' % self.intf.br_name)
        cmd = 'ip link add %s type gretap remote %s' % (self.intf.br_name, self.dstAddr)
        quietRun(cmd)
        cmd = 'ifconfig %s up' % self.intf.br_name
        quietRun(cmd)
        

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
