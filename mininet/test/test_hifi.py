#!/usr/bin/env python

"""Package: mininet
   Test creation and pings for topologies with link and/or CPU options."""

import unittest
import sys
from functools import partial

from mininet.net import Mininet
from mininet.node import OVSSwitch, UserSwitch, IVSSwitch
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.topo import Topo
from mininet.log import setLogLevel
from mininet.util import quietRun
from mininet.clean import cleanup

# Number of hosts for each test
N = 2


class SingleSwitchOptionsTopo(Topo):
    "Single switch connected to n hosts."
    def __init__(self, n=2, hopts=None, lopts=None):
        if not hopts:
            hopts = {}
        if not lopts:
            lopts = {}
        Topo.__init__(self, hopts=hopts, lopts=lopts)
        switch = self.addSwitch('s1')
        for h in range(n):
            host = self.addHost('h%s' % (h + 1))
            self.addLink(host, switch)

# Tell pylint not to complain about calls to other class
# pylint: disable=E1101

class testOptionsTopoCommon( object ):
    """Verify ability to create networks with host and link options
       (common code)."""

    switchClass = None  # overridden in subclasses

    @staticmethod
    def tearDown():
        "Clean up if necessary"
        if sys.exc_info != ( None, None, None ):
            cleanup()

    def runOptionsTopoTest( self, n, msg, hopts=None, lopts=None ):
        "Generic topology-with-options test runner."
        mn = Mininet( topo=SingleSwitchOptionsTopo( n=n, hopts=hopts,
                                                    lopts=lopts ),
                      host=CPULimitedHost, link=TCLink,
                      switch=self.switchClass, waitConnected=True )
        dropped = mn.run( mn.ping )
        hoptsStr = ', '.join( '%s: %s' % ( opt, value )
                              for opt, value in hopts.items() )
        loptsStr = ', '.join( '%s: %s' % ( opt, value )
                              for opt, value in lopts.items() )
        msg += ( '%s%% of pings were dropped during mininet.ping().\n'
                 'Topo = SingleSwitchTopo, %s hosts\n'
                 'hopts = %s\n'
                 'lopts = %s\n'
                 'host = CPULimitedHost\n'
                 'link = TCLink\n'
                 'Switch = %s\n'
                 % ( dropped, n, hoptsStr, loptsStr, self.switchClass ) )

        self.assertEqual( dropped, 0, msg=msg )

    def assertWithinTolerance( self, measured, expected, tolerance_frac, msg ):
        """Check that a given value is within a tolerance of expected
        tolerance_frac: less-than-1.0 value; 0.8 would yield 20% tolerance.
        """
        upperBound = ( float( expected ) + ( 1 - tolerance_frac ) *
                       float( expected ) )
        lowerBound = float( expected ) * tolerance_frac
        info = ( 'measured value is out of bounds\n'
                 'expected value: %s\n'
                 'measured value: %s\n'
                 'failure tolerance: %s\n'
                 'upper bound: %s\n'
                 'lower bound: %s\n'
                 % ( expected, measured, tolerance_frac,
                     upperBound, lowerBound ) )
        msg += info

        self.assertGreaterEqual( float( measured ), lowerBound, msg=msg )
        self.assertLessEqual( float( measured ), upperBound, msg=msg )

    def testCPULimits( self ):
        "Verify topology creation with CPU limits set for both schedulers."
        CPU_FRACTION = 0.1
        CPU_TOLERANCE = 0.8  # CPU fraction below which test should fail
        hopts = { 'cpu': CPU_FRACTION }
        #self.runOptionsTopoTest( N, hopts=hopts )

        mn = Mininet( SingleSwitchOptionsTopo( n=N, hopts=hopts ),
                      host=CPULimitedHost, switch=self.switchClass,
                      waitConnected=True )
        mn.start()
        results = mn.runCpuLimitTest( cpu=CPU_FRACTION )
        mn.stop()
        hostUsage = '\n'.join( 'h%s: %s' %
                               ( n + 1,
                                 results[ (n - 1) * 5 : (n * 5) - 1 ] )
                               for n in range( N ) )
        hoptsStr = ', '.join( '%s: %s' % ( opt, value )
                              for opt, value in hopts.items() )
        msg = ( '\nTesting cpu limited to %d%% of cpu per host\n'
                'cpu usage percent per host:\n%s\n'
                'Topo = SingleSwitchTopo, %s hosts\n'
                'hopts = %s\n'
                'host = CPULimitedHost\n'
                'Switch = %s\n'
                % ( CPU_FRACTION * 100, hostUsage, N, hoptsStr,
                    self.switchClass ) )
        for pct in results:
            #divide cpu by 100 to convert from percentage to fraction
            self.assertWithinTolerance( pct/100, CPU_FRACTION,
                                        CPU_TOLERANCE, msg )

    def testLinkBandwidth( self ):
        "Verify that link bandwidths are accurate within a bound."
        if self.switchClass is UserSwitch:
            self.skipTest( 'UserSwitch has very poor performance -'
                           ' skipping for now' )
        BW = 5  # Mbps
        BW_TOLERANCE = 0.8  # BW fraction below which test should fail
        # Verify ability to create limited-link topo first;
        lopts = { 'bw': BW, 'use_htb': True }
        # Also verify correctness of limit limitng within a bound.
        mn = Mininet( SingleSwitchOptionsTopo( n=N, lopts=lopts ),
                      link=TCLink, switch=self.switchClass,
                      waitConnected=True )
        bw_strs = mn.run( mn.iperf, fmt='m' )
        loptsStr = ', '.join( '%s: %s' % ( opt, value )
                              for opt, value in lopts.items() )
        msg = ( '\nTesting link bandwidth limited to %d Mbps per link\n'
                'iperf results[ client, server ]: %s\n'
                'Topo = SingleSwitchTopo, %s hosts\n'
                'Link = TCLink\n'
                'lopts = %s\n'
                'host = default\n'
                'switch = %s\n'
                % ( BW, bw_strs, N, loptsStr, self.switchClass ) )

        # On the client side, iperf doesn't wait for ACKs - it simply
        # reports how long it took to fill up the TCP send buffer.
        # As long as the kernel doesn't wait a long time before
        # delivering bytes to the iperf server, its reported data rate
        # should be close to the actual receive rate.
        serverRate, _clientRate = bw_strs
        bw = float( serverRate.split(' ')[0] )
        self.assertWithinTolerance( bw, BW, BW_TOLERANCE, msg )

    def testLinkDelay( self ):
        "Verify that link delays are accurate within a bound."
        DELAY_MS = 15
        DELAY_TOLERANCE = 0.8  # Delay fraction below which test should fail
        REPS = 3
        lopts = { 'delay': '%sms' % DELAY_MS, 'use_htb': True }
        mn = Mininet( SingleSwitchOptionsTopo( n=N, lopts=lopts ),
                      link=TCLink, switch=self.switchClass, autoStaticArp=True,
                      waitConnected=True )
        mn.start()
        for _ in range( REPS ):
            ping_delays = mn.pingFull()
        mn.stop()
        test_outputs = ping_delays[0]
        # Ignore unused variables below
        # pylint: disable=W0612
        node, dest, ping_outputs = test_outputs
        sent, received, rttmin, rttavg, rttmax, rttdev = ping_outputs
        pingFailMsg = 'sent %s pings, only received %s' % ( sent, received )
        self.assertEqual( sent, received, msg=pingFailMsg )
        # pylint: enable=W0612
        loptsStr = ', '.join( '%s: %s' % ( opt, value )
                              for opt, value in lopts.items() )
        msg = ( '\nTesting Link Delay of %s ms\n'
                'ping results across 4 links:\n'
                '(Sent, Received, rttmin, rttavg, rttmax, rttdev)\n'
                '%s\n'
                'Topo = SingleSwitchTopo, %s hosts\n'
                'Link = TCLink\n'
                'lopts = %s\n'
                'host = default'
                'switch = %s\n'
                % ( DELAY_MS, ping_outputs, N, loptsStr, self.switchClass ) )

        for rttval in [rttmin, rttavg, rttmax]:
            # Multiply delay by 4 to cover there & back on two links
            self.assertWithinTolerance( rttval, DELAY_MS * 4.0,
                                        DELAY_TOLERANCE, msg )

    def testLinkLoss( self ):
        "Verify that we see packet drops with a high configured loss rate."
        LOSS_PERCENT = 99
        REPS = 1
        lopts = { 'loss': LOSS_PERCENT, 'use_htb': True }
        mn = Mininet( topo=SingleSwitchOptionsTopo( n=N, lopts=lopts ),
                      host=CPULimitedHost, link=TCLink,
                      switch=self.switchClass,
                      waitConnected=True )
        # Drops are probabilistic, but the chance of no dropped packets is
        # 1 in 100 million with 4 hops for a link w/99% loss.
        dropped_total = 0
        mn.start()
        for _ in range(REPS):
            dropped_total += mn.ping(timeout='1')
        mn.stop()

        loptsStr = ', '.join( '%s: %s' % ( opt, value )
                              for opt, value in lopts.items() )
        msg = ( '\nTesting packet loss with %d%% loss rate\n'
                'number of dropped pings during mininet.ping(): %s\n'
                'expected number of dropped packets: 1\n'
                'Topo = SingleSwitchTopo, %s hosts\n'
                'Link = TCLink\n'
                'lopts = %s\n'
                'host = default\n'
                'switch = %s\n'
                % ( LOSS_PERCENT, dropped_total, N, loptsStr,
                    self.switchClass ) )

        self.assertGreater( dropped_total, 0, msg )

    def testMostOptions( self ):
        "Verify topology creation with most link options and CPU limits."
        lopts = { 'bw': 10, 'delay': '5ms', 'use_htb': True }
        hopts = { 'cpu': 0.5 / N }
        msg = '\nTesting many cpu and link options\n'
        self.runOptionsTopoTest( N, msg, hopts=hopts, lopts=lopts )

# pylint: enable=E1101

class testOptionsTopoOVSKernel( testOptionsTopoCommon, unittest.TestCase ):
    """Verify ability to create networks with host and link options
       (OVS kernel switch)."""
    longMessage = True
    switchClass = OVSSwitch

@unittest.skip( 'Skipping OVS user switch test for now' )
class testOptionsTopoOVSUser( testOptionsTopoCommon, unittest.TestCase ):
    """Verify ability to create networks with host and link options
       (OVS user switch)."""
    longMessage = True
    switchClass = partial( OVSSwitch, datapath='user' )

@unittest.skipUnless( quietRun( 'which ivs-ctl' ), 'IVS is not installed' )
class testOptionsTopoIVS( testOptionsTopoCommon, unittest.TestCase ):
    "Verify ability to create networks with host and link options (IVS)."
    longMessage = True
    switchClass = IVSSwitch

@unittest.skipUnless( quietRun( 'which ofprotocol' ),
                      'Reference user switch is not installed' )
class testOptionsTopoUserspace( testOptionsTopoCommon, unittest.TestCase ):
    """Verify ability to create networks with host and link options
     (UserSwitch)."""
    longMessage = True
    switchClass = UserSwitch

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
