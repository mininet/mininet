# -*- coding: utf-8 -*-

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

from os import environ
from sys import argv
from sys import exit
from getopt import getopt
from getopt import GetoptError

from mininet.topo import Topo
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.node import RemoteController


class MyTopo(Topo):
    """ Topology Class Used in all classes to add network components """
    def __init__(self, **opts):
        super(MyTopo, self).__init__(**opts)


class Switches():
    """ Class to control switches addition """

    def __init__(self, num, topo):

        for i in xrange(num):
            topo.addSwitch('s%s' % str(i))


class Hosts():
    """ Class to control host addition """

    def __init__(self):
        self._seq = 0

    def add(self, num, switch, topo):
        """ Adds hosts and its links """

        for i in xrange(num):
            host = topo.addHost("h%s" % str(self._seq))
            topo.addLink(host, switch)
            self._seq += 1


class Links():
    """ Create links between two switches """

    def __init__(self, topo, switch0, switch1):

        topo.addLink(switch0, switch1)


class ArgParser(object):
    """ Command line arguments parser class """

    # possible command line options
    OPTS = "s:h:"

    def __init__(self, argv):
        """ Tries to get options from command line """

        try:
            self.opts, self.args = getopt(argv, ArgParser.OPTS, ["help"])
        except GetoptError:
            self.usage()

        self.switches = 2  # default value for the number of switches
        self.hosts = 5  # default value for the number of hosts
        self.parse()

    def parse(self):
        """ Parses the arguments and set values to the script execution """

        for opt, args in self.opts:

            if opt == "--help":
                self.usage()
            elif opt == "-s":
                self.switches = int(args)
            elif opt == "-h":
                self.hosts = int(args)

    def usage(self):
        """ Prints how to usage the program """

        print "python dinamicnet.py -s <Number-of-Switches>" \
              " -h <hosts-per-switch>"
        exit()


if __name__ == "__main__":

    # Defines the log level
    setLogLevel('info')

    # parses command line arguments
    parser = ArgParser(argv[1:])

    # Build network topology
    topo = MyTopo()

    # Adds Switches to network
    Switches(parser.switches, topo)

    # Adds Hosts to network
    hosts = Hosts()
    for i, switch in enumerate(topo.switches()):
        hosts.add(parser.hosts, switch, topo)

        try:  # Add links between switches
            Links(topo, switch, topo.switches()[i + 1])
        except IndexError:
            break

    # Creates the Network using a remote controller
    net = Mininet(topo,
                  controller=lambda a: RemoteController(a, ip='127.0.0.1'))

    # Starts the network
    net.start()
    # Run the mininet client
    CLI(net)
    # Stop the network
    net.stop()
