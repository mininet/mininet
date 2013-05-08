#!/usr/bin/python

"""
cluster.py: prototyping/experimentation for distributed Mininet,
            aka Mininet: Cluster Edition

Bob Lantz, Spring 2013

Core classes:

    RemoteNode: a Node() running on a remote server
    RemoteOVSSwitch(): an OVSSwitch() running on a remote server
    RemoteLink: a Link() on a remote server
    Tunnel: a Link() between a local Node() and a RemoteNode()

These are largely interoperable with local objects.

Question: if we want to share a single ssh connection to all of the remote
objects on a Mininet server, how should this be handled? Should it be
handled in the RemoteNode() class or in another class?

- One Mininet to rule them all

It is important that a single topology be able to contain local nodes and
remote nodes.

- Multiple placement models

Placement should be as easy as possible. We should provide basic placement
support and also allow for explicit placement.

Questions:

What is the basic communication mechanism?

To start with? Probably a single multiplexed ssh connection between each
pair of mininet servers that needs to communicate.

How are tunnels created?

We have several options including OF capsulator, socat, vxlan, VDE, l2tp, etc.
It's not clear what the best one is.  Probably ssh tunnels if we're going to
have ssh connections to the mininet servers.

How are tunnels destroyed?

They are destroyed when the links are deleted in Mininet.stop()

How does RemoteNode.popen() work?

It could work in a variety of ways. One way would be to create a shared ssh
connection to the remote Mininet server and run mnexec -a -g.

Is there any value to using Paramiko vs. raw ssh?

Maybe.

Limitations:

We don't currently multiplex the ssh connections.

"""

from mininet.node import Node, Host, OVSSwitch, Controller
from mininet.link import Link, Intf
from mininet.net import Mininet
from mininet.topo import LinearTopo
from mininet.topolib import TreeTopo
from mininet.util import quietRun, makeIntfPair, errRun
from mininet.cli import CLI
from mininet.log import setLogLevel, debug, info

from signal import signal, SIGINT, SIG_IGN
from subprocess import Popen, PIPE, STDOUT
import select
import pty
import os
from time import sleep
from random import randrange


# BL note: so little code is required for remote nodes,
# we will probably just want to update the main Node()
# class to enable it for remote access! However, there
# are a large number of potential failure conditions with
# remote nodes which we may want to detect and handle.
# Another interesting point is that we could put everything
# in a mix-in class and easily add cluster mode to 2.0.

class RemoteMixin( object ):

    "A mix-in class to turn local nodes into remote nodes"

    def __init__( self, name, server=None, user=None, controlPath=None,
                 delayShell=False, **kwargs):
        """Instantiate a remote node
           name: name of remote node
           server: remote server (optional)
           user: user on remote server (optional)
           controlPath: ssh control path to server (optional)
           delayShell: delay calling startShell()
           **kwargs: see Node()"""
        self.server = server
        if server and not user:
            user = quietRun( 'who am i' ).split()[ 0 ]
        self.user = user
        self.controlPath = controlPath
        self.delayShell = delayShell
        super( RemoteMixin, self).__init__( name, **kwargs )

    # Command support via shell process in namespace
    def startShell( self, *args, **kwargs ):
        "Start a shell process for running commands"
        if self.delayShell:
            # Defer starting shell to wait for placement
            self.delayShell = False
            return
        super( RemoteMixin, self ).startShell( *args, **kwargs )
        self.pid = int( self.cmd( 'echo $$' ) )

    def _popen( self, cmd, **params):
        """Spawn a process on a remote node
            cmd: remote command to run (list)
            **params: parameters to Popen()
            returns: Popen() object"""
        if self.user and self.server and self.server != 'localhost':
            if self.controlPath:
                cmd = [ 'ssh', '-tt', '-S', self.controlPath,
                        '%s@%s' % ( self.user, self.server),
                       'sudo', '-E' ] + cmd
            else:
                cmd = [ 'ssh', '-tt', '%s@%s' % ( self.user, self.server),
                       'sudo', '-E' ] + cmd
        old = signal( SIGINT, SIG_IGN )
        popen = super( RemoteMixin, self )._popen( cmd, **params )
        signal( SIGINT, old )
        return popen


class RemoteNode( RemoteMixin, Node ):
    "A node on a remote server"
    pass


class RemoteHost( RemoteNode ):
    "A RemoteHost is simply a RemoteNode"
    pass


class RemoteOVSSwitch( RemoteMixin, OVSSwitch ):
    "Remote instance of Open vSwitch"
    pass


