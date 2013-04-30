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
from mininet.util import quietRun, makeIntfPair
from mininet.cli import CLI
from mininet.log import setLogLevel, debug

from signal import signal, SIGINT, SIG_IGN
from subprocess import Popen, PIPE, STDOUT
import select
import pty
import os
from time import sleep

class RemoteNode( Node ):

    "A RemoteNode is a Node which is running on a remote server."

    def __init__( self, name, server="ubuntu12", user=None, **kwargs):
        """Instantiate a RemoteNode
           remoteHost: name of remote host
           **kwargs: see Node()"""
        self.remote = True
        self.server = server
        if not user:
            user = quietRun( 'who am i' ).split()[ 0 ]
        self.user = user
        Node.__init__( self, name, **kwargs )

    def cleanup( self ):
        "Help python collect its garbage."
        if not self.inNamespace:
            for intfName in self.intfNames():
                if self.name in intfName:
                    # Warning: this can fail with many fds!!!!
                    self.pexec( 'ip link del ' + intfName )
        self.shell = None

    # Command support via shell process in namespace
    def startShell( self, *args, **kwargs ):
        "Start a shell process for running commands"
        Node.startShell( self, *args, **kwargs )
        self.pid = int( self.cmd( 'echo $$' ) )

    def _popen( self, cmd, **params):
        """Spawn a process on a remote node
            cmd: remote command to run (list)
            **params: parameters to Popen()
            returns: Popen() object"""
        cmd = [ 'ssh', '-tt', '%s@%s' % ( self.user, self.server),
               'sudo', '-E' ] + cmd
        old = signal( SIGINT, SIG_IGN )
        popen = Node._popen( self, cmd, **params )
        signal( SIGINT, old )
        return popen

class RemoteHost( RemoteNode ):
    "A RemoteHost is simply a RemoteNode"
    pass


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
        cmd = [ 'ssh', '-o', 'Tunnel=Ethernet', '-w', '9:9',
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

"""
Notes:

ip tuntap add dev s1-tap0 mode tap
    ip link set tap0 name s1-tap0

    ssh -v -o Tunnel=Ethernet -w 0:0 openflow@ubuntu12

Hmm... how do we shut down the ssh tunnel??!?!! arrgh.....
we could run it in the background on the node and rely on sighup perhaps???

Or we could rely on the destructor being called and use weak references
to break the reference cycle.... (probably the weak ref would be from the
Link to its interfaces, since the Intfs are the things which are going away...
or we could put the Links in a list in the Mininet object....)

Or we could explicitly keep track of them and delete them in Mininet()

"""


class RemoteOVSSwitch( OVSSwitch ):
    "Remote instance of Open vSwitch"
    
    def __init__( self, name, failMode='secure', server="localhost",
                 user=None, **kwargs):
        """Instantiate a RemoteNode
            remoteHost: name of remote host
            **kwargs: see Node()"""
        self.remote = True
        self.server = server
        if not user:
            self.user = quietRun( 'who am i' ).split()[ 0 ]
        OVSSwitch.__init__( self, name, failMode=failMode, **kwargs )

    def startShell( self, *args, **kwargs ):
        "startShell that sets remote PID"
        OVSSwitch.startShell( self, *args, **kwargs )
        self.pid = int( self.cmd( 'echo $$' ) )

    def cleanup( self ):
        "Help python collect its garbage."
        self.shell = None

    def _popen( self, cmd, **params):
        """Spawn a process on a remote node
            cmd: remote command to run (list)
            **params: parameters to Popen()
            returns: Popen() object"""
        cmd = [ 'ssh', '-tt', '%s@%s' % ( self.user, self.server), 'sudo', '-E' ] + cmd
        old = signal( SIGINT, SIG_IGN )
        popen = Node._popen( self, cmd, **params )
        signal( SIGINT, old )
        return popen

# Test remote Node classes

remoteHosts = [ 'h2' ]
remoteServer = 'ubuntu12'

def HostPlacer( name, *args, **params ):
    "Custom Host() constructor which places hosts on servers"
    if name in remoteHosts:
        return RemoteHost( name, *args, server=remoteServer, **params )
    else:
        return Host( name, *args, **params )

def SwitchPlacer( name, *args, **params ):
    "Custom Host() constructor which places hosts on servers"
    if name in remoteSwitches:
        return RemoteSwitch( name, *args, server=remoteServer, **params )
    else:
        return OVSSwitch( name, *args, **params )

def testRemoteNet1():
    "Test remote Node classes using topology"
    topo = LinearTopo( 2 )
    net = Mininet( topo=topo, host=HostPlacer, switch=SwitchPlacer )
    net.start()
    net.pingAll()
    net.stop()

def testRemoteNet():
    "Test remote Node classes"
    print '*** Remote Node Test'
    rhost = dict( cls=RemoteHost, server='ubuntu12' )
    rswitch = dict( cls=RemoteOVSSwitch, server='ubuntu12' )
    net = Mininet( link=RemoteLink )
    c0 = net.addController( 'c0' )
    eth0 = Intf( 'eth0', node=c0 )
    eth0.updateIP()
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


if __name__ == '__main__':
    setLogLevel( 'info' )
    testRemoteNet()
