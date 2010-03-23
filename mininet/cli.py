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

Bugs/limitations:

- Interactive commands are not supported at the moment

"""

from subprocess import call
from cmd import Cmd

from mininet.log import info, output, error

        
class CLI( Cmd ):
    "Simple command-line interface to talk to nodes."

    prompt = 'mininet> '

    def __init__( self, mininet ):
        self.mn = mininet
        self.nodelist = self.mn.controllers + self.mn.switches + self.mn.hosts
        self.nodemap = {}  # map names to Node objects
        for node in self.nodelist:
            self.nodemap[ node.name ] = node
        Cmd.__init__( self )
        info( '*** Starting CLI:\n' )
        while True:
            try:
                self.cmdloop()
                break
            except KeyboardInterrupt:
                info( 'Interrupt\n' )
                for node in self.nodelist:
                    waitForNode( node )

    def emptyline( self ):
        "Don't repeat last command when you hit return."
        pass

    # Disable pylint "Unused argument: 'arg's'" messages, as well as
    # "method could be a function" warning, since each CLI function
    # must have the same interface
    # pylint: disable-msg=W0613,R0201

    def do_help( self, args ):
        "Describe available CLI commands."
        Cmd.do_help( self, args )
        helpStr = ( 'You may also send a command to a node using:\n'
                   '  <node> command {args}\n'
                   'For example:\n'
                   '  mininet> h0 ifconfig\n'
                   '\n'
                   'The interpreter automatically substitutes IP '
                   'addresses\n'
                   'for node names when a node is the first arg, so commands'
                   ' like\n'
                   ' mininet> h2 ping h3\n'
                   'should work.\n'
                   '\n'
                   'Interactive commands are not supported yet.\n' )
        if args is "":
            self.stdout.write( helpStr )

    def do_nodes( self, args ):
        "List all nodes."
        nodes = ' '.join( [ node.name for node in sorted( self.nodelist ) ] )
        output( 'available nodes are: \n%s\n' % nodes )

    def do_net( self, args ):
        "List network connections."
        for switch in self.mn.switches:
            output( switch.name, '<->' )
            for intf in switch.intfs.values():
                name = switch.connection[ intf ][ 1 ]
                output( ' %s' % name )
            output( '\n' )

    def do_sh( self, args ):
        "Run an external shell command"
        call( args, shell=True )

    # do_py() needs to catch any exception during eval()
    # pylint: disable-msg=W0703

    def do_py( self, args ):
        """Evaluate a Python expression.
           Node names may be used, e.g.: h1.cmd('ls')"""
        try:
            result = eval( args, globals(), self.nodemap )
            if not result:
                return
            elif isinstance( result, str ):
                info( result + '\n' )
            else:
                info( repr( result ) + '\n' )
        except Exception, e:
            info( str( e ) + '\n' )

    # pylint: enable-msg=W0703

    def do_pingall( self, args ):
        "Ping between all hosts."
        self.mn.pingAll()

    def do_pingpair( self, args ):
        "Ping between first two hosts, useful for testing."
        self.mn.pingPair()

    def do_iperf( self, args ):
        "Simple iperf TCP test between two hosts."
        self.mn.iperf()

    def do_iperfudp( self, args ):
        "Simple iperf UDP test between two hosts."
        udpBw = args[ 0 ] if len( args ) else '10M'
        self.mn.iperfUdp( udpBw )

    def do_intfs( self, args ):
        "List interfaces."
        for node in self.nodelist:
            output( '%s: %s\n' %
                ( node.name, ' '.join( sorted( node.intfs.values() ) ) ) )

    def do_dump( self, args ):
        "Dump node info."
        for node in self.nodelist:
            output( '%s\n' % node )

    def do_link( self, args ):
        "Bring link(s) between two nodes up or down."
        args = args.split()
        if len(args) != 3:
            error( 'invalid number of args: link end1 end2 [up down]\n' )
        elif args[ 2 ] not in [ 'up', 'down' ]:
            error( 'invalid type: link end1 end2 [up down]\n' )
        else:
            self.mn.configLinkStatus( *args )

    def do_exit( self, args ):
        "Exit"
        return 'exited by user command'

    def do_quit( self, args ):
        "Exit"
        return self.do_exit( args )

    def do_EOF( self, args ):
        "Exit"
        return self.do_exit( args )

    def default( self, line ):
        """Called on an input line when the command prefix is not recognized.
        Overridden to run shell commands when a node is the first CLI argument.
        Past the first CLI argument, node names are automatically replaced with
        corresponding IP addrs."""

        first, args, line = self.parseline( line )
        if len(args) > 0 and args[ -1 ] == '\n':
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
            node.sendCmd( rest, printPid=True )
            waitForNode( node )
        else:
            self.stdout.write( '*** Unknown syntax: %s\n' % line )

    # pylint: enable-msg=W0613,R0201


# This function may be a candidate for util.py

def waitForNode( node ):
    "Wait for a node to finish, and  print its output."
    while node.waiting:
        try:
            data = node.monitor()
            info( '%s' % data )
        except KeyboardInterrupt:
            node.sendInt()

