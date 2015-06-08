#!/usr/bin/python

"""
fakecluster.py: a fake cluster for testing Mininet cluster edition!!!

We are going to self-host Mininet by creating a virtual cluster
for cluster edition.

Note: ssh is kind of a mess - you end up having to do things
like h1 sudo -E -u openflow ssh 10.2
"""

from mininet.net import Mininet
from mininet.nodelib import LinuxBridge, Server
from mininet.cli import CLI
from mininet.topo import Topo, SingleSwitchTopo
from mininet.log import setLogLevel, warn
from mininet.util import errRun, quietRun
from mininet.link import Link

from functools import partial

class MininetServer( Server ):
    "A server (for nested Mininet) that runs ssh and ovs"

    privateDirs = [ '/var/run/sshd', '/etc/openvswitch',
                    '/var/run/openvswitch', '/var/log/openvswitch' ]

    def __init__( self, *args, **kwargs ):
        "Turn on ovs by default"
        kwargs.setdefault( 'ovs', True )
        super( MininetServer, self ).__init__( *args, **kwargs )

    def config( self, **kwargs ):
        """Configure/start sshd and other stuff
           ovs: start Open vSwitch?"""
        self.ovs = kwargs.get( 'ovs' )
        super( MininetServer, self ).config( **kwargs )
        if self.ovs:
            self.service( 'openvswitch-switch start' )

    def terminate( self, *args, **kwargs ):
        "Shut down services and terminate server"
        if self.ovs:
            self.service( 'openvswitch-switch stop' )
        super( MininetServer, self ).terminate( *args, **kwargs )


class ServerLink( Link ):
    def intfName( self, node, n ):
        "Override to avoid destruction by cleanup!"
        # This is kind of ugly... for some reason 'eth0' fails so
        # we just use 'm1eth0'; however, this should nest reasonably.
        return ( node.name + 'eth' + repr( n ) if isinstance( node, Server )
                 else node.name + '-eth' + repr( n ) )
    def makeIntfPair( self, *args, **kwargs ):
        "Override to use quietRun"
        kwargs.update( runCmd=quietRun )
        super( ServerLink, self ).makeIntfPair( *args, **kwargs )

class ClusterTopo( Topo ):
    "Cluster topology: m1..mN"
    def build( self, n ):
        ms1 = self.addSwitch( 'ms1' )
        for i in range( 1, n + 1 ):
            h = self.addHost( 'm%d' % i )
            self.addLink( h, ms1, cls=ServerLink )


def test():
    "Test this setup"
    setLogLevel( 'info' )
    topo = ClusterTopo( 8 )
    host = partial( MininetServer, ssh=True, ovs=True)
    net = Mininet( topo=topo, host=host, switch=LinuxBridge, ipBase='10.0/24' )
    MininetServer.updateHostsFiles( net.hosts )
    # addNAT().configDefault() also connects root namespace to Mininet
    net.addNAT().configDefault()
    net.start()
    CLI( net )
    net.stop()

if __name__ == '__main__':
    test()
