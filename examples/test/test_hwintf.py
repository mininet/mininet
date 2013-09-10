#!/usr/bin/env python

"""TEST"""

import unittest
import pexpect
import re
from time import sleep
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import Node
from mininet.link import Link, Intf

class testHwintf( unittest.TestCase ):
    "Test ping with single switch topology (common code)."

    prompt = 'mininet>'

    def _testE2E( self ):
        results = [ "Results:", pexpect.EOF, pexpect.TIMEOUT ]
        p = pexpect.spawn( 'python -m mininet.examples.simpleperf' )
        index = p.expect( results, timeout=600 )
        self.assertEqual( index, 0 )
        p.wait()

    def setUp( self ):
        self.h3 = Node( 't0', ip='10.0.0.3/8' )
        self.n0 = Node( 't1', inNamespace=False)
        Link( self.h3, self.n0 )
        self.h3.configDefault()

    def testLocalPing( self ):
        p = pexpect.spawn( 'python -m mininet.examples.hwintf %s' % self.n0.intf() )
        p.expect( self.prompt )
        p.sendline( 'pingall' )
        p.expect ( '(\d+)% dropped' )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        self.assertEqual( percent, 0 )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def testExternalPing( self ):
        expectStr = '(\d+) packets transmitted, (\d+) received'
        p = pexpect.spawn( 'python -m mininet.examples.hwintf %s' % self.n0.intf() )
        p.expect( self.prompt )

        m = re.search( expectStr, self.h3.cmd( 'ping -v -c 1 10.0.0.1' ) )
        tx = m.group( 1 )
        rx = m.group( 2 )
        self.assertEqual( tx, rx )

        p.sendline( 'h1 ping -c 1 10.0.0.3')
        p.expect( expectStr )
        tx = p.match.group( 1 )
        rx = p.match.group( 2 )
        self.assertEqual( tx, rx )
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()

    def tearDown( self ):
        self.h3.terminate()
        self.n0.terminate()


            
    ''' TAP garbage 
     def testHwintf( self ):
        ifname = 'br3'
        #sudo ip tuntap add mode tap br0
        #sudo ip tuntap del mode tap br0
        #sudo ip link add name test0 type veth peer name test1
        #sudo ip link del test0
        t0 = Node( 't0', inNamespace=False, ip='10.0.0.3/8' )

        t1 = Node( 't1', inNamespace=False)
        #t0.cmd( 'ip tuntap add mode tap %s' % ifname )
        #Intf( ifname, t0 )
        print Link( t0, t1 )
        t0.configDefault()

        print t0.cmd( 'ifconfig' )
        ifname =  t1.intf()


        try:
            foo = pexpect.spawn( 'wireshark' )
            p = pexpect.spawn( 'python -m mininet.examples.hwintf %s' % ifname )
            p.expect( self.prompt )
            #t0.cmd( 'ip link set dev %s up' % ifname )
            #t0.cmd( "bash -c 'echo 1 > /proc/sys/net/ipv4/ip_forward'" )
            #t0.cmd( "bash -c 'echo 1 > /proc/sys/net/ipv4/conf/%s/proxy_arp'" % ifname)
            #t0.cmd( 'arp -Ds 10.0.0.3 s1 pub' )

            #p.sendline( 'x s1 wireshark' )
            print t0.cmd( 'ifconfig %s' % ifname )
            print t0.cmd( 'ip route' )
            print t0.cmd( 'ping -v -c 1 10.0.0.3' )
            print t0.cmd( 'ping -v -c 1 10.0.0.1' )

            p.interact()
            #p.wait()
        finally:
            #t0.cmd( 'ip tuntap del mode tap %s' % ifname )
            t0.terminate()
            t1.terminate()
        #t0.configDefault()
    '''

if __name__ == '__main__':
    setLogLevel( 'warning' )
    unittest.main()
