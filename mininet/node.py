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
from mininet.util import ( quietRun, errRun, errFail, moveIntf, isShellBuiltin,
                           numCores, retry, mountCgroups )
from mininet.moduledeps import moduleDeps, pathCheck, OVS_KMOD, OF_KMOD, TUN
from mininet.link import Link, Intf, TCIntf

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

        # Make pylint happy
        ( self.shell, self.execed, self.pid, self.stdin, self.stdout,
            self.lastPid, self.lastCmd, self.pollOut ) = (
                None, None, None, None, None, None, None, None )
        self.waiting = False
        self.readbuf = ''

        # Start command interpreter shell
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

    def cleanup( self ):
        "Help python collect its garbage."
        if not self.inNamespace:
            for intfName in self.intfNames():
                if self.name in intfName:
                    quietRun( 'ip link del ' + intfName )
        self.shell = None

    # Subshell I/O, commands and control

    def read( self, maxbytes=1024 ):
        """Buffered read from node, non-blocking.
           maxbytes: maximum number of bytes to return"""
        count = len( self.readbuf )
        if count < maxbytes:
            data = os.read( self.stdout.fileno(), maxbytes - count )
            self.readbuf += data
        if maxbytes >= len( self.readbuf ):
            result = self.readbuf
            self.readbuf = ''
        else:
            result = self.readbuf[ :maxbytes ]
            self.readbuf = self.readbuf[ maxbytes: ]
        return result

    def readline( self ):
        """Buffered readline from node, non-blocking.
           returns: line (minus newline) or None"""
        self.readbuf += self.read( 1024 )
        if '\n' not in self.readbuf:
            return None
        pos = self.readbuf.find( '\n' )
        line = self.readbuf[ 0: pos ]
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
        # Allow sendCmd( [ list ] )
        if len( args ) == 1 and type( args[ 0 ] ) is list:
            cmd = args[ 0 ]
        # Allow sendCmd( cmd, arg1, arg2... )
        elif len( args ) > 0:
            cmd = args
        # Convert to string
        if not isinstance( cmd, str ):
            cmd = ' '.join( [ str( c ) for c in cmd ] )
        if not re.search( r'\w', cmd ):
            # Replace empty commands with something harmless
            cmd = 'echo -n'
        self.lastCmd = cmd
        printPid = printPid and not isShellBuiltin( cmd )
        if len( cmd ) > 0 and cmd[ -1 ] == '&':
            # print ^A{pid}\n{sentinel}
            cmd += ' printf "\\001%d\n\\177" $! \n'
        else:
            # print sentinel
            cmd += '; printf "\\177"'
            if printPid and not isShellBuiltin( cmd ):
                cmd = 'mnexec -p ' + cmd
        self.write( cmd + '\n' )
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

    def popen( self, *args, **kwargs ):
        """Return a Popen() object in our namespace
           args: Popen() args, single list, or string
           kwargs: Popen() keyword args"""
        defaults = { 'stdout': PIPE, 'stderr': PIPE,
                     'mncmd':
                     [ 'mnexec', '-a', str( self.pid ) ] }
        defaults.update( kwargs )
        if len( args ) == 1:
            if type( args[ 0 ] ) is list:
                # popen([cmd, arg1, arg2...])
                cmd = args[ 0 ]
            elif type( args[ 0 ] ) is str:
                # popen("cmd arg1 arg2...")
                cmd = args[ 0 ].split()
            else:
                raise Exception( 'popen() requires a string or list' )
        elif len( args ) > 0:
            # popen( cmd, arg1, arg2... )
            cmd = list( args )
        # Attach to our namespace  using mnexec -a
        mncmd = defaults[ 'mncmd' ]
        del defaults[ 'mncmd' ]
        cmd = mncmd + cmd
        # Shell requires a string, not a list!
        if defaults.get( 'shell', False ):
            cmd = ' '.join( cmd )
        return Popen( cmd, **defaults )

    def pexec( self, *args, **kwargs ):
        """Execute a command using popen
           returns: out, err, exitcode"""
        popen = self.popen( *args, **kwargs)
        out, err = popen.communicate()
        exitcode = popen.wait()
        return out, err, exitcode

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
        debug( 'added intf %s:%d to node %s\n' % ( intf, port, self.name ) )
        if self.inNamespace:
            debug( 'moving', intf, 'into namespace for', self.name, '\n' )
            moveIntf( intf.name, self )

    def defaultIntf( self ):
        "Return interface for lowest port"
        ports = self.intfs.keys()
        if ports:
            return self.intfs[ min( ports ) ]
        else:
            warn( '*** defaultIntf: warning:', self.name,
                  'has no interfaces\n' )

    def intf( self, intf='' ):
        """Return our interface object with given string name,
           default intf if name is falsy (None, empty string, etc).
           or the input intf arg.

        Having this fcn return its arg for Intf objects makes it
        easier to construct functions with flexible input args for
        interfaces (those that accept both string names and Intf objects).
        """
        if not intf:
            return self.defaultIntf()
        elif type( intf) is str:
            return self.nameToIntf[ intf ]
        else:
            return intf

    def connectionsTo( self, node):
        "Return [ intf1, intf2... ] for all intfs that connect self to node."
        # We could optimize this if it is important
        connections = []
        for intf in self.intfList():
            link = intf.link
            if link:
                node1, node2 = link.intf1.node, link.intf2.node
                if node1 == self and node2 == node:
                    connections += [ ( intf, link.intf2 ) ]
                elif node1 == node and node2 == self:
                    connections += [ ( intf, link.intf1 ) ]
        return connections

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
        return self.cmd( 'route add -host', ip, 'dev', intf )

    def setDefaultRoute( self, intf=None ):
        """Set the default route to go through intf.
           intf: string, interface name"""
        if not intf:
            intf = self.defaultIntf()
        self.cmd( 'ip route flush root 0/0' )
        return self.cmd( 'route add default %s' % intf )

    # Convenience and configuration methods

    def setMAC( self, mac, intf=None ):
        """Set the MAC address for an interface.
           intf: intf or intf name
           mac: MAC address as string"""
        return self.intf( intf ).setMAC( mac )

    def setIP( self, ip, prefixLen=8, intf=None ):
        """Set the IP address for an interface.
           intf: intf or intf name
           ip: IP address as a string
           prefixLen: prefix length, e.g. 8 for /8 or 16M addrs"""
        # This should probably be rethought
        if '/' not in ip:
            ip = '%s/%s' % ( ip, prefixLen )
        return self.intf( intf ).setIP( ip )

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

    def config( self, mac=None, ip=None,
                defaultRoute=None, lo='up', **_params ):
        """Configure Node according to (optional) parameters:
           mac: MAC address for default interface
           ip: IP address for default interface
           ifconfig: arbitrary interface configuration
           Subclasses should override this method and call
           the parent class's config(**params)"""
        # If we were overriding this method, we would call
        # the superclass config method here as follows:
        # r = Parent.config( **_params )
        r = {}
        self.setParam( r, 'setMAC', mac=mac )
        self.setParam( r, 'setIP', ip=ip )
        self.setParam( r, 'defaultRoute', defaultRoute=defaultRoute )
        # This should be examined
        self.cmd( 'ifconfig lo ' + lo )
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

    def __repr__( self ):
        "More informative string representation"
        intfs = ( ','.join( [ '%s:%s' % ( i.name, i.IP() )
                              for i in self.intfList() ] ) )
        return '<%s %s: %s pid=%s> ' % (
            self.__class__.__name__, self.name, intfs, self.pid )

    def __str__( self ):
        "Abbreviated string representation"
        return self.name

    # Automatic class setup support

    isSetup = False

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
        pathCheck( 'mnexec', 'ifconfig', moduleName='Mininet')


