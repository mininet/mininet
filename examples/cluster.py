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

Maybe, but it doesn't seem to support L2 tunneling.

Should we preflight the entire network, including all server-to-server
connections?

Yes! We don't yet do this with link connections however.

Should we multiplex the link ssh connections?

YES!! This involves keeping track of all of the server-server links.
Note that the link connections will have to be disambiguated somehow.
For example, they could be server1-server2

Note on ssh and DNS:
Please add UseDNS: no to your /etc/ssh/sshd_config!!!

Things to do:

- control paths for links
- asynchronous/pipelined startup
- ssh debugging/profiling
- make connections into real objects

"""

from mininet.node import Node, Host, OVSSwitch, Controller
from mininet.link import Link, Intf
from mininet.net import Mininet
from mininet.topo import LinearTopo
from mininet.topolib import TreeTopo
from mininet.util import quietRun, makeIntfPair, errRun, retry
from mininet.cli import CLI as CLIbase
from mininet.log import setLogLevel, debug, info, error

from signal import signal, SIGINT, SIG_IGN
from subprocess import Popen, PIPE, STDOUT
import select
import pty
import os
from time import sleep
from random import randrange
from sys import exit
import re
from itertools import chain
from distutils.version import StrictVersion

# BL note: so little code is required for remote nodes,
# we will probably just want to update the main Node()
# class to enable it for remote access! However, there
# are a large number of potential failure conditions with
# remote nodes which we may want to detect and handle.
# Another interesting point is that we could put everything
# in a mix-in class and easily add cluster mode to 2.0.

class RemoteMixin( object ):

    "A mix-in class to turn local nodes into remote nodes"

    # ssh base command
    # BatchMode yes: don't ask for password
    # ForwardAgent yes: forward authentication credentials
    sshopts = [ 'ssh', '-o', 'BatchMode yes', 'ForwardAgent yes' ]

    def __init__( self, name, server=None, user=None, controlPath=None,
                 serverIP=None, splitInit=False, **kwargs):
        """Instantiate a remote node
           name: name of remote node
           server: remote server (optional)
           user: user on remote server (optional)
           controlPath: ssh control path to server (optional)
           delayShell: delay calling startShell()
           **kwargs: see Node()"""
        # We connect to servers via IP address
        if server == 'localhost':
            server = None
        self.server = server
        if not serverIP:
                serverIP = self.findServerIP( server )
        self.serverIP = serverIP
        if not user:
            user = quietRun( 'who am i' ).split()[ 0 ]
        self.user = user
        self.dest = '%s@%s' % ( self.user, self.serverIP )
        self.controlPath = controlPath
        self.splitInit = splitInit
        super( RemoteMixin, self).__init__( name, **kwargs )

    # Determine IP address of local host
    _ipMatchRegex = re.compile( r'\d+\.\d+\.\d+\.\d+' )

    @classmethod
    def findServerIP( cls, server, intf='eth0' ):
        "Return our server's IP address"
        # Check for this server
        if not server:
            output = quietRun( 'ifconfig %s' % intf  )
        # Otherwise, handle remote server
        else:
            # First, check for an IP address
            if server:
                ipmatch = cls._ipMatchRegex.findall( server )
                if ipmatch:
                    return ipmatch[ 0 ]
            # Otherwise, look up remote server
            output = quietRun( 'host %s' % server )
        ips = cls._ipMatchRegex.findall( output )
        ip = ips[ 0 ] if ips else None
        return ip

    # Command support via shell process in namespace
    def startShell( self, *args, **kwargs ):
        "Start a shell process for running commands"
        super( RemoteMixin, self ).startShell( *args, **kwargs )
        if self.splitInit:
            self.sendCmd( 'echo $$' )
        else:
            self.pid = int( self.cmd( 'echo $$' ) )

    def finishInit( self ):
        self.pid = int( self.waitOutput() )

    # Run command on node's server's root namespace
    # This is important for things like ssh control
    # network connections

    def rpopen( self, *args, **opts):
        """Create a popen object runing in server's root namespace
            args: strings, or single list of strings"""
        sudo = opts.pop( 'sudo', True )
        opts.setdefault( 'stdout', PIPE )
        opts.setdefault( 'close_fds', True )
        # single list of strings
        if len( args ) == 1:
            if type( args[ 0 ] ) is list:
                cmd = args[ 0 ]
            elif type( args[ 0 ] ) is str:
                cmd = args[ 0 ].split()
            else:
                raise Exception( 'rpopen: bad arg type %s' %
                                type( args[ 0 ] ) )
        result = ''
        # local host: use local Popen
        if not self.server:
            return Popen( cmd, **opts )
        # remote host: use ssh and controlPath
        ssh = ['ssh', '-n' ]  # do not read from stdin
        assert self.controlPath
        if self.controlPath:
            ssh += [ '-S', self.controlPath ]
        if sudo:
            cmd = [ 'sudo', '-E' ] + cmd
        cmd = ssh + [ self.dest ] + cmd
        # print 'rpopen', cmd
        popen = Popen( cmd, **opts )
        return popen

    def rcmd( self, *cmd, **opts):
        """rcmd: run a command on underlying server
           in root namespace
           args: string or list of strings
           returns: stdout and stderr"""
        sudo = opts.pop( 'sudo', True )
        popen = self.rpopen( *cmd, sudo=sudo, **opts )
        # These loops are tricky to get right.
        # Once the process exits, we can read
        # EOF twice if necessary.
        result = ''
        while True:
            poll = popen.poll()
            result += popen.stdout.read()
            if poll is not None:
                break
        return result

    def _popen( self, cmd, **params):
        """Spawn a process on a remote node
            cmd: remote command to run (list)
            **params: parameters to Popen()
            returns: Popen() object"""
        cmd = [ 'sudo', '-E' ] + cmd
        if self.user and self.server:
            if self.controlPath:
                cmd = [ 'ssh', '-tt', '-S', self.controlPath,
                        '%s@%s' % ( self.user, self.serverIP ) ] + cmd
            else:
                raise Exception( 'NO CONTROL PATH TO %s:%s' % (
                 self.name, self.serverIP ) )
                cmd = [ 'ssh', '-tt', '%s@%s'
                       % ( self.user, self.serverIP ) ] + cmd
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
    OVSVersions = {}
    def isOldOVS( self ):
        "Is remote switch using an old OVS version?"
        cls = type( self )
        if self.server not in cls.OVSVersions:
            info = self.cmd( 'ovs-vsctl --version' )
            cls.OVSVersions[ self.server ] =  re.findall( '\d+\.\d+', info )[ 0 ]
        return ( StrictVersion( cls.OVSVersions[ self.server ] ) <
                StrictVersion( '1.10' ) )


# RemoteController should really be renamed ExternalController
class RController( RemoteMixin, Controller ):
    "Remote instance of Controller()"
    def start( self, *args, **kwargs ):
        "Start and update IP address"
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

    @staticmethod
    def remoteMoveIntf( intf, node, printError=True ):
        """Move remote interface from root ns to node
            intf: string, interface
            dstNode: destination Node
            srcNode: source Node or None (default) for root ns
            printError: if true, print error"""
        intf = str( intf )
        cmd = 'ip link set %s netns %s' % ( intf, node.pid )
        node.rcmd( cmd )
        links = node.cmd( 'ip link show' )
        if not ( ' %s:' % intf ) in links:
            if printError:
                error( '*** Error: remoteMoveIntf: ' + intf +
                      ' not successfully moved to ' + node.name + '\n' )
            return False
        return True
    
    def makeTunnel( self, intfname1, intfname2, node1, node2 ):
        "Make a tunnel across switches on different servers"
        # 1. Create tap interfaces
        for node in node1, node2:
            # For now we are hard-wiring tap9, which we will rename
            node.rcmd( 'ip link delete tap9', stderr=PIPE )
            cmd = 'ip tuntap add dev tap9 mode tap user ' + node.user
            node.rcmd( cmd )
            links = node.rcmd( 'ip link show' )
            # print 'after add, links =', links
            assert 'tap9' in links
        # 2. Create ssh tunnel between tap interfaces
        # -n: close stdin
        dest = '%s@%s' % ( node2.user, node2.serverIP )
        cmd = [ 'ssh', '-n', '-o', 'Tunnel=Ethernet', '-w', '9:9',
                dest, 'echo @' ]
        self.cmd = cmd
        tunnel = node1.rpopen( cmd, sudo=False )
        # When we receive the character '@', it means that our
        # tunnel should be set up
        debug( 'Waiting for tunnel to come up...\n' )
        ch = tunnel.stdout.read( 1 )
        if ch != '@':
            error( 'makeTunnel:\n',
                   'Tunnel setup failed for',
                   '%s:%s' % ( node1, node1.dest ), 'to', 
                   '%s:%s\n' % ( node2, node2.dest ),
                  'command was:', cmd, '\n' )
            tunnel.terminate()
            tunnel.wait()
            error( ch + tunnel.stdout.read() )
            error( tunnel.stderr.read() )
            exit( 1 )
        # 3. Move interfaces if necessary
        for node in node1, node2:
            if node.inNamespace:
                retry( 3, .01, RemoteLink.remoteMoveIntf, 'tap9', node )
        # 4. Rename tap interfaces to desired names
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
                 switches=None, controllers=None, links=None ):
        """Initialize placement object
           servers: list of servers
           nodes: list of all nodes
           hosts: list of hosts
           switches: list of switches
           controllers: list of controllers
           links: list of links
           (all arguments are optional)
           returns: server"""
        self.servers = servers or []
        self.nodes = nodes or []
        self.hosts = hosts or []
        self.switches = switches or []
        self.controllers = controllers or []
        self.links = links or []

    def place( self, node ):
        "Return server for a given node"
        # Default placement: run locally
        return None


class RandomPlacer( Placer ):
    "Random placement"
    def place( self, nodename ):
        """Random placement function
            nodename: node name"""
        # This may be slow with lots of servers
        return self.servers[ randrange( 0, len( self.servers ) ) ]


class RoundRobinPlacer( Placer ):
    """Round-robin placement
       Note this will usually result in cross-server links between
       hosts and switches"""
    
    def __init__( self, *args, **kwargs ):
        Placer.__init__( self, *args, **kwargs )
        self.next = 0

    def place( self, nodename ):
        """Round-robin placement function
            nodename: node name"""
        # This may be slow with lots of servers
        server = self.servers[ self.next ]
        self.next = ( self.next + 1 ) % len( self.servers )
        return server



class SwitchBinPlacer( Placer ):
    """Place switches (and controllers) into evenly-sized bins,
       and attempt to co-locate hosts and switches"""

    def __init__( self, *args, **kwargs ):
        Placer.__init__( self, *args, **kwargs )
        # Easy lookup for servers and node sets
        self.servdict = dict( enumerate( self.servers ) )
        self.hset = frozenset( self.hosts )
        self.sset = frozenset( self.switches )
        self.cset = frozenset( self.controllers )
        # Server and switch placement indices
        self.placement =  self.calculatePlacement()

    @staticmethod
    def bin( nodes, servers ):
        "Distribute nodes evenly over servers"
        # Calculate base bin size
        nlen = len( nodes )
        slen = len( servers )
        # Basic bin size
        quotient = int( nlen / slen )
        binsizes = { server: quotient for server in servers }
        # Distribute remainder
        remainder = nlen % slen
        for server in servers[ 0 : remainder ]:
            binsizes[ server ] += 1
        # Create binsize[ server ] tickets for each server
        tickets = sum( [ binsizes[ server ] * [ server ]
                         for server in servers ], [] )
        # And assign one ticket to each node
        return { node: ticket for node, ticket in zip( nodes, tickets ) }

    def calculatePlacement( self ):
        "Pre-calculate node placement"
        placement = {}
        # Create host-switch connectivity map,
        # associating host with last switch that it's
        # connected to
        switchFor = {}
        for src, dst in self.links:
            if src in self.hset and dst in self.sset:
                switchFor[ src ] = dst
            if dst in self.hset and src in self.sset:
                switchFor[ dst ] = src
        # Place switches
        placement = self.bin( self.switches, self.servers )
        # Place controllers and merge into placement dict
        placement.update( self.bin( self.controllers, self.servers ) )
        # Co-locate hosts with their switches
        for h in self.hosts:
            if h in placement:
                # Host is already placed - leave it there
                continue
            if h in switchFor:
                placement[ h ] = placement[ switchFor[ h ] ]
            else:
                raise Exception(
                        "SwitchBinPlacer: cannot place isolated host " + h )
        return placement

    def place( self, node ):
        """Simple placement algorithm:
           place switches into evenly sized bins,
           and place hosts near their switches"""
        return self.placement[ node ]


class HostSwitchBinPlacer( Placer ):
    """Place switches *and hosts* into evenly-sized bins
       Note that this will usually result in cross-server
       links between hosts and switches"""

    def __init__( self, *args, **kwargs ):
        Placer.__init__( self, *args, **kwargs )
        # Calculate bin sizes
        scount = len( self.servers )
        self.hbin = max( int( len( self.hosts ) / scount ), 1 )
        self.sbin = max( int( len( self.switches ) / scount ), 1 )
        self.cbin = max( int( len( self.controllers ) / scount ) , 1 )
        info( 'scount:', scount )
        info( 'bins:', self.hbin, self.sbin, self.cbin, '\n' )
        self.servdict = dict( enumerate( self.servers ) )
        self.hset = frozenset( self.hosts )
        self.sset = frozenset( self.switches )
        self.cset = frozenset( self.controllers )
        self.hind, self.sind, self.cind = 0, 0, 0
    
    def place( self, nodename ):
        """Simple placement algorithm:
            place nodes into evenly sized bins"""
        # Place nodes into bins
        if nodename in self.hset:
            server = self.servdict[ self.hind / self.hbin ]
            self.hind += 1
        elif nodename in self.sset:
            server = self.servdict[ self.sind / self.sbin ]
            self.sind += 1
        elif nodename in self.cset:
            server = self.servdict[ self.cind / self.cbin ]
            self.cind += 1
        else:
            info( 'warning: unknown node', nodename )
            server = self.servdict[ 0 ]
        return server



# The MininetCluster class is not strictly necessary.
# However, it has several purposes:
# 1. To set up ssh connection sharing/multiplexing
# 2. To pre-flight the system so that everything is more likely to work
# 3. To allow connection/connectivity monitoring
# 4. To support pluggable placement algorithms

class MininetCluster( Mininet ):

    "Cluster-enhanced version of Mininet class"

    # Default ssh command
    # BatchMode yes: don't ask for password
    # ForwardAgent yes: forward authentication credentials
    sshcmd = [ 'ssh', '-o', 'BatchMode yes', '-o', 'ForwardAgent yes' ]

    def __init__( self, *args, **kwargs ):
        """servers: a list of servers to use (note: include
           localhost or None to use local system as well)
           user: user name for server ssh
           placement: Placer() subclass"""
        params = { 'host': RemoteHost,
                   'switch': RemoteOVSSwitch,
                   'controller': RController,
                   'link': RemoteLink,
                   'precheck': True }
        params.update( kwargs )
        servers = params.pop( 'servers', [] )
        servers = [ s if s != 'localhost' else None for s in servers ]
        self.servers = servers
        self.serverIP = params.pop( 'serverIP', {} )
        if not self.serverIP:
            self.serverIP = { server: RemoteMixin.findServerIP( server )
                              for server in self.servers }
        self.user = params.pop( 'user', None )
        if self.servers and not self.user:
            self.user = quietRun( 'who am i' ).split()[ 0 ]
        if params.pop( 'precheck' ):
            self.precheck()
        self.connections = {}
        self.placement = params.pop( 'placement', SwitchBinPlacer )
        # Make sure control directory exists
        self.cdir = os.environ[ 'HOME' ] + '/.ssh/mn'
        errRun( [ 'mkdir', '-p', self.cdir ] )
        Mininet.__init__( self, *args, **params )

    def popen( self, cmd ):
        "Popen() for server connections"
        old = signal( SIGINT, SIG_IGN )
        conn = Popen( cmd, stdout=PIPE, close_fds=True )
        signal( SIGINT, old )
        return conn

    def baddLink( self, *args, **kwargs ):
        "break addlink for testing"
        pass

    def precheck( self ):
        """Pre-check to make sure connection works and that
           we can call sudo without a password"""
        result = 0
        info( '*** Checking servers\n' )
        for server in self.servers:
            ip = self.serverIP[ server ]
            if not server:
                server = 'localhost'
            info( server, '' )
            dest = '%s@%s' % ( self.user, ip )
            cmd = self.sshcmd + [ '-n', dest, 'sudo true' ]
            out, err, code = errRun( cmd )
            if code != 0:
                error( '\nstartConnection: server connection check failed '
                       'to %s using command:\n%s\n'
                        % ( server, cmd ) )
            result |= code
        if result:
            error( '*** Precheck failed - please fix the errors reported above.\n'
                   '*** You may need to run mn -c on all nodes; also make\n'
                   '*** sure you are using sudo -E and that you can ssh into all\n'
                   '*** nodes and run sudo without entering a password.\n' )
            exit( 1 )
        info( '\n' )

    def startConnection( self, server1=None, server2=None ):
        """Start a master ssh connection between node1 and node2,
           on one of their servers (lowest alphabetically)
           and add it to our list of connections
           (wait for 'OK' before it actually starts up)
           returns: user@ip, control path, connection or None"""
        if server1 == server2:
            # No connection is required
            return
        # Use a canonical order
        # Note that None will end up as server1
        server1, server2 = sorted( ( server1, server2 ) )
        dest2 = '%s@%s' % ( self.user, self.serverIP[ server2 ] )
        cfile2 = '%s/%s-%s' % ( self.cdir, server1, server2 )
        # Create new master ssh connection
        cmd = self.sshcmd + [ '-n', '-o', 'ControlPersist=yes',
               '-M', '-S', cfile2,
               dest2, 'echo OK' ]
        if server1:
            # Create remote connection
            # We MUST have an existing connection to server1
            dest1, cfile1, _conn = self.connections[ ( None, server1 ) ]
            ssh = [ 'ssh', '-n', '-S', cfile1, dest1 ]
            cmd = ssh + cmd
        # Create and return connection
        conn2 = self.popen( cmd )
        return dest2, cfile2, conn2
    
    def waitConnected( _self, conns ):
        "Wait for a specific ssh connection to start up"
        for _dest, _cfile, conn in conns:
            assert conn.stdout.read( 2 ) == 'OK'
            info( '.' )

    def modifiedaddHost( self, *args, **kwargs ):
        "Slightly modify addHost"
        kwargs[ 'splitInit' ] = True
        return Mininet.addHost( *args, **kwargs )

    def startConnections( self ):
        "Initialize master ssh connections to servers"
        # Create ssh master connections
        conns = []
        for server in self.servers:
            if not server:
                continue
            key = ( None, server )
            if key not in self.connections:
                info( server, '' )
                conn = self.startConnection( *key )
                self.connections[ key ] = conn
                conns.append( conn )
        self.waitConnected( conns )
        info( '\n' )

    def startLinkConnections( self ):
        "Create control connections for server pairs"
        links = self.topo.links()
        conns = []
        for link in links:
            node1, node2 = link
            # Server pair for link
            server1, server2 = [
                self.topo.node_info[ n ][ 'server' ] for n in node1, node2 ]
            server1, server2 = sorted( ( server1, server2 ) )
            key = ( server1, server2 )
            if server1 != server2 and key not in self.connections:
                # Create a new control connection
                info( '(%s,%s)' % ( server1, server2 ) )
                conn = self.startConnection( *key )
                self.connections[ key ] = conn
                conns.append( conn )
        self.waitConnected( conns )

    def stopConnections( self ):
        for dest, cfile, conn in self.connections.values():
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
                                 switches=self.topo.switches(),
                                 links=self.topo.links() )
        for node in nodes:
            config = self.topo.node_info[ node ]
            server = config.setdefault( 'server', placer.place( node ) )
            if server:
                config.setdefault( 'serverIP', self.serverIP[ server ] )
            info( '%s:%s ' % ( node, server ) )
            key = ( None, server )
            _dest, cfile, _conn = self.connections.get(
                        key, ( None, None, None ) )
            if cfile:
                config.setdefault( 'controlPath', cfile )

    def buildFromTopo( self, *args, **kwargs ):
        "Start network"
        info( '*** Starting server connections\n' )
        self.startConnections()
        info( '\n' )
        info( '*** Placing nodes\n' )
        self.placeNodes()
        info( '\n' )
        info( '*** Starting link connections\n' )
        self.startLinkConnections()
        info( '\n' )
        Mininet.buildFromTopo( self, *args, **kwargs )

    def stop( self ):
        "Stop network"
        Mininet.stop( self )
        info( '*** Stopping server connections\n' )
        self.stopConnections()


def testNsTunnels():
    "Test tunnels between nodes in namespaces"
    net = Mininet( host=RemoteHost, link=RemoteLink )
    h1 = net.addHost( 'h1' )
    h2 = net.addHost( 'h2', server='ubuntu12' )
    net.addLink( h1, h2 )
    net.start()
    net.pingAll()
    net.stop()

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

# Need to test backwards placement, where each host is on
# a server other than its switch!! But seriously we could just
# do random switch placement rather than completely random
# host placement.

def testRemoteSwitches():
    "Test with local hosts and remote switches"
    servers = [ 'localhost', 'ubuntu12']
    topo = TreeTopo( depth=4, fanout=2 )
    net = MininetCluster( topo=topo, servers=servers,
                          placement=RoundRobinPlacer )
    net.start()
    net.pingAll()
    net.stop()


#
# For testing and demo purposes it would be nice to draw the
# network graph and color it based on server.

# The MininetCluster() class integrates pluggable placement
# functions, for maximum ease of use. MininetCluster() also
# pre-flights and multiplexes server connections.

def testMininetCluster():
    "Test MininetCluster()"
    servers = [ 'localhost', 'ubuntu2' ]
    topo = TreeTopo( depth=3, fanout=3 )
    net = MininetCluster( topo=topo, servers=servers,
                          placement=SwitchBinPlacer )
    net.start()
    net.pingAll()
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    # testRemoteTopo()
    # testRemoteNet()
    testMininetCluster()
    # testRemoteSwitches()


