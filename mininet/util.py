"Utility functions for Mininet."

from time import sleep
from resource import setrlimit, RLIMIT_NPROC, RLIMIT_NOFILE
from select import poll, POLLIN
from subprocess import call, check_call, Popen, PIPE, STDOUT
from mininet.log import output, info, error
import re

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
        if popen.returncode != None:
            break
    return out

# This is a bit complicated, but it enables us to
# monitor commount output as it is happening

def errRun( *cmd, **kwargs  ):
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
    # We use poll() because select() doesn't work with large fd numbers
    out, err = '', ''
    poller = poll()
    poller.register( popen.stdout, POLLIN )
    fdtofile = { popen.stdout.fileno(): popen.stdout }
    if popen.stderr:
        fdtofile[ popen.stderr.fileno() ] = popen.stderr
        poller.register( popen.stderr, POLLIN )
    while True:
        readable = poller.poll()
        for fd, event in readable:
            f = fdtofile[ fd ]
            data = f.read( 1024 )
            if echo:
                output( data )
            if f == popen.stdout:
                out += data
            elif f == popen.stderr:
                err += data
        returncode = popen.poll()
        if returncode is not None:
           break
    return out, err, returncode

def errFail( *cmd, **kwargs ):
    "Run a command using errRun and raise exception on nonzero exit"
    out, err, ret = errRun( *cmd, **kwargs )
    if ret:
        raise Exception( "errFail: failed with return code %s"
                         % ret )
    return out, err, ret

def quietRun( cmd, **kwargs ):
    "Run a command and return merged stdout and stderr"
    return errRun( cmd, stderr=STDOUT, **kwargs )[ 0 ]

# pylint: enable-msg=E1103
# pylint: disable-msg=E1101,W0612

def isShellBuiltin( cmd ):
    "Return True if cmd is a bash builtin."
    if isShellBuiltin.builtIns is None:
        isShellBuiltin.builtIns = quietRun( 'bash -c enable' )
    space = cmd.find( ' ' )
    if space > 0:
        cmd = cmd[ :space]
    return cmd in isShellBuiltin.builtIns

isShellBuiltin.builtIns = None

# pylint: enable-msg=E1101,W0612

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


# IP and Mac address formatting and parsing

def _colonHex( val, bytes ):
    """Generate colon-hex string.
       val: input as unsigned int
       bytes: number of bytes to convert
       returns: chStr colon-hex string"""
    pieces = []
    for i in range( bytes - 1, -1, -1 ):
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
    w = ( ip & 0xff000000 ) >> 24
    w = 10 if w == 0 else w
    x = ( ip & 0xff0000 ) >> 16
    y = ( ip & 0xff00 ) >> 8
    z = ip & 0xff
    return "%i.%i.%i.%i" % ( w, x, y, z )

def ipNum( w, x, y, z ):
    """Generate unsigned int from components ofIP address
       returns: w << 24 | x << 16 | y << 8 | z"""
    return  ( w << 24 ) | ( x << 16 ) | ( y << 8 ) | z

def ipParse( ip ):
    "Parse an IP address and return an unsigned int."
    args = [ int( arg ) for arg in ip.split( '.' ) ]
    return ipNum( *args )

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


# Other stuff we use

def fixLimits():
    "Fix ridiculously small resource limits."
    setrlimit( RLIMIT_NPROC, ( 4096, 8192 ) )
    setrlimit( RLIMIT_NOFILE, ( 16384, 32768 ) )

def natural( text ):
    "To sort sanely/alphabetically: sorted( l, key=natural )"
    def num( s ):
        return int( s ) if s.isdigit() else text
    return [  num( s ) for s in re.split( r'(\d+)', text ) ]

def numCores():
    "Returns number of CPU cores based on /proc/cpuinfo"
    if hasattr( numCores, 'ncores' ):
        return numCores.ncores
    try:
        numCores.ncores = int( quietRun('grep -c processor /proc/cpuinfo') )
    except ValueError:
        return 0
    return numCores.ncores

def custom( cls, **params ):
    "Returns customized constructor for class cls."
    def customized( *args, **kwargs):
        kwargs.update( params )
        return cls( *args, **kwargs )
    return customized

    
