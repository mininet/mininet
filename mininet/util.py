"Utility functions for Mininet."


from mininet.log import output, info, error, warn, debug

from time import sleep
from resource import getrlimit, setrlimit, RLIMIT_NPROC, RLIMIT_NOFILE
from select import poll, POLLIN, POLLHUP
from subprocess import call, check_call, Popen, PIPE, STDOUT
import re
from fcntl import fcntl, F_GETFL, F_SETFL
from os import O_NONBLOCK
import os
from functools import partial

# Command execution support

def run( cmd ):
    """Simple interface to subprocess.call()
       cmd: list of command params"""
    return call( cmd.split( ' ' ) )

def checkRun( cmd ):
    """Simple interface to subprocess.check_call()
       cmd: list of command params"""
    return check_call( cmd.split( ' ' ) )

# pylint doesn't understand explicit type checking
# pylint: disable=maybe-no-member

def oldQuietRun( *cmd ):
    """Run a command, routing stderr to stdout, and return the output.
       cmd: list of command params"""
    if len( cmd ) == 1:
        cmd = cmd[ 0 ]
        if isinstance( cmd, str ):
            cmd = cmd.split( ' ' )
    popen = Popen( cmd, stdout=PIPE, stderr=STDOUT )
    # We can't use Popen.communicate() because it uses
    # select(), which can't handle
    # high file descriptor numbers! poll() can, however.
    out = ''
    readable = poll()
    readable.register( popen.stdout )
    while True:
        while readable.poll():
            data = popen.stdout.read( 1024 )
            if len( data ) == 0:
                break
            out += data
        popen.poll()
        if popen.returncode is not None:
            break
    return out


# This is a bit complicated, but it enables us to
# monitor command output as it is happening

# pylint: disable=too-many-branches
def errRun( *cmd, **kwargs ):
    """Run a command and return stdout, stderr and return code
       cmd: string or list of command and args
       stderr: STDOUT to merge stderr with stdout
       shell: run command using shell
       echo: monitor output to console"""
    # By default we separate stderr, don't run in a shell, and don't echo
    stderr = kwargs.get( 'stderr', PIPE )
    shell = kwargs.get( 'shell', False )
    echo = kwargs.get( 'echo', False )
    if echo:
        # cmd goes to stderr, output goes to stdout
        info( cmd, '\n' )
    if len( cmd ) == 1:
        cmd = cmd[ 0 ]
    # Allow passing in a list or a string
    if isinstance( cmd, str ) and not shell:
        cmd = cmd.split( ' ' )
        cmd = [ str( arg ) for arg in cmd ]
    elif isinstance( cmd, list ) and shell:
        cmd = " ".join( arg for arg in cmd )
    debug( '*** errRun:', cmd, '\n' )
    popen = Popen( cmd, stdout=PIPE, stderr=stderr, shell=shell )
    # We use poll() because select() doesn't work with large fd numbers,
    # and thus communicate() doesn't work either
    out, err = '', ''
    poller = poll()
    poller.register( popen.stdout, POLLIN )
    fdtofile = { popen.stdout.fileno(): popen.stdout }
    outDone, errDone = False, True
    if popen.stderr:
        fdtofile[ popen.stderr.fileno() ] = popen.stderr
        poller.register( popen.stderr, POLLIN )
        errDone = False
    while not outDone or not errDone:
        readable = poller.poll()
        for fd, event in readable:
            f = fdtofile[ fd ]
            if event & POLLIN:
                data = f.read( 1024 )
                if echo:
                    output( data )
                if f == popen.stdout:
                    out += data
                    if data == '':
                        outDone = True
                elif f == popen.stderr:
                    err += data
                    if data == '':
                        errDone = True
            else:  # POLLHUP or something unexpected
                if f == popen.stdout:
                    outDone = True
                elif f == popen.stderr:
                    errDone = True
                poller.unregister( fd )

    returncode = popen.wait()
    debug( out, err, returncode )
    return out, err, returncode
# pylint: enable=too-many-branches

def errFail( *cmd, **kwargs ):
    "Run a command using errRun and raise exception on nonzero exit"
    out, err, ret = errRun( *cmd, **kwargs )
    if ret:
        raise Exception( "errFail: %s failed with return code %s: %s"
                         % ( cmd, ret, err ) )
    return out, err, ret