class Host( Node ):
    "A host is simply a Node"
    pass


class CPULimitedHost( Host ):

    "CPU limited host"

    def __init__( self, name, sched='cfs', **kwargs ):
        Host.__init__( self, name, **kwargs )
        # Initialize class if necessary
        if not CPULimitedHost.inited:
            CPULimitedHost.init()
        # Create a cgroup and move shell into it
        self.cgroup = 'cpu,cpuacct,cpuset:/' + self.name
        errFail( 'cgcreate -g ' + self.cgroup )
        # We don't add ourselves to a cpuset because you must
        # specify the cpu and memory placement first
        errFail( 'cgclassify -g cpu,cpuacct:/%s %s' % ( self.name, self.pid ) )
        # BL: Setting the correct period/quota is tricky, particularly
        # for RT. RT allows very small quotas, but the overhead
        # seems to be high. CFS has a mininimum quota of 1 ms, but
        # still does better with larger period values.
        self.period_us = kwargs.get( 'period_us', 100000 )
        self.sched = sched
        self.rtprio = 20

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
        "Return value of cgroup parameter"
        cmd = 'cgget -r %s.%s /%s' % (
            resource, param, self.name )
        return int( quietRun( cmd ).split()[ -1 ] )

    def cgroupDel( self ):
        "Clean up our cgroup"
        # info( '*** deleting cgroup', self.cgroup, '\n' )
        _out, _err, exitcode = errRun( 'cgdelete -r ' + self.cgroup )
        return exitcode != 0

    def popen( self, *args, **kwargs ):
        """Return a Popen() object in node's namespace
           args: Popen() args, single list, or string
           kwargs: Popen() keyword args"""
        # Tell mnexec to execute command in our cgroup
        mncmd = [ 'mnexec', '-a', str( self.pid ),
                  '-g', self.name ]
        if self.sched == 'rt':
            mncmd += [ '-r', str( self.rtprio ) ]
        return Host.popen( self, *args, mncmd=mncmd, **kwargs )

    def cleanup( self ):
        "Clean up our cgroup"
        retry( retries=3, delaySecs=1, fn=self.cgroupDel )

    def chrt( self ):
        "Set RT scheduling priority"
        quietRun( 'chrt -p %s %s' % ( self.rtprio, self.pid ) )
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
            self.chrt()
        info( '(%s %d/%dus) ' % ( sched, quota, period ) )

    def setCPUs( self, cores, mems=0 ):
        "Specify (real) cores that our cgroup can run on"
        if type( cores ) is list:
            cores = ','.join( [ str( c ) for c in cores ] )
        self.cgroupSet( resource='cpuset', param='cpus',
                        value=cores )
        # Memory placement is probably not relevant, but we
        # must specify it anyway
        self.cgroupSet( resource='cpuset', param='mems',
                        value=mems)
        # We have to do this here after we've specified
        # cpus and mems
        errFail( 'cgclassify -g cpuset:/%s %s' % (
                 self.name, self.pid ) )

    def config( self, cpu=None, cores=None, **params ):
        """cpu: desired overall system CPU fraction
           cores: (real) core(s) this host can run on
           params: parameters for Node.config()"""
        r = Node.config( self, **params )
        # Was considering cpu={'cpu': cpu , 'sched': sched}, but
        # that seems redundant
        self.setParam( r, 'setCPUFrac', cpu=cpu )
        self.setParam( r, 'setCPUs', cores=cores )
        return r

    inited = False

    @classmethod
    def init( cls ):
        "Initialization for CPULimitedHost class"
        mountCgroups()
        cls.inited = True


