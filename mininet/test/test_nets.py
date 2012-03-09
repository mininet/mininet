#!/usr/bin/env python

"""Package: mininet
   Test creation and all-pairs ping for each included mininet topo type."""

import unittest

from mininet.net import Mininet
from mininet.node import Host, Controller
from mininet.node import UserSwitch, OVSKernelSwitch
from mininet.topo import SingleSwitchTopo, LinearTopo
from mininet.log import setLogLevel

SWITCHES = { 'user': UserSwitch,
             'ovsk': OVSKernelSwitch,
}


class testSingleSwitch( unittest.TestCase ):
    "For each datapath type, test ping with single switch topologies."

    def testMinimal( self ):
        "Ping test with both datapaths on minimal topology"
        for switch in SWITCHES.values():
            mn = Mininet( SingleSwitchTopo(), switch, Host, Controller )
            dropped = mn.run( mn.ping )
            self.assertEqual( dropped, 0 )

    def testSingle5( self ):
        "Ping test with both datapaths on 5-host single-switch topology"
        for switch in SWITCHES.values():
            mn = Mininet( SingleSwitchTopo( k=5 ), switch, Host, Controller )
            dropped = mn.run( mn.ping )
            self.assertEqual( dropped, 0 )


class testLinear( unittest.TestCase ):
    "For each datapath type, test all-pairs ping with LinearNet."

    def testLinear5( self ):
        "Ping test with both datapaths on a 5-switch topology"
        for switch in SWITCHES.values():
            mn = Mininet( LinearTopo( k=5 ), switch, Host, Controller )
            dropped = mn.run( mn.ping )
            self.assertEqual( dropped, 0 )


if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