def quietRun( cmd, **kwargs ):
    "Run a command and return merged stdout and stderr"
    return errRun( cmd, stderr=STDOUT, **kwargs )[ 0 ]

# pylint: enable=maybe-no-member

def isShellBuiltin( cmd ):
    "Return True if cmd is a bash builtin."
    if isShellBuiltin.builtIns is None:
        isShellBuiltin.builtIns = quietRun( 'bash -c enable' )
    space = cmd.find( ' ' )
    if space > 0:
        cmd = cmd[ :space]
    return cmd in isShellBuiltin.builtIns

isShellBuiltin.builtIns = None

# Interface management
#
# Interfaces are managed as strings which are simply the
# interface names, of the form 'nodeN-ethM'.
#
# To connect nodes, we create a pair of veth interfaces, and then place them
# in the pair of nodes that we want to communicate. We then update the node's
# list of interfaces and connectivity map.
#
# For the kernel datapath, switch interfaces
# live in the root namespace and thus do not have to be
# explicitly moved.

def makeIntfPair( intf1, intf2, addr1=None, addr2=None, node1=None, node2=None,
                  deleteIntfs=True, runCmd=None ):
    """Make a veth pair connnecting new interfaces intf1 and intf2
       intf1: name for interface 1
       intf2: name for interface 2
       addr1: MAC address for interface 1 (optional)
       addr2: MAC address for interface 2 (optional)
       node1: home node for interface 1 (optional)
       node2: home node for interface 2 (optional)
       deleteIntfs: delete intfs before creating them
       runCmd: function to run shell commands (quietRun)
       raises Exception on failure"""
    if not runCmd:
        runCmd = quietRun if not node1 else node1.cmd
        runCmd2 = quietRun if not node2 else node2.cmd
    if deleteIntfs:
        # Delete any old interfaces with the same names
        runCmd( 'ip link del ' + intf1 )
        runCmd2( 'ip link del ' + intf2 )
    # Create new pair
    netns = 1 if not node2 else node2.pid
    if addr1 is None and addr2 is None:
        cmdOutput = runCmd( 'ip link add name %s '
                            'type veth peer name %s '
                            'netns %s' % ( intf1, intf2, netns ) )
    else:
        cmdOutput = runCmd( 'ip link add name %s '
                            'address %s '
                            'type veth peer name %s '
                            'address %s '
                            'netns %s' %
                            (  intf1, addr1, intf2, addr2, netns ) )
    if cmdOutput:
        raise Exception( "Error creating interface pair (%s,%s): %s " %
                         ( intf1, intf2, cmdOutput ) )

def retry( retries, delaySecs, fn, *args, **keywords ):
    """Try something several times before giving up.
       n: number of times to retry
       delaySecs: wait this long between tries
       fn: function to call
       args: args to apply to function call"""
    tries = 0
    while not fn( *args, **keywords ) and tries < retries:
        sleep( delaySecs )
        tries += 1
    if tries >= retries:
        error( "*** gave up after %i retries\n" % tries )
        exit( 1 )

def moveIntfNoRetry( intf, dstNode, printError=False ):
    """Move interface to node, without retrying.
       intf: string, interface
        dstNode: destination Node
        printError: if true, print error"""
    intf = str( intf )
    cmd = 'ip link set %s netns %s' % ( intf, dstNode.pid )
    cmdOutput = quietRun( cmd )
    # If ip link set does not produce any output, then we can assume
    # that the link has been moved successfully.
    if cmdOutput:
        if printError:
            error( '*** Error: moveIntf: ' + intf +
                   ' not successfully moved to ' + dstNode.name + ':\n',
                   cmdOutput )
        return False
    return True

def moveIntf( intf, dstNode, printError=True,
              retries=3, delaySecs=0.001 ):
    """Move interface to node, retrying on failure.
       intf: string, interface
       dstNode: destination Node
       printError: if true, print error"""
    retry( retries, delaySecs, moveIntfNoRetry, intf, dstNode,
           printError=printError )

# Support for dumping network

def dumpNodeConnections( nodes ):
    "Dump connections to/from nodes."

    def dumpConnections( node ):
        "Helper function: dump connections to node"
        for intf in node.intfList():
            output( ' %s:' % intf )
            if intf.link:
                intfs = [ intf.link.intf1, intf.link.intf2 ]
                intfs.remove( intf )
                output( intfs[ 0 ] )
            else:
                output( ' ' )

    for node in nodes:
        output( node.name )
        dumpConnections( node )
        output( '\n' )