# Some important things to note:
#
# The "IP" address which setIP() assigns to the switch is not
# an "IP address for the switch" in the sense of IP routing.
# Rather, it is the IP address for the control interface,
# on the control network, and it is only relevant to the
# controller. If you are running in the root namespace
# (which is the only way to run OVS at the moment), the
# control interface is the loopback interface, and you
# normally never want to change its IP address!
#
# In general, you NEVER want to attempt to use Linux's
# network stack (i.e. ifconfig) to "assign" an IP address or
# MAC address to a switch data port. Instead, you "assign"
# the IP and MAC addresses in the controller by specifying
# packets that you want to receive or send. The "MAC" address
# reported by ifconfig for a switch data port is essentially
# meaningless. It is important to understand this if you
# want to create a functional router using OpenFlow.

class Switch( Node ):
    """A Switch is a Node that is running (or has execed?)
       an OpenFlow switch."""

    portBase = 1  # Switches start with port 1 in OpenFlow
    dpidLen = 16  # digits in dpid passed to switch

    def __init__( self, name, dpid=None, opts='', listenPort=None, **params):
        """dpid: dpid for switch (or None to derive from name, e.g. s1 -> 1)
           opts: additional switch options
           listenPort: port to listen on for dpctl connections"""
        Node.__init__( self, name, **params )
        self.dpid = dpid if dpid else self.defaultDpid()
        self.opts = opts
        self.listenPort = listenPort
        if not self.inNamespace:
            self.controlIntf = Intf( 'lo', self, port=0 )

    def defaultDpid( self ):
        "Derive dpid from switch name, s1 -> 1"
        try:
            dpid = int( re.findall( '\d+', self.name )[ 0 ] )
            dpid = hex( dpid )[ 2: ]
            dpid = '0' * ( self.dpidLen - len( dpid ) ) + dpid
            return dpid
        except IndexError:
            raise Exception( 'Unable to derive default datapath ID - '
                             'please either specify a dpid or use a '
                             'canonical switch name such as s23.' )

    def defaultIntf( self ):
        "Return control interface"
        if self.controlIntf:
            return self.controlIntf
        else:
            return Node.defaultIntf( self )

    def sendCmd( self, *cmd, **kwargs ):
        """Send command to Node.
           cmd: string"""
        kwargs.setdefault( 'printPid', False )
        if not self.execed:
            return Node.sendCmd( self, *cmd, **kwargs )
        else:
            error( '*** Error: %s has execed and cannot accept commands' %
                   self.name )

    def __repr__( self ):
        "More informative string representation"
        intfs = ( ','.join( [ '%s:%s' % ( i.name, i.IP() )
                              for i in self.intfList() ] ) )
        return '<%s %s: %s pid=%s> ' % (
            self.__class__.__name__, self.name, intfs, self.pid )

