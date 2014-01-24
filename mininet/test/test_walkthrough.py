#!/usr/bin/env python

"""
Tests for the Mininet Walkthrough

TODO: missing xterm test
"""

import unittest
import pexpect
import os
from mininet.util import quietRun

class testWalkthrough( unittest.TestCase ):

    prompt = 'mininet>'

    # PART 1
    def testHelp( self ):
        """Check the usage message"""
        p = pexpect.spawn( 'mn -h' )
        index = p.expect( [ 'Usage: mn', pexpect.EOF ] )
        self.assertEqual( index, 0 )

    def testWireshark( self ):
        """Use tshark to test the of dissector"""
        tshark = pexpect.spawn( 'tshark -i lo -R of' )
        tshark.expect( 'Capturing on lo' )
        mn = pexpect.spawn( 'mn --test pingall' )
        mn.expect( '0% dropped' )
        tshark.expect( 'OFP 74 Hello' )
        tshark.sendintr()

    def testBasic( self ):
        """Test basic CLI commands (help, nodes, net, dump)"""
        p = pexpect.spawn( 'mn' )
        p.expect( self.prompt )
        # help command
        p.sendline( 'help' )
        index = p.expect( [ 'commands', self.prompt ] )
        self.assertEqual( index, 0, 'No output for "help" command')
        # nodes command
        p.sendline( 'nodes' )
        p.expect( '([chs]\d ?){4}' )
        nodes = p.match.group( 0 ).split()
        self.assertEqual( len( nodes ), 4, 'No nodes in "nodes" command')
        p.expect( self.prompt )
        # net command
        p.sendline( 'net' )
        expected = [ x for x in nodes ]
        while len( expected ) > 0:
            index = p.expect( expected )
            node = p.match.group( 0 )
            expected.remove( node )
            p.expect( '\n' )
        self.assertEqual( len( expected ), 0, '"nodes" and "net" differ')
        p.expect( self.prompt )
        # dump command
        p.sendline( 'dump' )
        expected = [ '<\w+ (%s)' % n for n in nodes ]
        actual = []
        for _ in nodes:
            index = p.expect( expected )
            node = p.match.group( 1 )
            actual.append( node )
            p.expect( '\n' )
        self.assertEqual( actual.sort(), nodes.sort(), '"nodes" and "dump" differ' ) 
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testHostCommands( self ):
        """Test ifconfig and ps on h1 and s1"""
        p = pexpect.spawn( 'mn' )
        p.expect( self.prompt )
        interfaces = [ 'h1-eth0', 's1-eth1', '[^-]eth0', 'lo', self.prompt ]
        # h1 ifconfig
        p.sendline( 'h1 ifconfig -a' )
        ifcount = 0
        while True:
            index = p.expect( interfaces )
            if index == 0 or index == 3:
                ifcount += 1
            elif index == 1:
                self.fail( 's1 interface displayed in "h1 ifconfig"' )
            elif index == 2:
                self.fail( 'eth0 displayed in "h1 ifconfig"' )
            else:
                break
        self.assertEqual( ifcount, 2, 'Missing interfaces on h1')
        # s1 ifconfig
        p.sendline( 's1 ifconfig -a' )
        ifcount = 0
        while True:
            index = p.expect( interfaces )
            if index == 0:
                self.fail( 'h1 interface displayed in "s1 ifconfig"' )
            elif index == 1 or index == 2 or index == 3:
                ifcount += 1
            else:
                break
        self.assertEqual( ifcount, 3, 'Missing interfaces on s1')
        # h1 ps
        p.sendline( 'h1 ps -a' )
        p.expect( self.prompt )
        h1Output = p.before
        # s1 ps
        p.sendline( 's1 ps -a' )
        p.expect( self.prompt )
        s1Output = p.before
        # strip command from ps output
        h1Output = h1Output.split( '\n', 1 )[ 1 ]
        s1Output = s1Output.split( '\n', 1 )[ 1 ]
        self.assertEqual( h1Output, s1Output, 'h1 and s1 "ps" output differs')
        p.sendline( 'exit' )
        p.wait()

    def testConnectivity( self ):
        """Test ping and pingall"""
        p = pexpect.spawn( 'mn' )
        p.expect( self.prompt )
        p.sendline( 'h1 ping -c 1 h2' )
        p.expect( '1 packets transmitted, 1 received' )
        p.expect( self.prompt )
        p.sendline( 'pingall' )
        p.expect( '0% dropped' )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testSimpleHTTP( self ):
        """Start an HTTP server on h1 and wget from h2"""
        p = pexpect.spawn( 'mn' )
        p.expect( self.prompt )
        p.sendline( 'h1 python -m SimpleHTTPServer 80 &' )
        p.expect( self.prompt )
        p.sendline( ' h2 wget -O - h1' )
        p.expect( '200 OK' )
        p.expect( self.prompt )
        p.sendline( 'h1 kill %python' )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    # PART 2
    def testRegressionRun( self ):
        """Test pingpair (0% drop) and iperf (bw > 0) regression tests"""
        # test pingpair
        p = pexpect.spawn( 'mn --test pingpair' )
        p.expect( '0% dropped' )
        p.expect( pexpect.EOF )
        # test iperf
        p = pexpect.spawn( 'mn --test iperf' )
        p.expect( "Results: \['([\d\.]+) .bits/sec'," )
        bw = float( p.match.group( 1 ) )
        self.assertTrue( bw > 0 )
        p.expect( pexpect.EOF )

    def testTopoChange( self ):
        """Test pingall on single,3 and linear,4 topos"""
        # testing single,3
        p = pexpect.spawn( 'mn --test pingall --topo single,3' )
        p.expect( '(\d+)/(\d+) received')
        received = int( p.match.group( 1 ) )
        sent = int( p.match.group( 2 ) )
        self.assertEqual( sent, 6, 'Wrong number of pings sent in single,3' )
        self.assertEqual( sent, received, 'Dropped packets in single,3')
        p.expect( pexpect.EOF )
        # testing linear,4
        p = pexpect.spawn( 'mn --test pingall --topo linear,4' )
        p.expect( '(\d+)/(\d+) received')
        received = int( p.match.group( 1 ) )
        sent = int( p.match.group( 2 ) )
        self.assertEqual( sent, 12, 'Wrong number of pings sent in linear,4' )
        self.assertEqual( sent, received, 'Dropped packets in linear,4')
        p.expect( pexpect.EOF )

    def testLinkChange( self ):
        """Test TCLink bw and delay"""
        p = pexpect.spawn( 'mn --link tc,bw=10,delay=10ms' )
        # test bw
        p.expect( self.prompt )
        p.sendline( 'iperf' )
        p.expect( "Results: \['([\d\.]+) Mbits/sec'," )
        bw = float( p.match.group( 1 ) )
        self.assertTrue( bw < 10.1, 'Bandwidth > 10 Mb/s')
        self.assertTrue( bw > 9.0, 'Bandwidth < 9 Mb/s')
        p.expect( self.prompt )
        # test delay
        p.sendline( 'h1 ping -c 4 h2' )
        p.expect( 'rtt min/avg/max/mdev = ([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms' )
        delay = float( p.match.group( 2 ) )
        self.assertTrue( delay > 40, 'Delay < 40ms' )
        self.assertTrue( delay < 45, 'Delay > 40ms' )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testVerbosity( self ):
        """Test debug and output verbosity"""
        # test output
        p = pexpect.spawn( 'mn -v output' )
        p.expect( self.prompt )
        self.assertEqual( len( p.before ), 0, 'Too much output for "output"' )
        p.sendline( 'exit' )
        p.wait()
        # test debug
        p = pexpect.spawn( 'mn -v debug --test none' )
        p.expect( pexpect.EOF )
        lines = p.before.split( '\n' )
        self.assertTrue( len( lines ) > 100, "Debug output is too short" )

    def testCustomTopo( self ):
        """Start Mininet using a custom topo, then run pingall"""
        custom = os.path.dirname( os.path.realpath( __file__ ) )
        custom = os.path.join( custom, '../../custom/topo-2sw-2host.py' )
        custom = os.path.normpath( custom )
        p = pexpect.spawn( 'mn --custom %s --topo mytopo --test pingall' % custom )
        p.expect( '0% dropped' )
        p.expect( pexpect.EOF )

    def testStaticMAC( self ):
        """Verify that MACs are set to easy to read numbers"""
        p = pexpect.spawn( 'mn --mac' )
        p.expect( self.prompt )
        for i in range( 1, 3 ):
            p.sendline( 'h%d ifconfig' % i )
            p.expect( 'HWaddr 00:00:00:00:00:0%d' % i )
            p.expect( self.prompt )

    def testSwitches( self ):
        """Run iperf test using user and ovsk switches"""
        switches = [ 'user', 'ovsk' ]
        for sw in switches:
            p = pexpect.spawn( 'mn --switch %s --test iperf' % sw )
            p.expect( "Results: \['([\d\.]+) .bits/sec'," )
            bw = float( p.match.group( 1 ) )
            self.assertTrue( bw > 0 )
            p.expect( pexpect.EOF )

    def testBenchmark( self ):
        """Run benchmark and verify that it takes less than 2 seconds"""
        p = pexpect.spawn( 'mn --test none' )
        p.expect( 'completed in ([\d\.]+) seconds' )
        time = float( p.match.group( 1 ) )
        self.assertTrue( time < 2, 'Benchmark takes more than 2 seconds' )

    def testOwnNamespace( self ):
        """Test running user switch in its own namespace"""
        p = pexpect.spawn( 'mn --innamespace --switch user' )
        p.expect( self.prompt )
        interfaces = [ 'h1-eth0', 's1-eth1', '[^-]eth0', 'lo', self.prompt ]
        p.sendline( 's1 ifconfig -a' )
        ifcount = 0
        while True:
            index = p.expect( interfaces )
            if index == 1 or index == 3:
                ifcount += 1
            elif index == 0:
                self.fail( 'h1 interface displayed in "s1 ifconfig"' )
            elif index == 2:
                self.fail( 'eth0 displayed in "s1 ifconfig"' )
            else:
                break
        self.assertEqual( ifcount, 2, 'Missing interfaces on s1' )
        # verify that all hosts a reachable
        p.sendline( 'pingall' )
        p.expect( '(\d+)% dropped' )
        dropped = int( p.match.group( 1 ) )
        self.assertEqual( dropped, 0, 'pingall failed')
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    # PART 3
    def testPythonInterpreter( self ):
        """Test py and px by checking IP for h1 and adding h3"""
        p = pexpect.spawn( 'mn' )
        p.expect( self.prompt )
        # test host IP
        p.sendline( 'py h1.IP()' )
        p.expect( '10.0.0.1' )
        p.expect( self.prompt )
        # test adding host
        p.sendline( "px net.addHost('h3')" )
        p.expect( self.prompt )
        p.sendline( "px net.addLink(s1, h3)" )
        p.expect( self.prompt )
        p.sendline( 'net' )
        p.expect( 'h3' )
        p.expect( self.prompt )
        p.sendline( 'py h3.MAC()' )
        p.expect( '([a-f0-9]{2}:?){6}' )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testLink( self ):
        """Test link CLI command using ping"""
        p = pexpect.spawn( 'mn' )
        p.expect( self.prompt )
        p.sendline( 'link s1 h1 down' )
        p.expect( self.prompt )
        p.sendline( 'h1 ping -c 1 h2' )
        p.expect( 'unreachable' )
        p.expect( self.prompt )
        p.sendline( 'link s1 h1 up' )
        p.expect( self.prompt )
        p.sendline( 'h1 ping -c 1 h2' )
        p.expect( '0% packet loss' )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    @unittest.skipUnless( os.path.exists( '/tmp/pox' ) or
                          '1 received' in quietRun( 'ping -c 1 github.com' ),
                          'Github is not reachable; cannot download Pox' )
    def testRemoteController( self ):
        """Test Mininet using Pox controller"""
        if not os.path.exists( '/tmp/pox' ):
            p = pexpect.spawn( 'git clone https://github.com/noxrepo/pox.git /tmp/pox' )
            p.expect( pexpect.EOF )
        pox = pexpect.spawn( '/tmp/pox/pox.py forwarding.l2_learning' )
        net = pexpect.spawn( 'mn --controller=remote,ip=127.0.0.1,port=6633 --test pingall' )
        net.expect( '0% dropped' )
        net.expect( pexpect.EOF )
        pox.sendintr()
        pox.wait()

if __name__ == '__main__':
    unittest.main()