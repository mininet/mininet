#!/usr/bin/env python

"""
cluster.py: prototyping/experimentation for distributed Mininet,
            aka Mininet: Cluster Edition

Author: Bob Lantz

Core classes:

    RemoteNode: a Node() running on a remote server
    RemoteOVSSwitch(): an OVSSwitch() running on a remote server
    RemoteLink: a Link() on a remote server
    Tunnel: a Link() between a local Node() and a RemoteNode()

These are largely interoperable with local objects.

- One Mininet to rule them all

It is important that the same topologies, APIs, and CLI can be used
with minimal or no modification in both local and distributed environments.

- Multiple placement models

Placement should be as easy as possible. We should provide basic placement
support and also allow for explicit placement.

Questions:

What is the basic communication mechanism?

To start with? Probably a single multiplexed ssh connection between each
pair of mininet servers that needs to communicate.

How are tunnels created?

We have several options including ssh, GRE, OF capsulator, socat, VDE, l2tp,
etc..  It's not clear what the best one is.  For now, we use ssh tunnels since
they are encrypted and semi-automatically shared.  We will probably want to
support GRE as well because it's very easy to set up with OVS.

How are tunnels destroyed?

They are destroyed when the links are deleted in Mininet.stop()

How does RemoteNode.popen() work?

It opens a shared ssh connection to the remote server and attaches to
the namespace using mnexec -a -g.

Is there any value to using Paramiko vs. raw ssh?

Maybe, but it doesn't seem to support L2 tunneling.

Should we preflight the entire network, including all server-to-server
connections?

Yes! We don't yet do this with remote server-to-server connections yet.

Should we multiplex the link ssh connections?

Yes, this is done automatically with ControlMaster=auto.

Note on ssh and DNS:
Please add UseDNS: no to your /etc/ssh/sshd_config!!!

Things to do:

- asynchronous/pipelined/parallel startup
- ssh debugging/profiling
- make connections into real objects
- support for other tunneling schemes
- tests and benchmarks
- hifi support (e.g. delay compensation)
"""

from signal import signal, SIGINT, SIG_IGN
from subprocess import Popen, PIPE, STDOUT
import os
from random import randrange
import sys
import re
from itertools import groupby
from operator import attrgetter

from mininet.node import Node, Host, OVSSwitch, Controller
from mininet.link import Link, Intf
from mininet.net import Mininet
from mininet.topo import LinearTopo
from mininet.topolib import TreeTopo
from mininet.util import quietRun, errRun, decode, StrictVersion
from mininet.examples.clustercli import CLI
from mininet.log import setLogLevel, debug, info, error
from mininet.clean import addCleanupCallback

# pylint: disable=too-many-arguments


def findUser():
    "Try to return logged-in (usually non-root) user"
    return (
            # If we're running sudo
            os.environ.get( 'SUDO_USER', False ) or
            # Logged-in user (if we have a tty)
            ( quietRun( 'who am i' ).split() or [ False ] )[ 0 ] or
            # Give up and return effective user
            quietRun( 'whoami' ).strip() )