class UserSwitch( Switch ):
    "User-space switch."

    dpidLen = 12

    def __init__( self, name, **kwargs ):
        """Init.
           name: name for the switch"""
        Switch.__init__( self, name, **kwargs )
        pathCheck( 'ofdatapath', 'ofprotocol',
                   moduleName='the OpenFlow reference user switch' +
                              '(openflow.org)' )
        if self.listenPort:
            self.opts += ' --listen=ptcp:%i ' % self.listenPort

    @classmethod
    def setup( cls ):
        "Ensure any dependencies are loaded; if not, try to load them."
        if not os.path.exists( '/dev/net/tun' ):
            moduleDeps( add=TUN )

    def dpctl( self, *args ):
        "Run dpctl command"
        if not self.listenPort:
            return "can't run dpctl without passive listening port"
        return self.cmd( 'dpctl ' + ' '.join( args ) +
                         ' tcp:127.0.0.1:%i' % self.listenPort )

    def start( self, controllers ):
        """Start OpenFlow reference user datapath.
           Log to /tmp/sN-{ofd,ofp}.log.
           controllers: list of controller objects"""
        # Add controllers
        clist = ','.join( [ 'tcp:%s:%d' % ( c.IP(), c.port )
                            for c in controllers ] )
        ofdlog = '/tmp/' + self.name + '-ofd.log'
        ofplog = '/tmp/' + self.name + '-ofp.log'
        self.cmd( 'ifconfig lo up' )
        intfs = [ str( i ) for i in self.intfList() if not i.IP() ]
        self.cmd( 'ofdatapath -i ' + ','.join( intfs ) +
                  ' punix:/tmp/' + self.name + ' -d ' + self.dpid +
                  ' 1> ' + ofdlog + ' 2> ' + ofdlog + ' &' )
        self.cmd( 'ofprotocol unix:/tmp/' + self.name +
                  ' ' + clist +
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
        self.dp = dp if dp else self.name
        self.intf = self.dp
        if self.inNamespace:
            error( "OVSKernelSwitch currently only works"
                   " in the root namespace.\n" )
            exit( 1 )

    @classmethod
    def setup( cls ):
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
        self.cmd( 'ovs-dpctl del-dp ' + self.dp )
        self.cmd( 'ovs-dpctl add-dp ' + self.dp )
        intfs = [ str( i ) for i in self.intfList() if not i.IP() ]
        self.cmd( 'ovs-dpctl', 'add-if', self.dp, ' '.join( intfs ) )
        # Run protocol daemon
        clist = ','.join( [ 'tcp:%s:%d' % ( c.IP(), c.port )
                            for c in controllers ] )
        self.cmd( 'ovs-openflowd ' + self.dp +
                  ' ' + clist +
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

    def __init__( self, name, failMode='secure', **params ):
        """Init.
           name: name for switch
           failMode: controller loss behavior (secure|open)"""
        Switch.__init__( self, name, **params )
        self.failMode = failMode

    @classmethod
    def setup( cls ):
        "Make sure Open vSwitch is installed and working"
        pathCheck( 'ovs-vsctl',
                   moduleName='Open vSwitch (openvswitch.org)')
        # This should no longer be needed, and it breaks
        # with OVS 1.7 which has renamed the kernel module:
        #  moduleDeps( subtract=OF_KMOD, add=OVS_KMOD )
        out, err, exitcode = errRun( 'ovs-vsctl -t 1 show' )
        if exitcode:
            error( out + err +
                   'ovs-vsctl exited with code %d\n' % exitcode +
                   '*** Error connecting to ovs-db with ovs-vsctl\n'
                   'Make sure that Open vSwitch is installed, '
                   'that ovsdb-server is running, and that\n'
                   '"ovs-vsctl show" works correctly.\n'
                   'You may wish to try '
                   '"service openvswitch-switch start".\n' )
            exit( 1 )

    def dpctl( self, *args ):
        "Run ovs-dpctl command"
        return self.cmd( 'ovs-dpctl', args[ 0 ], self, *args[ 1: ] )

    @staticmethod
    def TCReapply( intf ):
        """Unfortunately OVS and Mininet are fighting
           over tc queuing disciplines. As a quick hack/
           workaround, we clear OVS's and reapply our own."""
        if type( intf ) is TCIntf:
            intf.config( **intf.params )

    def attach( self, intf ):
        "Connect a data port"
        self.cmd( 'ovs-vsctl add-port', self, intf )
        self.cmd( 'ifconfig', intf, 'up' )
        self.TCReapply( intf )

    def detach( self, intf ):
        "Disconnect a data port"
        self.cmd( 'ovs-vsctl del-port', self, intf )

    def start( self, controllers ):
        "Start up a new OVS OpenFlow switch using ovs-vsctl"
        if self.inNamespace:
            raise Exception(
                'OVS kernel switch does not work in a namespace' )
        # We should probably call config instead, but this
        # requires some rethinking...
        self.cmd( 'ifconfig lo up' )
        # Annoyingly, --if-exists option seems not to work
        self.cmd( 'ovs-vsctl del-br', self )
        self.cmd( 'ovs-vsctl add-br', self )
        self.cmd( 'ovs-vsctl -- set Bridge', self,
                  'other_config:datapath-id=' + self.dpid )
        self.cmd( 'ovs-vsctl set-fail-mode', self, self.failMode )
        for intf in self.intfList():
            if not intf.IP():
                self.attach( intf )
        # Add controllers
        clist = ' '.join( [ 'tcp:%s:%d' % ( c.IP(), c.port )
                            for c in controllers ] )
        if self.listenPort:
            clist += ' ptcp:%s' % self.listenPort
        self.cmd( 'ovs-vsctl set-controller', self, clist )

    def stop( self ):
        "Terminate OVS switch."
        self.cmd( 'ovs-vsctl del-br', self )
        self.deleteIntfs()

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
        self.cmd( 'ifconfig lo up' )  # Shouldn't be necessary
        self.checkListening()

    def checkListening( self ):
        "Make sure no controllers are running on our port"
        # Verify that Telnet is installed first:
        out, _err, returnCode = errRun( "which telnet" )
        if 'telnet' not in out or returnCode != 0:
            raise Exception( "Error running telnet to check for listening "
                             "controllers; please check that it is "
                             "installed." )
        listening = self.cmd( "echo A | telnet -e A %s %d" %
                              ( self.ip, self.port ) )
        if 'Unable' not in listening:
            servers = self.cmd( 'netstat -atp' ).split( '\n' )
            pstr = ':%d ' % self.port
            clist = servers[ 0:1 ] + [ s for s in servers if pstr in s ]
            raise Exception( "Please shut down the controller which is"
                             " running on port %d:\n" % self.port +
                             '\n'.join( clist ) )

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

    def __repr__( self ):
        "More informative string representation"
        return '<%s %s: %s:%s pid=%s> ' % (
            self.__class__.__name__, self.name,
            self.IP(), self.port, self.pid )


class OVSController( Controller ):
    "Open vSwitch controller"
    def __init__( self, name, command='ovs-controller', **kwargs ):
        Controller.__init__( self, name, command=command, **kwargs )


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
                             cdir=noxCoreDir,
                             **kwargs )


class RemoteController( Controller ):
    "Controller running outside of Mininet's control."

    def __init__( self, name, ip='127.0.0.1',
                  port=6633, **kwargs):
        """Init.
           name: name to give controller
           ip: the IP address where the remote controller is
           listening
           port: the port where the remote controller is listening"""
        Controller.__init__( self, name, ip=ip, port=port, **kwargs )

    def start( self ):
        "Overridden to do nothing."
        return

    def stop( self ):
        "Overridden to do nothing."
        return

    def checkListening( self ):
        "Warn if remote controller is not accessible"
        listening = self.cmd( "echo A | telnet -e A %s %d" %
                              ( self.ip, self.port ) )
        if 'Unable' in listening:
            warn( "Unable to contact the remote controller"
                  " at %s:%d\n" % ( self.ip, self.port ) )
