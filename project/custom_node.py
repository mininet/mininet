#!/usr/bin/env python3
from mininet.link import Intf, Link
from mininet.log import warn
from mininet.net import Mininet
from mininet.node import Node, UserSwitch, Host, Switch, OVSSwitch, Controller
from mininet.cli import CLI


# from mininet.log import debug
from mininet.nodelib import LinuxBridge


class HostConnectedNode(Node):
    s0: OVSSwitch = None
    c0: Controller = None
    hostOnlyNetNextNode: int = 0
    hostNum = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        intf = Link(node1=HostConnectedNode.s0, intfName1=None,
                    node2=self, intfName2='local0').intf2
        self.setIP('66.0.0.%d/24' % (int(self.name[-1]) + 1), intf=intf)

        HostConnectedNode.hostOnlyNetNextNode += 1
        HostConnectedNode.hostNum += 1

    def defaultIntf(self):
        "Return interface for lowest port"
        ports = set(self.intfs.keys())
        # info(f"[Node={self.name}] Default Intf\n\tports={ports}\n\tInterfaces={self.intfs}\n\n")
        if not ports:
            warn('*** defaultIntf: warning:', self.name, 'has no interfaces\n')
            return None

        # TODO: consider if the min port is always 'local0'?
        min_port = min(ports)
        if self.intfs[min_port].name == 'local0':
            ports.remove(min_port)
        if ports:
            return self.intfs[min(ports)]
        else:
            warn('*** defaultIntf: warning:', self.name, 'has no interfaces\n')
            return None

    # TODO: delete Links after exit
    # def __del__(self):
    #     HostConnectedNode.hostNum -= 1
    #     if HostConnectedNode.hostNum == 0:
    #         HostConnectedNode.s0.stop()
    #         HostConnectedNode.c0.stop()

    @classmethod
    def setup(cls):
        HostConnectedNode.s0 = OVSSwitch('s0', inNamespace=False, listenPort=6666)
        HostConnectedNode.c0 = Controller('l-c0', inNamespace=False, port=6666)

        root_node = Host('h0', inNamespace=False)
        intf = Link(root_node, HostConnectedNode.s0).intf1
        root_node.setIP('66.0.0.1/24', intf=intf)
        cls.hostOnlyNetNextNode += 1

        cls.c0.start()
        cls.s0.start([cls.c0])
        # cls.s0.start([])


hosts = {"deb_host": HostConnectedNode}
