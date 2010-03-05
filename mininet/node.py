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
from mininet.util import quietRun, makeIntfPair, moveIntf

class Node( object ):
    """A virtual network node is simply a shell in a network namespace.
       We communicate with it using pipes."""

    inToNode = {} # mapping of input fds to nodes
    outToNode = {} # mapping of output fds to nodes

    def __init__( self, name, inNamespace=True,
        defaultMAC=None, defaultIP=None ):
        """name: name of node
           inNamespace: in network namespace?
           defaultMAC: default MAC address for intf 0
           defaultIP: default IP address for intf 0"""
        self.name = name
        closeFds = False # speed vs. memory use
        # xpg_echo is needed so we can echo our sentinel in sendCmd
        cmd = [ '/bin/bash', '-O', 'xpg_echo' ]
        self.inNamespace = inNamespace
        if self.inNamespace:
            cmd = [ 'netns' ] + cmd
        self.shell = Popen( cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT,
            close_fds=closeFds )
        self.stdin = self.shell.stdin
        self.stdout = self.shell.stdout
        self.pollOut = select.poll()
        self.pollOut.register( self.stdout )
        # Maintain mapping between file descriptors and nodes
        # This could be useful for monitoring multiple nodes
        # using select.poll()
        self.outToNode[ self.stdout.fileno() ] = self
        self.inToNode[ self.stdin.fileno() ] = self
        self.pid = self.shell.pid
        self.intfs = {} # dict of port numbers to interface names
        self.ports = {} # dict of interface names to port numbers
                        # replace with Port objects, eventually ?
        self.ips = {} # dict of interfaces to ip addresses as strings
        self.connection = {} # remote node connected to each interface
        self.waiting = False
        self.execed = False
        self.defaultIP = defaultIP
        self.defaultMAC = defaultMAC

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
    def read( self, bytes ):
        """Read from a node.
           bytes: maximum number of bytes to read"""
        return os.read( self.stdout.fileno(), bytes )

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

    def waitReadable( self ):
        "Wait until node's output is readable."
        self.pollOut.poll()

    def sendCmd( self, cmd ):
        """Send a command, followed by a command to echo a sentinel,
           and return without waiting for the command to complete."""
        assert not self.waiting
        if cmd[ -1 ] == '&':
            separator = '&'
            cmd = cmd[ :-1 ]
        else:
            separator = ';'
        if isinstance( cmd, list ):
            cmd = ' '.join( cmd )
        self.write( cmd + separator + ' echo -n "\\0177" \n' )
        self.waiting = True

    def monitor( self ):
        "Monitor the output of a command, returning (done?, data)."
        assert self.waiting
        self.waitReadable()
        data = self.read( 1024 )
        if len( data ) > 0 and data[ -1 ] == chr( 0177 ):
            self.waiting = False
            return True, data[ :-1 ]
        else:
            return False, data

    def sendInt( self ):
        "Send ^C, hopefully interrupting an interactive subprocess."
        self.write( chr( 3 ) )

    def waitOutput( self, verbose=False ):
        """Wait for a command to complete.
           Completion is signaled by a sentinel character, ASCII(127)
           appearing in the output stream.  Wait for the sentinel and return
           the output, including trailing newline.
           verbose: print output interactively"""
        log = info if verbose else debug
        assert self.waiting
        output = ''
        while True:
            self.waitReadable()
            data = self.read( 1024 )
            if len( data ) > 0  and data[ -1 ] == chr( 0177 ):
                output += data[ :-1 ]
                log( output )
                break
            else:
                output += data
        self.waiting = False
        return output

    def cmd( self, cmd, verbose=False ):
        """Send a command, wait for output, and return it.
           cmd: string"""
        log = info if verbose else debug
        log( '*** %s : %s\n' % ( self.name, cmd ) )
        self.sendCmd( cmd )
        return self.waitOutput( verbose )

    def cmdPrint( self, cmd ):
        """Call cmd and printing its output
           cmd: string"""
        return self.cmd( cmd, verbose=True )

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
        return 0

    def addIntf( self, intf, port ):
        """Add an interface.
           intf: interface name (nodeN-ethM)
           port: port number (typically OpenFlow port number)"""
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
        result = self.cmd( [ 'ifconfig', intf, 'down' ] )
        result += self.cmd( [ 'ifconfig', intf, 'hw', 'ether', mac ] )
        result += self.cmd( [ 'ifconfig', intf, 'up' ] )
        return result

    def setARP( self, ip, mac ):
        """Add an ARP entry.
           ip: IP address as string
           mac: MAC address as string"""
        result = self.cmd( [ 'arp', '-s', ip, mac ] )
        return result

    def setIP( self, intf, ip, prefixLen=8 ):
        """Set the IP address for an interface.
           intf: interface name
           ip: IP address as a string
           prefixLen: prefix length, e.g. 8 for /8 or 16M addrs"""
        ipSub = '%s/%d' % ( ip, prefixLen )
        result = self.cmd( [ 'ifconfig', intf, ipSub, 'up' ] )
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
        self.cmd( 'ip route flush' )
        return self.cmd( 'route add default ' + intf )

    def IP( self, intf=None ):
        "Return IP address of a node or specific interface."
        if len( self.ips ) == 1:
            return self.ips.values()[ 0 ]
        if intf:
            return self.ips.get( intf, None )

    def MAC( self, intf=None ):
        "Return MAC address of a node or specific interface."
        if intf is None and len( self.intfs ) == 1:
            intf = self.intfs.values()[ 0 ]
        ifconfig = self.cmd( 'ifconfig ' + intf )
        macs = re.findall( '..:..:..:..:..:..', ifconfig )
        if len( macs ) > 0:
            return macs[ 0 ]

    def intfIsUp( self, intf ):
        "Check if an interface is up."
        return 'UP' in self.cmd( 'ifconfig ' + intf )

    # Other methods
    def __str__( self ):
        result = self.name + ':'
        result += ' IP=' + str( self.IP() )
        result += ' intfs=' + ','.join( sorted( self.intfs.values() ) )
        result += ' waiting=' + str( self.waiting )
        return result