# RemoteController should really be renamed ExternalController
class RController( RemoteMixin, Controller ):
    "Remote instance of Controller()"
    def start( *args, **kwargs ):
        "Start and update IP address"
        print "UPDATING IP ADDRESS"
        Intf( 'eth0', node=self ).updateIP()
        super( RController, self ).start( *args, **kwargs )

class RemoteLink( Link ):

    "A RemoteLink is a link between nodes which may be on different servers"

    def __init__( self, node1, node2, **kwargs ):
        """Initialize a RemoteLink
           see Link() for parameters"""
        # Create links on remote node
        self.node1 = node1
        self.node2 = node2
        self.tunnel = None
        kwargs.setdefault( 'params1', {} )
        kwargs.setdefault( 'params2', {} )
        kwargs[ 'params1' ].setdefault( 'srcNode', self.node1 )
        kwargs[ 'params2' ].setdefault( 'srcNode', self.node1 )
        Link.__init__( self, node1, node2, **kwargs )

    def stop( self ):
        "Stop this link"
        if self.tunnel:
            self.tunnel.terminate()
        self.tunnel = None

    def makeIntfPair( self, intfname1, intfname2 ):
        """Create pair of interfaces
            intfname1: name of interface 1
            intfname2: name of interface 2
            (override this method [and possibly delete()]
            to change link type)"""
        node1, node2 = self.node1, self.node2
        server1 = getattr( node1, 'server', None )
        server2 = getattr( node2, 'server', None )
        if not server1 and not server2:
            return makeIntfPair( intfname1, intfname2, node=self.node1 )
        if server1 == server2:
            # Remote link within same server
            return makeIntfPair( intfname1, intfname2, node=self.node1 )
        # Otherwise, make a tunnel
        self.tunnel = self.makeTunnel( intfname1, intfname2, node1, node2 )
        return self.tunnel

    def makeTunnel( self, intfname1, intfname2, node1, node2 ):
        "Make a tunnel across switches on different servers"
        # For now, tunnels must be in the root namespace
        # In the future we can create them in the root NS and then
        # move them into the node NSes as necessary.
        assert not node1.inNamespace and not node2.inNamespace
        # 1. Create tap interfaces
        for node in node1, node2:
            # For now we are hard-wiring tap9, which we will rename
            node.cmd( 'ip link delete tap9' )
            cmd = 'ip tuntap add dev tap9 mode tap'
            user = getattr( node, 'user', None )
            if user:
                cmd += ' user ' + user
            node.cmd( cmd )
            assert 'tap9' in node.cmd( 'ip link show' )
        # 2. Create ssh tunnel between tap interfaces
        # -n: close stdin
        cmd = [ 'ssh', '-n', '-o', 'Tunnel=Ethernet', '-w', '9:9',
                 '%s@%s' %  ( node2.user, node2.server ), 'echo a' ]
        self.cmd = cmd
        old = signal( SIGINT, SIG_IGN )
        tunnel = Popen( cmd, stdin=PIPE, stdout=PIPE )
        signal( SIGINT, old )
        # When we receive the character 'a', it means that our
        # tunnel should be set up
        debug( 'Waiting for tunnel to come up...\n' )
        tunnel.stdout.read( 1 )
        # 3. Rename tap interfaces to desired names
        for node, intf in ( ( node1, intfname1 ), ( node2, intfname2 ) ):
            node.cmd( 'ip link set tap9 name', intf )
        for node, intf in ( ( node1, intfname1 ), ( node2, intfname2 ) ):
            assert intf in node.cmd( 'ip link show' )
        return tunnel

    def status( self ):
        "Detailed representation of link"
        if self.tunnel:
            if self.tunnel.poll() is not None:
                status = "Tunnel EXITED %s" % self.tunnel.returncode
            else:
                status = "Tunnel Running (%s: %s)" % (
                    self.tunnel.pid, self.cmd )
        else:
            status = "OK"
        return "%s %s" % ( Link.status( self ), status )



# Some simple placement algorithms for MininetCluster

class Placer( object ):
    "Node placement algorithm for MininetCluster"
    
    def __init__( self, servers=None, nodes=None, hosts=None,
                 switches=None, controllers=None ):
        """Initialize placement object
           servers: list of servers
           nodes: list of all nodes
           hosts: list of hosts
           switches: list of switches
           controllers: list of controllers
           (all arguments are optional)"""
        self.servers = servers or []
        self.nodes = nodes or []
        self.hosts = hosts or []
        self.switches = switches or []
        self.controllers = controllers or []
    
    def place( self, node ):
        "Return server for a given node"
        return 'localhost'


