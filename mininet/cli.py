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
('net') and to check connectivity ('ping_all', 'ping_pair')
and bandwidth ('iperf'.)

Bugs/limitations:

- Interactive commands are not supported at the moment;
  notably, if you type 'ping h1', you can control-C it, but
  it breaks the CLI and your network. ;-(
  For now, we recommend limiting CLI use to non-interactive
  commands which terminate in a reasonable amount of time.

- We don't (yet) support command line history editing. This is
  coming soon.

"""

from subprocess import call
import sys

from mininet.log import lg

class CLI( object ):
    "Simple command-line interface to talk to nodes."

    cmds = [ '?', 'help', 'nodes', 'net', 'sh', 'ping_all', 'exit',
            'ping_pair', 'iperf', 'iperf_udp', 'intfs', 'dump' ]

    def __init__( self, mininet ):
        self.mn = mininet
        self.nodemap = {} # map names to Node objects
        for node in self.mn.nodes.values():
            self.nodemap[ node.name ] = node
        for cname, cnode in self.mn.controllers.iteritems():
            self.nodemap[ cname ] = cnode
        self.nodelist = self.nodemap.values()
        self.run()

    # Disable pylint "Unused argument: 'arg's'" messages.
    # Each CLI function needs the same interface.
    # pylint: disable-msg=W0613

    # Commands
    def help( self, args ):
        "Semi-useful help for CLI."
        helpStr = ( 'Available commands are:' + str( self.cmds ) + '\n'
                   'You may also send a command to a node using:\n'
                   '  <node> command {args}\n'
                   'For example:\n'
                   '  mininet> h0 ifconfig\n'
                   '\n'
                   'The interpreter automatically substitutes IP '
                   'addresses\n'
                   'for node names, so commands like\n'
                   '  mininet> h0 ping -c1 h1\n'
                   'should work.\n'
                   '\n\n'
                   'Interactive commands are not really supported yet,\n'
                   'so please limit commands to ones that do not\n'
                   'require user interaction and will terminate\n'
                   'after a reasonable amount of time.\n' )
        print( helpStr )

    def nodes( self, args ):
        "List all nodes."
        nodes = ' '.join( [ node.name for node in sorted( self.nodelist ) ] )
        lg.info( 'available nodes are: \n%s\n' % nodes )

    def net( self, args ):
        "List network connections."
        for switchDpid in self.mn.topo.switches():
            switch = self.mn.nodes[ switchDpid ]
            lg.info( '%s <->', switch.name )
            for intf in switch.intfs:
                node = switch.connection[ intf ]
                lg.info( ' %s' % node.name )
            lg.info( '\n' )

    def sh( self, args ):
        "Run an external shell command"
        call( [ 'sh', '-c' ] + args )

    def pingAll( self, args ):
        "Ping between all hosts."
        self.mn.pingAll()

    def pingPair( self, args ):
        "Ping between first two hosts, useful for testing."
        self.mn.pingPair()

    def iperf( self, args ):
        "Simple iperf TCP test between two hosts."
        self.mn.iperf()

    def iperfUdp( self, args ):
        "Simple iperf UDP test between two hosts."
        udpBw = args[ 0 ] if len( args ) else '10M'
        self.mn.iperfUdp( udpBw )

    def intfs( self, args ):
        "List interfaces."
        for node in self.mn.nodes.values():
            lg.info( '%s: %s\n' % ( node.name, ' '.join( node.intfs ) ) )

    def dump( self, args ):
        "Dump node info."
        for node in self.mn.nodes.values():
            lg.info( '%s\n' % node )

    # Re-enable pylint "Unused argument: 'arg's'" messages.
    # pylint: enable-msg=W0613

    def run( self ):
        "Read and execute commands."
        lg.warn( '*** Starting CLI:\n' )
        while True:
            lg.warn( 'mininet> ' )
            inputLine = sys.stdin.readline()
            if inputLine == '':
                break
            if inputLine[ -1 ] == '\n':
                inputLine = inputLine[ :-1 ]
            cmd = inputLine.split( ' ' )
            first = cmd[ 0 ]
            rest = cmd[ 1: ]
            if first in self.cmds and hasattr( self, first ):
                getattr( self, first )( rest )
            elif first in self.nodemap and rest != []:
                node = self.nodemap[ first ]
                # Substitute IP addresses for node names in command
                rest = [ self.nodemap[ arg ].IP()
                    if arg in self.nodemap else arg
                    for arg in rest ]
                rest = ' '.join( rest )
                # Interactive commands don't work yet, and
                # there are still issues with control-c
                lg.warn( '*** %s: running %s\n' % ( node.name, rest ) )
                node.sendCmd( rest )
                while True:
                    try:
                        done, data = node.monitor()
                        lg.info( '%s\n' % data )
                        if done:
                            break
                    except KeyboardInterrupt:
                        node.sendInt()
            elif first == '':
                pass
            elif first in [ 'exit', 'quit' ]:
                break
            elif first == '?':
                self.help( rest )
            else:
                lg.error( 'CLI: unknown node or command: < %s >\n' % first )
            #lg.info( '*** CLI: command complete\n' )
        return 'exited by user command'