class ClusterCleanup( object ):
    "Cleanup callback"

    inited = False
    serveruser = {}

    @classmethod
    def add( cls, server, user='' ):
        "Add an entry to server: user dict"
        if not cls.inited:
            addCleanupCallback( cls.cleanup )
        if not user:
            user = findUser()
        cls.serveruser[ server ] = user

    @classmethod
    def cleanup( cls ):
        "Clean up"
        info( '*** Cleaning up cluster\n' )
        for server, user in cls.serveruser.items():
            if server == 'localhost':
                # Handled by mininet.clean.cleanup()
                continue
            else:
                cmd = [ 'su', user, '-c',
                        'ssh %s@%s sudo mn -c' % ( user, server ) ]
                info( cmd, '\n' )
                info( quietRun( cmd ) )

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
    # -q: don't print stupid diagnostic messages
    # BatchMode yes: don't ask for password
    # ForwardAgent yes: forward authentication credentials
    sshbase = [ 'ssh', '-q',
                '-o', 'BatchMode=yes',
                '-o', 'ForwardAgent=yes', '-tt' ]

    def __init__( self, name, server='localhost', user=None, serverIP=None,
                  controlPath=False, splitInit=False, **kwargs):
        """Instantiate a remote node
           name: name of remote node
           server: remote server (optional)
           user: user on remote server (optional)
           controlPath: specify shared ssh control path (optional)
           splitInit: split initialization?
           **kwargs: see Node()"""
        # We connect to servers by IP address
        self.server = server if server else 'localhost'
        self.serverIP = ( serverIP if serverIP
                          else self.findServerIP( self.server ) )
        self.user = user if user else findUser()
        ClusterCleanup.add( server=server, user=user )
        if controlPath is True:
            # Set a default control path for shared SSH connections
            controlPath = '/tmp/mn-%r@%h:%p'
        self.controlPath = controlPath
        self.splitInit = splitInit
        if self.user and self.server != 'localhost':
            self.dest = '%s@%s' % ( self.user, self.serverIP )
            self.sshcmd = [ 'sudo', '-E', '-u', self.user ] + self.sshbase
            if self.controlPath:
                self.sshcmd += [ '-o', 'ControlPath=' + self.controlPath,
                                 '-o', 'ControlMaster=auto',
                                 '-o', 'ControlPersist=' + '1' ]
            self.sshcmd += [ self.dest ]
            self.isRemote = True
        else:
            self.dest = None
            self.sshcmd = []
            self.isRemote = False
        # Satisfy pylint
        self.shell, self.pid = None, None
        super( RemoteMixin, self ).__init__( name, **kwargs )

    # Determine IP address of local host
    _ipMatchRegex = re.compile( r'\d+\.\d+\.\d+\.\d+' )

    @classmethod
    def findServerIP( cls, server ):
        "Return our server's IP address"
        # First, check for an IP address
        ipmatch = cls._ipMatchRegex.findall( server )
        if ipmatch:
            return ipmatch[ 0 ]
        # Otherwise, look up remote server
        output = quietRun( 'getent ahostsv4 %s' % server )
        ips = cls._ipMatchRegex.findall( output )
        ip = ips[ 0 ] if ips else None
        return ip

    # Command support via shell process in namespace
    def startShell( self, *args, **kwargs ):
        "Start a shell process for running commands"
        if self.isRemote:
            kwargs.update( mnopts='-c' )
        super( RemoteMixin, self ).startShell( *args, **kwargs )
        # Optional split initialization
        self.sendCmd( 'echo $$' )
        if not self.splitInit:
            self.finishInit()

    def finishInit( self ):
        "Wait for split initialization to complete"
        self.pid = int( self.waitOutput() )

    def rpopen( self, *cmd, **opts ):
        "Return a Popen object on underlying server in root namespace"
        params = { 'stdin': PIPE,
                   'stdout': PIPE,
                   'stderr': STDOUT,
                   'sudo': True }
        params.update( opts )
        return self._popen( *cmd, **params )

    def rcmd( self, *cmd, **opts):
        """rcmd: run a command on underlying server
           in root namespace
           args: string or list of strings
           returns: stdout and stderr"""
        popen = self.rpopen( *cmd, **opts )
        # info( 'RCMD: POPEN:', popen, '\n' )
        # These loops are tricky to get right.
        # Once the process exits, we can read
        # EOF twice if necessary.
        result = ''
        while True:
            poll = popen.poll()
            result += decode( popen.stdout.read() )
            if poll is not None:
                break
        return result

    @staticmethod
    def _ignoreSignal():
        "Detach from process group to ignore all signals"
        os.setpgrp()

    def _popen( self, cmd, sudo=True, tt=True, **params):
        """Spawn a process on a remote node
            cmd: remote command to run (list)
            **params: parameters to Popen()
            returns: Popen() object"""
        if isinstance( cmd, str):
            cmd = cmd.split()
        if self.isRemote:
            if sudo:
                cmd = [ 'sudo', '-E' ] + cmd
            if tt:
                cmd = self.sshcmd + cmd
            else:
                # Hack: remove -tt
                sshcmd = list( self.sshcmd )
                sshcmd.remove( '-tt' )
                cmd = sshcmd + cmd
        else:
            if self.user and not sudo:
                # Drop privileges
                cmd = [ 'sudo', '-E', '-u', self.user ] + cmd
        params.update( preexec_fn=self._ignoreSignal )
        debug( '_popen', cmd, '\n' )
        popen = super( RemoteMixin, self )._popen( cmd, **params )
        return popen

    def popen( self, *args, **kwargs ):
        "Override: disable -tt"
        return super( RemoteMixin, self).popen( *args, tt=False, **kwargs )

    def addIntf( self, *args, **kwargs ):
        "Override: use RemoteLink.moveIntf"
        # kwargs.update( moveIntfFn=RemoteLink.moveIntf )
        # pylint: disable=useless-super-delegation
        return super( RemoteMixin, self).addIntf( *args, **kwargs )


