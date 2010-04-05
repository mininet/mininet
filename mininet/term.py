"""
Terminal creation and cleanup.
Utility functions to run a term (connected via screen(1)) on each host.

Requires GNU screen(1) and xterm(1).
Optionally uses gnome-terminal.
"""

import re
from subprocess import Popen

from mininet.log import error
from mininet.util import quietRun

def makeTerm( node, title = '', term = 'xterm' ):
    """Run screen on a node, and hook up an xterm.
       node: Node object
       title: base title
       returns: process created"""
    title += ': ' + node.name
    if not node.inNamespace:
        title += ' (root)'
    cmd = ''
    if term == 'xterm':
        cmd = [ 'xterm', '-title', title, '-e' ]
    elif term == 'gnome':
        cmd = [ 'gnome-terminal', '--title', title, '-e' ]
    else:
        error( 'invalid terminal type: %s' % term )
        return
    if not node.execed:
        node.cmd( 'screen -dmS ' + node.name)
        #cmd += [ 'screen', '-D', '-RR', '-S', node.name ]
        # Compress these for gnome-terminal, which expects one token to follow
        # the -e option    .
        cmd += [ 'screen -D -RR -S ' + node.name ]
    else:
        cmd += [ 'sh', '-c', 'exec tail -f /tmp/' + node.name + '*.log' ]
    return Popen( cmd )

def cleanUpScreens():
    "Remove moldy old screen sessions."
    r = r'(\d+.[hsc]\d+)'
    output = quietRun( 'screen -ls' ).split( '\n' )
    for line in output:
        m = re.search( r, line )
        if m:
            quietRun( 'screen -S ' + m.group( 1 ) + ' -X quit' )

def makeTerms( nodes, title = '', term = 'xterm' ):
    """Create terminals.
       nodes: list of Node objects
       title: base title for each
       returns: list of created terminal processes"""
    return [ makeTerm( node, title, term ) for node in nodes ]
