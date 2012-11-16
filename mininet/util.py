"Utility functions for Mininet."

from mininet.log import output, info, error, warn

from time import sleep
from resource import setrlimit, RLIMIT_NPROC, RLIMIT_NOFILE
from select import poll, POLLIN
from subprocess import call, check_call, Popen, PIPE, STDOUT
import re
from fcntl import fcntl, F_GETFL, F_SETFL
from os import O_NONBLOCK
import os

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
# pylint: disable-msg=E1103

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

def errRun( *cmd, **kwargs ):
    """Run a command and return stdout, stderr and return code
       cmd: string or list of command and args
       stderr: STDOUT to merge stderr with stdout
       shell: run command using shell
       echo: monitor output to console"""
    # Allow passing in a list or a string
    if len( cmd ) == 1:
        cmd = cmd[ 0 ]
        if isinstance( cmd, str ):
            cmd = cmd.split( ' ' )
    cmd = [ str( arg ) for arg in cmd ]
    # By default we separate stderr, don't run in a shell, and don't echo
    stderr = kwargs.get( 'stderr', PIPE )
    shell = kwargs.get( 'shell', False )
    echo = kwargs.get( 'echo', False )
    if echo:
        # cmd goes to stderr, output goes to stdout
        info( cmd, '\n' )
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
        for fd, _event in readable:
            f = fdtofile[ fd ]
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
    returncode = popen.wait()
    return out, err, returncode

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

# pylint: enable-msg=E1103
# pylint: disable-msg=E1101

def isShellBuiltin( cmd ):
    "Return True if cmd is a bash builtin."
    if isShellBuiltin.builtIns is None:
        isShellBuiltin.builtIns = quietRun( 'bash -c enable' )
    space = cmd.find( ' ' )
    if space > 0:
        cmd = cmd[ :space]
    return cmd in isShellBuiltin.builtIns

isShellBuiltin.builtIns = None

# pylint: enable-msg=E1101

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

def makeIntfPair( intf1, intf2 ):
    """Make a veth pair connecting intf1 and intf2.
       intf1: string, interface
       intf2: string, interface
       returns: success boolean"""
    # Delete any old interfaces with the same names
    quietRun( 'ip link del ' + intf1 )
    quietRun( 'ip link del ' + intf2 )
    # Create new pair
    cmd = 'ip link add name ' + intf1 + ' type veth peer name ' + intf2
    return quietRun( cmd )

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

def moveIntfNoRetry( intf, node, printError=False ):
    """Move interface to node, without retrying.
       intf: string, interface
       node: Node object
       printError: if true, print error"""
    cmd = 'ip link set ' + intf + ' netns ' + repr( node.pid )
    quietRun( cmd )
    links = node.cmd( 'ip link show' )
    if not ( ' %s:' % intf ) in links:
        if printError:
            error( '*** Error: moveIntf: ' + intf +
                   ' not successfully moved to ' + node.name + '\n' )
        return False
    return True

def moveIntf( intf, node, printError=False, retries=3, delaySecs=0.001 ):
    """Move interface to node, retrying on failure.
       intf: string, interface
       node: Node object
       printError: if true, print error"""
    retry( retries, delaySecs, moveIntfNoRetry, intf, node, printError )

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
       returns: ip address string w.x.y.z, or 10.x.y.z if w==0"""
    w = ( ip >> 24 ) & 0xff
    w = 10 if w == 0 else w
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
    # Ugly but functional
    assert i < ( 1 << ( 32 - prefixLen ) )
    mask = 0xffffffff ^ ( ( 1 << prefixLen ) - 1 )
    ipnum = i + ( ipBaseNum & mask )
    return ipStr( ipnum )

def ipParse( ip ):
    "Parse an IP address and return an unsigned int."
    args = [ int( arg ) for arg in ip.split( '.' ) ]
    return ipNum( *args )

def netParse( ipstr ):
    """Parse an IP network specification, returning
       address and prefix len as unsigned ints"""
    prefixLen = 0
    if '/' in ipstr:
        ip, pf = ipstr.split( '/' )
        prefixLen = int( pf )
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
    while True:
        fds = poller.poll( timeoutms )
        if fds:
            for fd, _event in fds:
                host = fdToHost[ fd ]
                popen = popens[ host ]
                if readline:
                    # Attempt to read a line of output
                    # This blocks until we receive a newline!
                    line = popen.stdout.readline()
                else:
                    line = popen.stdout.read( readmax )
                yield host, line
                # Check for EOF
                if not line:
                    popen.poll()
                    if popen.returncode is not None:
                        poller.unregister( fd )
                        del popens[ host ]
                        if not popens:
                            return
        else:
            yield None, ''

# Other stuff we use

def fixLimits():
    "Fix ridiculously small resource limits."
    setrlimit( RLIMIT_NPROC, ( 8192, 8192 ) )
    setrlimit( RLIMIT_NOFILE, ( 16384, 16384 ) )

def mountCgroups():
    "Make sure cgroups file system is mounted"
    mounts = quietRun( 'mount' )
    cgdir = '/sys/fs/cgroup'
    csdir = cgdir + '/cpuset'
    if ('cgroup on %s' % cgdir not in mounts and
            'cgroups on %s' % cgdir not in mounts):
        raise Exception( "cgroups not mounted on " + cgdir )
    if 'cpuset on %s' % csdir not in mounts:
        errRun( 'mkdir -p ' + csdir )
        errRun( 'mount -t cgroup -ocpuset cpuset ' + csdir )

def natural( text ):
    "To sort sanely/alphabetically: sorted( l, key=natural )"
    def num( s ):
        "Convert text segment to int if necessary"
        return int( s ) if s.isdigit() else s
    return [  num( s ) for s in re.split( r'(\d+)', text ) ]

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
        key, val = s.split( '=' )
        kwargs[ key ] = makeNumeric( val )
    return fn, args, kwargs

def customConstructor( constructors, argStr ):
    """Return custom constructor based on argStr
    The args and key/val pairs in argsStr will be automatically applied
    when the generated constructor is later used.
    """
    cname, newargs, kwargs = splitArgs( argStr )
    constructor = constructors.get( cname, None )

    if not constructor:
        raise Exception( "error: %s is unknown - please specify one of %s" %
                         ( cname, constructors.keys() ) )

    def customized( name, *args, **params ):
        "Customized constructor, useful for Node, Link, and other classes"
        params = params.copy()
        params.update( kwargs )
        if not newargs:
            return constructor( name, *args, **params )
        if args:
            warn( 'warning: %s replacing %s with %s\n' % (
                  constructor, args, newargs ) )
        return constructor( name, *newargs, **params )

    customized.__name__ = 'customConstructor(%s)' % argStr
    return customized

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
        print "*** Mininet must run as root."
        exit( 1 )
    return