def dumpNetConnections( net ):
    "Dump connections in network"
    nodes = net.controllers + net.switches + net.hosts
    dumpNodeConnections( nodes )

def dumpPorts( switches ):
    "dump interface to openflow port mappings for each switch"
    for switch in switches:
        output( '%s ' % switch.name )
        for intf in switch.intfList():
            port = switch.ports[ intf ]
            output( '%s:%d ' % ( intf, port ) )
        output( '\n' )

# IP and Mac address formatting and parsing

def _colonHex( val, bytecount ):
    """Generate colon-hex string.
       val: input as unsigned int
       bytecount: number of bytes to convert
       returns: chStr colon-hex string"""
    pieces = []
    for i in range( bytecount - 1, -1, -1 ):
        piece = ( ( 0xff << ( i * 8 ) ) & val ) >> ( i * 8 )
        pieces.append( '%02x' % piece )
    chStr = ':'.join( pieces )
    return chStr

def macColonHex( mac ):
    """Generate MAC colon-hex string from unsigned int.
       mac: MAC address as unsigned int
       returns: macStr MAC colon-hex string"""
    return _colonHex( mac, 6 )

def ipStr( ip ):
    """Generate IP address string from an unsigned int.
       ip: unsigned int of form w << 24 | x << 16 | y << 8 | z
       returns: ip address string w.x.y.z"""
    w = ( ip >> 24 ) & 0xff
    x = ( ip >> 16 ) & 0xff
    y = ( ip >> 8 ) & 0xff
    z = ip & 0xff
    return "%i.%i.%i.%i" % ( w, x, y, z )

def ipNum( w, x, y, z ):
    """Generate unsigned int from components of IP address
       returns: w << 24 | x << 16 | y << 8 | z"""
    return ( w << 24 ) | ( x << 16 ) | ( y << 8 ) | z

def ipAdd( i, prefixLen=8, ipBaseNum=0x0a000000 ):
    """Return IP address string from ints
       i: int to be added to ipbase
       prefixLen: optional IP prefix length
       ipBaseNum: option base IP address as int
       returns IP address as string"""
    imax = 0xffffffff >> prefixLen
    assert i <= imax, 'Not enough IP addresses in the subnet'
    mask = 0xffffffff ^ imax
    ipnum = ( ipBaseNum & mask ) + i
    return ipStr( ipnum )

def ipParse( ip ):
    "Parse an IP address and return an unsigned int."
    args = [ int( arg ) for arg in ip.split( '.' ) ]
    while len(args) < 4:
        args.insert( len(args) - 1, 0 )
    return ipNum( *args )

def netParse( ipstr ):
    """Parse an IP network specification, returning
       address and prefix len as unsigned ints"""
    prefixLen = 0
    if '/' in ipstr:
        ip, pf = ipstr.split( '/' )
        prefixLen = int( pf )
    #if no prefix is specified, set the prefix to 24
    else:
        ip = ipstr
        prefixLen = 24
    return ipParse( ip ), prefixLen

def checkInt( s ):
    "Check if input string is an int"
    try:
        int( s )
        return True
    except ValueError:
        return False

def checkFloat( s ):
    "Check if input string is a float"
    try:
        float( s )
        return True
    except ValueError:
        return False

def makeNumeric( s ):
    "Convert string to int or float if numeric."
    if checkInt( s ):
        return int( s )
    elif checkFloat( s ):
        return float( s )
    else:
        return s

# Popen support

def pmonitor(popens, timeoutms=500, readline=True,
             readmax=1024 ):
    """Monitor dict of hosts to popen objects
       a line at a time
       timeoutms: timeout for poll()
       readline: return single line of output
       yields: host, line/output (if any)
       terminates: when all EOFs received"""
    poller = poll()
    fdToHost = {}
    for host, popen in popens.iteritems():
        fd = popen.stdout.fileno()
        fdToHost[ fd ] = host
        poller.register( fd, POLLIN )
        if not readline:
            # Use non-blocking reads
            flags = fcntl( fd, F_GETFL )
            fcntl( fd, F_SETFL, flags | O_NONBLOCK )
    while popens:
        fds = poller.poll( timeoutms )
        if fds:
            for fd, event in fds:
                host = fdToHost[ fd ]
                popen = popens[ host ]
                if event & POLLIN:
                    if readline:
                        # Attempt to read a line of output
                        # This blocks until we receive a newline!
                        line = popen.stdout.readline()
                    else:
                        line = popen.stdout.read( readmax )
                    yield host, line
                # Check for EOF
                elif event & POLLHUP:
                    poller.unregister( fd )
                    del popens[ host ]
        else:
            yield None, ''

