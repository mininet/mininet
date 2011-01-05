#!/usr/bin/env python

"""Package: mininet
   Test creation and all-pairs ping for each included mininet topo type."""

import unittest

from mininet.net import init, Mininet
from mininet.node import Host, Controller, ControllerParams
# from mininet.node import KernelSwitch
from mininet.node import UserSwitch, OVSKernelSwitch
from mininet.topo import SingleSwitchTopo, LinearTopo
from mininet.log import setLogLevel

SWITCHES = { 'user': UserSwitch,
             'ovsk': OVSKernelSwitch,
            # 'kernel': KernelSwitch
}


class testSingleSwitch( unittest.TestCase ):
    "For each datapath type, test ping with single switch topologies."

    def testMinimal( self ):
        "Ping test with both datapaths on minimal topology"
        init()
        for switch in SWITCHES.values():
            controllerParams = ControllerParams( '10.0.0.0', 8 )
            mn = Mininet( SingleSwitchTopo(), switch, Host, Controller,
                         controllerParams )
            dropped = mn.run( mn.ping )
            self.assertEqual( dropped, 0 )

    def testSingle5( self ):
        "Ping test with both datapaths on 5-host single-switch topology"
        init()
        for switch in SWITCHES.values():
            controllerParams = ControllerParams( '10.0.0.0', 8 )
            mn = Mininet( SingleSwitchTopo( k=5 ), switch, Host, Controller,
                         controllerParams )
            dropped = mn.run( mn.ping )
            self.assertEqual( dropped, 0 )


class testLinear( unittest.TestCase ):
    "For each datapath type, test all-pairs ping with LinearNet."

    def testLinear5( self ):
        "Ping test with both datapaths on a 5-switch topology"
        init()
        for switch in SWITCHES.values():
            controllerParams = ControllerParams( '10.0.0.0', 8 )
            mn = Mininet( LinearTopo( k=5 ), switch, Host, Controller,
                         controllerParams )
            dropped = mn.run( mn.ping )
            self.assertEqual( dropped, 0 )


if __name__ == '__main__':
    setLogLevel('warning')
    unittest.main()
