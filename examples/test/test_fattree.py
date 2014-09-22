#!/usr/bin/env python

"""
Test for fattree.py
"""

import unittest
import pexpect
import sys
from mininet.topolib import FatTreeTopo1

class testFatTree( unittest.TestCase ):

    prompt = 'mininet>'

    @unittest.skipIf( '-quick' in sys.argv, 'long test' )
    def testFatTreePing( self ):
        "Run the example and run pingall"
        p = pexpect.spawn( 'python -m mininet.examples.fattree' )
        p.expect( self.prompt, timeout=6000 ) 
        p.sendline( 'pingall' )
        p.expect ( '(\d+)% dropped', timeout=6000 )
        percent = int( p.match.group( 1 ) ) if p.match else -1
        p.expect( self.prompt )
        p.sendline( 'exit' )
        p.wait()
        self.assertEqual( percent, 0 )

    def testFatTreeTopo( self ):
        k = 4
        fanout = 2
        ft = FatTreeTopo1( k=k, fanout=fanout )
        
        
        hosts = fanout*(k ** 2) / 2
        self.assertEqual(len(ft.hosts()), hosts)
        switches = 5 * (k ** 2) / 4
        self.assertEqual(len(ft.switches()), switches)
        nodes = hosts + switches
        self.assertEqual(len(ft.nodes()), nodes)

        self.assertEqual(len(ft.layer_nodes(0)), (k ** 2) / 4)
        self.assertEqual(len(ft.layer_nodes(1)), (k ** 2) / 2)
        self.assertEqual(len(ft.layer_nodes(2)), (k ** 2) / 2)
        self.assertEqual(len(ft.layer_nodes(3)), (k ** 3) / 4)

        self.assertEqual(len(ft.links()), 3 * hosts)

    def testfatTreePorts( self ):
        k = 4
        fanout = 2
        ft = FatTreeTopo1( k=k, fanout=fanout )

        tuples  = [('s1', 's5', 1, 1),
                   ('s2','s5', 1, 3),
                   ('s3', 's11', 2, 1),
                   ('s4', 's19', 4, 3),
                   ('s5', 's6', 2, 1),
                   ('s5', 's8', 4, 1),
                   ('s6', 's7', 3, 2),
                   ('s7', 's8', 4, 3),
                   ('s6', 'h1', 2, 0),
                   ('s6', 'h2', 4, 0)
                  ]

        for tuple_ in tuples:
            src, dst, srcp_exp, dstp_exp = tuple_
            (srcp, dstp) = ft.port(src, dst)
            self.assertEqual(srcp, srcp_exp)
            self.assertEqual(dstp, dstp_exp)
            # flip order and ensure same result
            (dstp, srcp) = ft.port(dst, src)
            self.assertEqual(srcp, srcp_exp)
            self.assertEqual(dstp, dstp_exp)


if __name__ == '__main__':
    unittest.main()
