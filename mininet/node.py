"""
Node objects for Mininet.

Nodes provide a simple abstraction for interacting with hosts, switches
and controllers. Local nodes are simply one or more processes on the local
machine.

Node: superclass for all (primarily local) network nodes.

Host: a virtual host. By default, a host is simply a shell; commands
    may be sent using Cmd (which waits for output), or using sendCmd(),
    which returns immediately, allowing subsequent monitoring using
    monitor(). Examples of how to run experiments using this
    functionality are provided in the examples/ directory.

Switch: superclass for switch nodes.

UserSwitch: a switch using the user-space switch from the OpenFlow
    reference implementation.

KernelSwitch: a switch using the kernel switch from the OpenFlow reference
    implementation.

OVSSwitch: a switch using the OpenVSwitch OpenFlow-compatible switch
    implementation (openvswitch.org).

Controller: superclass for OpenFlow controllers. The default controller
    is controller(8) from the reference implementation.

NOXController: a controller node using NOX (noxrepo.org).

RemoteController: a remote controller node, which may use any
    arbitrary OpenFlow-compatible controller, and which is not
    created or managed by mininet.

Future enhancements:

- Possibly make Node, Switch and Controller more abstract so that
  they can be used for both local and remote nodes

- Create proxy objects for remote nodes (Mininet: Cluster Edition)
"""

import os
import re
import signal
import select
from subprocess import Popen, PIPE, STDOUT
from time import sleep

from mininet.log import info, error, debug
from mininet.util import quietRun, makeIntfPair, moveIntf, isShellBuiltin
from mininet.moduledeps import moduleDeps, pathCheck, OVS_KMOD, OF_KMOD, TUN

SWITCH_PORT_BASE = 1  # For OF > 0.9, switch ports start at 1 rather than zero

