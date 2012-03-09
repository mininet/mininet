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

CPULimitedHost: a virtual host whose CPU bandwidth is limited by
    RT or CFS bandwidth limiting.

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

from mininet.log import info, error, warn, debug
from mininet.util import quietRun, errRun, errFail, moveIntf, isShellBuiltin
from mininet.util import numCores
from mininet.moduledeps import moduleDeps, pathCheck, OVS_KMOD, OF_KMOD, TUN
from mininet.link import Link

class Node( object ):
    """A virtual network node is simply a shell in a network namespace.
       We communicate with it using pipes."""

    portBase = 0  # Nodes always start with eth0/port0, even in OF 1.0

    def __init__( self, name, inNamespace=True, **params ):
        """name: name of node
           inNamespace: in network namespace?
           params: Node parameters (see config() for details)"""

        # Make sure class actually works
        self.checkSetup()

        self.name = name
        self.inNamespace = inNamespace

        # Stash configuration parameters for future reference
        self.params = params

        self.intfs = {}  # dict of port numbers to interfaces
        self.ports = {}  # dict of interfaces to port numbers
                         # replace with Port objects, eventually ?
        self.nameToIntf = {}  # dict of interface names to Intfs

        # Start command interpreter shell
        self.shell = None
        self.startShell()

    # File descriptor to node mapping support
    # Class variables and methods

    inToNode = {}  # mapping of input fds to nodes
    outToNode = {}  # mapping of output fds to nodes

    @classmethod
    def fdToNode( cls, fd ):
        """Return node corresponding to given file descriptor.
           fd: file descriptor
           returns: node"""
        node = cls.outToNode.get( fd )
        return node or cls.inToNode.get( fd )

    # Automatic class setup support

    isSetup = False;

    @classmethod
    def checkSetup( cls ):
        "Make sure our class and superclasses are set up"
        while cls and not getattr( cls, 'isSetup', True ):
            cls.setup()
            cls.isSetup = True
            # Make pylint happy
            cls = getattr( type( cls ), '__base__', None )

    @classmethod
    def setup( cls ):
        "Make sure our class dependencies are available"
        pathCheck( 'mnexec', 'ifconfig',  moduleName='Mininet')

    def cleanup( self ):
        "Help python collect its garbage."
        self.shell = None

    # Command support via shell process in namespace

    def startShell( self ):
        "Start a shell process for running commands"
        if self.shell:
            error( "%s: shell is already running" )
            return
        # mnexec: (c)lose descriptors, (d)etach from tty,
        # (p)rint pid, and run in (n)amespace 
        opts = '-cdp'
        if self.inNamespace:
            opts += 'n'
        # bash -m: enable job control
        cmd = [ 'mnexec', opts, 'bash', '-m' ]
        self.shell = Popen( cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT,
            close_fds=True )
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
        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''
        self.waiting = False

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
            cmd = ' '.join( [ str( c ) for c in cmd ] )
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

    def newPort( self ):
        "Return the next port number to allocate."
        if len( self.ports ) > 0:
            return max( self.ports.values() ) + 1
        return self.portBase

    def addIntf( self, intf, port=None ):
        """Add an interface.
           intf: interface
           port: port number (optional, typically OpenFlow port number)"""
        if port is None:
            port = self.newPort()
        self.intfs[ port ] = intf
        self.ports[ intf ] = port
        self.nameToIntf[ intf.name ] = intf
        debug( '\n' )
        debug( 'added intf %s:%d to node %s\n' % ( intf,port, self.name ) )
        if self.inNamespace:
            debug( 'moving', intf, 'into namespace for', self.name, '\n' )
            moveIntf( intf.name, self )

    def defaultIntf( self ):
        "Return interface for lowest port"
        ports = self.intfs.keys()
        if ports:
            return self.intfs[ min( ports ) ]

    def intf( self, intf='' ):
        """Return our interface object with given name,x
           or default intf if name is empty"""
        if not intf:
            return self.defaultIntf()
        elif type( intf) is str:
            return self.nameToIntf[ intf ]
        else:
            return intf

    def linksTo( self, node):
        "Return [ link1, link2...] for all links from self to node."
        # We could optimize this if it is important
        links = []
        for intf in self.intfs:
            link = intf.link
            nodes = ( link.intf1.node, link.intf2.node )
            if self in nodes and node in nodes:
                links.append( link )
        return links

    def deleteIntfs( self ):
        "Delete all of our interfaces."
        # In theory the interfaces should go away after we shut down.
        # However, this takes time, so we're better off removing them
        # explicitly so that we won't get errors if we run before they
        # have been removed by the kernel. Unfortunately this is very slow,
        # at least with Linux kernels before 2.6.33
        for intf in self.intfs.values():
            intf.delete()
            info( '.' )

    # Routing support

    def setARP( self, ip, mac ):
        """Add an ARP entry.
           ip: IP address as string
           mac: MAC address as string"""
        result = self.cmd( 'arp', '-s', ip, mac )
        return result

    def setHostRoute( self, ip, intf ):
        """Add route to host.
           ip: IP address as dotted decimal
           intf: string, interface name"""
        return self.cmd( 'route add -host ' + ip + ' dev ' + intf )

    def setDefaultRoute( self, intf=None ):
        """Set the default route to go through intf.
           intf: string, interface name"""
        if not intf:
            intf = self.defaultIntf()
        self.cmd( 'ip route flush root 0/0' )
        return self.cmd( 'route add default %s' % intf )

    # Convenience and configuration methods

    def setMAC( self, mac, intf=''):
        """Set the MAC address for an interface.
           intf: intf or intf name
           mac: MAC address as string"""
        return self.intf( intf ).setMAC( mac )

    def setIP( self, ip, prefixLen=8, intf='' ):
        """Set the IP address for an interface.
           intf: interface name
           ip: IP address as a string
           prefixLen: prefix length, e.g. 8 for /8 or 16M addrs"""
        # This should probably be rethought:
        ipSub = '%s/%s' % ( ip, prefixLen )
        return self.intf( intf ).setIP( ipSub )

    def IP( self, intf=None ):
        "Return IP address of a node or specific interface."
        return self.intf( intf ).IP()

    def MAC( self, intf=None ):
        "Return MAC address of a node or specific interface."
        return self.intf( intf ).MAC()

    def intfIsUp( self, intf=None ):
        "Check if an interface is up."
        return self.intf( intf ).isUp()

    # The reason why we configure things in this way is so
    # That the parameters can be listed and documented in
    # the config method.
    # Dealing with subclasses and superclasses is slightly
    # annoying, but at least the information is there!

    def setParam( self, results, method, **param ):
        """Internal method: configure a *single* parameter
           results: dict of results to update
           method: config method name
           param: arg=value (ignore if value=None)
           value may also be list or dict"""
        name, value = param.items()[ 0 ]
        f = getattr( self, method, None )
        if not f or value is None:
            return
        if type( value ) is list:
            result = f( *value )
        elif type( value ) is dict:
            result = f( **value )
        else:
            result = f( value )
        results[ name ] = result
        return result

    def config( self, mac=None, ip=None, ifconfig=None, 
                defaultRoute=None, **params):
        """Configure Node according to (optional) parameters:
           mac: MAC address for default interface
           ip: IP address for default interface
           ifconfig: arbitrary interface configuration
           Subclasses should override this method and call
           the parent class's config(**params)"""
        # If we were overriding this method, we would call
        # the superclass config method here as follows:
        # r = Parent.config( **params )
        r = {}
        self.setParam( r, 'setMAC', mac=mac )
        self.setParam( r, 'setIP', ip=ip )
        self.setParam( r, 'ifconfig', ifconfig=ifconfig )
        self.setParam( r, 'defaultRoute', defaultRoute=defaultRoute )
        return r

    def configDefault( self, **moreParams ):
        "Configure with default parameters"
        self.params.update( moreParams )
        self.config( **self.params )

    # This is here for backward compatibility
    def linkTo( self, node, link=Link ):
        """(Deprecated) Link to another node
           replace with Link( node1, node2)"""
        return link( self, node )

    # Other methods

    def intfList( self ):
        "List of our interfaces sorted by port number"
        return [ self.intfs[ p ] for p in sorted( self.intfs.iterkeys() ) ]

    def intfNames( self ):
        "The names of our interfaces sorted by port number"
        return [ str( i ) for i in self.intfList() ]

    def __str__( self ):
        return '%s: IP=%s intfs=%s pid=%s' % (
            self.name, self.IP(), ','.join( self.intfNames() ), self.pid )


