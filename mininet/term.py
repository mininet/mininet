"""
Terminal creation and cleanup.
Utility functions to run a terminal (connected via socat(1)) on each host.

Requires socat(1) and xterm(1).
Optionally uses gnome-terminal.
"""
from mininet.log import error
from mininet.util import quietRun, errRun

from os import environ, getpid, path
from subprocess import Popen
from tempfile import NamedTemporaryFile

def tunnelX11( node, display=None):
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
        # XXX Need to handle case where node is in UTS namespace
        # in this case, we need to set XAUTHORITY to a private
        # xauth file
        if False and 'uts' in node.inNamespace and  not hasattr( node, 'xauthFile' ):
            node.xauthFile = NamedTemporaryFile()
            quietRun( 'xauth extract $DISPLAY | xauth -f %s merge' % node.xauthFile.name )
        port = 6000 + int( float( screen ) )
        # This can conflict if we are running nested Mininet
        # in a pid namespace
        socket = '/tmp/mininet.x11.%d' % getpid()
        if not path.exists( socket ):
            cmd = 'socat unix-listen:%s,fork tcp:localhost:%d' % ( socket, port  )
            # Should be shut down when mn shuts down
            tunnelX11.socket = Popen( cmd, shell=True )
        # Create a tunnel for the TCP connection
        cmd = 'socat tcp-listen:%d,fork,reuseaddr unix:%s' % ( port, socket )

    return 'localhost:' + screen, node.popen( cmd )

"""

With pid namespaces, we can't easily escape the pid jail using mnexec
(or can we?)

What we can do, however, is create a unix socket in /tmp which connects
to our x server, and a tcp listener in the host that connects to our
unix socket!

We just have to make sure that we clean up our processes and sockets
when we quit.

If we're using UTS namespaces, then xauth will get confused because
our hostname has changed. So, we use a private XAUTHORITY file per
host. We need to initialize this file with the key of our X server;
this is a bit hard to figure out because the usual xauth list $DISPLAY
may fail even if xlib can figure out a backup cookie to use.

But what about namespace conflicts? This could certainly be very
annoying for nested mininet!! In this case, our nested mininet servers
should have a private /tmp that they can use.... except that conflicts
with the shared unix domain socket in /tmp! ;-p

We could also use a random name for the socket, to avoid the namespace
conflict, although it's not clear what to do for cleanup to avoid
blasting this....

Perhaps the best idea is to use a canonical name (mininet.x11) and if the
first name fails, try a second name??

Another idea is to create a tmp dir for Mininet based on the pid of the
mn process.....

recommendation: for now, use mininet.x11.1234 as the socket.

"""



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
        'xterm': [ 'xterm', '-title', title, '-display' ],
        'gterm': [ 'gnome-terminal', '--title', title, '--display' ]
    }
    if term not in cmds:
        error( 'invalid terminal type: %s' % term )
        return
    display, tunnel = tunnelX11( node, display )
    if display is None:
        return []
    term = node.popen( cmds[ term ] +
                       [ display, '-e', 'env TERM=ansi %s' % cmd ] )
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
    errRun( "pkill -9 -f mnexec.*socat" )

def makeTerms( nodes, title='Node', term='xterm' ):
    """Create terminals.
       nodes: list of Node objects
       title: base title for each
       returns: list of created tunnel/terminal processes"""
    terms = []
    for node in nodes:
        terms += makeTerm( node, title, term )
    return terms
