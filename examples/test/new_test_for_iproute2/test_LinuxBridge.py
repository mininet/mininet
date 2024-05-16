#!/usr/bin/env python
import re
import unittest
from mininet.net import Mininet
from mininet.nodelib import LinuxBridge
from mininet.topo import Topo
from functools import partial
from mininet.util import irange

class RingTopo( Topo ):
    
    def build( self, switchNum=3, hosts=1 ):
        if switchNum < 3:
            raise Exception( 'The minimal number of switches to form a ring is 3.')
        first = self.addSwitch( 's1' )
        for hostnum in irange( 1, hosts ):
            host = self.addHost( 'h%s' % hostnum )
            self.addLink( first, host )
        last = first
        for number in irange( 2, switchNum ):
            next = self.addSwitch( 's%s' % number )
            for hostnum in irange( ((number-1)*hosts)+1, ((number-1)*hosts)+hosts ):
                host = self.addHost( 'h%s' % hostnum )
                self.addLink( next, host )
            self.addLink( last, next )
            last = next
        self.addLink( last, first )
        

def NodesConnectedToSwitch( switch ):
    result = []
    for intf in switch.intfList():
        if intf.link:
            intfs = [ intf.link.intf1, intf.link.intf2 ]
            intfs.remove( intf )
            node = intfs[ 0 ].node
            name = node.name
            if name[0:1]=='h':
                result.append(node)
    return result

class lxbrTest(unittest.TestCase):
    
    def setUp( self ):
        self.regex = '(\d+) received'
        topo = RingTopo(hosts=2)
        switch = partial( LinuxBridge, stp=True )
        self.net = Mininet( topo=topo, switch=switch, waitConnected=True )
        self.net.start()
        self.hosts = [ self.net.getNodeByName( h ) for h in topo.hosts() ]
        self.switches = [ self.net.getNodeByName( s ) for s in topo.switches() ]
        self.swichToStop = self.switches[ -1 ]
        self.nodeToPing = NodesConnectedToSwitch(self.swichToStop)[-1]
        self.pingingNode = [h for h in self.hosts if h != self.nodeToPing][0]

    def testHostsAndSwitchesNum( self ):
        self.assertFalse(len(self.switches) < 3)
        self.assertFalse(len(self.hosts) < 2)

    def testAfterSetup( self ):
        isForwarding = 'forwarding' in self.swichToStop.cmd('bridge link show | grep \'%s state\'' % self.swichToStop.name )
        self.assertTrue(isForwarding)
        ping = self.pingingNode.cmd('ping -c 1 %s | grep packets' % self.nodeToPing.IP())
        pingReceived = re.search(self.regex,ping)
        received = pingReceived.group(1)
        self.assertEqual(int(received),1)
        
    def testAfterStopLinuxBridge( self ):
        self.swichToStop.stop(deleteIntfs=False)
        stoppedSwitchState = self.swichToStop.cmd('bridge link show | grep \'%s state\'' % self.swichToStop.name )
        self.assertEqual(stoppedSwitchState,'')
        ping = self.pingingNode.cmd('ping -c 1 %s | grep packets' % self.nodeToPing.IP())
        pingReceived = re.search(self.regex,ping)
        received = pingReceived.group(1)
        self.assertEqual(int(received),0)
        
    def testAfterStartLinuxBridge( self ):
        self.swichToStop.start([])
        isListening = 'listening' in self.swichToStop.cmd('bridge link show | grep \'%s state\'' % self.swichToStop.name )
        self.assertTrue(isListening)
        self.net.waitConnected()
        isForwarding = 'forwarding' in self.swichToStop.cmd('bridge link show | grep \'%s state\'' % self.swichToStop.name )
        self.assertTrue(isForwarding)
        ping = self.pingingNode.cmd('ping -c 1 %s | grep packets' % self.nodeToPing.IP())
        pingReceived = re.search(self.regex,ping)
        received = pingReceived.group(1)
        self.assertEqual(int(received),1)
        
        
    def tearDown( self ):
        self.net.stop()
   
if __name__ == '__main__':
    unittest.main()    