class RemoteNode( RemoteMixin, Node ):
    "A node on a remote server"
    pass


class RemoteHost( RemoteNode ):
    "A RemoteHost is simply a RemoteNode"
    pass


class RemoteOVSSwitch( RemoteMixin, OVSSwitch ):
    "Remote instance of Open vSwitch"

    OVSVersions = {}

    def __init__( self, *args, **kwargs ):
        # No batch startup yet
        kwargs.update( batch=True )
        super( RemoteOVSSwitch, self ).__init__( *args, **kwargs )

    def isOldOVS( self ):  # pylint: disable=arguments-differ
        "Is remote switch using an old OVS version?"
        cls = type( self )
        if self.server not in cls.OVSVersions:
            # pylint: disable=not-callable
            vers = self.cmd( 'ovs-vsctl --version' )
            # pylint: enable=not-callable
            cls.OVSVersions[ self.server ] = re.findall(
                r'\d+\.\d+', vers )[ 0 ]
        return ( StrictVersion( cls.OVSVersions[ self.server ] ) <
                 StrictVersion( '1.10' ) )

    @classmethod
    # pylint: disable=arguments-differ
    def batchStartup( cls, switches, **_kwargs ):
        "Start up switches in per-server batches"
        key = attrgetter( 'server' )
        for server, switchGroup in groupby( sorted( switches, key=key ), key ):
            info( '(%s)' % server )
            group = tuple( switchGroup )
            switch = group[ 0 ]
            OVSSwitch.batchStartup( group, run=switch.cmd )
        return switches

    @classmethod
    # pylint: disable=arguments-differ
    def batchShutdown( cls, switches, **_kwargs ):
        "Stop switches in per-server batches"
        key = attrgetter( 'server' )
        for server, switchGroup in groupby( sorted( switches, key=key ), key ):
            info( '(%s)' % server )
            group = tuple( switchGroup )
            switch = group[ 0 ]
            OVSSwitch.batchShutdown( group, run=switch.rcmd )
        return switches


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
        self.cmd = None  # satisfy pylint
        Link.__init__( self, node1, node2, **kwargs )

    def stop( self ):
        "Stop this link"
        if self.tunnel:
            self.tunnel.terminate()
            self.intf1.delete()
            self.intf2.delete()
        else:
            Link.stop( self )
        self.tunnel = None

    def makeIntfPair( self,  # pylint: disable=arguments-renamed
                      intfname1, intfname2, addr1=None, addr2=None,
                      node1=None, node2=None, deleteIntfs=True ):
        """Create pair of interfaces
            intfname1: name of interface 1
            intfname2: name of interface 2
            (override this method [and possibly delete()]
            to change link type)"""
        node1 = self.node1 if node1 is None else node1
        node2 = self.node2 if node2 is None else node2
        server1 = getattr( node1, 'server', 'localhost' )
        server2 = getattr( node2, 'server', 'localhost' )
        if server1 == server2:
            # Link within same server
            return Link.makeIntfPair( intfname1, intfname2, addr1, addr2,
                                      node1, node2, deleteIntfs=deleteIntfs )
        # Otherwise, make a tunnel
        self.tunnel = self.makeTunnel( node1, node2, intfname1, intfname2,
                                       addr1, addr2 )
        return self.tunnel

    @staticmethod
    def moveIntf( intf, node ):
        """Move remote interface from root ns to node
            intf: string, interface
            dstNode: destination Node
            srcNode: source Node or None (default) for root ns"""
        intf = str( intf )
        cmd = 'ip link set %s netns %s' % ( intf, node.pid )
        result = node.rcmd( cmd )
        if result:
            raise Exception('error executing command %s' % cmd)
        return True

    def makeTunnel( self, node1, node2, intfname1, intfname2,
                    addr1=None, addr2=None ):
        "Make a tunnel across switches on different servers"
        # We should never try to create a tunnel to ourselves!
        assert node1.server != node2.server
        # And we can't ssh into this server remotely as 'localhost',
        # so try again swappping node1 and node2
        if node2.server == 'localhost':
            return self.makeTunnel( node1=node2, node2=node1,
                                    intfname1=intfname2, intfname2=intfname1,
                                    addr1=addr2, addr2=addr1 )
        debug( '\n*** Make SSH tunnel ' + node1.server + ':' + intfname1 +
               ' == ' + node2.server + ':' + intfname2 )
        # 1. Create tap interfaces
        for node in node1, node2:
            # For now we are hard-wiring tap9, which we will rename
            cmd = 'ip tuntap add dev tap9 mode tap user ' + node.user
            result = node.rcmd( cmd )
            if result:
                raise Exception( 'error creating tap9 on %s: %s' %
                                 ( node, result ) )
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
        ch = decode( tunnel.stdout.read( 1 ) )
        if ch != '@':
            ch += decode( tunnel.stdout.read() )
            cmd = ' '.join( cmd )
            raise Exception( 'makeTunnel:\n'
                             'Tunnel setup failed for '
                             '%s:%s' % ( node1, node1.dest ) + ' to '
                             '%s:%s\n' % ( node2, node2.dest ) +
                             'command was: %s' % cmd + '\n' +
                             'result was: ' + ch )
        # 3. Move interfaces if necessary
        for node in node1, node2:
            if not self.moveIntf( 'tap9', node ):
                raise Exception( 'interface move failed on node %s' % node )
        # 4. Rename tap interfaces to desired names
        for node, intf, addr in ( ( node1, intfname1, addr1 ),
                                  ( node2, intfname2, addr2 ) ):
            if not addr:
                result = node.cmd( 'ip link set tap9 name', intf )
            else:
                result = node.cmd( 'ip link set tap9 name', intf,
                                   'address', addr )
            if result:
                raise Exception( 'error renaming %s: %s' % ( intf, result ) )
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
        result = "%s %s" % ( Link.status( self ), status )
        return result