class Host( Node ):
    "A host is simply a Node"
    pass


class CPULimitedHost( Host ):

    "CPU limited host"

    def __init__( self, *args, **kwargs ):
        Node.__init__( self, *args, **kwargs )
        # Create a cgroup and move shell into it
        self.cgroup = 'cpu,cpuacct:/' + self.name
        errFail( 'cgcreate -g ' + self.cgroup )
        errFail( 'cgclassify -g %s %s' % ( self.cgroup, self.pid ) )
        self.period_us = kwargs.get( 'period_us', 10000 )
        self.sched = kwargs.get( 'sched', 'rt' )

    def cleanup( self ):
        "Clean up our cgroup"
        Host.cleanup( self )
        debug( '*** deleting cgroup', self.cgroup, '\n' )
        errFail( 'cgdelete -r ' + self.cgroup )

    def cgroupSet( self, param, value, resource='cpu' ):
        "Set a cgroup parameter and return its value"
        cmd = 'cgset -r %s.%s=%s /%s' % (
            resource, param, value, self.name )
        quietRun( cmd )
        nvalue = int( self.cgroupGet( param, resource ) )
        if nvalue != value:
            error( '*** error: cgroupSet: %s set to %s instead of %s\n'
                   % ( param, nvalue, value ) )
        return nvalue

    def cgroupGet( self, param, resource='cpu' ):
        cmd = 'cgget -r %s.%s /%s' % (
            resource, param, self.name )
        return quietRun( cmd ).split()[ -1 ]

    def chrt( self, prio=20 ):
        "Set RT scheduling priority"
        quietRun( 'chrt -p %s %s' % ( prio, self.pid ) )
        result = quietRun( 'chrt -p %s' % self.pid )
        firstline = result.split( '\n' )[ 0 ]
        lastword = firstline.split( ' ' )[ -1 ]
        if lastword != 'SCHED_RR':
            error( '*** error: could not assign SCHED_RR to %s\n' % self.name )
        return lastword

    def rtInfo( self, f ):
        "Internal method: return parameters for RT bandwidth"
        pstr, qstr = 'rt_period_us', 'rt_runtime_us'
        # RT uses wall clock time for period and quota
        quota = int( self.period_us * f * numCores() )
        return pstr, qstr, self.period_us, quota

    def cfsInfo( self, f):
        "Internal method: return parameters for CFS bandwidth"
        pstr, qstr = 'cfs_period_us', 'cfs_quota_us'
        # CFS uses wall clock time for period and CPU time for quota.
        quota = int( self.period_us * f * numCores() )
        period = self.period_us
        if f > 0 and quota < 1000:
            debug( '(cfsInfo: increasing default period) ' )
            quota = 1000
            period = int( quota / f / numCores() )
        return pstr, qstr, period, quota

    # BL comment:
    # This may not be the right API, 
    # since it doesn't specify CPU bandwidth in "absolute"
    # units the way link bandwidth is specified.
    # We should use MIPS or SPECINT or something instead.
    # Alternatively, we should change from system fraction
    # to CPU seconds per second, essentially assuming that
    # all CPUs are the same.

    def setCPUFrac( self, f=-1, sched=None):
        """Set overall CPU fraction for this host
           f: CPU bandwidth limit (fraction)
           sched: 'rt' or 'cfs'
           Note 'cfs' requires CONFIG_CFS_BANDWIDTH"""
        if not f:
            return
        if not sched:
            sched = self.sched
        if sched == 'rt':
            pstr, qstr, period, quota = self.rtInfo( f )
        elif sched == 'cfs':
            pstr, qstr, period, quota = self.cfsInfo( f )
        else:
            return
        if quota < 0:
            # Reset to unlimited
            quota = -1
        # Set cgroup's period and quota
        self.cgroupSet( pstr, period )
        self.cgroupSet( qstr, quota )
        if sched == 'rt':
            # Set RT priority if necessary
            self.chrt( prio=20 )
        info( '(%s %d/%dus) ' % ( sched, quota, period ) )

    def config( self, cpu=None, sched=None, **params ):
        """cpu: desired overall system CPU fraction
           params: parameters for Node.config()"""
        r = Node.config( self, **params )
        # Was considering cpu={'cpu': cpu , 'sched': sched}, but
        # that seems redundant
        self.setParam( r, 'setCPUFrac', cpu=cpu )
        return r

