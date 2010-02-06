"""
Node objects for Mininet.

Nodes provide a simple abstraction for interacting with
hosts, switches and controllers. Local nodes are simply
one or more processes on the local machine.

Node: superclass for all (currently only local) network nodes.

Host: a virtual host.

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
"""

from subprocess import Popen, PIPE, STDOUT
import os
import signal
import sys
import select

flush = sys.stdout.flush

from mininet.log import lg
from mininet.util import quietRun, macColonHex, ipStr


class Node( object ):
    """A virtual network node is simply a shell in a network namespace.
       We communicate with it using pipes."""
    inToNode = {}
    outToNode = {}

    def __init__( self, name, inNamespace=True ):
        self.name = name
        closeFds = False # speed vs. memory use
        # xpgEcho is needed so we can echo our sentinel in sendCmd
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
        self.intfCount = 0
        self.intfs = [] # list of interface names, as strings
        self.ips = {} # dict of interfaces to ip addresses as strings
        self.connection = {}
        self.waiting = False
        self.execed = False
        self.ports = {} # dict of ints to interface strings
                        # replace with Port object, eventually

    def fdToNode( self, f ):
        """Insert docstring.
           f: unknown
           returns: bool unknown"""
        node = self.outToNode.get( f )
        return node or self.inToNode.get( f )

    def cleanup( self ):
        "Help python collect its garbage."
        self.shell = None

    # Subshell I/O, commands and control
    def read( self, filenoMax ):
        """Insert docstring.
           filenoMax: unknown"""
        return os.read( self.stdout.fileno(), filenoMax )

    def write( self, data ):
        """Write data to node.
           data: string"""
        os.write( self.stdin.fileno(), data )

    def terminate( self ):
        "Send kill signal to Node and cleanup after it."
        os.kill( self.pid, signal.SIGKILL )
        self.cleanup()

    def stop( self ):
        "Stop node."
        self.terminate()

    def waitReadable( self ):
        "Poll on node."
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
        "Monitor the output of a command, returning (done, data)."
        assert self.waiting
        self.waitReadable()
        data = self.read( 1024 )
        if len( data ) > 0 and data[ -1 ] == chr( 0177 ):
            self.waiting = False
            return True, data[ :-1 ]
        else:
            return False, data

    def sendInt( self ):
        "Send ^C, hopefully interrupting a running subprocess."
        self.write( chr( 3 ) )

    def waitOutput( self ):
        """Wait for a command to complete.
           Completion is signaled by a sentinel character, ASCII(127)
           appearing in the output stream.  Wait for the sentinel and return
           the output, including trailing newline."""
        assert self.waiting
        output = ''
        while True:
            self.waitReadable()
            data = self.read( 1024 )
            if len( data ) > 0  and data[ -1 ] == chr( 0177 ):
                output += data[ :-1 ]
                break
            else:
                output += data
        self.waiting = False
        return output

    def cmd( self, cmd ):
        """Send a command, wait for output, and return it.
           cmd: string"""
        self.sendCmd( cmd )
        return self.waitOutput()

    def cmdPrint( self, cmd ):
        """Call cmd and printing its output
           cmd: string"""
        #lg.info( '*** %s : %s', self.name, cmd )
        result = self.cmd( cmd )
        #lg.info( '%s\n', result )
        return result

    # Interface management, configuration, and routing
    def intfName( self, n ):
        "Construct a canonical interface name node-intf for interface N."
        return self.name + '-eth' + repr( n )

    def newIntf( self ):
        "Reserve and return a new interface name."
        intfName = self.intfName( self.intfCount )
        self.intfCount += 1
        self.intfs += [ intfName ]
        return intfName

    def setMAC( self, intf, mac ):
        """Set the MAC address for an interface.
           mac: MAC address as unsigned int"""
        macStr = macColonHex( mac )
        result = self.cmd( [ 'ifconfig', intf, 'down' ] )
        result += self.cmd( [ 'ifconfig', intf, 'hw', 'ether', macStr ] )
        result += self.cmd( [ 'ifconfig', intf, 'up' ] )
        return result

    def setARP( self, ip, mac ):
        """Add an ARP entry.
           ip: IP address as unsigned int
           mac: MAC address as unsigned int"""
        ip = ipStr( ip )
        mac = macColonHex( mac )
        result = self.cmd( [ 'arp', '-s', ip, mac ] )
        return result

    def setIP( self, intf, ip, bits ):
        """Set the IP address for an interface.
           intf: string, interface name
           ip: IP address as a string
           bits:"""
        result = self.cmd( [ 'ifconfig', intf, ip + bits, 'up' ] )
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

    def IP( self ):
        "Return IP address of first interface"
        if len( self.intfs ) > 0:
            return self.ips.get( self.intfs[ 0 ], None )

    def intfIsUp( self ):
        "Check if one of our interfaces is up."
        return 'UP' in self.cmd( 'ifconfig ' + self.intfs[ 0 ] )

    # Other methods
    def __str__( self ):
        result = self.name + ':'
        if self.IP():
            result += ' IP=' + self.IP()
        result += ' intfs=' + ','.join( self.intfs )
        result += ' waiting=' + repr( self.waiting )
        return result


