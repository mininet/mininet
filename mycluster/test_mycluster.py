import unittest
import random
import time
from mininet.log import info
from mininet.net import Mininet
from mycluster import MyCLusterTopo
from mininet.node import RemoteController


class TestMyCluster(unittest.TestCase):
    REM_CONT_IP = '10.0.2.9'
    REM_CONT_PORT = 6653

    NODE_NAMES = ['ln5', 'ln6', 'sn7', 'ln15', 'ln16', 'sn17']

    def start_network(self):

        net = Mininet(topo=MyCLusterTopo(), build=False)

        info('** Adding controller IP={}, PORT={} **'.format(self.REM_CONT_IP, self.REM_CONT_PORT))
        c0 = net.addController(name='c0',
                               controller=RemoteController,
                               ip=self.REM_CONT_IP,
                               port=self.REM_CONT_PORT)

        c0.start()
        net.build()
        net.start()
        info('** Network started **')
        return net

    @staticmethod
    def stop_network(net):
        if net is not None:
            info()
            net.stop()
            info('** Network stopped **')

    def del_random_node_network(self, net):
        rand_node = random.choice(self.NODE_NAMES)
        if net is not None:
            rn = net.getNodeByName(rand_node)
            rn.stop()
            info('** Stopped node {} **'.format(rand_node))
            return rand_node
        else:
            print('No Network is running.')

    def test_ping_all(self):
        net = self.start_network()
        time.sleep(5)
        ping_result = net.pingAll()
        # For first time something could be dropped
        if ping_result != 0.0:
            ping_result = net.pingAll()
        self.stop_network(net)
        assert ping_result == 0.0, 'Should have 0.0% packets dropped.'

    def test_ping_all_after_random_shutdown(self):
        net = self.start_network()
        time.sleep(5)
        rn_name = self.del_random_node_network(net)
        time.sleep(5)
        ping_result = net.pingAll()
        if ping_result != 0.0:
            ping_result = net.pingAll()
        self.stop_network(net)
        assert ping_result == 0.0, 'Should have 0.0% packets dropped.\nStopped node: {}'\
            .format(rn_name)


if __name__ == "__main__":
    unittest.main()
