#!/usr/bin/python

"""
    This script builds a network using mininet for using with
a remote controller like POX.

    The script receives from command line two arguments. The number
of Switches and the number of Hosts per Switch. Then, it will build
the network topology based on this arguments.

    First of all, it build a topology and add the Switches to the network.
After that, add the same number of Hosts for each Switch added. Lastly
it make links between each switch.

@author: Gustavo Pantuza
@since: 18.07.2013

"""

from optparse import OptionParser

from mininet.topo import LinearTopo
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.node import RemoteController

def main():
    # Defines the log level
    setLogLevel('info')

    # parses command line arguments
    parser = OptionParser()
    parser.add_option('-H', dest='hosts', default=5,
                      help='Number of hosts per switch')
    parser.add_option('-S', dest='switches', default=2,
                      help='Number of switches')
    (options, args) = parser.parse_args()

    # Build network topology (see mininet/topo.py)
    topo = LinearTopo(int(options.switches), int(options.hosts))

    # Creates the Network using a remote controller
    net = Mininet(topo,
                  controller=lambda a: RemoteController(a, ip='127.0.0.1'))

    # Starts the network
    net.start()
    # Run the mininet client
    CLI(net)
    # Stop the network
    net.stop()

if __name__ == "__main__":
    main()