class RemoteSSHLink( RemoteLink ):
    "Remote link using SSH tunnels"
    def __init__(self, node1, node2, **kwargs):
        RemoteLink.__init__( self, node1, node2, **kwargs )


class RemoteGRELink( RemoteLink ):
    "Remote link using GRE tunnels"

    GRE_KEY = 0

    def __init__(self, node1, node2, **kwargs):
        RemoteLink.__init__( self, node1, node2, **kwargs )

    def stop( self ):
        "Stop this link"
        if self.tunnel:
            self.intf1.delete()
            self.intf2.delete()
        else:
            Link.stop( self )
        self.tunnel = None

    def makeIntfPair( self, intfname1, intfname2, addr1=None, addr2=None,
                      node1=None, node2=None, deleteIntfs=True   ):
        """Create pair of interfaces
            intfname1: name of interface 1
            intfname2: name of interface 2
            (override this method [and possibly delete()]
            to change link type)"""
        node1 = self.node1 if node1 is None else node1
        node2 = self.node2 if node2 is None else node2
        server1 = getattr( node1, 'server', 'localhost' )
        server2 = getattr( node2, 'server', 'localhost' )
        if server1 == server2:
            # Link within same server
            Link.makeIntfPair( intfname1, intfname2, addr1, addr2,
                               node1, node2, deleteIntfs=deleteIntfs )
            # Need to reduce the MTU of all emulated hosts to 1450 for GRE
            # tunneling, otherwise packets larger than 1400 bytes cannot be
            # successfully transmitted through the tunnel.
            node1.cmd('ip link set dev %s mtu 1450' % intfname1)
            node2.cmd('ip link set dev %s mtu 1450' % intfname2)
        else:
            # Otherwise, make a tunnel
            self.makeTunnel( node1, node2, intfname1, intfname2, addr1, addr2 )
            self.tunnel = 1

    def makeTunnel(self, node1, node2, intfname1, intfname2,
                       addr1=None, addr2=None):
        "Make a tunnel across switches on different servers"
        # We should never try to create a tunnel to ourselves!
        assert node1.server != node2.server
        if node2.server == 'localhost':
            return self.makeTunnel( node1=node2, node2=node1,
                                    intfname1=intfname2, intfname2=intfname1,
                                    addr1=addr2, addr2=addr1 )
        IP1, IP2 = node1.serverIP, node2.serverIP
        # GRE tunnel needs to be set up with the IP of the local interface
        # that connects the remote node, NOT '127.0.0.1' of localhost
        if node1.server == 'localhost':
            output = quietRun('ip route get %s' % node2.serverIP)
            IP1 = output.split(' src ')[1].split()[0]
        debug( '\n*** Make GRE tunnel ' + node1.server + ':' + intfname1 +
               ' == ' + node2.server + ':' + intfname2 )
        tun1 = 'local ' + IP1 + ' remote ' + IP2
        tun2 = 'local ' + IP2 + ' remote ' + IP1
        self.__class__.GRE_KEY += 1
        for (node, intfname, addr, tun) in [(node1, intfname1, addr1, tun1),
                                            (node2, intfname2, addr2, tun2)]:
            node.rcmd('ip link delete ' + intfname)
            result = node.rcmd('ip link add name ' + intfname + ' type gretap '
                               + tun + ' ttl 64 key '
                               + str( self.__class__.GRE_KEY) )
            if result:
                raise Exception('error creating gretap on %s: %s'
                                % (node, result))
            if addr:
                node.rcmd('ip link set %s address %s' % (intfname, addr))

            node.rcmd('ip link set dev %s up' % intfname)
            node.rcmd('ip link set dev %s mtu 1450' % intfname)
            if not self.moveIntf(intfname, node):
                raise Exception('interface move failed on node %s' % node)
        return None  # May want to return something useful here


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
        assert self, node  # satisfy pylint
        # Default placement: run locally
        return 'localhost'


