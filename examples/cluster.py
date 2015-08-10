#!/usr/bin/python

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

Yes, it creates fewer processes.

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


-------------------

Cluster TNG:

- paramiko for faster connections and fewer processes
- shared shell switches for faster startup and fewer processes...
- new, possibly lighter-weight tunneling schemes??
- possibly batch link startup!??!?!


"""

from mininet.node import Node, Host, OVSSwitch, Controller
from mininet.link import Link, Intf
from mininet.net import Mininet
from mininet.topo import LinearTopo
from mininet.topolib import TreeTopo
from mininet.util import quietRun, errRun, irange, natural
from mininet.examples.clustercli import ClusterCLI as CLI
from mininet.log import setLogLevel, debug, info, error
from mininet.clean import addCleanupCallback
from mininet.topo import Topo

from signal import signal, SIGINT, SIG_IGN
from subprocess import Popen, PIPE
import os
from random import randrange
from math import ceil
import sys
import re
from itertools import groupby
from operator import attrgetter, itemgetter
from distutils.version import StrictVersion
from types import MethodType
from threading import Thread

# select.select() doesn't work with lots of file descriptors :(
from select import poll, POLLIN, POLLOUT, POLLERR, POLLHUP
import select

def pollSelect( rlist, wlist, xlist, timeout ):
    "Reimplementation of select() using poll()"
    poller = poll()
    for f in rlist:
        poller.register( f, POLLIN )
    for f in wlist:
        poller.register( f, POLLOUT )
    for f in xlist:
        poller.register( f, POLLERR | POLLHUP )
    debug( '*' )  # So we can see when this is called
    fids = poller.poll( timeout )
    result = { fid: events for fid, events in fids }
    r, w, x = [], [], []
    r = [ f for f in rlist
          if ( result.get( f, 0 ) & POLLIN ) or
             ( type( f ) != int and result.get( f.fileno(), 0 ) & POLLIN ) ]
    w = [ f for f in wlist
          if ( result.get( f, 0 ) & POLLOUT ) or
             ( type( f ) != int and result.get( f.fileno(), 0 ) & POLLOUT ) ]
    x = [ f for f in xlist
          if ( result.get( f, 0 ) & POLLERR ) or
             ( result.get( f, 0 ) & POLLHUP ) or
             ( type( f ) != int and result.get( f.fileno(), 0 ) & POLLERR ) or
             ( type( f ) != int and result.get( f.fileno(), 0 ) & POLLHUP ) ]
    return r, w, x

select.select = pollSelect


SSHClient, AutoAddPolicy, AgentRequestHandler = None, None, None

def importParamiko():
    "Import paramiko on demand"
    global SSHClient, AutoAddPolicy, AgentRequestHandler
    from paramiko.client import SSHClient, AutoAddPolicy
    from paramiko.agent import AgentRequestHandler


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
        for server, user in cls.serveruser.iteritems():
            if server == 'localhost':
                # Handled by mininet.clean.cleanup()
                continue
            else:
                ip = RemoteMixin.findServerIP( server )
                cmd = [ 'sudo', '-u', user,
                        'ssh %s@%s sudo mn -c' % ( user, ip ) ]
                info( cmd, '\n' )
                info( quietRun( cmd, shell=True) )


def argsToCmd( *args, **kwargs ):
    "Convert argument list to command"
    if not isinstance( args[ 0 ], basestring ):
        # Assume args[0] is arg list
        assert len( args ) == 1
        args = args[ 0 ]
    cmd = ' '.join( str( arg ) for arg in args )
    return cmd


class Popenssh( object ):
    "A Popen-like object over an SSH channel"

    # Map of ip address to open SSH connection (paramiko.SSHClient)
    connections = {}
    agents = {}
    channelCount = {}    # count of channels per connection

    def __init__( self, *args, **kwargs ):
        "ip: IP address of remote SSH server"
        server = kwargs.pop( 'server', 'localhost' )
        user = kwargs.pop( 'user' )
        sudo = kwargs.pop( 'sudo', False )
        shell = kwargs.pop( 'shell', False )
        stdin = kwargs.pop( 'stdin', PIPE )
        stdout = kwargs.pop( 'stdout', PIPE )
        stderr = kwargs.pop( 'stderr', PIPE )
        # We can't wire up to other files/descriptors
        assert stdin == stderr == stdout == PIPE
        cmd = argsToCmd( *args )
        if shell:
            cmd = 'bash -c "%s"' % cmd
        if sudo:
            cmd = 'sudo -E %s' % cmd
        self.connection = self.connect( user, server )
        self.stdin, self.stdout, self.stderr = (
            self.connection.exec_command( cmd,
                                          **kwargs ) )
        self.channel = self.stdout.channel
        self.stdin.fileno = self.stdin.channel.fileno
        self.stdout.fileno = self.stdout.channel.fileno
        # self.stdout.channel.setblocking( 0 )
        self.exit_status = None

    # We support a subset of the Popen API, which should be enough
    # for us to get by as far as Mininet is concerned, with minimal
    # code changes!!

    def poll( self ):
        "If channel has exited, set exit_status"
        if self.channel.exit_status_ready():
            self.exit_status = self.channel.recv_exit_status()
        return self.exit_status

    chunkSize = 100

    @classmethod
    def connect( cls, user, server, preallocCount=0 ):
        "Return a (possibly existing) SSHClient connected to ip"
        dest = '%s@%s' % ( user, server )
        if preallocCount:
            count = preallocCount
        else:
            count = cls.channelCount.get( dest , 0 )
            cls.channelCount[ dest ] = count + 1
        key = "%s:%s" % ( dest, count / cls.chunkSize )
        if key in cls.connections:
            return cls.connections[ key ]
        info( key, '' )
        if not SSHClient:
            importParamiko()
        client = SSHClient()
        client.set_missing_host_key_policy( AutoAddPolicy() )
        client.load_system_host_keys()
        keyfile = '%s/.ssh/cluster_key' % os.environ[ 'HOME' ]
        client.connect( server, username=user, key_filename=keyfile )
        agentsession = client.get_transport().open_session()
        agenthandler = AgentRequestHandler( agentsession )
        cls.agents[ key ] = ( agentsession, agenthandler )
        cls.connections[ key ] = client
        return client

    @classmethod
    def stopConnections( cls ):
        for connection in cls.connections.values():
            info( '.' )
            connection.close()

    def communicate( self ):
        "Return stdout, stderr"
        stdout, stderr = '', ''
        poller = poll()
        poller.register( self.channel.fileno(), POLLIN | POLLERR | POLLHUP )
        while True:
            exitcode = self.poll()
            poller.poll()
            while self.channel.recv_ready():
                stdout += self.stdout.read( 1024 )
            while self.channel.recv_stderr_ready():
                stderr += self.stderr.read( 1024 )
            if exitcode is not None:
                break
        return stdout, stderr

    def wait( self ):
        poller = poll()
        poller.register( self.channel.fileno(), POLLIN | POLLERR | POLLHUP )
        while True:
            poller.poll()
            if self.poll() is not None:
                break


    @classmethod
    def prealloc( cls, user, server, count ):
        "Preallocate shared connections to server"
        debug( '*** Preallocating', count, 'connections to', server, '\n' )
        for i in range( 0, count, cls.chunkSize ):
            serverIP = RemoteMixin.findServerIP( server )
            cls.connect( user, serverIP, i )

    @classmethod
    def shutdown( cls ):
        "Shut down all connections"
        for c in cls.connections:
            cls.shutdown()


class RemoteMixin( object ):
    "Experimental RemoteMixin replacement that uses paramiko"

    def __init__( self, name, server='localhost', user=None, serverIP=None,
                  controlPath=True, splitInit=False, **kwargs):
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
        if self.user: #  and self.server != 'localhost':
            self.dest = '%s@%s' % ( self.user, self.serverIP )
        else:
            self.dest = None
            self.sshcmd = []
            self.isRemote = False
        # Satisfy pylint
        self.shell, self.pid = None, None
        super( RemoteMixin, self ).__init__( name, **kwargs )

    # Command support via shell process in namespace
    def startShell( self, mnopts=None ):
        "Start a shell process for running commands"
        if self.shell:
            error( "%s: shell is already running\n" % self.name )
            return
        # mnexec: (c)lose descriptors
        # (p)rint pid, and run in (n)etwork and (m)ount namespace
        opts = '-cp' if mnopts is None else mnopts
        # Handle additional namespaces if specified
        nsmap = { 'pid': 'P', 'mnt': 'm', 'net': 'n', 'uts': 'u' }
        chars = [ nsmap.get( ns, '' ) for ns in self.ns ]
        opts += ''.join( chars )
        # bash -i: force interactive
        # -s: pass $* to shell, and make process easy to find in ps
        # prompt is set to sentinel chr( 127 )
        cmd = [ 'sudo -E', 'mnexec', opts, 'env', 'PS1=' + chr( 127 ),
                'bash', '--norc', '-is', 'mininet:' + self.name ]
        # Spawn a shell subprocess in a pseudo-tty, to disable buffering
        # in the subprocess and insulate it from signals (e.g. SIGINT)
        # received by the parent
        self.shell = Popenssh( cmd, server=self.serverIP, user=self.user,
                               get_pty=True )
        self.stdin = self.shell.stdin
        self.stdout = self.shell.stdout
        self.pollOut = poll()
        self.pollOut.register( self.stdout.fileno() )
        # Maintain mapping between file descriptors and nodes
        # This is useful for monitoring multiple nodes
        # using select.poll()
        self.outToNode[ self.stdout.fileno() ] = self
        self.inToNode[ self.stdin.fileno() ] = self
        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''
        # Wait for prompt
        self.waiting = True
        self.waitOutput()
        # +m: disable job control notification
        out = self.cmd( 'unset HISTFILE; stty -echo; set +m; echo $$' ).split( '\r\n')
        self.pid = int( out[ 1 ] )

    # Subshell I/O, commands and control

    def read( self, maxbytes=1 ):
        """Buffered read from node, non-blocking.
           maxbytes: maximum number of bytes to return"""
        count = len( self.readbuf )
        if count < maxbytes:
            data = self.stdout.channel.recv( maxbytes - count )
            self.readbuf += data
        if maxbytes >= len( self.readbuf ):
            result = self.readbuf
            self.readbuf = ''
        else:
            result = self.readbuf[ :maxbytes ]
            self.readbuf = self.readbuf[ maxbytes: ]
        return result

    def write( self, data ):
        """Write data to node.
           data: string"""
        self.stdin.write( data )

    def waitReadable( self, timeoutms=None ):
        """Wait until node's output is readable.
           timeoutms: timeout in ms or None to wait indefinitely."""
        if len( self.readbuf ) == 0:
            while True:
                self.pollOut.poll( timeoutms )
                if self.stdout.channel.recv_ready():
                    return

    def sendInt( self ):
        "Send interrupt to our process group"
        self.rcmd( 'kill -INT -%d' % self.pid )

    def terminate( self ):
        "Shut down connection?"
        self.stdout.channel.close()
        self.stdout.channel.shutdown( 2 )

    # We'd like to have reusable control connections
    # for setting up tunnels, etc.

    rootNodes = {}  # map of ip to server RemoteNode

    @classmethod
    def rootNode( cls, server ):
        "Return shared node in root namespace for server"
        if server in cls.rootNodes:
            return cls.rootNodes[ server ]
        node = RemoteNode( server, server=server, inNamespace=False )
        cls.rootNodes[ server ] = node
        return node

    # Hmm....

    def rcmd( self, *args, **kwargs ):
        "Run command in root namespace"
        errFail = kwargs.pop( 'errFail', False )
        result = self.rootNode( self.server ).cmd( *args )
        if errFail and result.strip():
            error( 'rcmd returned error:', repr( result ) )
            # raise Exception( result )
        return result

    def _popen( self, *args, **kwargs ):
        kwargs.setdefault( 'sudo', True )
        return Popenssh( *args, server=self.serverIP, user=self.user, **kwargs )

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
        ips = [ ip for ip in ips if not ip.startswith( '127.' ) ]
        ip = ips[ 0 ] if ips else None
        return ip

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

    def isOldOVS( self ):
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

    def startShell( self, *args, **kwargs ):
        "Don't start a shell"
        self.shell = None
        self.root = self.rootNode( self.server )
        self.pid = self.root.pid
        self.stdin = self.root.shell.stdin
        self.stdout = self.root.shell.stdout
        self.stderr = self.root.shell.stderr

    def terminate( self, *args, **kwargs ):
        "Don't kill our pgroup"
        pass


    # This seems like overkill - perhaps we should
    # just modify the CLI!!

    def sendCmd( self, *args, **kwargs ):
        return self.root.sendCmd( *args, **kwargs )

    def monitor( self, *args, **kwargs ):
        return self.root.monitor( *args, **kwargs )

    def cmd( self, *args, **kwargs ):
        "Delegate to root node"
        return self.rcmd( *args, **kwargs )

    @property
    def waiting( self ):
        return self.root.waiting

    @waiting.setter
    def waiting( self, val ):
        pass

    @classmethod
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
    def batchShutdown( cls, switches, **_kwargs ):
        "Stop switches in per-server batches"
        key = attrgetter( 'server' )
        # Don't kill init
        for switch in switches:
            switch.pid = None
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
        # Hack: don't bring up intfs immediately
        kwargs[ 'params1' ].update( up=None )
        kwargs[ 'params2' ].update( up=None )
        super( RemoteLink, self ).__init__( node1, node2, **kwargs )

    def stop( self ):
        "Stop this link"
        if self.tunnel:
            self.node.rcmd( 'kill', self.pids() )
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
        server1 = getattr( node1, 'server' )
        server2 = getattr( node2, 'server' )
        if server1 == server2:
            # Link within same server
            return Link.makeIntfPair( intfname1, intfname2, addr1, addr2,
                                      node1, node2, deleteIntfs=deleteIntfs,
                                      runCmd=node1.rcmd )
        # Otherwise, make a tunnel
        self.tunnel = self.makeTunnel( node1, node2, intfname1, intfname2,
                                       addr1, addr2 )

    tapNum = {}  # map of server to tap interface number
    tapStart = 10

    @classmethod
    def nextTapNum( cls, server ):
        "Return next usable tap interface number for server"
        num = cls.tapNum.get( server, cls.tapStart )
        cls.tapNum[ server] = num + 1
        return num

    def makeTunnel( self, node1, node2, intfname1, intfname2,
                    addr1=None, addr2=None ):
        "Make an SSH tunnel across switches on different servers"
        debug( 'tunnel from', node1.serverIP, 'to', node2.serverIP )
        # Can't use loopback address to tunnel across servers
        assert ( not node1.serverIP.startswith( '127.' ) and
                 not node2.serverIP.startswith( '127.' ) )
        num1 = self.nextTapNum( node1. server )
        num2 = self.nextTapNum( node2.server )
        tap1, tap2 = 'tap%d' % num1, 'tap%d' % num2
        # For concurrency, we only call node1 directly using rcmd,
        # using pexec for node2
        # Second command needs sudo...
        node1.rcmd( 'ip link del', tap1, ' 2> /dev/null;'
                    'sudo ip tuntap add dev', tap1,
                    'mode tap user', node1.user, errFail=True )
        # Second command needs sudo...
        out, err, code = node2.pexec( 'ip link del', tap2, ' 2>  /dev/null;'
                    'sudo ip tuntap add dev', tap2,
                    'mode tap user', node2.user )
        if err:
            error( err )
            return
        # XXX Painful.... it would be nice to avoid sudo here
        self.cmd = ( 'sudo -E -u %s ssh -f -l %s -n -o BatchMode=yes -o Tunnel=Ethernet'
                      ' -w %d:%d %s echo @' %
                     ( node1.user, node2.user, num1, num2, node2.serverIP ) )
        self.node = node1
        # Wait for '@' to appear, signaling tunnel is up
        root = node1.rootNode( node1.server )
        debug( '***', node1.server, self.cmd, '\n' )
        assert not root.waiting
        root.sendCmd( self.cmd )
        while '@' not in root.monitor():
            pass
        root.waitOutput()
        node1.rcmd( 'ip link set', tap1, 'name', intfname1, 'netns', node1.pid,
                     errFail=True )
        out, err, code = node2.pexec( 'ip link set', tap2, 'name', intfname2,
                                      'netns', node2.pid )
        if err:
            error( err )
        return self.cmd

    def pids( self ):
        "Look for tunnel pid(s)"
        out = self.node.rcmd( 'pgrep -f "%s"' % self.cmd ).strip()
        return ' '.join( re.findall( '\d+', out ) )

    def status( self ):
        "Detailed representation of link"
        if self.tunnel:
            pid = self.tunnel.pid()
            if pid:
                status = "Tunnel Running (%s: %s)" % ( self.node, pid )
            else:
                status = "Tunnel Exited (%s)" % self.node
        else:
            status = "Local"
        result = "%s %s" % ( Link.status( self ), status )
        return result


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
    def place( self, nodename ):
        """Random placement function
            nodename: node name"""
        assert nodename  # please pylint
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
        assert nodename  # please pylint
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
        self.cbin = max( int( len( self.controllers ) / scount ), 1 )
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


### Threaded Object Creation

class FunctionThread( Thread ):
    "Parallel functions calls"

    def __init__( self, fn, params ):
        """fn: function to call
           params: list of (*args, **kwargs)"""
        self.fn = fn
        self.params = params
        self.results = []
        Thread.__init__( self )

    def run( self ):
        for args, kwargs in self.params:
            self.results.append( self.fn( *args, **kwargs ) )
            info( '.' )
            sys.stdout.flush()

    @classmethod
    def call( cls, fn, chunks, callback=debug ):
        """Call function on multiple threds
           fn: function to call
           chunks: chunks of (*args, **kwargs) lists"""
        debug( '*** Creating threads\n' )
        threads = [ cls( fn, chunk ) for chunk in chunks ]
        debug( '*** Starting threads\n' )
        for thread in threads:
            thread.start()
        debug( '*** Waiting for thread completion\n' )
        results = []
        for thread in threads:
            thread.join()
            callback( ' '.join( str( obj ) for obj in thread.results ) )
            results += thread.results
        return results


def chunk( items, n ):
    "Divide items into n chunks"
    length = len( items )
    chunksize = int( ceil( float( length ) / n ) )
    return [ items[ i : i + chunksize ] for i in range( 0, length, chunksize ) ]


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
        Mininet.__init__( self, *args, **params )

    def popen( self, cmd ):
        "Popen() for server connections"
        assert self  # please pylint
        old = signal( SIGINT, SIG_IGN )
        conn = Popen( cmd, stdin=PIPE, stdout=PIPE, close_fds=True )
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


    _defaultUser = ''

    @classmethod
    def defaultUser( cls ):
        "Return default user"
        if not cls._defaultUser:
            cls._defaultUser = findUser()
        return cls._defaultUser

    def nodekey( self, node ):
        "Return user@server for node in topo"
        info = self.topo.nodeInfo( node )
        user = info.get( 'user', self.defaultUser() )
        server = info.get( 'server', None )
        return '%s@%s' % ( user, server )

    def nodeiter( self, nodes ):
        "Iterator over groups of nodes on same server"
        nodes = sorted( nodes, key=self.nodekey )
        for dest, nodeGroup in groupby( nodes, key=self.nodekey ):
            yield dest, sorted( nodeGroup, key=natural )

    def linkiter( self, links ):
        "Iterator over groups of links starting on same server"
        def linkkey( link ):
            src, dst, params = link
            return self.nodekey( params[ 'node1' ] )
        links = sorted( links, key=linkkey )
        for dest, serverGroup in groupby( links, linkkey ):
            yield dest, tuple( serverGroup )

    def preallocate( self ):
        "Preallocate rcmd channels so paramiko's select() works!"
        nodes = self.topo.nodes()
        for dest, serverGroup in self.nodeiter( nodes ):
            if dest:
                user, server = dest.split( '@' )  # ah well...
                Popenssh.prealloc( user, server, len( serverGroup ) + 1 )
                RemoteNode.rootNode( server )

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
        serverToNodes = {}
        for node in nodes:
            config = self.topo.nodeInfo( node )
            # keep local server name consistent accross nodes
            if 'server' in config.keys() and config[ 'server' ] is None:
                config[ 'server' ] = 'localhost'
            server = config.setdefault( 'server', placer.place( node ) )
            if server:
                config.setdefault( 'serverIP', self.serverIP[ server ] )
            key = ( None, server )
            _dest, cfile, _conn = self.connections.get(
                        key, ( None, None, None ) )
            if cfile:
                config.setdefault( 'controlPath', cfile )
            serverToNodes.setdefault( server, [] )
            serverToNodes[ server ].append( node )
        for server in sorted( serverToNodes, key=natural ):
            nodes = ' '.join( sorted( serverToNodes[ server ], key=natural ) )
            info( '%s: %s\n' % ( server , nodes) )

    def addController( self, *args, **kwargs ):
        "Patch to update IP address to global IP address"
        controller = Mininet.addController( self, *args, **kwargs )
        # Update IP address for controller that may not be local
        if ( isinstance( controller, Controller )
             and controller.IP() == '127.0.0.1' ):
            links = controller.cmd( 'ip link show' )
            eth0 = re.findall( ' (.*eth0):', links )
            if not eth0:
                raise Exception( 'Cannot find IP address for controller eth0' )
            Intf( eth0[ 0 ], node=controller ).updateIP()
        return controller

    def buildFromTopo( self, topo ):
        "Start network"
        info( '*** Placing nodes\n' )
        self.placeNodes()
        info( '*** Preallocating connections\n' )
        self.preallocate()
        info( '\n' )

        # Normal buildFromTopo follows

        # Possibly we should clean up here and/or validate
        # the topo
        if self.cleanup:
            pass

        info( '*** Creating network\n' )

        if not self.controllers and self.controller:
            # Add a default controller
            info( '*** Adding controller\n' )
            classes = self.controller
            if not isinstance( classes, list ):
                classes = [ classes ]
            for i, cls in enumerate( classes ):
                # Allow Controller objects because nobody understands partial()
                if isinstance( cls, Controller ):
                    self.addController( cls )
                else:
                    self.addController( 'c%d' % i, cls )

        info( '*** Adding hosts:\n' )
        # Thread per server for now...
        chunks = [ [ ( [ name ], topo.nodeInfo( name ) ) for name in group ]
                   for dest, group in self.nodeiter( self.topo.hosts() ) ]
        hosts = FunctionThread.call( self.addHost, chunks )
        self.hosts = sorted( self.hosts, key=natural )

        info( '\n*** Adding switches:\n' )
        for switchName in topo.switches():
            # A bit ugly: add batch parameter if appropriate
            params = topo.nodeInfo( switchName)
            cls = params.get( 'cls', self.switch )
            if hasattr( cls, 'batchStartup' ):
                params.setdefault( 'batch', True )
            self.addSwitch( switchName, **params )
            info( switchName + ' ' )

        # ugly - fix this!
        chunks = [ [ ( [], params ) for src, dst, params in group ]
                  for dest, group in
                  self.linkiter( self.topo.links( withInfo=True) ) ]
        debug( '*** %d chunks\n' % len( chunks ) )
        info( '\n*** Adding links\n' )
        self.links = FunctionThread.call( self.addLink, chunks )

        info( '\n*** HACK: bringing up switch links\n' )
        for switch in self.switches:
            switch.cmd( ';'.join( 'ifconfig %s up' % intf
                                  for intf in switch.intfs.values() ) )
            info( '.' )
        info( '\n' )

    def stop( self ):
        super( MininetCluster, self ).stop()
        info( '*** Stopping connections' )
        Popenssh.stopConnections()
        info( '\n' )

def testNsTunnels():
    "Test tunnels between nodes in namespaces"
    net = Mininet( host=RemoteHost, link=RemoteLink )
    h1 = net.addHost( 'h1' )
    h2 = net.addHost( 'h2', server='ubuntu2' )
    net.addLink( h1, h2 )
    net.start()
    net.pingAll()
    net.stop()

# Manual topology creation with net.add*()
#
# This shows how node options may be used to manage
# cluster placement using the net.add*() API

def testRemoteNet( remote='ubuntu2' ):
    "Test remote Node classes"
    print '*** Remote Node Test'
    net = Mininet( host=RemoteHost, switch=RemoteOVSSwitch,
                   link=RemoteLink )
    c0 = net.addController( 'c0' )
    # Make sure controller knows its non-loopback address
    Intf( 'eth0', node=c0 ).updateIP()
    print "*** Creating local h1"
    h1 = net.addHost( 'h1' )
    print "*** Creating remote h2"
    h2 = net.addHost( 'h2', server=remote )
    print "*** Creating local s1"
    s1 = net.addSwitch( 's1' )
    print "*** Creating remote s2"
    s2 = net.addSwitch( 's2', server=remote )
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
remoteServer = 'ubuntu2'

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
    servers = [ 'localhost', 'ubuntu2']
    topo = TreeTopo( depth=2, fanout=2 )
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
    servers = [ '10.0.1.%d' % i for i in irange( 1, 12 ) ]
    topo = TreeTopo( depth=4, fanout=4 )
    net = MininetCluster( topo=topo, servers=servers,
                          placement=SwitchBinPlacer )
    net.start()
    # net.pingAll()
    CLI( net )
    net.stop()

def signalTest():
    "Make sure hosts are robust to signals"
    h = RemoteHost( 'h0', server='ubuntu1' )
    h.shell.send_signal( SIGINT )
    h.shell.poll()
    if h.shell.returncode is None:
        print 'OK: ', h, 'has not exited'
    else:
        print 'FAILURE:', h, 'exited with code', h.shell.returncode
    h.stop()

# Extremely basic test
def basicTest():
    servers = [ 'localhost' ]
    net = MininetCluster( servers=servers )
    h1 = net.addHost( 'h1', server='localhost' )
    h2 = net.addHost( 'h2', server='ubuntu3' )
    net.addLink( h1, h2 )
    net.start()
    CLI( net )
    net.stop()

def paraTest():
    "How many of these can we make?"
    l = []
    for i in range( 0, 1024 ):
        l.append( Popenssh( 'bash' ) )
        print i,
        sys.stdout.flush()


if __name__ == '__main__':
    setLogLevel( 'info' )
    testMininetCluster()
    # testRemoteTopo()
    # testRemoteNet()
    # testMininetCluster()
    # testRemoteSwitches()
    # signalTest()
