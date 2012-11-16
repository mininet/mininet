#!/usr/bin/env python

"""Package: mininet
   Test creation and pings for topologies with link and/or CPU options."""

import unittest

from mininet.net import Mininet
from mininet.node import OVSKernelSwitch
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.topo import Topo
from mininet.log import setLogLevel


SWITCH = OVSKernelSwitch
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


class testOptionsTopo( unittest.TestCase ):
    "Verify ability to create networks with host and link options."

    def runOptionsTopoTest( self, n, hopts=None, lopts=None ):
        "Generic topology-with-options test runner."
        mn = Mininet( topo=SingleSwitchOptionsTopo( n=n, hopts=hopts,
                                                    lopts=lopts ),
                      host=CPULimitedHost, link=TCLink )
        dropped = mn.run( mn.ping )
        self.assertEqual( dropped, 0 )

    def assertWithinTolerance(self, measured, expected, tolerance_frac):
        """Check that a given value is within a tolerance of expected
        tolerance_frac: less-than-1.0 value; 0.8 would yield 20% tolerance.
        """
        self.assertTrue( float(measured) >= float(expected) * tolerance_frac )
        self.assertTrue( float(measured) >= float(expected) * tolerance_frac )

    def testCPULimits( self ):
        "Verify topology creation with CPU limits set for both schedulers."
        CPU_FRACTION = 0.1
        CPU_TOLERANCE = 0.8  # CPU fraction below which test should fail
        hopts = { 'cpu': CPU_FRACTION }
        #self.runOptionsTopoTest( N, hopts=hopts )

        mn = Mininet( SingleSwitchOptionsTopo( n=N, hopts=hopts ),
                      host=CPULimitedHost )
        mn.start()
        results = mn.runCpuLimitTest( cpu=CPU_FRACTION )
        mn.stop()
        for cpu in results:
            self.assertWithinTolerance( cpu, CPU_FRACTION, CPU_TOLERANCE )

    def testLinkBandwidth( self ):
        "Verify that link bandwidths are accurate within a bound."
        BW = 5  # Mbps
        BW_TOLERANCE = 0.8  # BW fraction below which test should fail
        # Verify ability to create limited-link topo first;
        lopts = { 'bw': BW, 'use_htb': True }
        # Also verify correctness of limit limitng within a bound.
        mn = Mininet( SingleSwitchOptionsTopo( n=N, lopts=lopts ),
                      link=TCLink )
        bw_strs = mn.run( mn.iperf )
        for bw_str in bw_strs:
            bw = float( bw_str.split(' ')[0] )
            self.assertWithinTolerance( bw, BW, BW_TOLERANCE )

    def testLinkDelay( self ):
        "Verify that link delays are accurate within a bound."
        DELAY_MS = 15
        DELAY_TOLERANCE = 0.8  # Delay fraction below which test should fail
        lopts = { 'delay': '%sms' % DELAY_MS, 'use_htb': True }
        mn = Mininet( SingleSwitchOptionsTopo( n=N, lopts=lopts ),
                      link=TCLink )
        ping_delays = mn.run( mn.pingFull )
        test_outputs = ping_delays[0]
        # Ignore unused variables below
        # pylint: disable-msg=W0612
        node, dest, ping_outputs = test_outputs
        sent, received, rttmin, rttavg, rttmax, rttdev = ping_outputs
        self.assertEqual( sent, received )
        # pylint: enable-msg=W0612
        for rttval in [rttmin, rttavg, rttmax]:
            # Multiply delay by 4 to cover there & back on two links
            self.assertWithinTolerance( rttval, DELAY_MS * 4.0,
                                        DELAY_TOLERANCE)

    def testLinkLoss( self ):
        "Verify that we see packet drops with a high configured loss rate."
        LOSS_PERCENT = 99
        REPS = 1
        lopts = { 'loss': LOSS_PERCENT, 'use_htb': True }
        mn = Mininet( topo=SingleSwitchOptionsTopo( n=N, lopts=lopts ),
                      host=CPULimitedHost, link=TCLink )
        # Drops are probabilistic, but the chance of no dropped packets is
        # 1 in 100 million with 4 hops for a link w/99% loss.
        dropped_total = 0
        mn.start()
        for _ in range(REPS):
            dropped_total += mn.ping(timeout='1')
        mn.stop()
        self.assertTrue(dropped_total > 0)

    def testMostOptions( self ):
        "Verify topology creation with most link options and CPU limits."
        lopts = { 'bw': 10, 'delay': '5ms', 'use_htb': True }
        hopts = { 'cpu': 0.5 / N }
        self.runOptionsTopoTest( N, hopts=hopts, lopts=lopts )


if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