class RandomPlacer( Placer ):
    "Random placement"
    def place( self, node ):
        """Random placement function
            node: node"""
        assert node  # please pylint
        # This may be slow with lots of servers
        return self.servers[ randrange( 0, len( self.servers ) ) ]


class RoundRobinPlacer( Placer ):
    """Round-robin placement
       Note this will usually result in cross-server links between
       hosts and switches"""

    def __init__( self, *args, **kwargs ):
        Placer.__init__( self, *args, **kwargs )
        self.next = 0

    def place( self, node ):
        """Round-robin placement function
            node: node"""
        assert node  # please pylint
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
        self.placement = self.calculatePlacement()

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
        return dict( zip( nodes, tickets ) )

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
        self.cbin = max( int( len( self.controllers ) / scount ), 1 )
        info( 'scount:', scount )
        info( 'bins:', self.hbin, self.sbin, self.cbin, '\n' )
        self.servdict = dict( enumerate( self.servers ) )
        self.hset = frozenset( self.hosts )
        self.sset = frozenset( self.switches )
        self.cset = frozenset( self.controllers )
        self.hind, self.sind, self.cind = 0, 0, 0

    def place( self, node ):
        """Simple placement algorithm:
            place nodes into evenly sized bins"""
        # Place nodes into bins
        if node in self.hset:
            server = self.servdict[ self.hind / self.hbin ]
            self.hind += 1
        elif node in self.sset:
            server = self.servdict[ self.sind / self.sbin ]
            self.sind += 1
        elif node in self.cset:
            server = self.servdict[ self.cind / self.cbin ]
            self.cind += 1
        else:
            info( 'warning: unknown node', node )
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
    sshcmd = [ 'ssh', '-o', 'BatchMode=yes', '-o', 'ForwardAgent=yes' ]

    def __init__( self, *args, **kwargs ):
        """servers: a list of servers to use (note: include
           localhost or None to use local system as well)
           user: user name for server ssh
           placement: Placer() subclass"""
        params = { 'host': RemoteHost,
                   'switch': RemoteOVSSwitch,
                   'link': RemoteLink,
                   'precheck': True }
        params.update( kwargs )
        servers = params.pop( 'servers', [ 'localhost' ] )
        servers = [ s if s else 'localhost' for s in servers ]
        self.servers = servers
        self.serverIP = params.pop( 'serverIP', {} )
        if not self.serverIP:
            self.serverIP = { server: RemoteMixin.findServerIP( server )
                              for server in self.servers }
        self.user = params.pop( 'user', findUser() )
        if params.pop( 'precheck' ):
            self.precheck()
        self.connections = {}
        self.placement = params.pop( 'placement', SwitchBinPlacer )
        # Make sure control directory exists
        self.cdir = os.environ[ 'HOME' ] + '/.ssh/mn'
        errRun( [ 'mkdir', '-p', self.cdir ] )
        # pylint: disable=unexpected-keyword-arg
        Mininet.__init__( self, *args, **params )

    def popen( self, cmd ):
        "Popen() for server connections"
        assert self  # please pylint
        old = signal( SIGINT, SIG_IGN )
        # pylint: disable=consider-using-with
        conn = Popen( cmd, stdin=PIPE, stdout=PIPE, close_fds=True )
        # pylint: enable=consider-using-with
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
            if not server or server == 'localhost':
                continue
            info( server, '' )
            dest = '%s@%s' % ( self.user, ip )
            cmd = [ 'sudo', '-E', '-u', self.user ]
            cmd += self.sshcmd + [ '-n', dest, 'sudo true' ]
            debug( ' '.join( cmd ), '\n' )
            _out, _err, code = errRun( cmd )
            if code != 0:
                error( '\nstartConnection: server connection check failed '
                       'to %s using command:\n%s\n'
                        % ( server, ' '.join( cmd ) ) )
            result |= code
        if result:
            error( '*** Server precheck failed.\n'
                   '*** Make sure that the above ssh command works'
                   ' correctly.\n'
                   '*** You may also need to run mn -c on all nodes, and/or\n'
                   '*** use sudo -E.\n' )
            sys.exit( 1 )
        info( '\n' )

    def modifiedaddHost( self, *args, **kwargs ):
        "Slightly modify addHost"
        assert self  # please pylint
        kwargs[ 'splitInit' ] = True
        return Mininet.addHost( *args, **kwargs )

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
            config = self.topo.nodeInfo( node )
            # keep local server name consistent accross nodes
            if 'server' in config.keys() and config[ 'server' ] is None:
                config[ 'server' ] = 'localhost'
            server = config.setdefault( 'server', placer.place( node ) )
            if server:
                config.setdefault( 'serverIP', self.serverIP[ server ] )
            info( '%s:%s ' % ( node, server ) )
            key = ( None, server )
            _dest, cfile, _conn = self.connections.get(
                        key, ( None, None, None ) )
            if cfile:
                config.setdefault( 'controlPath', cfile )

    @staticmethod
    def isLoopback( ipaddr ):
        "Is ipaddr an IPv4 loopback address?"
        return ipaddr.startswith( '127.' )

    # pylint: disable=arguments-differ,signature-differs
    def addController( self, *args, **kwargs ):
        "Patch to update IP address to global IP address"
        controller = Mininet.addController( self, *args, **kwargs )
        controllerIP = controller.IP()
        if ( not isinstance( controller, Controller ) or
             not self.isLoopback( controller.IP() ) ):
            return controller
        # Find route to a different server IP address
        serverIPs = [ ip for ip in self.serverIP.values()
                      if ip != controllerIP ]
        if not serverIPs:
            return None  # no remote servers - loopback is fine
        for remoteIP in serverIPs:
            # Route should contain 'dev <intfname>'
            route = controller.cmd( 'ip route get', remoteIP,
                                    r'| egrep -o "dev\s[^[:space:]]+"' )
            if not route:
                raise Exception('addController: no route from', controller,
                                'to', remoteIP )
            intf = route.split()[ 1 ].strip()
            if intf != 'lo':
                break
        if intf == 'lo':
            raise Exception( 'addController: could not find external '
                             'interface/IP for %s' % controller )
        debug( 'adding', intf, 'to', controller )
        Intf( intf, node=controller ).updateIP()
        debug( controller, 'IP address updated to', controller.IP() )
        return controller

    # pylint: disable=arguments-differ,signature-differs
    def buildFromTopo( self, *args, **kwargs ):
        "Start network"
        info( '*** Placing nodes\n' )
        self.placeNodes()
        info( '\n' )
        Mininet.buildFromTopo( self, *args, **kwargs )


