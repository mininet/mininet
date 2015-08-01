#!/usr/bin/env python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import Link, Intf, TCLink
from mininet.topo import Topo
from mininet.util import dumpNodeConnections
import logging
import os

logging.basicConfig(filename='./fattree.log', level=logging.INFO)
logger = logging.getLogger(__name__)


class Fattree(Topo):
    logger.debug("Class Fattree")
    CoreSwitchList = []
    AggSwitchList = []
    EdgeSwitchList = []
    HostList = []

    def __init__(self, k, density):
        logger.debug("Class Fattree init")
        self.pod = k
        self.iCoreLayerSwitch = (k/2)**2
        self.iAggLayerSwitch = k*k/2
        self.iEdgeLayerSwitch = k*k/2
        self.density = density
        self.iHost = self.iEdgeLayerSwitch * density

        #Init Topo
        Topo.__init__(self)

    def createTopo(self):
        self.createCoreLayerSwitch(self.iCoreLayerSwitch)
        self.createAggLayerSwitch(self.iAggLayerSwitch)
        self.createEdgeLayerSwitch(self.iEdgeLayerSwitch)
        self.createHost(self.iHost)

    """
    Create Switch and Host
    """

    def _addSwitch(self, number, level, switch_list):
        for x in xrange(1, number+1):
            PREFIX = str(level) + "00"
            if x >= int(10):
                PREFIX = str(level) + "0"
            switch_list.append(self.addSwitch('s' + PREFIX + str(x)))

    def createCoreLayerSwitch(self, NUMBER):
        logger.debug("Create Core Layer")
        self._addSwitch(NUMBER, 1, self.CoreSwitchList)

    def createAggLayerSwitch(self, NUMBER):
        logger.debug("Create Agg Layer")
        self._addSwitch(NUMBER, 2, self.AggSwitchList)

    def createEdgeLayerSwitch(self, NUMBER):
        logger.debug("Create Edge Layer")
        self._addSwitch(NUMBER, 3, self.EdgeSwitchList)

    def createHost(self, NUMBER):
        logger.debug("Create Host")
        for x in xrange(1, NUMBER+1):
            PREFIX = "h00"
            if x >= int(10):
                PREFIX = "h0"
            elif x >= int(100):
                PREFIX = "h"
            self.HostList.append(self.addHost(PREFIX + str(x)))

    """
    Add Link
    """
    def createLink(self, bw_c2a=0.2, bw_a2e=0.1, bw_h2a=0.5):
        logger.debug("Add link Core to Agg.")
        end = self.pod/2
        for x in xrange(0, self.iAggLayerSwitch, end):
            for i in xrange(0, end):
                for j in xrange(0, end):
                    self.addLink(
                        self.CoreSwitchList[i*end+j],
                        self.AggSwitchList[x+i],
                        bw=bw_c2a)

        logger.debug("Add link Agg to Edge.")
        for x in xrange(0, self.iAggLayerSwitch, end):
            for i in xrange(0, end):
                for j in xrange(0, end):
                    self.addLink(
                        self.AggSwitchList[x+i], self.EdgeSwitchList[x+j],
                        bw=bw_a2e)

        logger.debug("Add link Edge to Host.")
        for x in xrange(0, self.iEdgeLayerSwitch):
            for i in xrange(0, self.density):
                self.addLink(
                    self.EdgeSwitchList[x],
                    self.HostList[self.density * x + i],
                    bw=bw_h2a)

    def set_ovs_protocol_13(self,):
        self._set_ovs_protocol_13(self.CoreSwitchList)
        self._set_ovs_protocol_13(self.AggSwitchList)
        self._set_ovs_protocol_13(self.EdgeSwitchList)

    def _set_ovs_protocol_13(self, sw_list):
            for sw in sw_list:
                cmd = "sudo ovs-vsctl set bridge %s protocols=OpenFlow13" % sw
                os.system(cmd)


def iperfTest(net, topo):
    logger.debug("Start iperfTEST")
    h1000, h1015, h1016 = net.get(
        topo.HostList[0], topo.HostList[14], topo.HostList[15])

    #iperf Server
    h1000.popen(
        'iperf -s -u -i 1 > iperf_server_differentPod_result', shell=True)

    #iperf Server
    h1015.popen(
        'iperf -s -u -i 1 > iperf_server_samePod_result', shell=True)

    #iperf Client
    h1016.cmdPrint('iperf -c ' + h1000.IP() + ' -u -t 10 -i 1 -b 100m')
    h1016.cmdPrint('iperf -c ' + h1015.IP() + ' -u -t 10 -i 1 -b 100m')


def pingTest(net):
    logger.debug("Start Test all network")
    net.pingAll()


def createTopo():
    logging.debug("LV1 Create Fattree")
    topo = Fattree(8, 4)
    topo.createTopo()
    topo.createLink(bw_c2a=0.2, bw_a2e=0.1, bw_h2a=0.05)

    logging.debug("LV1 Start Mininet")
    CONTROLLER_IP = "127.0.0.1"
    CONTROLLER_PORT = 6633
    net = Mininet(topo=topo, link=TCLink, controller=None, autoSetMacs=True,
                  autoStaticArp=True)
    net.addController(
        'controller', controller=RemoteController,
        ip=CONTROLLER_IP, port=CONTROLLER_PORT)
    net.start()

    '''
        Set OVS's protocol as OF13
    '''
    topo.set_ovs_protocol_13()

    logger.debug("LV1 dumpNode")

    #dumpNodeConnections(net.hosts)
    #pingTest(net)
    #iperfTest(net, topo)

    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    if os.getuid() != 0:
        logger.debug("You are NOT root")
    elif os.getuid() == 0:
        createTopo()