class Node( object ):
    """A virtual network node is simply a shell in a network namespace.
       We communicate with it using pipes."""

    inToNode = {}  # mapping of input fds to nodes
    outToNode = {}  # mapping of output fds to nodes

    portBase = 0  # Nodes always start with eth0/port0, even in OF 1.0

    def __init__( self, name, inNamespace=True,
        defaultMAC=None, defaultIP=None, **kwargs ):
        """name: name of node
           inNamespace: in network namespace?
           defaultMAC: default MAC address for intf 0
           defaultIP: default IP address for intf 0"""
        self.name = name
        self.inNamespace = inNamespace
        self.defaultIP = defaultIP
        self.defaultMAC = defaultMAC
        opts = '-cdp'
        if self.inNamespace:
            opts += 'n'
        cmd = [ 'mnexec', opts, 'bash', '-m' ]
        self.shell = Popen( cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT,
            close_fds=False )
        self.stdin = self.shell.stdin
        self.stdout = self.shell.stdout
        self.pid = self.shell.pid
        self.pollOut = select.poll()
        self.pollOut.register( self.stdout )
        # Maintain mapping between file descriptors and nodes
        # This is useful for monitoring multiple nodes
        # using select.poll()
        self.outToNode[ self.stdout.fileno() ] = self
        self.inToNode[ self.stdin.fileno() ] = self
        self.intfs = {}  # dict of port numbers to interface names
        self.ports = {}  # dict of interface names to port numbers
                         # replace with Port objects, eventually ?
        self.ips = {}  # dict of interfaces to ip addresses as strings
        self.macs = {}  # dict of interfacesto mac addresses as strings
        self.connection = {}  # remote node connected to each interface
        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''
        self.waiting = False
        # Stash additional information as desired
        self.args = kwargs

    @classmethod
    def fdToNode( cls, fd ):
        """Return node corresponding to given file descriptor.
           fd: file descriptor
           returns: node"""
        node = Node.outToNode.get( fd )
        return node or Node.inToNode.get( fd )

    def cleanup( self ):
        "Help python collect its garbage."
        self.shell = None

    # Subshell I/O, commands and control
    def read( self, bytes=1024 ):
        """Buffered read from node, non-blocking.
           bytes: maximum number of bytes to return"""
        count = len( self.readbuf )
        if count < bytes:
            data = os.read( self.stdout.fileno(), bytes - count )
            self.readbuf += data
        if bytes >= len( self.readbuf ):
            result = self.readbuf
            self.readbuf = ''
        else:
            result = self.readbuf[ :bytes ]
            self.readbuf = self.readbuf[ bytes: ]
        return result

    def readline( self ):
        """Buffered readline from node, non-blocking.
           returns: line (minus newline) or None"""
        self.readbuf += self.read( 1024 )
        if '\n' not in self.readbuf:
            return None
        pos = self.readbuf.find( '\n' )
        line = self.readbuf[ 0 : pos ]
        self.readbuf = self.readbuf[ pos + 1: ]
        return line

    def write( self, data ):
        """Write data to node.
           data: string"""
        os.write( self.stdin.fileno(), data )

    def terminate( self ):
        "Send kill signal to Node and clean up after it."
        os.kill( self.pid, signal.SIGKILL )
        self.cleanup()

    def stop( self ):
        "Stop node."
        self.terminate()

    def waitReadable( self, timeoutms=None ):
        """Wait until node's output is readable.
           timeoutms: timeout in ms or None to wait indefinitely."""
        if len( self.readbuf ) == 0:
            self.pollOut.poll( timeoutms )

    def sendCmd( self, *args, **kwargs ):
        """Send a command, followed by a command to echo a sentinel,
           and return without waiting for the command to complete.
           args: command and arguments, or string
           printPid: print command's PID?"""
        assert not self.waiting
        printPid = kwargs.get( 'printPid', True )
        if len( args ) > 0:
            cmd = args
        if not isinstance( cmd, str ):
            cmd = ' '.join( cmd )
        if not re.search( r'\w', cmd ):
            # Replace empty commands with something harmless
            cmd = 'echo -n'
        if len( cmd ) > 0 and cmd[ -1 ] == '&':
            separator = '&'
            cmd = cmd[ :-1 ]
        else:
            separator = ';'
            if printPid and not isShellBuiltin( cmd ):
                cmd = 'mnexec -p ' + cmd
        self.write( cmd + separator + ' printf "\\177" \n' )
        self.lastCmd = cmd
        self.lastPid = None
        self.waiting = True

    def sendInt( self, sig=signal.SIGINT ):
        "Interrupt running command."
        if self.lastPid:
            try:
                os.kill( self.lastPid, sig )
            except OSError:
                pass

    def monitor( self, timeoutms=None ):
        """Monitor and return the output of a command.
           Set self.waiting to False if command has completed.
           timeoutms: timeout in ms or None to wait indefinitely."""
        self.waitReadable( timeoutms )
        data = self.read( 1024 )
        # Look for PID
        marker = chr( 1 ) + r'\d+\n'
        if chr( 1 ) in data:
            markers = re.findall( marker, data )
            if markers:
                self.lastPid = int( markers[ 0 ][ 1: ] )
                data = re.sub( marker, '', data )
        # Look for sentinel/EOF
        if len( data ) > 0 and data[ -1 ] == chr( 127 ):
            self.waiting = False
            data = data[ :-1 ]
        elif chr( 127 ) in data:
            self.waiting = False
            data = data.replace( chr( 127 ), '' )
        return data

    def waitOutput( self, verbose=False ):
        """Wait for a command to complete.
           Completion is signaled by a sentinel character, ASCII(127)
           appearing in the output stream.  Wait for the sentinel and return
           the output, including trailing newline.
           verbose: print output interactively"""
        log = info if verbose else debug
        output = ''
        while self.waiting:
            data = self.monitor()
            output += data
            log( data )
        return output

    def cmd( self, *args, **kwargs ):
        """Send a command, wait for output, and return it.
           cmd: string"""
        verbose = kwargs.get( 'verbose', False )
        log = info if verbose else debug
        log( '*** %s : %s\n' % ( self.name, args ) )
        self.sendCmd( *args, **kwargs )
        return self.waitOutput( verbose )

    def cmdPrint( self, *args):
        """Call cmd and printing its output
           cmd: string"""
        return self.cmd( *args, **{ 'verbose': True } )

    # Interface management, configuration, and routing

    # BL notes: This might be a bit redundant or over-complicated.
    # However, it does allow a bit of specialization, including
    # changing the canonical interface names. It's also tricky since
    # the real interfaces are created as veth pairs, so we can't
    # make a single interface at a time.

    def intfName( self, n ):
        "Construct a canonical interface name node-ethN for interface n."
        return self.name + '-eth' + repr( n )

    def newPort( self ):
        "Return the next port number to allocate."
        if len( self.ports ) > 0:
            return max( self.ports.values() ) + 1
        return self.portBase

    def addIntf( self, intf, port=None ):
        """Add an interface.
           intf: interface name (e.g. nodeN-ethM)
           port: port number (optional, typically OpenFlow port number)"""
        if port is None:
            port = self.newPort()
        self.intfs[ port ] = intf
        self.ports[ intf ] = port
        #info( '\n' )
        #info( 'added intf %s:%d to node %s\n' % ( intf,port, self.name ) )
        if self.inNamespace:
            #info( 'moving w/inNamespace set\n' )
            moveIntf( intf, self )

    def registerIntf( self, intf, dstNode, dstIntf ):
        "Register connection of intf to dstIntf on dstNode."
        self.connection[ intf ] = ( dstNode, dstIntf )

    def connectionsTo( self, node):
        "Return [(srcIntf, dstIntf)..] for connections to dstNode."
        # We could optimize this if it is important
        connections = []
        for intf in self.connection.keys():
            dstNode, dstIntf = self.connection[ intf ]
            if dstNode == node:
                connections.append( ( intf, dstIntf ) )
        return connections

    # This is a symmetric operation, but it makes sense to put
    # the code here since it is tightly coupled to routines in
    # this class. For a more symmetric API, you can use
    # mininet.util.createLink()

    def linkTo( self, node2, port1=None, port2=None ):
        """Create link to another node, making two new interfaces.
           node2: Node to link us to
           port1: our port number (optional)
           port2: node2 port number (optional)
           returns: intf1 name, intf2 name"""
        node1 = self
        if port1 is None:
            port1 = node1.newPort()
        if port2 is None:
            port2 = node2.newPort()
        intf1 = node1.intfName( port1 )
        intf2 = node2.intfName( port2 )
        makeIntfPair( intf1, intf2 )
        node1.addIntf( intf1, port1 )
        node2.addIntf( intf2, port2 )
        node1.registerIntf( intf1, node2, intf2 )
        node2.registerIntf( intf2, node1, intf1 )
        return intf1, intf2

    def deleteIntfs( self ):
        "Delete all of our interfaces."
        # In theory the interfaces should go away after we shut down.
        # However, this takes time, so we're better off removing them
        # explicitly so that we won't get errors if we run before they
        # have been removed by the kernel. Unfortunately this is very slow,
        # at least with Linux kernels before 2.6.33
        for intf in self.intfs.values():
            quietRun( 'ip link del ' + intf )
            info( '.' )
            # Does it help to sleep to let things run?
            sleep( 0.001 )

    def setMAC( self, intf, mac ):
        """Set the MAC address for an interface.
           mac: MAC address as string"""
        result = self.cmd( 'ifconfig', intf, 'down' )
        result += self.cmd( 'ifconfig', intf, 'hw', 'ether', mac )
        result += self.cmd( 'ifconfig', intf, 'up' )
        return result

    def setARP( self, ip, mac ):
        """Add an ARP entry.
           ip: IP address as string
           mac: MAC address as string"""
        result = self.cmd( 'arp', '-s', ip, mac )
        return result

    def setIP( self, intf, ip, prefixLen=8 ):
        """Set the IP address for an interface.
           intf: interface name
           ip: IP address as a string
           prefixLen: prefix length, e.g. 8 for /8 or 16M addrs"""
        ipSub = '%s/%d' % ( ip, prefixLen )
        result = self.cmd( 'ifconfig', intf, ipSub, 'up' )
        self.ips[ intf ] = ip
        return result

    def setHostRoute( self, ip, intf ):
        """Add route to host.
           ip: IP address as dotted decimal
           intf: string, interface name"""
        return self.cmd( 'route add -host ' + ip + ' dev ' + intf )

    def setDefaultRoute( self, intf ):
        """Set the default route to go through intf.
           intf: string, interface name"""
        self.cmd( 'ip route flush root 0/0' )
        return self.cmd( 'route add default ' + intf )

    def defaultIntf( self ):
        "Return interface for lowest port"
        ports = self.intfs.keys()
        if ports:
            return self.intfs[ min( ports ) ]

    _ipMatchRegex = re.compile( r'\d+\.\d+\.\d+\.\d+' )
    _macMatchRegex = re.compile( r'..:..:..:..:..:..' )

    def IP( self, intf=None ):
        "Return IP address of a node or specific interface."
        if intf is None:
            intf = self.defaultIntf()
        if intf and not self.waiting:
            self.updateIP( intf )
        return self.ips.get( intf, None )

    def MAC( self, intf=None ):
        "Return MAC address of a node or specific interface."
        if intf is None:
            intf = self.defaultIntf()
        if intf and not self.waiting:
            self.updateMAC( intf )
        return self.macs.get( intf, None )

    def updateIP( self, intf ):
        "Update IP address for an interface"
        assert not self.waiting
        ifconfig = self.cmd( 'ifconfig ' + intf )
        ips = self._ipMatchRegex.findall( ifconfig )
        if ips:
            self.ips[ intf ] = ips[ 0 ]
        else:
            self.ips[ intf ] = None

    def updateMAC( self, intf ):
        "Update MAC address for an interface"
        assert not self.waiting
        ifconfig = self.cmd( 'ifconfig ' + intf )
        macs = self._macMatchRegex.findall( ifconfig )
        if macs:
            self.macs[ intf ] = macs[ 0 ]
        else:
            self.macs[ intf ] = None

    def intfIsUp( self, intf ):
        "Check if an interface is up."
        return 'UP' in self.cmd( 'ifconfig ' + intf )

    # Other methods
    def __str__( self ):
        intfs = sorted( self.intfs.values() )
        return '%s: IP=%s intfs=%s pid=%s' % (
            self.name, self.IP(), ','.join( intfs ), self.pid )