# Default remote server for tests
remoteServer = 'ubuntu2'

def testNsTunnels( remote=remoteServer, link=RemoteGRELink ):
    "Test tunnels between nodes in namespaces"
    net = Mininet( host=RemoteHost, link=link, waitConnected=True )
    h1 = net.addHost( 'h1')
    h2 = net.addHost( 'h2', server=remote )
    net.addLink( h1, h2 )
    net.start()
    net.pingAll()
    net.stop()

# Manual topology creation with net.add*()
#
# This shows how node options may be used to manage
# cluster placement using the net.add*() API

def testRemoteNet( remote=remoteServer, link=RemoteGRELink ):
    "Test remote Node classes"
    info( '*** Remote Node Test\n' )
    net = Mininet( host=RemoteHost, switch=RemoteOVSSwitch,
                   link=link, controller=ClusterController,
                   waitConnected=True )
    c0 = net.addController( 'c0' )
    # Make sure controller knows its non-loopback address
    info( "*** Creating local h1\n" )
    h1 = net.addHost( 'h1' )
    info( "*** Creating remote h2\n" )
    h2 = net.addHost( 'h2', server=remote )
    info( "*** Creating local s1\n" )
    s1 = net.addSwitch( 's1' )
    info( "*** Creating remote s2\n" )
    s2 = net.addSwitch( 's2', server=remote )
    info( "*** Adding links\n" )
    net.addLink( h1, s1 )
    net.addLink( s1, s2 )
    net.addLink( h2, s2 )
    net.start()
    info( 'Mininet is running on', quietRun( 'hostname' ).strip(), '\n' )
    for node in c0, h1, h2, s1, s2:
        info( 'Node', node, 'is running on',
              node.cmd( 'hostname' ).strip(), '\n' )
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
        return RemoteOVSSwitch( name, *args, **params )

