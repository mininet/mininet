"""
A simple command-line interface for Mininet.

The Mininet CLI provides a simple control console which
makes it easy to talk to nodes. For example, the command

mininet> h27 ifconfig

runs 'ifconfig' on host h27.

Having a single console rather than, for example, an xterm for each
node is particularly convenient for networks of any reasonable
size.

The CLI automatically substitutes IP addresses for node names,
so commands like

mininet> h2 ping h3

should work correctly and allow host h2 to ping host h3

Several useful commands are provided, including the ability to
list all nodes ('nodes'), to print out the network topology
('net') and to check connectivity ('pingall', 'pingpair')
and bandwidth ('iperf'.)
"""

from subprocess import call
from cmd import Cmd
from os import isatty
from select import poll, POLLIN
import sys

from mininet.log import info, output, error
from mininet.term import makeTerms
from mininet.util import quietRun, isShellBuiltin

class CLI( Cmd ):
    "Simple command-line interface to talk to nodes."

    prompt = 'mininet> '

    def __init__( self, mininet, stdin=sys.stdin, script=None ):
        self.mn = mininet
        self.nodelist = self.mn.controllers + self.mn.switches + self.mn.hosts
        self.nodemap = {}  # map names to Node objects
        for node in self.nodelist:
            self.nodemap[ node.name ] = node
        # Attempt to handle input
        self.stdin = stdin
        self.inPoller = poll()
        self.inPoller.register( stdin )
        self.inputFile = script
        Cmd.__init__( self )
        info( '*** Starting CLI:\n' )
        if self.inputFile:
            self.do_source( self.inputFile )
            return
        while True:
            try:
                # Make sure no nodes are still waiting
                for node in self.nodelist:
                    while node.waiting:
                        node.sendInt()
                        node.monitor()
                if self.isatty():
                    quietRun( 'stty sane' )
                self.cmdloop()
                break
            except KeyboardInterrupt:
                output( '\nInterrupt\n' )

    def emptyline( self ):
        "Don't repeat last command when you hit return."
        pass

    # Disable pylint "Unused argument: 'arg's'" messages, as well as
    # "method could be a function" warning, since each CLI function
    # must have the same interface
    # pylint: disable-msg=W0613,R0201

    helpStr = (
        'You may also send a command to a node using:\n'
        '  <node> command {args}\n'
        'For example:\n'
        '  mininet> h1 ifconfig\n'
        '\n'
        'The interpreter automatically substitutes IP addresses\n'
        'for node names when a node is the first arg, so commands\n'
        'like\n'
        '  mininet> h2 ping h3\n'
        'should work.\n'
        '\n'
        'Some character-oriented interactive commands require\n'
        'noecho:\n'
        '  mininet> noecho h2 vi foo.py\n'
        'However, starting up an xterm/gterm is generally better:\n'
        '  mininet> xterm h2\n\n'
    )

    def do_help( self, line ):
        "Describe available CLI commands."
        Cmd.do_help( self, line )
        if line is '':
            output( self.helpStr )

    def do_nodes( self, line ):
        "List all nodes."
        nodes = ' '.join( [ node.name for node in sorted( self.nodelist ) ] )
        output( 'available nodes are: \n%s\n' % nodes )

    def do_net( self, line ):
        "List network connections."
        for switch in self.mn.switches:
            output( switch.name, '<->' )
            for intf in switch.intfs.values():
                # Ugly, but pylint wants it
                name = switch.connection.get( intf,
                    ( None, 'Unknown ' ) )[ 1 ]
                output( ' %s' % name )
            output( '\n' )

    def do_sh( self, line ):
        "Run an external shell command"
        call( line, shell=True )

    # do_py() needs to catch any exception during eval()
    # pylint: disable-msg=W0703

    def do_py( self, line ):
        """Evaluate a Python expression.
           Node names may be used, e.g.: h1.cmd('ls')"""
        try:
            result = eval( line, globals(), self.nodemap )
            if not result:
                return
            elif isinstance( result, str ):
                output( result + '\n' )
            else:
                output( repr( result ) + '\n' )
        except Exception, e:
            output( str( e ) + '\n' )

    # pylint: enable-msg=W0703

    def do_pingall( self, line ):
        "Ping between all hosts."
        self.mn.pingAll()

    def do_pingpair( self, line ):
        "Ping between first two hosts, useful for testing."
        self.mn.pingPair()

    def do_iperf( self, line ):
        "Simple iperf TCP test between two (optionally specified) hosts."
        args = line.split()
        if not args:
            self.mn.iperf()
        elif len(args) == 2:
            hosts = []
            err = False
            for arg in args:
                if arg not in self.nodemap:
                    err = True
                    error( "node '%s' not in network\n" % arg )
                else:
                    hosts.append( self.nodemap[ arg ] )
            if not err:
                self.mn.iperf( hosts )
        else:
            error( 'invalid number of args: iperf src dst\n' )

    def do_iperfudp( self, line ):
        "Simple iperf TCP test between two (optionally specified) hosts."
        args = line.split()
        if not args:
            self.mn.iperf( l4Type='UDP' )
        elif len(args) == 3:
            udpBw = args[ 0 ]
            hosts = []
            err = False
            for arg in args[ 1:3 ]:
                if arg not in self.nodemap:
                    err = True
                    error( "node '%s' not in network\n" % arg )
                else:
                    hosts.append( self.nodemap[ arg ] )
            if not err:
                self.mn.iperf( hosts, l4Type='UDP', udpBw=udpBw )
        else:
            error( 'invalid number of args: iperfudp bw src dst\n' +
                   'bw examples: 10M\n' )

    def do_intfs( self, line ):
        "List interfaces."
        for node in self.nodelist:
            output( '%s: %s\n' %
                ( node.name, ' '.join( sorted( node.intfs.values() ) ) ) )

    def do_dump( self, line ):
        "Dump node info."
        for node in self.nodelist:
            output( '%s\n' % node )

    def do_link( self, line ):
        "Bring link(s) between two nodes up or down."
        args = line.split()
        if len(args) != 3:
            error( 'invalid number of args: link end1 end2 [up down]\n' )
        elif args[ 2 ] not in [ 'up', 'down' ]:
            error( 'invalid type: link end1 end2 [up down]\n' )
        else:
            self.mn.configLinkStatus( *args )

    def do_xterm( self, line, term='xterm' ):
        "Spawn xterm(s) for the given node(s)."
        args = line.split()
        if not args:
            error( 'usage: %s node1 node2 ...\n' % term )
        else:
            for arg in args:
                if arg not in self.nodemap:
                    error( "node '%s' not in network\n" % arg )
                else:
                    node = self.nodemap[ arg ]
                    self.mn.terms += makeTerms( [ node ], term = term )

    def do_gterm( self, line ):
        "Spawn gnome-terminal(s) for the given node(s)."
        self.do_xterm( line, term='gterm' )

    def do_exit( self, line ):
        "Exit"
        return 'exited by user command'

    def do_quit( self, line ):
        "Exit"
        return self.do_exit( line )

    def do_EOF( self, line ):
        "Exit"
        output( '\n' )
        return self.do_exit( line )

    def isatty( self ):
        "Is our standard input a tty?"
        return isatty( self.stdin.fileno() )

    def do_noecho( self, line ):
        "Run an interactive command with echoing turned off."
        if self.isatty():
            quietRun( 'stty -echo' )
        self.default( line )
        if self.isatty():
            quietRun( 'stty echo' )

    def do_source( self, line ):
        "Read commands from an input file."
        args = line.split()
        if len(args) != 1:
            error( 'usage: source <file>\n' )
            return
        try:
            self.inputFile = open( args[ 0 ] )
            while True:
                line = self.inputFile.readline()
                if len( line ) > 0:
                    self.onecmd( line )
                else:
                    break
        except IOError:
            error( 'error reading file %s\n' % args[ 0 ] )
        self.inputFile = None

    def do_dpctl( self, line ):
        "Run dpctl command on all switches."
        args = line.split()
        if len(args) == 0:
            error( 'usage: dpctl command [arg1] [arg2] ...\n' )
            return
        if not self.mn.listenPort:
            error( "can't run dpctl w/no passive listening port\n")
            return
        for sw in self.mn.switches:
            output( '*** ' + sw.name + ' ' + ('-' * 72) + '\n' )
            output( sw.cmd( 'dpctl ' + ' '.join(args) +
                            ' tcp:127.0.0.1:%i' % sw.listenPort ) )

    def default( self, line ):
        """Called on an input line when the command prefix is not recognized.
        Overridden to run shell commands when a node is the first CLI argument.
        Past the first CLI argument, node names are automatically replaced with
        corresponding IP addrs."""

        first, args, line = self.parseline( line )
        if args and len(args) > 0 and args[ -1 ] == '\n':
            args = args[ :-1 ]
        rest = args.split( ' ' )

        if first in self.nodemap:
            node = self.nodemap[ first ]
            # Substitute IP addresses for node names in command
            rest = [ self.nodemap[ arg ].IP()
                    if arg in self.nodemap else arg
                    for arg in rest ]
            rest = ' '.join( rest )
            # Run cmd on node:
            builtin = isShellBuiltin( first )
            node.sendCmd( rest, printPid=( not builtin ) )
            self.waitForNode( node )
        else:
            error( '*** Unknown command: %s\n' % first )

    # pylint: enable-msg=W0613,R0201

    def waitForNode( self, node ):
        "Wait for a node to finish, and  print its output."
        # Pollers
        nodePoller = poll()
        nodePoller.register( node.stdout )
        bothPoller = poll()
        bothPoller.register( self.stdin )
        bothPoller.register( node.stdout )
        if self.isatty():
            # Buffer by character, so that interactive
            # commands sort of work
            quietRun( 'stty -icanon min 1' )
        while True:
            try:
                bothPoller.poll()
                # XXX BL: this doesn't quite do what we want.
                if False and self.inputFile:
                    key = self.inputFile.read( 1 )
                    if key is not '':
                        node.write(key)
                    else:
                        self.inputFile = None
                if isReadable( self.inPoller ):
                    key = self.stdin.read( 1 )
                    node.write( key )
                if isReadable( nodePoller ):
                    data = node.monitor()
                    output( data )
                if not node.waiting:
                    break
            except KeyboardInterrupt:
                node.sendInt()

# Helper functions

def isReadable( poller ):
    "Check whether a Poll object has a readable fd."
    for fdmask in poller.poll( 0 ):
        mask = fdmask[ 1 ]
        if mask & POLLIN:
            return True
