#!/usr/bin/env python

"""Package: mininet
   Test creation and all-pairs ping for each included mininet topo type."""

import unittest

from mininet.net import Mininet
from mininet.node import Host, Controller
from mininet.node import UserSwitch, OVSKernelSwitch, IVSSwitch
from mininet.topo import SingleSwitchTopo, LinearTopo
from mininet.log import setLogLevel


class testSingleSwitchCommon( object ):
    "Test ping with single switch topology (common code)."

    switchClass = None # overridden in subclasses

    def testMinimal( self ):
        "Ping test on minimal topology"
        mn = Mininet( SingleSwitchTopo(), self.switchClass, Host, Controller )
        dropped = mn.run( mn.ping )
        self.assertEqual( dropped, 0 )

    def testSingle5( self ):
        "Ping test on 5-host single-switch topology"
        mn = Mininet( SingleSwitchTopo( k=5 ), self.switchClass, Host, Controller )
        dropped = mn.run( mn.ping )
        self.assertEqual( dropped, 0 )

class testSingleSwitchOVSKernel( testSingleSwitchCommon, unittest.TestCase ):
    "Test ping with single switch topology (OVS kernel switch)."
    switchClass = OVSKernelSwitch

class testSingleSwitchIVS( testSingleSwitchCommon, unittest.TestCase ):
    "Test ping with single switch topology (IVS switch)."
    switchClass = IVSSwitch

class testSingleSwitchUserspace( testSingleSwitchCommon, unittest.TestCase ):
    "Test ping with single switch topology (Userspace switch)."
    switchClass = UserSwitch


class testLinearCommon( object ):
    "Test all-pairs ping with LinearNet (common code)."

    switchClass = None # overridden in subclasses

    def testLinear5( self ):
        "Ping test on a 5-switch topology"
        mn = Mininet( LinearTopo( k=5 ), self.switchClass, Host, Controller )
        dropped = mn.run( mn.ping )
        self.assertEqual( dropped, 0 )

class testLinearOVSKernel( testLinearCommon, unittest.TestCase ):
    "Test all-pairs ping with LinearNet (OVS kernel switch)."
    switchClass = OVSKernelSwitch

class testLinearIVS( testLinearCommon, unittest.TestCase ):
    "Test all-pairs ping with LinearNet (IVS switch)."
    switchClass = IVSSwitch

class testLinearUserspace( testLinearCommon, unittest.TestCase ):
    "Test all-pairs ping with LinearNet (Userspace switch)."
    switchClass = UserSwitch


if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