def ClusterController( *args, **kwargs):
    "Custom Controller() constructor which updates its intf IP address"
    intf = kwargs.pop( 'intf', '' )
    controller = Controller( *args, **kwargs )
    # Find out its IP address so that cluster switches can connect
    if not intf:
        output = controller.cmd(
            r"ip a | egrep -o '\w+:\s\w+'" ).split( '\n' )
        for line in output:
            intf = line.split()[ -1 ]
            if intf != 'lo':
                break
        if intf == 'lo':
            raise Exception( 'Could not find non-loopback interface'
                             'for %s' % controller )
    Intf( intf, node=controller ).updateIP()
    return controller

def testRemoteTopo( link=RemoteGRELink ):
    "Test remote Node classes using Mininet()/Topo() API"
    topo = LinearTopo( 2 )
    net = Mininet( topo=topo, host=HostPlacer, switch=SwitchPlacer,
                   link=link, controller=ClusterController )
    net.start()
    net.pingAll()
    net.stop()

# Need to test backwards placement, where each host is on
# a server other than its switch!! But seriously we could just
# do random switch placement rather than completely random
# host placement.

def testRemoteSwitches( remote=remoteServer, link=RemoteGRELink ):
    "Test with local hosts and remote switches"
    servers = [ 'localhost', remote]
    topo = TreeTopo( depth=4, fanout=2 )
    net = MininetCluster( topo=topo, servers=servers, link=link,
                          placement=RoundRobinPlacer )
    net.start()
    net.pingAll()
    net.stop()


# For testing and demo purposes it would be nice to draw the
# network graph and color it based on server.

# The MininetCluster() class integrates pluggable placement
# functions, for maximum ease of use. MininetCluster() also
# pre-flights and multiplexes server connections.

def testMininetCluster( remote=remoteServer, link=RemoteGRELink ):
    "Test MininetCluster()"
    servers = [ 'localhost', remote ]
    topo = TreeTopo( depth=3, fanout=3 )
    net = MininetCluster( topo=topo, servers=servers, link=link,
                          placement=SwitchBinPlacer )
    net.start()
    net.pingAll()
    net.stop()

def signalTest( remote=remoteServer):
    "Make sure hosts are robust to signals"
    h = RemoteHost( 'h0', server=remote )
    h.shell.send_signal( SIGINT )
    h.shell.poll()
    if h.shell.returncode is None:
        info( 'signalTest: SUCCESS: ', h, 'has not exited after SIGINT', '\n' )
    else:
        info( 'signalTest: FAILURE:', h, 'exited with code',
              h.shell.returncode, '\n' )
    h.stop()


if __name__ == '__main__':
    setLogLevel( 'info' )
    remoteLink = RemoteSSHLink
    testRemoteTopo(link=remoteLink)
    testNsTunnels( remote=remoteServer, link=remoteLink )
    testRemoteNet( remote=remoteServer, link=remoteLink)
    testMininetCluster( remote=remoteServer, link=remoteLink)
    testRemoteSwitches( remote=remoteServer, link=remoteLink)
    signalTest( remote=remoteServer )
