#!/usr/bin/env python3
from mininet.link import Link
from mininet.log import warn
from mininet.node import Node, Host, OVSKernelSwitch


# from mininet.log import debug
from mininet.nodelib import LinuxBridge


class HostConnectedNode(Node):
    s0: OVSKernelSwitch = None
    hostOnlyNetNextNode: int = 0
    hostNum = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        intf = Link(node1=self, intfName1='local0',
                    node2=HostConnectedNode.s0, intfName2=None).intf1
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
        HostConnectedNode.s0 = LinuxBridge('s0', inNamespace=False, failMode="standalone")

        root_node = Host('h0', inNamespace=False)
        intf = Link(root_node, HostConnectedNode.s0).intf1
        root_node.setIP('66.0.0.1/24', intf=intf)
        cls.hostOnlyNetNextNode += 1

        cls.s0.start([])


hosts = {"deb_host": HostConnectedNode}