# Some important things to note:
#
# The "IP" address which we assign to the switch is not
# an "IP address for the switch" in the sense of IP routing.
# Rather, it is the IP address for a control interface if
# (and only if) you happen to be running the switch in a
# namespace, which is something we currently don't support
# for OVS!
#
# In general, you NEVER want to attempt to use Linux's
# network stack (i.e. ifconfig) to "assign" an IP address or
# MAC address to a switch data port. Instead, you "assign"
# the IP and MAC addresses in the controller by specifying
# packets that you want to receive or send. The "MAC" address
# reported by ifconfig for a switch data port is essentially
# meaningless.
#
# So, I'm trying changing the API to make it
# impossible to try this, since it will not work, since nobody
# ever makes separate control networks in Mininet, and indeed
# we don't even support running OVS in a namespace.
#
# Note if we have a separate control network, then it does
# make sense to have s1-eth0 as s1's control network interface,
# and we should set controlIntf accordingly.

class Switch( Node ):
    """A Switch is a Node that is running (or has execed?)
       an OpenFlow switch."""

    portBase = 1  # Switches start with port 1 in OpenFlow

    def __init__( self, name, dpid=None, opts='', listenPort=None, **params):
        """dpid: dpid for switch (or None for default)
           opts: additional switch options
           listenPort: port to listen on for dpctl connections"""
        Node.__init__( self, name, **params )
        self.dpid = dpid if dpid else self.defaultDpid()
        self.opts = opts
        self.listenPort = listenPort
        if self.listenPort:
            self.opts += ' --listen=ptcp:%i ' % self.listenPort
        self.controlIntf = None

    def defaultDpid( self ):
        "Derive dpid from switch name, s1 -> 1"
        dpid = int( re.findall( '\d+', self.name )[ 0 ] )
        dpid = hex( dpid )[ 2: ]
        dpid = '0' * ( 12 - len( dpid ) ) + dpid
        return dpid

    def defaultIntf( self ):
        "Return control interface, if any"
        if not self.inNamespace:
            error( "error: tried to access control interface of "
                   " switch %s in root namespace" % self.name )
        return self.controlIntf

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
        ports = sorted( self.ports.values() )
        intfs = [ str( self.intfs[ p ] ) for p in ports ]
        if self.inNamespace:
            intfs = intfs[ :-1 ]
        self.cmd( 'ofdatapath -i ' + ','.join( intfs ) +
            ' punix:/tmp/' + self.name + ' -d ' + self.dpid + 
            ' --no-slicing ' +
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


class OVSLegacyKernelSwitch( Switch ):
    """Open VSwitch legacy kernel-space switch using ovs-openflowd.
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
            ' --fail=secure ' + self.opts + 
            ' --datapath-id=' + self.dpid +
            ' 1>' + ofplog + ' 2>' + ofplog + '&' )
        self.execed = False

    def stop( self ):
        "Terminate kernel datapath."
        quietRun( 'ovs-dpctl del-dp ' + self.dp )
        self.cmd( 'kill %ovs-openflowd' )
        self.deleteIntfs()


class OVSSwitch( Switch ):
    "Open vSwitch switch. Depends on ovs-vsctl."

    def __init__( self, name, **params ):
        """Init.
           name: name for switch
           defaultMAC: default MAC as unsigned int; random value if None"""
        Switch.__init__( self, name, **params )
        # self.dp is the text name for the datapath that
        # we use for ovs-vsctl. This is different from the
        # dpid, which is a 64-bit numerical value used by
        # the openflow protocol.
        self.dp = name
        
    @staticmethod
    def setup():
        "Make sure Open vSwitch is installed and working"
        pathCheck( 'ovs-vsctl', 
            moduleName='Open vSwitch (openvswitch.org)')
        moduleDeps( subtract=OF_KMOD, add=OVS_KMOD )
        out, err, exitcode = errRun( 'ovs-vsctl -t 1 show' )
        if exitcode:
            error( out + err + 
                   'ovs-vsctl exited with code %d\n' % exitcode +
                   '*** Error connecting to ovs-db with ovs-vsctl\n'
                   'Make sure that Open vSwitch is installed, '
                   'that ovsdb-server is running, and that\n'
                   '"ovs-vsctl show" works correctly.\n'
                   'You may wish to try "service openvswitch-switch start".\n' )
            exit( 1 )

    def start( self, controllers ):
        "Start up a new OVS OpenFlow switch using ovs-vsctl"
        # Annoyingly, --if-exists option seems not to work
        self.cmd( 'ovs-vsctl del-br ', self.dp )
        self.cmd( 'ovs-vsctl add-br', self.dp )
        self.cmd( 'ovs-vsctl set-fail-mode', self.dp, 'secure' )
        ports = sorted( self.ports.values() )
        intfs = [ self.intfs[ port ] for port in ports ]
        # XXX: Ugly check - we should probably fix this!
        if ports and ( len( ports ) != ports[ -1 ] + 1 - self.portBase ):
            raise Exception( 'only contiguous, one-indexed port ranges '
                            'supported: %s' % self.intfs )
        for intf in intfs:
            self.cmd( 'ovs-vsctl add-port', self.dp, intf )
            self.cmd( 'ifconfig', intf, 'up' )
        # Add controllers
        clist = ','.join( [ 'tcp:%s:%d' % ( c.IP(), c.port ) for c in controllers ] )
        self.cmd( 'ovs-vsctl set-controller', self.dp, clist )

    def stop( self ):
        "Terminate OVS switch."
        self.cmd( 'ovs-vsctl del-br', self.dp )

OVSKernelSwitch = OVSSwitch


class Controller( Node ):
    """A Controller is a Node that is running (or has execed?) an
       OpenFlow controller."""

    def __init__( self, name, inNamespace=False, command='controller',
                 cargs='-v ptcp:%d', cdir=None, ip="127.0.0.1",
                 port=6633, **params ):
        self.command = command
        self.cargs = cargs
        self.cdir = cdir
        self.ip = ip
        self.port = port
        Node.__init__( self, name, inNamespace=inNamespace,
            ip=ip, **params  )

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
        if self.intfs:
            ip = Node.IP( self, intf )
        else:
            ip = self.ip
        return ip


class OVSController( Controller ):
    "Open vSwitch controller"
    def __init__( self, name, command='ovs-controller', **kwargs ):
        Controller.__init__( self, name, command=command, **kwargs )


# BL: This really seems to be poorly specified,
# so it's going to go away!

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

    def __init__( self, name, *noxArgs, **kwargs ):
        """Init.
           name: name to give controller
           noxArgs: arguments (strings) to pass to NOX"""
        if not noxArgs:
            warn( 'warning: no NOX modules specified; '
                  'running packetdump only\n' )
            noxArgs = [ 'packetdump' ]
        elif type( noxArgs ) not in ( list, tuple ):
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
