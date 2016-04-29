"""
Terminal creation and cleanup.
Utility functions to run a terminal (connected via socat(1)) on each host.

Requires socat(1) and xterm(1).
Optionally uses gnome-terminal.
"""
from mininet.log import error
from mininet.util import quietRun, errRun

from os import environ, getpid, path, setsid
from subprocess import Popen, PIPE, STDOUT
from tempfile import NamedTemporaryFile

def getAuthX11( display ):
    "Return X11 credentials for display"
    host, screen = display.split( ':' )
    host = host.split( '/' )[ 0 ]
    hostname = quietRun( 'hostname' ).strip()
    # First, try hostname:display
    if host == 'localhost':
        host = hostname
    result = quietRun( 'xauth list %s:%s' % ( host, screen ) )
    # Otherwise, try hostname/unix:display
    if not result:
        result = quietRun( 'xauth list %s/unix:%s' % ( host, screen ) )
    items = result.strip().split()
    if len( items ) != 3:
        raise Exception( "getAuthX11: could not fetch credentials for " +
                         display )
    return items

# This is tricky with uts and pid namespaces
# For uts namespaces, we create and use a private $XAUTHORITY
# and add credentials for the node's hostname.
# To enable pid namespaces to work, we proxy the X11
# socket twice using socat - first with a shared socket in /tmp, and
# second with a TCP listener in the host network  namespace.
# Note that this will fail if /tmp is not shared - we should
# probably think about this some more. We could potentially
# specify a globally shared directory somehow if /tmp is
# private.

def tunnelX11( node, display=None ):
    """Create an X11 tunnel from node:6000 to the root host
       display: display on root host (optional)
       returns: node $DISPLAY, Popen object for tunnel"""
    if display is None and 'DISPLAY' in environ:
        display = environ[ 'DISPLAY' ]
    if display is None:
        error( "Error: Cannot connect to display\n" )
        return None, None
    host, screen = display.split( ':' )
    # Unix sockets should work
    if not host or host == 'unix':
        # GDM3 doesn't put credentials in .Xauthority,
        # so allow root to just connect
        quietRun( 'xhost +si:localuser:root' )
        return display, None
    else:
        hostname = quietRun( 'hostname' ).strip()
        port = 6000 + int( float( screen ) )
        if 'uts' in node.ns and ( hostname in display or
                                  'localhost' in display ):
            # Use private xauth file, and add credentials
            # for this hostname
            if not hasattr( node, 'xauthFile' ):
                node.xauthFile = NamedTemporaryFile()
            _display, proto, cookie = getAuthX11( display )
            creds = '%s %s %s' % ( '%s/unix:%s' % ( node.name, screen ),
                                   proto, cookie )
            node.cmd( 'export XAUTHORITY=' + node.xauthFile.name )
            node.cmd( 'xauth -f $XAUTHORITY add ' + creds )
        # Create a shared unix socket in /tmp
        # This can conflict if we are running nested Mininet
        # in a pid namespace, and it will also fail if /tmp is not
        # shared
        socket = '/tmp/mininet.x11.%d' % getpid()
        if not hasattr( tunnelX11, 'socket' ):
            cmd = ( 'socat unix-listen:%s,fork tcp:localhost:%d' %
                    ( socket, port  ) ).split()
            tunnelX11.socket = Popen( cmd )
        # Create a tunnel for the TCP connection
        cmd = 'socat tcp-listen:%d,fork,reuseaddr unix:%s' % ( port, socket )
    return 'localhost:' + screen, node.popen( cmd )

def makeTerm( node, title='Node', term='xterm', display=None, cmd='bash'):
    """Create an X11 tunnel to the node and start up a terminal.
       node: Node object
       title: base title
       term: 'xterm' or 'gterm'
       returns: two Popen objects, tunnel and terminal"""
    title = '"%s: %s"' % ( title, node.name )
    if not node.inNamespace:
        title += ' (root)'
    cmds = {
        'xterm': [ 'xterm', '-title', title ],
        'gterm': [ 'gnome-terminal', '--title', title ]
    }
    if term not in cmds:
        error( 'invalid terminal type: %s' % term )
        return
    display, tunnel = tunnelX11( node, display )
    if display is None:
        return []
    env = [ 'env', 'TERM=ansi', 'DISPLAY=%s' % display ]
    if hasattr( node, 'xauthFile' ):
        env += [ 'XAUTHORITY=%s' % node.xauthFile.name ]
    term = node.popen( env + cmds[ term ] + [ '-e', cmd ] )
    return [ tunnel, term ] if tunnel else [ term ]

def runX11( node, cmd ):
    "Run an X11 client on a node"
    _display, tunnel = tunnelX11( node )
    if _display is None:
        return []
    popen = node.popen( cmd )
    return [ tunnel, popen ]

def cleanUpScreens():
    "Remove moldy socat X11 tunnels."
    errRun( "pkill -9 -f socat.*mininet" )

def makeTerms( nodes, title='Node', term='xterm' ):
    """Create terminals.
       nodes: list of Node objects
       title: base title for each
       returns: list of created tunnel/terminal processes"""
    terms = []
    for node in nodes:
        terms += makeTerm( node, title, term )
    return terms