# Other stuff we use
def sysctlTestAndSet( name, limit ):
    "Helper function to set sysctl limits"
    #convert non-directory names into directory names
    if '/' not in name:
        name = '/proc/sys/' + name.replace( '.', '/' )
    #read limit
    with open( name, 'r' ) as readFile:
        oldLimit = readFile.readline()
        if isinstance( limit, int ):
            #compare integer limits before overriding
            if int( oldLimit ) < limit:
                with open( name, 'w' ) as writeFile:
                    writeFile.write( "%d" % limit )
        else:
            #overwrite non-integer limits
            with open( name, 'w' ) as writeFile:
                writeFile.write( limit )

def rlimitTestAndSet( name, limit ):
    "Helper function to set rlimits"
    soft, hard = getrlimit( name )
    if soft < limit:
        hardLimit = hard if limit < hard else limit
        setrlimit( name, ( limit, hardLimit ) )

def fixLimits():
    "Fix ridiculously small resource limits."
    debug( "*** Setting resource limits\n" )
    try:
        rlimitTestAndSet( RLIMIT_NPROC, 8192 )
        rlimitTestAndSet( RLIMIT_NOFILE, 16384 )
        #Increase open file limit
        sysctlTestAndSet( 'fs.file-max', 10000 )
        #Increase network buffer space
        sysctlTestAndSet( 'net.core.wmem_max', 16777216 )
        sysctlTestAndSet( 'net.core.rmem_max', 16777216 )
        sysctlTestAndSet( 'net.ipv4.tcp_rmem', '10240 87380 16777216' )
        sysctlTestAndSet( 'net.ipv4.tcp_wmem', '10240 87380 16777216' )
        sysctlTestAndSet( 'net.core.netdev_max_backlog', 5000 )
        #Increase arp cache size
        sysctlTestAndSet( 'net.ipv4.neigh.default.gc_thresh1', 4096 )
        sysctlTestAndSet( 'net.ipv4.neigh.default.gc_thresh2', 8192 )
        sysctlTestAndSet( 'net.ipv4.neigh.default.gc_thresh3', 16384 )
        #Increase routing table size
        sysctlTestAndSet( 'net.ipv4.route.max_size', 32768 )
        #Increase number of PTYs for nodes
        sysctlTestAndSet( 'kernel.pty.max', 20000 )
    # pylint: disable=broad-except
    except Exception:
        warn( "*** Error setting resource limits. "
              "Mininet's performance may be affected.\n" )
    # pylint: enable=broad-except


def mountCgroups():
    "Make sure cgroups file system is mounted"
    mounts = quietRun( 'cat /proc/mounts' )
    cgdir = '/sys/fs/cgroup'
    csdir = cgdir + '/cpuset'
    if ('cgroup %s' % cgdir not in mounts and
            'cgroups %s' % cgdir not in mounts):
        raise Exception( "cgroups not mounted on " + cgdir )
    if 'cpuset %s' % csdir not in mounts:
        errRun( 'mkdir -p ' + csdir )
        errRun( 'mount -t cgroup -ocpuset cpuset ' + csdir )

def natural( text ):
    "To sort sanely/alphabetically: sorted( l, key=natural )"
    def num( s ):
        "Convert text segment to int if necessary"
        return int( s ) if s.isdigit() else s
    return [  num( s ) for s in re.split( r'(\d+)', str( text ) ) ]

def naturalSeq( t ):
    "Natural sort key function for sequences"
    return [ natural( x ) for x in t ]

def numCores():
    "Returns number of CPU cores based on /proc/cpuinfo"
    if hasattr( numCores, 'ncores' ):
        return numCores.ncores
    try:
        numCores.ncores = int( quietRun('grep -c processor /proc/cpuinfo') )
    except ValueError:
        return 0
    return numCores.ncores

