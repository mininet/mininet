#!/usr/bin/env python3
import os
import signal

from mininet.link import Link
from mininet.log import warn, info
from mininet.node import Node, Host, OVSKernelSwitch


class HostConnectedNode(Node):
    hostONet = {
        "ssh_cmd": "/usr/sbin/sshd -D -o UseDNS=no -u0",
        "ssh_pid": [],
        "nextNodeID": 2,
        "hostNum": 0
    }
    hostSwitch: OVSKernelSwitch = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Connect to Host Only Net
        intf_lo, intf_s0 = (lambda x: (x.intf1, x.intf2))(
            Link(node1=self, intfName1='local0',
                 node2=self.hostSwitch, intfName2=None)
        )
        self.hostSwitch.attach(intf_s0)
        self.setIP('66.0.0.%d/24' % (int(self.name[-1]) + 1), intf=intf_lo)

        self.hostONet['nextNodeID'] += 1
        self.hostONet['hostNum'] += 1

        # SSH start
        self.cmd(self.hostONet['ssh_cmd'] + f' -o ListenAddress={self.IP(intf_lo)} &')
        info(f"\n*** Start SSH server on {self.name} via {self.IP(intf_lo)} with PID={self.lastPid}\n")
        self.hostONet['ssh_pid'].append(self.lastPid)

    def defaultIntf(self):
        "Return interface for lowest port"
        ports = set(self.intfs.keys())
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

    def __del__(self):
        self.hostONet['hostNum'] -= 1
        if self.hostONet['hostNum'] == 0:
            for ssh in self.hostONet['ssh_pid']:
                os.system(f"kill {ssh}")
            for i_name in self.hostSwitch.intfNames():
                if i_name != "lo":
                    os.system('ip l del ' + i_name + ' 2> /dev/null')
            os.system('ovs-vsctl del-br ' + self.hostSwitch.name)

    @classmethod
    def setup(cls):
        cls.hostSwitch = OVSKernelSwitch('s0', inNamespace=False, failMode="standalone")

        root_node = Host('h0', inNamespace=False)
        intf = Link(root_node, cls.hostSwitch).intf1
        root_node.setIP('66.0.0.1/24', intf=intf)

        cls.hostSwitch.start([])


hosts = {"deb_host": HostConnectedNode}
