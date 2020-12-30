#!/usr/bin/env python

"""Package: mininet
   Test functions defined in mininet.util."""

import os
import socket
import tempfile
import unittest

from mininet.util import quietRun, ipStr, ipNum, ipAdd, updateHostsFile

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
        "Test integer to string conversion of IP addresses"

        self.assertEqual( ipStr( 0xc0000201, socket.AF_INET ), "192.0.2.1" )

        self.assertEqual( ipStr( 0x7f000001, socket.AF_INET ), "127.0.0.1" )

        self.assertEqual( ipStr( 0x01, socket.AF_INET ), "0.0.0.1")

        ip1 = ipStr( 0x20010db8000000000000000000000001, socket.AF_INET6 )
        ip2 = "2001:db8::1"
        self.assertEqual( ip1, ip2 )

        self.assertEqual( ipStr( 0x01, socket.AF_INET6 ), "::1")

    def testIpNum( self ):
        "Test string to integer conversion of IP addresses"

        self.assertEqual( ipNum("192.0.2.1"), 0xc0000201 )

        self.assertEqual( ipNum("127.0.0.1"), 0x7f000001 )

        self.assertEqual( ipNum("0.0.0.1"), 0x00000001 )

        ip1 = ipNum("2001:db8::1")
        ip2 = 0x20010db8000000000000000000000001
        self.assertEqual( ip1, ip2 )

        self.assertEqual( ipNum("::1"), 0x01 )

    def testIpAdd( self ):
        "Test addition of integer to integer IP address"

        ip1 = ipAdd( 1, 24, 0xc0000200, socket.AF_INET )
        ip2 = "192.0.2.1"
        self.assertEqual( ip1, ip2 )

        ip1 = ipAdd( 2**8 - 1, 24, 0xc0000200, socket.AF_INET )
        ip2 = "192.0.2.255"
        self.assertEqual( ip1, ip2 )

        with self.assertRaises(AssertionError):
            ipAdd( 256, 24, 0xc0000200, socket.AF_INET )

        ip1 = ipAdd( 1, 64, 0x20010db8000000000000000000000000,
                        socket.AF_INET6 )
        ip2 = "2001:db8::1"
        self.assertEqual( ip1, ip2 )

        ip1 = ipAdd( 2**64 - 1, 64, 0x20010db8000000000000000000000000,
                        socket.AF_INET6 )
        ip2 = "2001:db8::ffff:ffff:ffff:ffff"
        self.assertEqual( ip1, ip2 )

        with self.assertRaises(AssertionError):
            ipAdd( 2**64, 64, 0x20010db8000000000000000000000000,
                    socket.AF_INET6 )

class testHostsFile( unittest.TestCase ):
    "Test building and updating of hosts file"

    def testBuildHostsFile( self ):
        "Test building and updating of hosts file"

        output1 = '192.0.2.1 h1\n2001:db8::1 h1\n' + \
                '192.0.2.2 h2\n2001:db8::2 h2\n'
        output2 = '2001:db8::1 h1\n192.0.2.2 h2\n' + \
                '2001:db8::22 h2\n2001:db8::1 h4\n'

        tmp = tempfile.NamedTemporaryFile()
        fileName = tmp.name
        tmp.close()

        try:
            updateHostsFile( fileName, None, '192.0.2.1', 'h1' )
            updateHostsFile( fileName, None, '2001:db8::1', 'h1' )
            updateHostsFile( fileName, None, '192.0.2.2', 'h2' )
            updateHostsFile( fileName, None, '2001:db8::2', 'h2' )

            with open( fileName, 'r' ) as fh:
                self.assertEqual( fh.read(), output1 )

            updateHostsFile( fileName, '192.0.2.1', None, None )
            updateHostsFile( fileName, '2001:db8::2', '2001:db8::22', 'h2' )
            updateHostsFile( fileName, None, '2001:db8::1', 'h4' )

            with open( fileName, 'r' ) as fh:
                self.assertEqual( fh.read(), output2 )

        finally:
            os.unlink( tmp.name )


if __name__ == "__main__":
    unittest.main()
