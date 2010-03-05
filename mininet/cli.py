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

mininet> h0 ping -c1 h31

should work correctly and allow host h0 to ping host h31.
Note the '-c1' argument as per the Bugs/limitations section below!

Several useful commands are provided, including the ability to
list all nodes ('nodes'), to print out the network topology
('net') and to check connectivity ('pingall', 'pingpair')
and bandwidth ('iperf'.)

Bugs/limitations:

- Interactive commands are not supported at the moment;
  notably, if you type 'ping h1', you can control-C it, but
  it breaks the CLI and your network. ;-(
  For now, we recommend limiting CLI use to non-interactive
  commands which terminate in a reasonable amount of time.

"""

from subprocess import call
from cmd import Cmd

from mininet.log import info, output

class CLI( Cmd ):
    "Simple command-line interface to talk to nodes."

    prompt = 'mininet> '

    def __init__( self, mininet ):
        self.mn = mininet
        self.nodelist = self.mn.controllers + self.mn.switches + self.mn.hosts
        self.nodemap = {} # map names to Node objects
        for node in self.nodelist:
            self.nodemap[ node.name ] = node
        Cmd.__init__( self )
        info( '*** Starting CLI:\n' )
        self.cmdloop()

    # Disable pylint "Unused argument: 'arg's'" messages.
    # Each CLI function needs the same interface.
    # pylint: disable-msg=W0613

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
                   ' mininet> h0 ping -c1 h1\n'
                   'should work.\n'
                   '\n'
                   'Interactive commands are not really supported yet,\n'
                   'so please limit commands to ones that do not\n'
                   'require user interaction and will terminate\n'
                   'after a reasonable amount of time.\n' )
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
            node.sendCmd( rest )
            while True:
                try:
                    done, data = node.monitor()
                    info( '%s' % data )
                    if done:
                        break
                except KeyboardInterrupt:
                    node.sendInt()
        else:
            self.stdout.write( '*** Unknown syntax: %s\n' % line )

    # Re-enable pylint "Unused argument: 'arg's'" messages.
    # pylint: enable-msg=W0613
