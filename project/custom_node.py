#!/usr/bin/env python3
from mininet.link import Link
from mininet.log import warn, info
from mininet.node import Node, Host, OVSKernelSwitch


# from mininet.log import debug
from mininet.nodelib import LinuxBridge
from mininet.util import waitListening

ssh_path = "/usr/sbin/sshd"
ssh_cmd = ssh_path + " -D -o UseDNS=no -u0"


class HostConnectedNode(Node):
    s0: OVSKernelSwitch = None
    hostOnlyNetNextNode: int = 0
    hostNum = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Connect to Host Only Net
        intf_lo, intf_s0 = (lambda x: (x.intf1, x.intf2))(
            Link(node1=self, intfName1='local0',
                 node2=HostConnectedNode.s0, intfName2=None)
        )
        HostConnectedNode.s0.attach(intf_s0)
        self.setIP('66.0.0.%d/24' % (int(self.name[-1]) + 1), intf=intf_lo)

        HostConnectedNode.hostOnlyNetNextNode += 1
        HostConnectedNode.hostNum += 1

        # SSH start
        self.cmd(ssh_cmd + f' -o ListenAddress={self.IP(intf_lo)} &')
        info(f"\n*** Start SSH server on {self.name} via {self.IP(intf_lo)}\n")


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
    #         self.cmd('kill %' + ssh_path)

    @classmethod
    def setup(cls):
        HostConnectedNode.s0 = OVSKernelSwitch('s0', inNamespace=False, failMode="standalone")

        root_node = Host('h0', inNamespace=False)
        intf = Link(root_node, HostConnectedNode.s0).intf1
        root_node.setIP('66.0.0.1/24', intf=intf)
        cls.hostOnlyNetNextNode += 1

        cls.s0.start([])


hosts = {"deb_host": HostConnectedNode}