def irange(start, end):
    """Inclusive range from start to end (vs. Python insanity.)
       irange(1,5) -> 1, 2, 3, 4, 5"""
    return range( start, end + 1 )

def custom( cls, **params ):
    "Returns customized constructor for class cls."
    # Note: we may wish to see if we can use functools.partial() here
    # and in customConstructor
    def customized( *args, **kwargs):
        "Customized constructor"
        kwargs = kwargs.copy()
        kwargs.update( params )
        return cls( *args, **kwargs )
    customized.__name__ = 'custom(%s,%s)' % ( cls, params )
    return customized

def splitArgs( argstr ):
    """Split argument string into usable python arguments
       argstr: argument string with format fn,arg2,kw1=arg3...
       returns: fn, args, kwargs"""
    split = argstr.split( ',' )
    fn = split[ 0 ]
    params = split[ 1: ]
    # Convert int and float args; removes the need for function
    # to be flexible with input arg formats.
    args = [ makeNumeric( s ) for s in params if '=' not in s ]
    kwargs = {}
    for s in [ p for p in params if '=' in p ]:
        key, val = s.split( '=', 1 )
        kwargs[ key ] = makeNumeric( val )
    return fn, args, kwargs

def customClass( classes, argStr ):
    """Return customized class based on argStr
    The args and key/val pairs in argStr will be automatically applied
    when the generated class is later used.
    """
    cname, args, kwargs = splitArgs( argStr )
    cls = classes.get( cname, None )
    if not cls:
        raise Exception( "error: %s is unknown - please specify one of %s" %
                         ( cname, classes.keys() ) )
    if not args and not kwargs:
        return cls

    return specialClass( cls, append=args, defaults=kwargs )

def specialClass( cls, prepend=None, append=None,
                  defaults=None, override=None ):
    """Like functools.partial, but it returns a class
       prepend: arguments to prepend to argument list
       append: arguments to append to argument list
       defaults: default values for keyword arguments
       override: keyword arguments to override"""

    if prepend is None:
        prepend = []

    if append is None:
        append = []

    if defaults is None:
        defaults = {}

    if override is None:
        override = {}

    class CustomClass( cls ):
        "Customized subclass with preset args/params"
        def __init__( self, *args, **params ):
            newparams = defaults.copy()
            newparams.update( params )
            newparams.update( override )
            cls.__init__( self, *( list( prepend ) + list( args ) +
                                   list( append ) ),
                          **newparams )

    CustomClass.__name__ = '%s%s' % ( cls.__name__, defaults )
    return CustomClass


def buildTopo( topos, topoStr ):
    """Create topology from string with format (object, arg1, arg2,...).
    input topos is a dict of topo names to constructors, possibly w/args.
    """
    topo, args, kwargs = splitArgs( topoStr )
    if topo not in topos:
        raise Exception( 'Invalid topo name %s' % topo )
    return topos[ topo ]( *args, **kwargs )

def ensureRoot():
    """Ensure that we are running as root.

    Probably we should only sudo when needed as per Big Switch's patch.
    """
    if os.getuid() != 0:
        print( "*** Mininet must run as root." )
        exit( 1 )
    return

def waitListening( client=None, server='127.0.0.1', port=80, timeout=None ):
    """Wait until server is listening on port.
       returns True if server is listening"""
    runCmd = ( client.cmd if client else
               partial( quietRun, shell=True ) )
    if not runCmd( 'which telnet' ):
        raise Exception('Could not find telnet' )
    # pylint: disable=maybe-no-member
    serverIP = server if isinstance( server, basestring ) else server.IP()
    cmd = ( 'echo A | telnet -e A %s %s' % ( serverIP, port ) )
    time = 0
    result = runCmd( cmd )
    while 'Connected' not in result:
        if 'No route' in result:
            rtable = runCmd( 'route' )
            error( 'no route to %s:\n%s' % ( server, rtable ) )
            return False
        if timeout and time >= timeout:
            error( 'could not connect to %s on port %d\n' % ( server, port ) )
            return False
        debug( 'waiting for', server, 'to listen on port', port, '\n' )
        info( '.' )
        sleep( .5 )
        time += .5
        result = runCmd( cmd )
    return True