class Host( Node ):
    "A host is simply a Node."
    pass


class Switch( Node ):
    """A Switch is a Node that is running ( or has execed )
       an OpenFlow switch."""

    def sendCmd( self, cmd ):
        """Send command to Node.
           cmd: string"""
        if not self.execed:
            return Node.sendCmd( self, cmd )
        else:
            lg.error( '*** Error: %s has execed and cannot accept commands' %
                     self.name )

    def monitor( self ):
        "Monitor node."
        if not self.execed:
            return Node.monitor( self )
        else:
            return True, ''


class UserSwitch( Switch ):
    """User-space switch.
       Currently only works in the root namespace."""

    def __init__( self, name ):
        """Init.
           name: name for the switch"""
        Switch.__init__( self, name, inNamespace=False )

    def start( self, controllers ):
        """Start OpenFlow reference user datapath.
           Log to /tmp/sN-{ ofd,ofp }.log.
           controllers: dict of controller names to objects"""
        if 'c0' not in controllers:
            raise Exception( 'User datapath start() requires controller c0' )
        controller = controllers[ 'c0' ]
        ofdlog = '/tmp/' + self.name + '-ofd.log'
        ofplog = '/tmp/' + self.name + '-ofp.log'
        self.cmd( 'ifconfig lo up' )
        intfs = self.intfs
        self.cmdPrint( 'ofdatapath -i ' + ','.join( intfs ) + ' punix:/tmp/' +
                      self.name + ' 1> ' + ofdlog + ' 2> ' + ofdlog + ' &' )
        self.cmdPrint( 'ofprotocol unix:/tmp/' + self.name + ' tcp:' +
                      controller.IP() + ' --fail=closed 1> ' + ofplog + ' 2>' +
                      ofplog + ' &' )

    def stop( self ):
        "Stop OpenFlow reference user datapath."
        self.cmd( 'kill %ofdatapath' )
        self.cmd( 'kill %ofprotocol' )


class KernelSwitch( Switch ):
    """Kernel-space switch.
       Currently only works in the root namespace."""

    def __init__( self, name, dp=None, dpid=None ):
        """Init.
           name:
           dp: netlink id ( 0, 1, 2, ... )
           dpid: datapath ID as unsigned int; random value if None"""
        Switch.__init__( self, name, inNamespace=False )
        self.dp = dp
        self.dpid = dpid

    def start( self, controllers ):
        "Start up reference kernel datapath."
        ofplog = '/tmp/' + self.name + '-ofp.log'
        quietRun( 'ifconfig lo up' )
        # Delete local datapath if it exists;
        # then create a new one monitoring the given interfaces
        quietRun( 'dpctl deldp nl:%i' % self.dp )
        self.cmdPrint( 'dpctl adddp nl:%i' % self.dp )
        if self.dpid:
            intf = 'of%i' % self.dp
            macStr = macColonHex( self.dpid )
            self.cmd( [ 'ifconfig', intf, 'hw', 'ether', macStr ] )

        if len( self.ports ) != max( self.ports.keys() ) + 1:
            raise Exception( 'only contiguous, zero-indexed port ranges'
                            'supported: %s' % self.ports )
        intfs = [ self.ports[ port ] for port in self.ports.keys() ]
        self.cmdPrint( 'dpctl addif nl:' + str( self.dp ) + ' ' +
            ' '.join( intfs ) )
        # Run protocol daemon
        self.cmdPrint( 'ofprotocol nl:' + str( self.dp ) + ' tcp:' +
                      controllers[ 'c0' ].IP() + ':' +
                      str( controllers[ 'c0' ].port ) +
                      ' --fail=closed 1> ' + ofplog + ' 2>' + ofplog + ' &' )
        self.execed = False

    def stop( self ):
        "Terminate kernel datapath."
        quietRun( 'dpctl deldp nl:%i' % self.dp )
        # In theory the interfaces should go away after we shut down.
        # However, this takes time, so we're better off to remove them
        # explicitly so that we won't get errors if we run before they
        # have been removed by the kernel. Unfortunately this is very slow.
        self.cmd( 'kill %ofprotocol' )
        for intf in self.intfs:
            quietRun( 'ip link del ' + intf )
            lg.info( '.' )


