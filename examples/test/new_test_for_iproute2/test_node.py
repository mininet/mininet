#!/usr/bin/env python
import re
import unittest
import json
from mininet.net import Mininet
from mininet.util import genRandomMac

def jsonIpAddrToStrAddrInfo( jsonip ):
    ipaddress = json.loads(jsonip)
    return [ a for a in ipaddress[0]["addr_info"] if a["family"] == "inet" ]

class TestsetHostRoute(unittest.TestCase):
    
    def setUp( self ):
        self.regex = '(\d+) received'
        self.net = Mininet()
        self.h1 = self.net.addHost( 'h1', ip='192.168.1.1/24' )
        self.h2 = self.net.addHost( 'h2', ip='10.0.0.2/8' )
        self.net.addLink( self.h1, self.h2 )
        self.net.start()

    def testsetHostRoute( self ):
        result = self.h1.cmd('ping -c 1 %s' % self.h2.IP())
        self.assertTrue( 'Network is unreachable' in result )
        self.h1.setHostRoute(self.h2.IP(), self.h1.defaultIntf().name)
        self.h2.setHostRoute(self.h1.IP(), self.h2.defaultIntf().name)
        ping = self.h1.cmd('ping -c 1 %s | grep packets' % self.h2.IP())
        pingReceived = re.search(self.regex,ping)
        received = pingReceived.group(1)
        self.assertEqual(int(received),1)

    def tearDown( self ):
        self.net.stop()

class TestsetARP(unittest.TestCase):

    def setUp( self ):
        self.net = Mininet()
        self.c0 = self.net.addController()
        self.s1 = self.net.addSwitch( 's1' )
        self.h1 = self.net.addHost( 'h1' )
        self.h2 = self.net.addHost( 'h2' )
        self.h3 = self.net.addHost( 'h3' )
        self.net.addLink( self.h1, self.s1 )
        self.net.addLink( self.h2, self.s1 )
        self.net.addLink( self.h3, self.s1 )
        self.net.start()

    def testsetARP( self ):
        h1result = self.h1.cmd('ip neigh')
        self.assertEqual(h1result,'')
        h2result = self.h2.cmd('ip neigh')
        self.assertEqual(h2result,'')
        h3result = self.h3.cmd('ip neigh')
        self.assertEqual(h3result,'')
        
        self.h1.setARP(self.h2.IP(),self.h2.MAC())
        self.h2.setARP(self.h3.IP(),self.h3.MAC(),intf='h2-eth0')
        self.h3.setARP(self.h1.IP(),self.h1.MAC(),intf=self.h3.intfs[0])
        
        h1result = json.loads(self.h1.cmd('ip -j -p neigh'))
        h2result = json.loads(self.h2.cmd('ip -j -p neigh'))
        h3result = json.loads(self.h3.cmd('ip -j -p neigh'))
        
        h2ip = h1result[0]['dst']
        h2mac = h1result[0]['lladdr']
        self.assertEqual(self.h2.IP(),h2ip)
        self.assertEqual(self.h2.MAC(),h2mac)
        
        h3ip = h2result[0]['dst']
        h3mac = h2result[0]['lladdr']
        self.assertEqual(self.h3.IP(),h3ip)
        self.assertEqual(self.h3.MAC(),h3mac)
        
        h1ip = h3result[0]['dst']
        h1mac = h3result[0]['lladdr']
        self.assertEqual(self.h1.IP(),h1ip)
        self.assertEqual(self.h1.MAC(),h1mac)
        
    def tearDown( self ):
        self.net.stop()

class TestIPandMAC(unittest.TestCase):

    def setUp( self ):
        self.net = Mininet()
        self.c0 = self.net.addController()
        self.s1 = self.net.addSwitch( 's1' )
        self.h1 = self.net.addHost( 'h1' )
        self.h2 = self.net.addHost( 'h2' )
        self.net.addLink( self.h1, self.s1 )
        self.net.addLink( self.h2, self.s1 )
        self.net.start()

    def testIP( self ):
        addrInfo = jsonIpAddrToStrAddrInfo(self.h1.cmd( 'ip -j -p address show dev h1-eth0' ))[0]
        ip = addrInfo['local']
        prefixlen = str( addrInfo['prefixlen'] )
        self.assertEqual( ip, self.h1.intfs[0].ip )
        self.assertEqual( ip, self.h1.IP() )
        self.assertEqual( prefixlen, self.h1.intfs[0].prefixLen )
        newip = '10.25.0.1'
        newPrefixlen = '24'
        self.h1.cmd('ip addr del', '%s/%s' % (ip,prefixlen) ,'dev','h1-eth0')
        self.h1.cmd('ip addr add', '%s/%s' % (newip,newPrefixlen) ,'dev','h1-eth0')
        addrInfo = jsonIpAddrToStrAddrInfo(self.h1.cmd( 'ip -j -p address show dev h1-eth0' ))[0]
        ip = addrInfo['local']
        prefixlen = str( addrInfo['prefixlen'] )
        self.assertFalse( ip == self.h1.intfs[0].ip )
        self.assertFalse( prefixlen == self.h1.intfs[0].prefixLen )
        self.assertFalse( ip == self.h1.IP() )
        self.assertEqual( ip, self.h1.IP(intf='h1-eth0', update=True) )
        self.assertEqual( ip, self.h1.intfs[0].ip )
        self.assertEqual( prefixlen, self.h1.intfs[0].prefixLen )

    def testMAC( self ):
        h1eth0mac = json.loads(self.h1.cmd( 'ip -br -j -p link show dev', self.h1.intfs[0].name ))[0]["address"]
        self.assertEqual( h1eth0mac, self.h1.intfs[0].mac )
        self.assertEqual( h1eth0mac, self.h1.MAC() )
        newmac = genRandomMac()
        self.h1.cmd('ip link set dev', self.h1.intfs[0].name, 'down')
        self.h1.cmd('ip link set dev', self.h1.intfs[0].name, 'address', newmac)
        self.h1.cmd('ip link set dev', self.h1.intfs[0].name, 'up')
        h1eth0mac = json.loads(self.h1.cmd( 'ip -br -j -p link show dev', self.h1.intfs[0].name ))[0]["address"]
        self.assertTrue( h1eth0mac == newmac )
        self.assertFalse( h1eth0mac == self.h1.intfs[0].mac )
        self.assertFalse( h1eth0mac == self.h1.MAC() )
        self.assertTrue( h1eth0mac == self.h1.MAC(intf='h1-eth0', update=True) )
        self.assertTrue( h1eth0mac == self.h1.intfs[0].mac )
        
    def tearDown( self ):
        self.net.stop()

if __name__ == '__main__':
    unittest.main()   
        