class RandomPlacer( Placer ):
    "Random placement"
    def place( self, nodename ):
        """Random placement function
            nodename: node name"""
        # This may be slow with lots of servers
        return self.servers[ randrange( 0, len( self.servers ) ) ]


class RoundRobinPlacer( Placer ):
    "Round-robin placement"
    
    def __init__( self, *args, **kwargs ):
        Placer.__init__( self, *args, **kwargs )
        next = 0

    def place( self, nodename ):
        """Round-robin placement function
            nodename: node name"""
        # This may be slow with lots of servers
        server = self.servers[ self.next ]
        self.next = ( self.next + 1 ) % len( net.servers )
        return server

class BinPlacer( Placer ):
    "Placement into evenly-sized bins"

    def __init__( self, *args, **kwargs ):
        Placer.__init__( self, *args, **kwargs )
        # Calculate bin sizes
        scount = len( self.servers )
        self.hbin = max( int( len( self.hosts ) / scount ), 1 )
        self.sbin = max( int( len( self.switches ) / scount ), 1 )
        self.cbin = max( int( len( self.controllers ) / scount ) , 1 )
        print "scount", scount
        print "bins:", self.hbin, self.sbin, self.cbin
        # Dicts for easy lookup
        self.hdict = { h: True for h in self.hosts }
        self.sdict = { s: True for s in self.switches }
        self.cdict = { c: True for c in self.controllers }
        self.hind, self.sind, self.cind = 0, 0, 0
    
    def place( self, nodename ):
        """Simple placement algorithm:
            place nodes into evenly sized bins"""
        # Place nodes into bins
        if nodename in self.hdict:
            server = self.servers[ self.hind / self.hbin ]
            self.hind += 1
        elif nodename in self.sdict:
            server = self.servers[ self.sind / self.sbin ]
            self.sind += 1
        elif nodename in self.cdict:
            server = self.servers[ self.cind / self.cbin ]
            self.cind += 1
        else:
            info( 'warning: unknown node', nodename )
            server = servers[ 0 ]
        return server



# The MininetCluster class is not strictly necessary.
# However, it has several purposes:
# 1. To set up ssh connection sharing/multiplexing
# 2. To pre-flight the system so that everything is more likely to work
# 3. To allow connection/connectivity monitoring
# 4. To support pluggable placement algorithms

class MininetCluster( Mininet ):

    "Cluster-enhanced version of Mininet class"

    def __init__( self, *args, **kwargs ):
        """servers: a list of servers to use (note: include
           localhost or None to use local system as well)
           placement: f( servers, nodename ) -> server"""
        params = { 'host': RemoteHost,
                   'switch': RemoteOVSSwitch,
                   'controller': ClusterController,
                   'link': RemoteLink }
        params.update( kwargs )
        self.servers = params.pop( 'servers', [] )
        self.user = params.pop( 'user', None )
        if self.servers and not self.user:
            self.user = quietRun( 'who am i' ).split()[ 0 ]
        self.connections = {}
        self.placement = params.pop( 'placement', BinPlacer )
        self.startConnections()
        Mininet.__init__( self, *args, **params )

    def popen( self, cmd ):
        "Popen() for server connections"
        old = signal( SIGINT, SIG_IGN )
        conn = Popen( cmd, stdout=PIPE, stderr=PIPE, close_fds=True )
        signal( SIGINT, old )
        return conn

    def startConnections( self ):
        "Initialize master ssh connections to servers"
        # Make sure control directory exists
        cdir = os.environ[ 'HOME' ] + '/.ssh/controlmasters'
        errRun( [ 'mkdir', '-p', cdir ] )
        # Create ssh master connections
        info( '*** Starting server connections\n')
        for server in self.servers:
            dest = '%s@%s' % ( self.user, server )
            cfile = '%s/%s' % ( cdir, dest )
            cmd = [ 'ssh', '-n', '-M', '-S', cfile, dest, 'echo a' ]
            info( dest, '' )
            conn = self.popen( cmd )
            self.connections[ server ] = ( dest, conn, cfile )
        # Wait for them to start up
        for server in self.servers:
            _dest, conn, _cfile = self.connections[ server ]
            conn.stdout.read()
            info( '.' )
        info( '\n' )

    def stopConnections( self ):
        for server in self.servers:
            dest, conn, cfile = self.connections[ server ]
            cmd = [ 'ssh', '-O', 'stop', '-S', cfile, dest ]
            errRun( cmd )
            conn.terminate()
            conn.wait()
        self.connections = []

    def placeNodes( self ):
        """Place nodes on servers (if they don't have a server), and
           start shell processes"""
        if not self.servers or not self.topo:
            # No shirt, no shoes, no service
            return
        nodes = self.topo.nodes()
        placer = self.placement( servers=self.servers,
                                 nodes=self.topo.nodes(),
                                 hosts=self.topo.hosts(),
                                 switches=self.topo.switches() )
        for node in nodes:
            config = self.topo.node_info[ node ]
            server = config.setdefault( 'server', placer.place( node ) )
            _dest, _conn, cfile = self.connections.get( server,
                                    ( None, None, None ) )
            if cfile:
                config.setdefault( 'controlPath', cfile )
            info( '%s:%s ' % ( node, server ) )

    def buildFromTopo( self, *args, **kwargs ):
        "Start network"
        info( '*** Placing nodes\n' )
        self.placeNodes()
        info( '\n' )
        Mininet.buildFromTopo( self, *args, **kwargs )

    def stop( self ):
        "Stop network"
        Mininet.stop( self )
        info( '*** Stopping server connections\n' )
        self.stopConnections()



