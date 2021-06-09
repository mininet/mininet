#!/usr/bin/env python3
import os
from mininet.link import Link
from mininet.log import warn, info
from mininet.node import Node, Host, OVSKernelSwitch


class HostConnectedNode(Node):
    """
    Implements a Host node witch creates and connects Host Only Interface
    to previously created Host Only Network.
    The Host Only Network works in 66.0.0.0/24 address space.
    The Root interface h0-eth0 has by default 66.0.0.1 IP
    (though it we can access the Host Only Network)
    On each created Node by default is opened a SSH server.
    """
    hostONet = {
        "ssh_cmd": "/usr/sbin/sshd -D -o UseDNS=no -u0",
        "ssh_pid": [],
        "nextNodeID": 2,
        "hostNum": 0
    }
    hostSwitch: OVSKernelSwitch = None

    def __init__(self, *args, **kwargs):
        super(HostConnectedNode, self).__init__(*args, **kwargs)
        self.hostOnlyLink: Link = None
        HostConnectedNode.checkHostOnlySetup()
        self.setupHostOnlyIntf()
        self.startHostOnlySSH()

    def setupHostOnlyIntf(self):
        # Connect to Host Only Net
        self.hostOnlyLink = Link(node1=self, intfName1=f'{self.name}-local0',
                                 node2=self.hostSwitch, intfName2=None)

        HostConnectedNode.hostSwitch.attach(self.hostOnlyLink.intf2)
        self.setHostOnlyIP()
        HostConnectedNode.hostONet['hostNum'] += 1

    def getHostOnlyIntf(self):
        return self.hostOnlyLink.intf1

    def setHostOnlyIP(self):
        self.setIP(self.getNextHostOnlyIP(), intf=self.getHostOnlyIntf())
        HostConnectedNode.hostONet['nextNodeID'] += 1

    def getNextHostOnlyIP(self):
        return '66.0.0.%d/24' % (int(self.name[-1]) + 1)

    def startHostOnlySSH(self):
        # SSH start
        if self.getHostOnlyIntf() is None:
            warn(f"Warning: No Host Only Interface! Can not start SSH for {self.name}\n")
        self.cmd(HostConnectedNode.hostONet['ssh_cmd'] + f' -o ListenAddress={self.IP(self.getHostOnlyIntf())} &')
        info(f"\n*** Start SSH server on {self.name} via {self.IP(self.getHostOnlyIntf())} with PID={self.lastPid}\n")
        HostConnectedNode.hostONet['ssh_pid'].append(self.lastPid)

    def defaultIntf(self):
        """Return interface for lowest port except of Host Only Interface"""
        ports = set(self.intfs.keys())
        if not ports:
            warn('*** defaultIntf: warning:', self.name, 'has no interfaces\n')
            return None

        min_port = min(ports)
        if self.intfs[min_port].name.endswith('-local0'):
            ports.remove(min_port)
        if ports:
            return self.intfs[min(ports)]
        else:
            warn('*** defaultIntf: warning:', self.name, 'has no interfaces\n')
            return None

    def terminate(self):
        self.cmd('ip link del ' + self.hostOnlyLink.intf1.name)
        self.cmd('ip link del ' + self.hostOnlyLink.intf2.name)
        del self.hostOnlyLink
        HostConnectedNode.hostONet['hostNum'] -= 1
        if HostConnectedNode.hostONet['hostNum'] == 0:
            for ssh in self.hostONet['ssh_pid']:
                os.system(f"kill {ssh} 2> /dev/null")
            HostConnectedNode.hostONet['ssh_pid'].clear()
            for i_name in HostConnectedNode.hostSwitch.intfNames():
                if i_name != "lo":
                    os.system(f'ip l del {i_name} 2> /dev/null')
            os.system(f'ovs-vsctl del-br {HostConnectedNode.hostSwitch.name} 2> /dev/null')
            HostConnectedNode.hostSwitch = None
            HostConnectedNode.hostONet['nextNodeID'] = 2
            info("*** Stop Host Only Network !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
        super(HostConnectedNode, self).terminate()

    @classmethod
    def checkHostOnlySetup(cls):
        if cls.hostSwitch is None:
            info("*** Start Host Only Network !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            cls.hostSwitch = OVSKernelSwitch('s0', inNamespace=False, failMode="standalone")

            root_node = Host('h0', inNamespace=False)
            intf = Link(root_node, cls.hostSwitch).intf1
            root_node.setIP('66.0.0.1/24', intf=intf)

            cls.hostSwitch.start([])


hosts = {"deb_host": HostConnectedNode}