class OVSKernelSwitch( Switch ):
    """Open VSwitch kernel-space switch.
       Currently only works in the root namespace."""

    def __init__( self, name, dp=None, dpid=None ):
        """Init.
           name:
           dp: netlink id ( 0, 1, 2, ... )
           dpid: datapath ID as unsigned int; random value if None"""
        Switch.__init__( self, name, inNamespace=False )
        self.dp = dp
        self.dpid = dpid

    def start( self, controllers ):
        "Start up kernel datapath."
        ofplog = '/tmp/' + self.name + '-ofp.log'
        quietRun( 'ifconfig lo up' )
        # Delete local datapath if it exists;
        # then create a new one monitoring the given interfaces
        quietRun( 'ovs-dpctl del-dp dp%i' % self.dp )
        self.cmdPrint( 'ovs-dpctl add-dp dp%i' % self.dp )
        if self.dpid:
            intf = 'dp' % self.dp
            macStr = macColonHex( self.dpid )
            self.cmd( [ 'ifconfig', intf, 'hw', 'ether', macStr ] )

        if len( self.ports ) != max( self.ports.keys() ) + 1:
            raise Exception( 'only contiguous, zero-indexed port ranges'
                            'supported: %s' % self.ports )
        intfs = [ self.ports[ port ] for port in self.ports.keys() ]
        self.cmdPrint( 'ovs-dpctl add-if dp' + str( self.dp ) + ' ' +
                      ' '.join( intfs ) )
        # Run protocol daemon
        self.cmdPrint( 'ovs-openflowd dp' + str( self.dp ) + ' tcp:' +
                      controllers[ 'c0' ].IP() + ':' +
                      ' --fail=closed 1> ' + ofplog + ' 2>' + ofplog + ' &' )
        self.execed = False

    def stop( self ):
        "Terminate kernel datapath."
        quietRun( 'ovs-dpctl del-dp dp%i' % self.dp )
        # In theory the interfaces should go away after we shut down.
        # However, this takes time, so we're better off to remove them
        # explicitly so that we won't get errors if we run before they
        # have been removed by the kernel. Unfortunately this is very slow.
        self.cmd( 'kill %ovs-openflowd' )
        for intf in self.intfs:
            quietRun( 'ip link del ' + intf )
            lg.info( '.' )


class Controller( Node ):
    """A Controller is a Node that is running (or has execed?) an
       OpenFlow controller."""

    def __init__( self, name, inNamespace=False, controller='controller',
                 cargs='-v ptcp:', cdir=None, ipAddress="127.0.0.1",
                 port=6633 ):
        self.controller = controller
        self.cargs = cargs
        self.cdir = cdir
        self.ipAddress = ipAddress
        self.port = port
        Node.__init__( self, name, inNamespace=inNamespace )

    def start( self ):
        """Start <controller> <args> on controller.
           Log to /tmp/cN.log"""
        cout = '/tmp/' + self.name + '.log'
        if self.cdir is not None:
            self.cmdPrint( 'cd ' + self.cdir )
        self.cmdPrint( self.controller + ' ' + self.cargs +
            ' 1> ' + cout + ' 2> ' + cout + ' &' )
        self.execed = False

    def stop( self ):
        "Stop controller."
        self.cmd( 'kill %' + self.controller )
        self.terminate()

    def IP( self ):
        "Return IP address of the Controller"
        return self.ipAddress


class ControllerParams( object ):
    "Container for controller IP parameters."

    def __init__( self, ip, subnetSize ):
        """Init.
           ip: integer, controller IP
            subnetSize: integer, ex 8 for slash-8, covering 17M"""
        self.ip = ip
        self.subnetSize = subnetSize


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
        noxCoreDir = os.environ[ 'NOX_CORE_DIR' ]
        if not noxCoreDir:
            raise Exception( 'please set NOX_CORE_DIR env var\n' )
        Controller.__init__( self, name,
            controller=noxCoreDir + '/nox_core',
            cargs='--libdir=/usr/local/lib -v -i ptcp: ' + \
                    ' '.join( noxArgs ),
            cdir = noxCoreDir, **kwargs )


class RemoteController( Controller ):
    "Controller running outside of Mininet's control."

    def __init__( self, name, inNamespace=False, ipAddress='127.0.0.1',
                 port=6633 ):
        """Init.
           name: name to give controller
           ipAddress: the IP address where the remote controller is
           listening
           port: the port where the remote controller is listening"""
        Controller.__init__( self, name, ipAddress=ipAddress, port=port )

    def start( self ):
        "Overridden to do nothing."
        return

    def stop( self ):
        "Overridden to do nothing."
        return
