#!/usr/bin/env python

"""Package: mininet
   Test creation and all-pairs ping for each included mininet topo type."""

import unittest
import sys
from functools import partial

from mininet.net import Mininet
from mininet.node import Host, Controller
from mininet.node import UserSwitch, OVSSwitch, IVSSwitch
from mininet.topo import SingleSwitchTopo, LinearTopo
from mininet.log import setLogLevel
from mininet.util import quietRun
from mininet.clean import cleanup

# Tell pylint not to complain about calls to other class
# pylint: disable=E1101

class testSingleSwitchCommon( object ):
    "Test ping with single switch topology (common code)."

    switchClass = None  # overridden in subclasses

    @staticmethod
    def tearDown():
        "Clean up if necessary"
        if sys.exc_info() != ( None, None, None ):
            cleanup()

    def testMinimal( self ):
        "Ping test on minimal topology"
        mn = Mininet( SingleSwitchTopo(), self.switchClass, Host, Controller,
                      waitConnected=True )
        dropped = mn.run( mn.ping )
        self.assertEqual( dropped, 0 )

    def testSingle5( self ):
        "Ping test on 5-host single-switch topology"
        mn = Mininet( SingleSwitchTopo( k=5 ), self.switchClass, Host,
                      Controller, waitConnected=True )
        dropped = mn.run( mn.ping )
        self.assertEqual( dropped, 0 )

# pylint: enable=E1101

class testSingleSwitchOVSKernel( testSingleSwitchCommon, unittest.TestCase ):
    "Test ping with single switch topology (OVS kernel switch)."
    switchClass = OVSSwitch

class testSingleSwitchOVSUser( testSingleSwitchCommon, unittest.TestCase ):
    "Test ping with single switch topology (OVS user switch)."
    switchClass = partial( OVSSwitch, datapath='user' )

@unittest.skipUnless( quietRun( 'which ivs-ctl' ), 'IVS is not installed' )
class testSingleSwitchIVS( testSingleSwitchCommon, unittest.TestCase ):
    "Test ping with single switch topology (IVS switch)."
    switchClass = IVSSwitch

@unittest.skipUnless( quietRun( 'which ofprotocol' ),
                      'Reference user switch is not installed' )
class testSingleSwitchUserspace( testSingleSwitchCommon, unittest.TestCase ):
    "Test ping with single switch topology (Userspace switch)."
    switchClass = UserSwitch


# Tell pylint not to complain about calls to other class
# pylint: disable=E1101

class testLinearCommon( object ):
    "Test all-pairs ping with LinearNet (common code)."

    switchClass = None  # overridden in subclasses

    def testLinear5( self ):
        "Ping test on a 5-switch topology"
        mn = Mininet( LinearTopo( k=5 ), self.switchClass, Host,
                      Controller, waitConnected=True )
        dropped = mn.run( mn.ping )
        self.assertEqual( dropped, 0 )

# pylint: enable=E1101


class testLinearOVSKernel( testLinearCommon, unittest.TestCase ):
    "Test all-pairs ping with LinearNet (OVS kernel switch)."
    switchClass = OVSSwitch

class testLinearOVSUser( testLinearCommon, unittest.TestCase ):
    "Test all-pairs ping with LinearNet (OVS user switch)."
    switchClass = partial( OVSSwitch, datapath='user' )

@unittest.skipUnless( quietRun( 'which ivs-ctl' ), 'IVS is not installed' )
class testLinearIVS( testLinearCommon, unittest.TestCase ):
    "Test all-pairs ping with LinearNet (IVS switch)."
    switchClass = IVSSwitch

@unittest.skipUnless( quietRun( 'which ofprotocol' ),
                      'Reference user switch is not installed' )
class testLinearUserspace( testLinearCommon, unittest.TestCase ):
    "Test all-pairs ping with LinearNet (Userspace switch)."
    switchClass = UserSwitch


if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
