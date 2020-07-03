#!/usr/bin/env python

"""Package: mininet
   Test functions defined in mininet.util."""

import socket
import unittest

from mininet.util import quietRun, ipStr, ipNum, ipAdd

class testQuietRun( unittest.TestCase ):
    """Test quietRun that runs a command and returns its merged output from
    STDOUT and STDIN"""

    @staticmethod
    def getEchoCmd( n ):
        "Return a command that will print n characters"
        return "echo -n " + "x" * n

    def testEmpty( self ):
        "Run a command that prints nothing"
        output = quietRun(testQuietRun.getEchoCmd( 0 ) )
        self.assertEqual( 0, len( output ) )

    def testOneRead( self ):
        """Run a command whose output is entirely read on the first call if
        each call reads at most 1024 characters
        """
        for n in [ 42, 1024 ]:
            output = quietRun( testQuietRun.getEchoCmd( n ) )
            self.assertEqual( n, len( output ) )

    def testMultipleReads( self ):
        "Run a command whose output is not entirely read on the first read"
        for n in [ 1025, 4242 ]:
            output = quietRun(testQuietRun.getEchoCmd( n ) )
            self.assertEqual( n, len( output ) )

class testIPFuncs( unittest.TestCase ):
    """Test IP manipulation"""

    def testIpStr( self ):
        self.assertEqual( ipStr( 0xc0000201, socket.AF_INET ), "192.0.2.1" )
        self.assertEqual( ipStr( 0x7f000001, socket.AF_INET ), "127.0.0.1" )
        self.assertEqual( ipStr( 0x01, socket.AF_INET ), "0.0.0.1")
        self.assertEqual( ipStr( 0x20010db8000000000000000000000001, socket.AF_INET6 ), "2001:db8::1" )
        self.assertEqual( ipStr( 0x01, socket.AF_INET6 ), "::1")

    def testIpNum( self ):
        self.assertEqual( ipNum("192.0.2.1"), 0xc0000201 )
        self.assertEqual( ipNum("127.0.0.1"), 0x7f000001 )
        self.assertEqual( ipNum("0.0.0.1"), 0x00000001 )
        self.assertEqual( ipNum("2001:db8::1"), 0x20010db8000000000000000000000001 )
        self.assertEqual( ipNum("::1"), 0x01 )

    def testIpAdd( self ):
        self.assertEqual( ipAdd( 1, 24, 0xc0000200, socket.AF_INET ), "192.0.2.1" )
        self.assertEqual( ipAdd( 2**8 - 1, 24, 0xc0000200, socket.AF_INET ), "192.0.2.255" )
        with self.assertRaises(AssertionError):
            ipAdd( 256, 24, 0xc0000200, socket.AF_INET )

        self.assertEqual( ipAdd( 1, 64, 0x20010db8000000000000000000000000, socket.AF_INET6 ), "2001:db8::1" )
        self.assertEqual( ipAdd( 2**64 - 1, 64, 0x20010db8000000000000000000000000, socket.AF_INET6 ), "2001:db8::ffff:ffff:ffff:ffff" )
        with self.assertRaises(AssertionError):
            ipAdd( 2**64, 64, 0x20010db8000000000000000000000000, socket.AF_INET6 )

if __name__ == "__main__":
    unittest.main()