class Host( Node ):
    "A host is simply a Node."


class Switch( Node ):
    """A Switch is a Node that is running (or has execed?)
       an OpenFlow switch."""

    portBase = SWITCH_PORT_BASE  # 0 for OF < 1.0, 1 for OF >= 1.0

    def __init__( self, name, opts='', listenPort=None, **kwargs):
        Node.__init__( self, name, **kwargs )
        self.opts = opts
        self.listenPort = listenPort
        if self.listenPort:
            self.opts += ' --listen=ptcp:%i ' % self.listenPort

    def defaultIntf( self ):
        "Return interface for HIGHEST port"
        ports = self.intfs.keys()
        if ports:
            intf = self.intfs[ max( ports ) ]
        return intf

    def sendCmd( self, *cmd, **kwargs ):
        """Send command to Node.
           cmd: string"""
        kwargs.setdefault( 'printPid', False )
        if not self.execed:
            return Node.sendCmd( self, *cmd, **kwargs )
        else:
            error( '*** Error: %s has execed and cannot accept commands' %
                     self.name )

class UserSwitch( Switch ):
    "User-space switch."

    def __init__( self, name, **kwargs ):
        """Init.
           name: name for the switch"""
        Switch.__init__( self, name, **kwargs )
        pathCheck( 'ofdatapath', 'ofprotocol',
            moduleName='the OpenFlow reference user switch (openflow.org)' )

    @staticmethod
    def setup():
        "Ensure any dependencies are loaded; if not, try to load them."
        if not os.path.exists( '/dev/net/tun' ):
            moduleDeps( add=TUN )

    def start( self, controllers ):
        """Start OpenFlow reference user datapath.
           Log to /tmp/sN-{ofd,ofp}.log.
           controllers: list of controller objects"""
        controller = controllers[ 0 ]
        ofdlog = '/tmp/' + self.name + '-ofd.log'
        ofplog = '/tmp/' + self.name + '-ofp.log'
        self.cmd( 'ifconfig lo up' )
        mac_str = ''
        if self.defaultMAC:
            # ofdatapath expects a string of hex digits with no colons.
            mac_str = ' -d ' + ''.join( self.defaultMAC.split( ':' ) )
        intfs = sorted( self.intfs.values() )
        if self.inNamespace:
            intfs = intfs[ :-1 ]
        self.cmd( 'ofdatapath -i ' + ','.join( intfs ) +
            ' punix:/tmp/' + self.name + mac_str + ' --no-slicing ' +
            ' 1> ' + ofdlog + ' 2> ' + ofdlog + ' &' )
        self.cmd( 'ofprotocol unix:/tmp/' + self.name +
            ' tcp:%s:%d' % ( controller.IP(), controller.port ) +
            ' --fail=closed ' + self.opts +
            ' 1> ' + ofplog + ' 2>' + ofplog + ' &' )

    def stop( self ):
        "Stop OpenFlow reference user datapath."
        self.cmd( 'kill %ofdatapath' )
        self.cmd( 'kill %ofprotocol' )
        self.deleteIntfs()

