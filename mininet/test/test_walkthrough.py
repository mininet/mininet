#!/usr/bin/env python

"""
Tests for the Mininet Walkthrough

TODO: missing xterm test
"""

import unittest
import pexpect
import os
import re
from mininet.util import quietRun
from distutils.version import StrictVersion
from time import sleep

# allow Unicode for re patterns
# pylint:disable=anomalous-backslash-in-string

def tsharkVersion():
    "Return tshark version"
    versionStr = quietRun( 'tshark -v' )
    versionMatch = re.findall( u'TShark[^\d]*(\d+.\d+.\d+)', versionStr )
    return versionMatch[ 0 ]

# pylint doesn't understand pexpect.match, unfortunately!
# pylint:disable=maybe-no-member

class testWalkthrough( unittest.TestCase ):
    "Test Mininet walkthrough"

    prompt = u'mininet>'

    # PART 1
    def testHelp( self ):
        "Check the usage message"
        p = pexpect.spawn( 'mn -h', encoding='utf-8' )
        index = p.expect( [ u'Usage: mn', pexpect.EOF ] )
        self.assertEqual( index, 0 )

    def testWireshark( self ):
        "Use tshark to test the of dissector"
        # Satisfy pylint
        assert self
        if StrictVersion( tsharkVersion() ) < StrictVersion( '1.12.0' ):
            tshark = pexpect.spawn( 'tshark -i lo -R of', encoding='utf-8' )
        else:
            tshark = pexpect.spawn( 'tshark -i lo -Y openflow_v1',
                                    encoding='utf-8' )
        tshark.expect( [ u'Capturing on lo', u"Capturing on 'Loopback'" ] )
        mn = pexpect.spawn( 'mn --test pingall', encoding='utf-8' )
        mn.expect( u'0% dropped' )
        tshark.expect( [ u'74 Hello', u'74 of_hello',
                         u'74 Type: OFPT_HELLO' ] )
        tshark.sendintr()
        mn.expect( pexpect.EOF )
        tshark.expect( pexpect.EOF )

    def testBasic( self ):
        "Test basic CLI commands (help, nodes, net, dump)"
        p = pexpect.spawn( 'mn', encoding='utf-8' )
        p.expect( self.prompt )
        # help command
        p.sendline( 'help' )
        index = p.expect( [ u'commands', self.prompt ] )
        self.assertEqual( index, 0, u'No output for "help" command')
        # nodes command
        p.sendline( 'nodes' )
        p.expect( u'([chs]\d ?){4}' )
        nodes = p.match.group( 0 ).split()
        self.assertEqual( len( nodes ), 4, u'No nodes in "nodes" command')
        p.expect( self.prompt )
        # net command
        p.sendline( 'net' )
        expected = [ x for x in nodes ]
        while len( expected ) > 0:
            index = p.expect( expected )
            node = p.match.group( 0 )
            expected.remove( node )
            p.expect( u'\n' )
        self.assertEqual( len( expected ), 0, u'"nodes" and "net" differ')
        p.expect( self.prompt )
        # dump command
        p.sendline( 'dump' )
        expected = [ u'<\w+ (%s)' % n for n in nodes ]
        actual = []
        for _ in nodes:
            index = p.expect( expected )
            node = p.match.group( 1 )
            actual.append( node )
            p.expect( u'\n' )
        self.assertEqual( actual.sort(), nodes.sort(),
                          u'"nodes" and "dump" differ' )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testHostCommands( self ):
        "Test ifconfig and ps on h1 and s1"
        p = pexpect.spawn( 'mn', encoding='utf-8' )
        p.expect( self.prompt )
        # Third pattern is a local interface beginning with 'eth' or 'en'
        interfaces = [ u'h1-eth0', u's1-eth1', u'[^-](eth|en)\w*\d', u'lo',
                       self.prompt ]
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
        self.assertEqual( ifcount, 2, u'Missing interfaces on h1')
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
        self.assertTrue( ifcount >= 3, u'Missing interfaces on s1')
        # h1 ps
        p.sendline( "h1 ps -a | egrep -v 'ps|grep'" )
        p.expect( self.prompt )
        h1Output = p.before
        # s1 ps
        p.sendline( "s1 ps -a | egrep -v 'ps|grep'" )
        p.expect( self.prompt )
        s1Output = p.before
        # strip command from ps output and compute diffs
        h1Output = h1Output.split( '\n' )[ 1: ]
        s1Output = s1Output.split( '\n' )[ 1: ]
        diffs = set( h1Output ).difference( set( s1Output ) )
        # allow up to two diffs to account for daemons, etc.
        self.assertTrue( len( diffs ) <= 2,
                         u'h1 and s1 "ps" output differ too much: %s' % diffs )
        p.sendline( 'exit' )
        p.wait()

    def testConnectivity( self ):
        "Test ping and pingall"
        p = pexpect.spawn( 'mn', encoding='utf-8' )
        p.expect( self.prompt )
        p.sendline( 'h1 ping -c 1 h2' )
        p.expect( u'1 packets transmitted, 1 received' )
        p.expect( self.prompt )
        p.sendline( 'pingall' )
        p.expect( u'0% dropped' )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testSimpleHTTP( self ):
        "Start an HTTP server on h1 and wget from h2"
        p = pexpect.spawn( 'mn', encoding='utf-8' )
        p.expect( self.prompt )
        p.sendline( 'h1 python -m SimpleHTTPServer 80 &' )
        # The walkthrough doesn't specify a delay here, and
        # we also don't read the output (also a possible problem),
        # but for now let's wait a couple of seconds to make
        # it less likely to fail due to the race condition.
        sleep( 2 )
        p.expect( self.prompt )
        p.sendline( ' h2 wget -O - h1' )
        p.expect( u'200 OK' )
        p.expect( self.prompt )
        p.sendline( 'h1 kill %python' )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    # PART 2
    def testRegressionRun( self ):
        "Test pingpair (0% drop) and iperf (bw > 0) regression tests"
        # test pingpair
        p = pexpect.spawn( 'mn --test pingpair', encoding='utf-8' )
        p.expect( u'0% dropped' )
        p.expect( pexpect.EOF )
        # test iperf
        p = pexpect.spawn( 'mn --test iperf', encoding='utf-8' )
        p.expect( u"Results: \['([\d\.]+) .bits/sec'," )
        bw = float( p.match.group( 1 ) )
        self.assertTrue( bw > 0 )
        p.expect( pexpect.EOF )

    def testTopoChange( self ):
        "Test pingall on single,3 and linear,4 topos"
        # testing single,3
        p = pexpect.spawn( 'mn --test pingall --topo single,3',
                           encoding='utf-8' )
        p.expect( u'(\d+)/(\d+) received')
        received = int( p.match.group( 1 ) )
        sent = int( p.match.group( 2 ) )
        self.assertEqual( sent, 6, u'Wrong number of pings sent in single,3' )
        self.assertEqual( sent, received, u'Dropped packets in single,3')
        p.expect( pexpect.EOF )
        # testing linear,4
        p = pexpect.spawn( 'mn --test pingall --topo linear,4',
                           encoding='utf-8' )
        p.expect( u'(\d+)/(\d+) received')
        received = int( p.match.group( 1 ) )
        sent = int( p.match.group( 2 ) )
        self.assertEqual( sent, 12, u'Wrong number of pings sent in linear,4' )
        self.assertEqual( sent, received, u'Dropped packets in linear,4')
        p.expect( pexpect.EOF )

    def testLinkChange( self ):
        "Test TCLink bw and delay"
        p = pexpect.spawn( 'mn --link tc,bw=10,delay=10ms', encoding='utf-8' )
        # test bw
        p.expect( self.prompt )
        p.sendline( 'iperf' )
        p.expect( u"Results: \['([\d\.]+) Mbits/sec'," )
        bw = float( p.match.group( 1 ) )
        self.assertTrue( bw < 10.1, u'Bandwidth %.2f >= 10.1 Mb/s' % bw )
        self.assertTrue( bw > 9.0, u'Bandwidth %.2f <= 9 Mb/s' % bw )
        p.expect( self.prompt )
        # test delay
        p.sendline( 'h1 ping -c 4 h2' )
        p.expect( u'rtt min/avg/max/mdev = '
                  u'([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms' )
        delay = float( p.match.group( 2 ) )
        self.assertTrue( delay > 40, u'Delay < 40ms' )
        self.assertTrue( delay < 45, u'Delay > 40ms' )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testVerbosity( self ):
        "Test debug and output verbosity"
        # test output
        p = pexpect.spawn( 'mn -v output', encoding='utf-8' )
        p.expect( self.prompt )
        self.assertEqual( len( p.before ), 0, 'Too much output for "output"' )
        p.sendline( 'exit' )
        p.wait()
        # test debug
        p = pexpect.spawn( 'mn -v debug --test none', encoding='utf-8' )
        p.expect( pexpect.EOF )
        lines = p.before.split( '\n' )
        self.assertTrue( len( lines ) > 70, "Debug output is too short" )

    def testCustomTopo( self ):
        "Start Mininet using a custom topo, then run pingall"
        # Satisfy pylint
        assert self
        custom = os.path.dirname( os.path.realpath( __file__ ) )
        custom = os.path.join( custom, '../../custom/topo-2sw-2host.py' )
        custom = os.path.normpath( custom )
        p = pexpect.spawn(
            'mn --custom %s --topo mytopo --test pingall' % custom,
            encoding='utf-8' )
        p.expect( u'0% dropped' )
        p.expect( pexpect.EOF )

    def testStaticMAC( self ):
        "Verify that MACs are set to easy to read numbers"
        p = pexpect.spawn( 'mn --mac', encoding='utf-8' )
        p.expect( self.prompt )
        for i in range( 1, 3 ):
            p.sendline( 'h%d ifconfig' % i )
            p.expect( u'HWaddr 00:00:00:00:00:0%d' % i )
            p.expect( self.prompt )
        p.sendline( 'exit' )
        p.expect( pexpect.EOF )

    def testSwitches( self ):
        "Run iperf test using user and ovsk switches"
        switches = [ u'user', u'ovsk' ]
        for sw in switches:
            p = pexpect.spawn( 'mn --switch %s --test iperf' % sw,
                               encoding='utf-8' )
            p.expect( u"Results: \['([\d\.]+) .bits/sec'," )
            bw = float( p.match.group( 1 ) )
            self.assertTrue( bw > 0 )
            p.expect( pexpect.EOF )

    def testBenchmark( self ):
        "Run benchmark and verify that it takes less than 2 seconds"
        p = pexpect.spawn( 'mn --test none' )
        p.expect( u'completed in ([\d\.]+) seconds' )
        time = float( p.match.group( 1 ) )
        self.assertTrue( time < 2, 'Benchmark takes more than 2 seconds' )

    def testOwnNamespace( self ):
        "Test running user switch in its own namespace"
        p = pexpect.spawn( 'mn --innamespace --switch user'
                           , encoding='utf-8')
        p.expect( self.prompt )
        interfaces = [ u'h1-eth0',
                       u's1-eth1',
                       u'[^-]eth0',
                       u'lo',
                       self.prompt ]
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
        p.expect( u'(\d+)% dropped' )
        dropped = int( p.match.group( 1 ) )
        self.assertEqual( dropped, 0, 'pingall failed')
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    # PART 3
    def testPythonInterpreter( self ):
        "Test py and px by checking IP for h1 and adding h3"
        p = pexpect.spawn( 'mn', encoding='utf-8' )
        p.expect( self.prompt )
        # test host IP
        p.sendline( 'py h1.IP()' )
        p.expect( u'10.0.0.1' )
        p.expect( self.prompt )
        # test adding host
        p.sendline( "px net.addHost('h3')" )
        p.expect( self.prompt )
        p.sendline( "px net.addLink(s1, h3)" )
        p.expect( self.prompt )
        p.sendline( 'net' )
        p.expect( u'h3' )
        p.expect( self.prompt )
        p.sendline( 'py h3.MAC()' )
        p.expect( u'([a-f0-9]{2}:?){6}' )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testLink( self ):
        "Test link CLI command using ping"
        p = pexpect.spawn( 'mn', encoding='utf-8' )
        p.expect( self.prompt )
        p.sendline( 'link s1 h1 down' )
        p.expect( self.prompt )
        p.sendline( 'h1 ping -c 1 h2' )
        p.expect( u'unreachable' )
        p.expect( self.prompt )
        p.sendline( 'link s1 h1 up' )
        p.expect( self.prompt )
        p.sendline( 'h1 ping -c 1 h2' )
        p.expect( u'0% packet loss' )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    @unittest.skipUnless( os.path.exists( '/tmp/pox' ) or
                          '1 received' in quietRun( 'ping -c 1 github.com' ),
                          'Github is not reachable; cannot download Pox' )
    def testRemoteController( self ):
        "Test Mininet using Pox controller"
        # Satisfy pylint
        assert self
        if not os.path.exists( '/tmp/pox' ):
            p = pexpect.spawn(
                'git clone https://github.com/noxrepo/pox.git /tmp/pox'
                , encoding='utf-8' )
            p.expect( pexpect.EOF )
        pox = pexpect.spawn( '/tmp/pox/pox.py forwarding.l2_learning',
                             encoding='utf-8' )
        net = pexpect.spawn(
            'mn --controller=remote,ip=127.0.0.1,port=6633 --test pingall',
            encoding='utf-8' )
        net.expect( u'0% dropped' )
        net.expect( pexpect.EOF )
        pox.sendintr()
        pox.wait()


if __name__ == '__main__':
    unittest.main()
