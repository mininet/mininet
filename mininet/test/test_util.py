#!/usr/bin/env python

"""Package: mininet
   Test functions defined in mininet.util."""

import unittest

from mininet.util import quietRun

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


if __name__ == "__main__":
    unittest.main()