class Host( Node ):
    "A host is simply a Node."
    pass


class Switch( Node ):
    """A Switch is a Node that is running (or has execed?)
       an OpenFlow switch."""

    def sendCmd( self, cmd ):
        """Send command to Node.
           cmd: string"""
        if not self.execed:
            return Node.sendCmd( self, cmd )
        else:
            error( '*** Error: %s has execed and cannot accept commands' %
                     self.name )

    def monitor( self ):
        "Monitor node."
        if not self.execed:
            return Node.monitor( self )
        else:
            return True, ''


class UserSwitch( Switch ):
    "User-space switch."

    def __init__( self, name, *args, **kwargs ):
        """Init.
           name: name for the switch"""
        Switch.__init__( self, name, **kwargs )

    def start( self, controllers ):
        """Start OpenFlow reference user datapath.
           Log to /tmp/sN-{ofd,ofp}.log.
           controllers: list of controller objects"""
        controller = controllers[ 0 ]
        ofdlog = '/tmp/' + self.name + '-ofd.log'
        ofplog = '/tmp/' + self.name + '-ofp.log'
        self.cmd( 'ifconfig lo up' )
        intfs = sorted( self.intfs.values() )
        if self.inNamespace:
            intfs = intfs[ :-1 ]
        self.cmd( 'ofdatapath -i ' + ','.join( intfs ) +
            ' punix:/tmp/' + self.name +
            ' 1> ' + ofdlog + ' 2> ' + ofdlog + ' &' )
        self.cmd( 'ofprotocol unix:/tmp/' + self.name +
            ' tcp:' + controller.IP() + ' --fail=closed' +
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
        self.dp = dp
        if self.inNamespace:
            error( "KernelSwitch currently only works"
                " in the root namespace." )
            exit( 1 )

    def start( self, controllers ):
        "Start up reference kernel datapath."
        ofplog = '/tmp/' + self.name + '-ofp.log'
        quietRun( 'ifconfig lo up' )
        # Delete local datapath if it exists;
        # then create a new one monitoring the given interfaces
        quietRun( 'dpctl deldp nl:%i' % self.dp )
        self.cmd( 'dpctl adddp nl:%i' % self.dp )
        if self.defaultMAC:
            intf = 'of%i' % self.dp
            self.cmd( [ 'ifconfig', intf, 'hw', 'ether', self.defaultMAC ] )
        if len( self.intfs ) != max( self.intfs ) + 1:
            raise Exception( 'only contiguous, zero-indexed port ranges'
                            'supported: %s' % self.intfs )
        intfs = [ self.intfs[ port ] for port in sorted( self.intfs.keys() ) ]
        self.cmd( 'dpctl addif nl:' + str( self.dp ) + ' ' +
            ' '.join( intfs ) )
        # Run protocol daemon
        controller = controllers[ 0 ]
        self.cmd( 'ofprotocol nl:' + str( self.dp ) + ' tcp:' +
                      controller.IP() + ':' +
                      str( controller.port ) +
                      ' --fail=closed 1> ' + ofplog + ' 2>' + ofplog + ' &' )
        self.execed = False

    def stop( self ):
        "Terminate kernel datapath."
        quietRun( 'dpctl deldp nl:%i' % self.dp )
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
        self.dp = dp
        if self.inNamespace:
            error( "OVSKernelSwitch currently only works"
                " in the root namespace." )
            exit( 1 )

    def start( self, controllers ):
        "Start up kernel datapath."
        ofplog = '/tmp/' + self.name + '-ofp.log'
        quietRun( 'ifconfig lo up' )
        # Delete local datapath if it exists;
        # then create a new one monitoring the given interfaces
        quietRun( 'ovs-dpctl del-dp dp%i' % self.dp )
        self.cmd( 'ovs-dpctl add-dp dp%i' % self.dp )
        if self.defaultMAC:
            intf = 'dp' % self.dp
            mac = self.defaultMAC
            self.cmd( [ 'ifconfig', intf, 'hw', 'ether', mac ] )

        if len( self.intfs ) != max( self.intfs ) + 1:
            raise Exception( 'only contiguous, zero-indexed port ranges'
                            'supported: %s' % self.intfs )
        intfs = [ self.intfs[ port ] for port in sorted( self.intfs.keys() ) ]
        self.cmd( 'ovs-dpctl add-if dp' + str( self.dp ) + ' ' +
                      ' '.join( intfs ) )
        # Run protocol daemon
        controller = controllers[ 0 ]
        self.cmd( 'ovs-openflowd dp' + str( self.dp ) + ' tcp:' +
                      controller.IP() + ':' +
                      ' --fail=closed 1> ' + ofplog + ' 2>' + ofplog + ' &' )
        self.execed = False

    def stop( self ):
        "Terminate kernel datapath."
        quietRun( 'ovs-dpctl del-dp dp%i' % self.dp )
        self.cmd( 'kill %ovs-openflowd' )
        self.deleteIntfs()


class Controller( Node ):
    """A Controller is a Node that is running (or has execed?) an
       OpenFlow controller."""

    def __init__( self, name, inNamespace=False, controller='controller',
                 cargs='-v ptcp:', cdir=None, defaultIP="127.0.0.1",
                 port=6633 ):
        self.controller = controller
        self.cargs = cargs
        self.cdir = cdir
        self.port = port
        Node.__init__( self, name, inNamespace=inNamespace,
            defaultIP=defaultIP )

    def start( self ):
        """Start <controller> <args> on controller.
           Log to /tmp/cN.log"""
        cout = '/tmp/' + self.name + '.log'
        if self.cdir is not None:
            self.cmd( 'cd ' + self.cdir )
        self.cmd( self.controller + ' ' + self.cargs +
            ' 1> ' + cout + ' 2> ' + cout + ' &' )
        self.execed = False

    def stop( self ):
        "Stop controller."
        self.cmd( 'kill %' + self.controller )
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

    def __init__( self, name, inNamespace=False, noxArgs=None, **kwargs ):
        """Init.
           name: name to give controller
           noxArgs: list of args, or single arg, to pass to NOX"""
        if type( noxArgs ) != list:
            noxArgs = [ noxArgs ]
        if not noxArgs:
            noxArgs = [ 'packetdump' ]

        if 'NOX_CORE_DIR' not in os.environ:
            exit( 'exiting; please set missing NOX_CORE_DIR env var' )
        noxCoreDir = os.environ[ 'NOX_CORE_DIR' ]

        Controller.__init__( self, name,
            controller=noxCoreDir + '/nox_core',
            cargs='--libdir=/usr/local/lib -v -i ptcp: ' +
                    ' '.join( noxArgs ),
            cdir = noxCoreDir, **kwargs )


class RemoteController( Controller ):
    "Controller running outside of Mininet's control."

    def __init__( self, name, inNamespace=False, defaultIP='127.0.0.1',
                 port=6633 ):
        """Init.
           name: name to give controller
           defaultIP: the IP address where the remote controller is
           listening
           port: the port where the remote controller is listening"""
        Controller.__init__( self, name, defaultIP=defaultIP, port=port )

    def start( self ):
        "Overridden to do nothing."
        return

    def stop( self ):
        "Overridden to do nothing."
        return
