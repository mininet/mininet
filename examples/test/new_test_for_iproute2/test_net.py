#!/usr/bin/env python
import unittest
import json
from mininet.net import Mininet
from mininet.util import pexpect

class TestConfigLinkStatus(unittest.TestCase):
    
    def setUp( self ):
        self.net = Mininet()
        self.c0 = self.net.addController()
        self.s1 = self.net.addSwitch( 's1' )
        self.h1 = self.net.addHost( 'h1' )
        self.h2 = self.net.addHost( 'h2' )
        self.net.addLink( self.h1, self.s1 )
        self.net.addLink( self.h2, self.s1 )
        self.net.start()

    def testStatusDown( self ):
        self.net.configLinkStatus('h1','s1','down')
        h1Result = json.loads(self.h1.cmd( 'ip -br -j -p link show dev h1-eth0' ))
        s1Result = json.loads(self.s1.cmd( 'ip -br -j -p link show dev s1-eth1' ))
        self.assertFalse('UP' in h1Result[0]['flags'])
        self.assertFalse('UP' in s1Result[0]['flags'])

    def testStatusUp( self ):
        self.net.configLinkStatus('h1','s1','up')
        h1Result = json.loads(self.h1.cmd( 'ip -br -j -p link show dev h1-eth0' ))
        s1Result = json.loads(self.s1.cmd( 'ip -br -j -p link show dev s1-eth1' ))
        self.assertTrue('UP' in h1Result[0]['flags'])
        self.assertTrue('UP' in s1Result[0]['flags'])          
        
    def tearDown( self ):
        self.net.stop()

class TestPingAllFull(unittest.TestCase):

    def setUp( self ):
        self.net = Mininet()
        self.c0 = self.net.addController()
        self.s1 = self.net.addSwitch( 's1' )
        self.h1 = self.net.addHost( 'h1', ip='0.0.0.0/0' )
        self.h2 = self.net.addHost( 'h2', ip='0.0.0.0/0' )
        self.net.addLink( self.h1, self.s1 )
        self.net.addLink( self.h2, self.s1 )
        self.net.start()
        
    def testPingAllFull( self ):
        h1ip = self.h1.IP(update=True)
        h2ip = self.h2.IP(update=True)
        all_outputs = self.net.pingAllFull()
        for outputs in all_outputs:
            _, _, ping_outputs = outputs
            sent, received, _, _, _, _ = ping_outputs
            self.assertTrue( sent == 0 and received == 0 and h1ip is None and h2ip is None )
        
        h1newip = '11.0.0.1'
        h2newip = '10.0.0.2'
        self.h1.setIP( h1newip )
        self.h2.setIP( h2newip )
        h1ip = self.h1.IP()
        h2ip = self.h2.IP()
        all_outputs = self.net.pingAllFull()
        for outputs in all_outputs:
            _, _, ping_outputs = outputs
            sent, received, _, _, _, _ = ping_outputs
            self.assertTrue( sent == 1 and received == 0 and h1ip == h1newip and h2ip == h2newip )
        
        h1newip = '10.0.0.1'
        self.h1.setIP( h1newip )
        h1ip = self.h1.IP()
        all_outputs = self.net.pingAllFull()
        for outputs in all_outputs:
            _, _, ping_outputs = outputs
            sent, received, _, _, _, _ = ping_outputs
            self.assertTrue( sent == 1 and received == 1 and h1ip == h1newip and h2ip == h2newip )
            
    def tearDown( self ):
        self.net.stop()
        
class testPingAll( unittest.TestCase ):
    
    def setUp( self ):
        self.prompt = 'mininet>'
        self.opts = [ 'No packets sent','\*\*\* Results: \d{1,3}% dropped \((\d+\/\d+) received\)', self.prompt ]
        self.net = pexpect.spawn( 'python ./forTests/net.py' )
        self.net.expect( self.prompt )
        
    def testPingall( self ):
        self.net.sendline( 'pingall' )
        packets = None
        result = None
        while True:
            index = self.net.expect( self.opts )
            if index == 0:
                packets = self.net.match.group( 0 )
            elif index == 1:
                result == self.net.match.group( 1 )
            else:
                break
        
        self.assertTrue( packets == 'No packets sent' )
        self.assertTrue( result is None )
        
        self.net.sendline( 'py h1.setIP(\'11.0.0.1\')' )
        self.net.expect( self.prompt )
        self.net.sendline( 'py h2.setIP(\'10.0.0.2\')' )
        self.net.expect( self.prompt )
        self.net.sendline( 'pingall' )
        packets = None
        result = None
        while True:
            index = self.net.expect( self.opts )
            if index == 0:
                packets = self.net.match.group( 0 )
            elif index == 1:
                result = self.net.match.group( 1 ).split( '/' )
            else:
                break
                
        self.assertTrue( packets is None )
        self.assertTrue( int(result[0]) == 0 and int(result[1]) == 2 )
        
        self.net.sendline( 'py h1.setIP(\'10.0.0.1\')' )
        self.net.expect( self.prompt )
        self.net.sendline( 'pingall' )
        packets = None
        result = None
        while True:
            index = self.net.expect( self.opts )
            if index == 0:
                packets = self.net.match.group( 0 )
            elif index == 1:
                result = self.net.match.group( 1 ).split( '/' )
            else:
                break
                
        self.assertTrue( packets is None )
        self.assertTrue( int(result[0]) == 2 and int(result[1]) == 2 )

    def tearDown( self ):
        self.net.sendline( 'exit' )
        self.net.wait()

if __name__ == '__main__':
    unittest.main()        