class KernelSwitch( Switch ):
    """Kernel-space switch.
       Currently only works in root namespace."""

    def __init__( self, name, dp=None, **kwargs ):
        """Init.
           name: name for switch
           dp: netlink id (0, 1, 2, ...)
           defaultMAC: default MAC as string; random value if None"""
        Switch.__init__( self, name, **kwargs )
        self.dp = 'nl:%i' % dp
        self.intf = 'of%i' % dp
        if self.inNamespace:
            error( "KernelSwitch currently only works"
                " in the root namespace." )
            exit( 1 )

    @staticmethod
    def setup():
        "Ensure any dependencies are loaded; if not, try to load them."
        pathCheck( 'ofprotocol',
            moduleName='the OpenFlow reference kernel switch'
            ' (openflow.org) (NOTE: not available in OpenFlow 1.0!)' )
        moduleDeps( subtract=OVS_KMOD, add=OF_KMOD )

    def start( self, controllers ):
        "Start up reference kernel datapath."
        ofplog = '/tmp/' + self.name + '-ofp.log'
        quietRun( 'ifconfig lo up' )
        # Delete local datapath if it exists;
        # then create a new one monitoring the given interfaces
        quietRun( 'dpctl deldp ' + self.dp )
        self.cmd( 'dpctl adddp ' + self.dp )
        if self.defaultMAC:
            self.cmd( 'ifconfig', self.intf, 'hw', 'ether', self.defaultMAC )
        ports = sorted( self.ports.values() )
        if len( ports ) != ports[ -1 ] + 1 - self.portBase:
            raise Exception( 'only contiguous, zero-indexed port ranges'
                            'supported: %s' % ports )
        intfs = [ self.intfs[ port ] for port in ports ]
        self.cmd( 'dpctl', 'addif', self.dp, ' '.join( intfs ) )
        # Run protocol daemon
        controller = controllers[ 0 ]
        self.cmd( 'ofprotocol ' + self.dp +
            ' tcp:%s:%d' % ( controller.IP(), controller.port ) +
            ' --fail=closed ' + self.opts +
            ' 1> ' + ofplog + ' 2>' + ofplog + ' &' )
        self.execed = False

    def stop( self ):
        "Terminate kernel datapath."
        quietRun( 'dpctl deldp ' + self.dp )
        self.cmd( 'kill %ofprotocol' )
        self.deleteIntfs()


