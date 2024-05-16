#!/usr/bin/env python
import unittest
import json
from mininet.net import Mininet
from mininet.util import genRandomMac

def jsonIpAddrToStrAddrInfo( jsonip ):
    ipaddress = json.loads(jsonip)
    return [ a for a in ipaddress[0]["addr_info"] if a["family"] == "inet" ]

class TestLink(unittest.TestCase):
    
    def setUp( self ):
        self.net = Mininet()
        self.c0 = self.net.addController()
        self.s1 = self.net.addSwitch( 's1' )
        self.h1 = self.net.addHost( 'h1' )
        self.h2 = self.net.addHost( 'h2' )
        self.net.addLink( self.h1, self.s1 )
        self.net.addLink( self.h2, self.s1 )
        self.net.start()

    def testIpLinkNoArgsNoOpts( self ):
        iplink = self.h1.intfs[0].ipLink()
        iplink2 = self.h1.cmd('ip link')
        self.assertEqual(iplink,iplink2)

    def testIpLinkWrongDevExeption( self ):
        s1eth1 = self.s1.intfs[1]
        s1eth2 = self.s1.intfs[2]
        self.assertFalse(s1eth1.name == s1eth2.name)
        with self.assertRaises(Exception):
            iplink = s1eth1.ipLink('show', 'dev', s1eth2.name )

    def testIpLinkArgsOpts( self ):
        iplink = self.h1.intfs[0].ipLink('show','dev','h1-eth0',options='-br')
        iplink2 = self.h1.cmd('ip -br link show dev h1-eth0')
        self.assertEqual(iplink,iplink2)

    def testIpLinkUpDown( self ):
        iplink = json.loads(self.h1.cmd('ip -br -j -p link show dev h1-eth0'))
        self.assertTrue('UP' in iplink[0]['flags'])
        
        self.h1.intfs[0].ipLink('set','dev','h1-eth0','down')
        iplink = json.loads(self.h1.cmd('ip -br -j -p link show dev h1-eth0'))
        self.assertFalse('UP' in iplink[0]['flags'])
        
        self.h1.intfs[0].ipLink('set','dev','h1-eth0','up')
        iplink = json.loads(self.h1.cmd('ip -br -j -p link show dev h1-eth0'))
        self.assertTrue('UP' in iplink[0]['flags'])

    def testIpAddrNoArgsNoOpts( self ):
        ipaddress = self.h1.intfs[0].ipAddress()
        ipaddress2 = self.h1.cmd('ip address')
        self.assertEqual(ipaddress,ipaddress2)

    def testIpAddrWrongDevExeption( self ):
        h1eth0 = self.h1.intfs[0]
        with self.assertRaises(Exception):
            ipaddress = h1eth0.ipAddress('show', 'dev', 'lo')

    def testIpAddrArgsOpts( self ):
        ipaddress = self.h1.intfs[0].ipAddress('show','dev','h1-eth0',options='-br -j')
        ipaddress2 = self.h1.cmd('ip -br -j address show dev h1-eth0')
        self.assertEqual(ipaddress,ipaddress2)

    def testIpAddrAddDel( self ):
        addrInfo = jsonIpAddrToStrAddrInfo(self.h1.intfs[0].ipAddress( 'show', 'dev', 'h1-eth0', options='-j -p' ))[0]
        ipFromIpAddr = '%s/%s' % (addrInfo['local'],addrInfo['prefixlen'])
        ipFromVar = '%s/%s' % (self.h1.intfs[0].ip, self.h1.intfs[0].prefixLen)
        self.assertEqual(ipFromIpAddr,ipFromVar)
        
        self.h1.intfs[0].ipAddress('del', ipFromIpAddr ,'dev','h1-eth0')
        addrInfo = jsonIpAddrToStrAddrInfo(self.h1.cmd( 'ip -j -p address show dev h1-eth0' ))
        self.assertTrue(addrInfo == [])
        
        newip = '172.16.10.25/16'
        self.h1.intfs[0].ipAddress('add', newip ,'dev','h1-eth0')
        addrInfo = jsonIpAddrToStrAddrInfo(self.h1.cmd( 'ip -j -p address show dev h1-eth0' ))[0]
        ipFromCmd = '%s/%s' % (addrInfo['local'],addrInfo['prefixlen'])
        self.assertEqual(newip,ipFromCmd)
        
        oldip = newip
        newip = '10.0.0.1/8'
        self.h1.intfs[0].ipAddress('del', oldip ,'dev','h1-eth0')
        self.h1.intfs[0].ipAddress('add', newip ,'dev','h1-eth0')

    def testSetIPNormalCases( self ):
        addrInfo = jsonIpAddrToStrAddrInfo(self.h2.cmd( 'ip -j -p address show dev h2-eth0' ))[0]
        ip = addrInfo['local']
        prefixlen = str(addrInfo['prefixlen'])
        self.assertEqual(ip,self.h2.intfs[0].ip)
        self.assertEqual(prefixlen,self.h2.intfs[0].prefixLen)
        
        newip = '192.168.0.2'
        newPrefix = '24'
        self.h2.intfs[0].setIP('%s/%s' % (newip,newPrefix))
        addrInfo = jsonIpAddrToStrAddrInfo(self.h2.cmd( 'ip -j -p address show dev h2-eth0' ))[0]
        ip = addrInfo['local']
        prefixlen = str( addrInfo['prefixlen'] )
        self.assertEqual( ip, self.h2.intfs[0].ip )
        self.assertEqual( prefixlen, self.h2.intfs[0].prefixLen )
        self.assertEqual( ip, newip )
        self.assertEqual( prefixlen, newPrefix )

        newip = '10.0.0.2'
        newPrefix = '8'
        self.h2.intfs[0].setIP( newip, newPrefix )
        addrInfo = jsonIpAddrToStrAddrInfo(self.h2.cmd( 'ip -j -p address show dev h2-eth0' ))[0]
        ip = addrInfo['local']
        prefixlen = str( addrInfo['prefixlen'] )
        self.assertEqual( ip, self.h2.intfs[0].ip )
        self.assertEqual( prefixlen, self.h2.intfs[0].prefixLen )
        self.assertEqual( ip, newip )
        self.assertEqual( prefixlen, newPrefix )

    def testSetIPToNull( self ):
        newip = '0.0.0.0'
        newPrefix = '8'
        self.h2.intfs[0].setIP('%s/%s' % (newip,newPrefix))
        addrInfo = jsonIpAddrToStrAddrInfo(self.h2.cmd( 'ip -j -p address show dev h2-eth0' ))
        self.assertTrue(addrInfo == [])
        self.assertEqual( None, self.h2.intfs[0].ip )
        self.assertEqual( None, self.h2.intfs[0].prefixLen )
        
        newip = '10.0.0.2'
        newPrefix = '8'
        self.h2.intfs[0].setIP('%s/%s' % (newip,newPrefix))

    def testSetIPWrongCases( self ):
        addrInfo = jsonIpAddrToStrAddrInfo(self.h1.cmd( 'ip -j -p address show dev h1-eth0' ))[0]
        ip = addrInfo['local']
        prefixlen = str( addrInfo['prefixlen'] )
        
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP()
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP(None)
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP(None, None)
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('10.0.0.56', None)
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP(None, '24')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('', '')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('10.1.0.108', '')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('', '16')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('192.168.10.1')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('256.5.200.34/8')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('256.5.200.34','8')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('175.256.200.34/16')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('175.256.200.34','16')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('175.55.256.34/24')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('175.55.256.34','24')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('175.55.60.256/24')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('175.55.60.256','24')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('128.99.60','24')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('128.99.60/24')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('175.55.60.56.15','24')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('175.55.60.56.15/24')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('abc.def.ghi.jkl/26')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('ijtiht+g9edcxr','26')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('192.168.10.1/33')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('192.168.10.1','33')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('192.168.10.1/k1')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setIP('192.168.10.1','k1')
        
        addrInfo = jsonIpAddrToStrAddrInfo(self.h1.cmd( 'ip -j -p address show dev h1-eth0' ))[0]
        ip2 = addrInfo['local']
        prefixlen2 = str( addrInfo['prefixlen'] )
        self.assertEqual( ip, self.h1.intfs[0].ip )
        self.assertEqual( prefixlen, self.h1.intfs[0].prefixLen )
        self.assertEqual( ip, ip2 )
        self.assertEqual( prefixlen, prefixlen2 )

    def testSetMACNormalCases( self ):
        h1eth0mac = json.loads(self.h1.cmd( 'ip -br -j -p link show dev', self.h1.intfs[0].name ))[0]["address"]
        self.assertEqual( h1eth0mac, self.h1.intfs[0].mac )
        for ch in '02468ace':
            newmac = genRandomMac(second_digit=ch)
            self.h1.intfs[0].setMAC(newmac)
            h1eth0mac = json.loads(self.h1.cmd( 'ip -br -j -p link show dev', self.h1.intfs[0].name ))[0]["address"]
            self.assertEqual( h1eth0mac, self.h1.intfs[0].mac )
            self.assertEqual( h1eth0mac, newmac )
            
    def testSetMACWrongCases( self ):
        h1eth0mac = json.loads(self.h1.cmd( 'ip -br -j -p link show dev', self.h1.intfs[0].name ))[0]["address"]
        self.assertEqual( h1eth0mac, self.h1.intfs[0].mac )
        with self.assertRaises(Exception):
            self.h1.intfs[0].setMAC()
        with self.assertRaises(Exception):
            self.h1.intfs[0].setMAC('00:00:00:00:00:00')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setMAC('ff:ff:ff:ff:ff:ff')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setMAC('02:050:1b:cf:b9:03')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setMAC('d6:05:1b:cf:z9:94')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setMAC('26:65:5d:cf:f9:')
        with self.assertRaises(Exception):
            self.h1.intfs[0].setMAC('c8:2b:1b:cf:f9:94:01')
        for ch in '13579bdf':
            newmac = genRandomMac(second_digit=ch)
            with self.assertRaises(Exception):
                self.h1.intfs[0].setMAC(newmac)

    def testUpdateIP( self ):
        addrInfo = jsonIpAddrToStrAddrInfo(self.h1.cmd( 'ip -j -p address show dev h1-eth0' ))[0]
        ip = addrInfo['local']
        prefixlen = str( addrInfo['prefixlen'] )
        self.assertEqual( ip, self.h1.intfs[0].ip )
        self.assertEqual( prefixlen, self.h1.intfs[0].prefixLen )
        newip = '10.237.125.10'
        newPrefixlen = '24'
        self.h1.cmd('ip addr del', '%s/%s' % (ip,prefixlen) ,'dev','h1-eth0')
        self.h1.cmd('ip addr add', '%s/%s' % (newip,newPrefixlen) ,'dev','h1-eth0')
        addrInfo = jsonIpAddrToStrAddrInfo(self.h1.cmd( 'ip -j -p address show dev h1-eth0' ))[0]
        ip = addrInfo['local']
        prefixlen = str( addrInfo['prefixlen'] )
        self.assertTrue( ip == newip )
        self.assertTrue( prefixlen == newPrefixlen )
        self.assertFalse( ip == self.h1.intfs[0].ip )
        self.assertFalse( prefixlen == self.h1.intfs[0].prefixLen )
        self.h1.intfs[0].updateIP()
        self.assertTrue( ip == self.h1.intfs[0].ip )
        self.assertTrue( prefixlen == self.h1.intfs[0].prefixLen )

    def testUpdateMAC( self ):
        h1eth0mac = json.loads(self.h1.cmd( 'ip -br -j -p link show dev', self.h1.intfs[0].name ))[0]["address"]
        self.assertEqual( h1eth0mac, self.h1.intfs[0].mac )
        newmac = genRandomMac()
        self.h1.cmd('ip link set dev', self.h1.intfs[0].name, 'down')
        self.h1.cmd('ip link set dev', self.h1.intfs[0].name, 'address', newmac)
        self.h1.cmd('ip link set dev', self.h1.intfs[0].name, 'up')
        h1eth0mac = json.loads(self.h1.cmd( 'ip -br -j -p link show dev', self.h1.intfs[0].name ))[0]["address"]
        self.assertTrue( h1eth0mac == newmac )
        self.assertFalse( h1eth0mac == self.h1.intfs[0].mac )
        self.h1.intfs[0].updateMAC()
        self.assertTrue( h1eth0mac == self.h1.intfs[0].mac )

    def testUpdateAddr( self ):
        addrInfo = jsonIpAddrToStrAddrInfo(self.h1.cmd( 'ip -j -p address show dev h1-eth0' ))[0]
        ip = addrInfo['local']
        prefixlen = str( addrInfo['prefixlen'] )
        self.assertEqual( ip, self.h1.intfs[0].ip )
        self.assertEqual( prefixlen, self.h1.intfs[0].prefixLen )
        h1eth0mac = json.loads(self.h1.cmd( 'ip -br -j -p link show dev', self.h1.intfs[0].name ))[0]["address"]
        self.assertEqual( h1eth0mac, self.h1.intfs[0].mac )
        newip = '10.114.0.1'
        newPrefixlen = '28'
        newmac = genRandomMac()
        self.h1.cmd('ip addr del', '%s/%s' % (ip,prefixlen) ,'dev','h1-eth0')
        self.h1.cmd('ip addr add', '%s/%s' % (newip,newPrefixlen) ,'dev','h1-eth0')
        self.h1.cmd('ip link set dev', self.h1.intfs[0].name, 'down')
        self.h1.cmd('ip link set dev', self.h1.intfs[0].name, 'address', newmac)
        self.h1.cmd('ip link set dev', self.h1.intfs[0].name, 'up')
        addrInfo = jsonIpAddrToStrAddrInfo(self.h1.cmd( 'ip -j -p address show dev h1-eth0' ))[0]
        ip = addrInfo['local']
        prefixlen = str( addrInfo['prefixlen'] )
        h1eth0mac = json.loads(self.h1.cmd( 'ip -br -j -p link show dev', self.h1.intfs[0].name ))[0]["address"]
        self.assertTrue( ip == newip )
        self.assertTrue( prefixlen == newPrefixlen )
        self.assertFalse( ip == self.h1.intfs[0].ip )
        self.assertFalse( prefixlen == self.h1.intfs[0].prefixLen )
        self.assertTrue( h1eth0mac == newmac )
        self.assertFalse( h1eth0mac == self.h1.intfs[0].mac )
        self.h1.intfs[0].updateAddr()
        self.assertTrue( ip == self.h1.intfs[0].ip )
        self.assertTrue( prefixlen == self.h1.intfs[0].prefixLen )
        self.assertTrue( h1eth0mac == self.h1.intfs[0].mac )
    
    def testIP( self ):
        addrInfo = jsonIpAddrToStrAddrInfo(self.h1.cmd( 'ip -j -p address show dev h1-eth0' ))[0]
        ip = addrInfo['local']
        prefixlen = str( addrInfo['prefixlen'] )
        self.assertEqual( ip, self.h1.intfs[0].ip )
        self.assertEqual( ip, self.h1.intfs[0].IP() )
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
        self.assertFalse( ip == self.h1.intfs[0].IP() )
        self.assertEqual( ip, self.h1.intfs[0].IP(update=True) )
        self.assertEqual( ip, self.h1.intfs[0].ip )
        self.assertEqual( prefixlen, self.h1.intfs[0].prefixLen )
        
    def testMAC( self ):
        h1eth0mac = json.loads(self.h1.cmd( 'ip -br -j -p link show dev', self.h1.intfs[0].name ))[0]["address"]
        self.assertEqual( h1eth0mac, self.h1.intfs[0].mac )
        self.assertEqual( h1eth0mac, self.h1.intfs[0].MAC() )
        newmac = genRandomMac()
        self.h1.cmd('ip link set dev', self.h1.intfs[0].name, 'down')
        self.h1.cmd('ip link set dev', self.h1.intfs[0].name, 'address', newmac)
        self.h1.cmd('ip link set dev', self.h1.intfs[0].name, 'up')
        h1eth0mac = json.loads(self.h1.cmd( 'ip -br -j -p link show dev', self.h1.intfs[0].name ))[0]["address"]
        self.assertTrue( h1eth0mac == newmac )
        self.assertFalse( h1eth0mac == self.h1.intfs[0].mac )
        self.assertFalse( h1eth0mac == self.h1.intfs[0].MAC() )
        self.assertTrue( h1eth0mac == self.h1.intfs[0].MAC(update=True) )
        self.assertTrue( h1eth0mac == self.h1.intfs[0].mac )
        
    def testIsUpDown( self ):
        self.h1.cmd( 'ip link set', self.h1.intfs[0].name, 'down' )
        result = self.h1.cmd( 'ip link show dev', self.h1.intfs[0].name )
        isup = "UP" in result
        isup2 = self.h1.intfs[0].isUp()
        self.assertEqual( isup, False )
        self.assertEqual( isup2, False )
        
    def testIsUpUp( self ):
        isup2 = self.h1.intfs[0].isUp(setUp=True)
        result = self.h1.cmd( 'ip link show dev', self.h1.intfs[0].name )
        isup = "UP" in result
        self.assertEqual( isup, True )
        self.assertEqual( isup2, True )

    def testRename( self ):
        oldname = self.h1.intfs[0].name
        result = self.h1.cmd( 'ip link show dev', oldname )
        notexist = 'not exist' in result
        self.assertEqual( notexist, False )
        
        newname = 'h1-net0'
        result = self.h1.cmd( 'ip link show dev', newname )
        notexist = 'not exist' in result
        self.assertEqual( notexist, True )
        
        self.h1.intfs[0].rename(newname)
        
        result = self.h1.cmd( 'ip link show dev', oldname )
        notexist = 'not exist' in result
        self.assertEqual( notexist, True )
        
        result = self.h1.cmd( 'ip link show dev', newname )
        notexist = 'not exist' in result
        self.assertEqual( notexist, False )

    def testConfigAndSetParam( self ):
        addr = self.h1.intfs[0].config(ipAddress=['show','dev','h1-eth0',{'options':'-j -p -f inet'}])
        addrInfo = jsonIpAddrToStrAddrInfo(addr['ipAddress'])[0]
        ip = addrInfo['local']
        pref = str(addrInfo['prefixlen'])
        self.assertEqual( ip, self.h1.intfs[0].ip )
        self.assertEqual( pref, self.h1.intfs[0].prefixLen )
        
        self.h1.intfs[0].config(ipAddress=['add','10.0.0.3/8','dev','h1-eth0'])
        addr = self.h1.intfs[0].config(ipAddress=['show','dev','h1-eth0',{'options':'-j -p -f inet'}])
        twoIpInfo = jsonIpAddrToStrAddrInfo(addr['ipAddress'])
        
        self.assertTrue(len(twoIpInfo) == 2)
        
        addrInfo = twoIpInfo[0]
        ip = addrInfo['local']
        pref = str(addrInfo['prefixlen'])
        self.assertEqual( ip, self.h1.intfs[0].ip )
        self.assertEqual( pref, self.h1.intfs[0].prefixLen )
        
        addrInfo2 = twoIpInfo[1]
        ip2 = addrInfo2['local']
        pref2 = str(addrInfo2['prefixlen'])
        self.assertEqual( ip2, '10.0.0.3' )
        self.assertEqual( pref2, '8' )
        
        result = {}
        self.h1.intfs[0].setParam(result, 'ipAddress', **{'delip':['del','10.0.0.3/8','dev','h1-eth0']})
        self.h1.intfs[0].setParam(result, 'ipAddress', **{'showip':['show dev h1-eth0',{'options':'-j -p -f inet'}]})
        oneIpInfo = jsonIpAddrToStrAddrInfo(result['showip'])
        
        self.assertTrue(len(oneIpInfo) == 1)
        
        addrInfo = oneIpInfo[0]
        ip = addrInfo['local']
        pref = str(addrInfo['prefixlen'])
        self.assertEqual( ip, self.h1.intfs[0].ip )
        self.assertEqual( pref, self.h1.intfs[0].prefixLen )
        
        linkInfo = self.h1.intfs[0].config(ipLink=['show dev h1-eth0',{'options':'-j -p -br'}])
        isUp = 'UP' in json.loads(linkInfo['ipLink'])[0]['flags']
        self.assertTrue(isUp)
        
        self.h1.intfs[0].setParam(result, 'ipLink', **{'down':['set','dev','h1-eth0','down']})
        self.h1.intfs[0].setParam(result, 'ipLink', **{'show':['show dev h1-eth0',{'options':'-j -p -br'}]})
        isUp = 'UP' in json.loads(result['show'])[0]['flags']
        self.assertFalse(isUp)
        
        self.h1.cmd('ip link set dev h1-eth0 up')
        
    def tearDown( self ):
        self.net.stop()
   
if __name__ == '__main__':
    unittest.main()        
        