# Manual topology creation with net.add*()
#
# This shows how node options may be used to manage
# cluster placement using the net.add*() API

def testRemoteNet():
    "Test remote Node classes"
    print '*** Remote Node Test'
    rhost = dict( cls=RemoteHost, server='ubuntu12' )
    rswitch = dict( cls=RemoteOVSSwitch, server='ubuntu12' )
    net = Mininet( link=RemoteLink )
    c0 = net.addController( 'c0' )
    # Make sure controller knows its non-loopback address
    Intf( 'eth0', node=c0 ).updateIP()
    print "*** Creating local h1"
    h1 = net.addHost( 'h1' )
    print "*** Creating remote h2"
    h2 = net.addHost( 'h2', **rhost )
    print "*** Creating local s1"
    s1 = net.addSwitch( 's1' )
    print "*** Creating remote s2"
    s2 = net.addSwitch( 's2', **rswitch )
    print "*** Adding links"
    net.addLink( h1, s1 )
    net.addLink( s1, s2 )
    net.addLink( h2, s2 )
    net.start()
    print 'Mininet is running on', quietRun( 'hostname' ).strip()
    for node in c0, h1, h2, s1, s2:
        print 'Node', node, 'is running on', node.cmd( 'hostname' ).strip()
    net.pingAll()
    CLI( net )
    net.stop()


# High-level/Topo API example
#
# This shows how existing Mininet topologies may be used in cluster
# mode by creating node placement functions and a controller which
# can be accessed remotely. This implements a very compatible version
# of cluster edition with a minimum of code!

remoteHosts = [ 'h2' ]
remoteSwitches = [ 's2' ]
remoteServer = 'ubuntu12'

def HostPlacer( name, *args, **params ):
    "Custom Host() constructor which places hosts on servers"
    if name in remoteHosts:
        return RemoteHost( name, *args, server=remoteServer, **params )
    else:
        return Host( name, *args, **params )

def SwitchPlacer( name, *args, **params ):
    "Custom Switch() constructor which places switches on servers"
    if name in remoteSwitches:
        return RemoteOVSSwitch( name, *args, server=remoteServer, **params )
    else:
        return OVSSwitch( name, *args, **params )

def ClusterController( *args, **kwargs):
    "Custom Controller() constructor which updates its eth0 IP address"
    controller = Controller( *args, **kwargs )
    # Find out its IP address so that cluster switches can connect
    Intf( 'eth0', node=controller ).updateIP()
    return controller

def testRemoteTopo():
    "Test remote Node classes using Mininet()/Topo() API"
    topo = LinearTopo( 2 )
    net = Mininet( topo=topo, host=HostPlacer, switch=SwitchPlacer,
                  link=RemoteLink, controller=ClusterController )
    net.start()
    net.pingAll()
    net.stop()


# The MininetCluster() class integrates pluggable placement
# functions, for maximum ease of use. MininetCluster() also
# pre-flights and multiplexes server connections.

def testMininetCluster():
    "Test MininetCluster()"
    servers = [ 'localhost', 'ubuntu12' ]
    user = 'openflow'
    topo = LinearTopo( 15 )
    net = MininetCluster( topo=topo, servers=servers, user=user,
                          placement=RandomPlacer )
    net.start()
    net.pingAll()
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    # testRemoteTopo()
    # testRemoteNet()
    testMininetCluster()