class OVSKernelSwitch( Switch ):
    """Open VSwitch kernel-space switch.
       Currently only works in the root namespace."""

    def __init__( self, name, dp=None, **kwargs ):
        """Init.
           name: name for switch
           dp: netlink id (0, 1, 2, ...)
           defaultMAC: default MAC as unsigned int; random value if None"""
        Switch.__init__( self, name, **kwargs )
        self.dp = 'dp%i' % dp
        self.intf = self.dp
        if self.inNamespace:
            error( "OVSKernelSwitch currently only works"
                " in the root namespace.\n" )
            exit( 1 )

    @staticmethod
    def setup():
        "Ensure any dependencies are loaded; if not, try to load them."
        pathCheck( 'ovs-dpctl', 'ovs-openflowd',
            moduleName='Open vSwitch (openvswitch.org)')
        moduleDeps( subtract=OF_KMOD, add=OVS_KMOD )

    def start( self, controllers ):
        "Start up kernel datapath."
        ofplog = '/tmp/' + self.name + '-ofp.log'
        quietRun( 'ifconfig lo up' )
        # Delete local datapath if it exists;
        # then create a new one monitoring the given interfaces
        quietRun( 'ovs-dpctl del-dp ' + self.dp )
        self.cmd( 'ovs-dpctl add-dp ' + self.dp )
        mac_str = ''
        if self.defaultMAC:
            # ovs-openflowd expects a string of exactly 16 hex digits with no
            # colons.
            mac_str = ' --datapath-id=0000' + \
                      ''.join( self.defaultMAC.split( ':' ) ) + ' '
        ports = sorted( self.ports.values() )
        if len( ports ) != ports[ -1 ] + 1 - self.portBase:
            raise Exception( 'only contiguous, one-indexed port ranges '
                            'supported: %s' % self.intfs )
        intfs = [ self.intfs[ port ] for port in ports ]
        self.cmd( 'ovs-dpctl', 'add-if', self.dp, ' '.join( intfs ) )
        # Run protocol daemon
        controller = controllers[ 0 ]
        self.cmd( 'ovs-openflowd ' + self.dp +
            ' tcp:%s:%d' % ( controller.IP(), controller.port ) +
            ' --fail=secure ' + self.opts + mac_str +
            ' 1>' + ofplog + ' 2>' + ofplog + '&' )
        self.execed = False

    def stop( self ):
        "Terminate kernel datapath."
        quietRun( 'ovs-dpctl del-dp ' + self.dp )
        self.cmd( 'kill %ovs-openflowd' )
        self.deleteIntfs()


class Controller( Node ):
    """A Controller is a Node that is running (or has execed?) an
       OpenFlow controller."""

    def __init__( self, name, inNamespace=False, command='controller',
                 cargs='-v ptcp:%d', cdir=None, defaultIP="127.0.0.1",
                 port=6633 ):
        self.command = command
        self.cargs = cargs
        self.cdir = cdir
        self.port = port
        Node.__init__( self, name, inNamespace=inNamespace,
            defaultIP=defaultIP )

    def start( self ):
        """Start <controller> <args> on controller.
           Log to /tmp/cN.log"""
        pathCheck( self.command )
        cout = '/tmp/' + self.name + '.log'
        if self.cdir is not None:
            self.cmd( 'cd ' + self.cdir )
        self.cmd( self.command + ' ' + self.cargs % self.port +
            ' 1>' + cout + ' 2>' + cout + '&' )
        self.execed = False

    def stop( self ):
        "Stop controller."
        self.cmd( 'kill %' + self.command )
        self.terminate()

    def IP( self, intf=None ):
        "Return IP address of the Controller"
        ip = Node.IP( self, intf=intf )
        if ip is None:
            ip = self.defaultIP
        return ip

class ControllerParams( object ):
    "Container for controller IP parameters."

    def __init__( self, ip, prefixLen ):
        """Init.
           ip: string, controller IP address
           prefixLen: prefix length, e.g. 8 for /8, covering 16M"""
        self.ip = ip
        self.prefixLen = prefixLen


class NOX( Controller ):
    "Controller to run a NOX application."

    def __init__( self, name, noxArgs=None, **kwargs ):
        """Init.
           name: name to give controller
           noxArgs: list of args, or single arg, to pass to NOX"""
        if not noxArgs:
            noxArgs = [ 'packetdump' ]
        elif type( noxArgs ) != list:
            noxArgs = [ noxArgs ]

        if 'NOX_CORE_DIR' not in os.environ:
            exit( 'exiting; please set missing NOX_CORE_DIR env var' )
        noxCoreDir = os.environ[ 'NOX_CORE_DIR' ]

        Controller.__init__( self, name,
            command=noxCoreDir + '/nox_core',
            cargs='--libdir=/usr/local/lib -v -i ptcp:%s ' +
                    ' '.join( noxArgs ),
            cdir=noxCoreDir, **kwargs )


class RemoteController( Controller ):
    "Controller running outside of Mininet's control."

    def __init__( self, name, defaultIP='127.0.0.1',
                 port=6633, **kwargs):
        """Init.
           name: name to give controller
           defaultIP: the IP address where the remote controller is
           listening
           port: the port where the remote controller is listening"""
        Controller.__init__( self, name, defaultIP=defaultIP, port=port,
            **kwargs )

    def start( self ):
        "Overridden to do nothing."
        return

    def stop( self ):
        "Overridden to do nothing."
        return
