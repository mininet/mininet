SDN firewall
============
(Firewall application implemented in a software defined network, using mininet and python)

A small network is set up on the virtual machine, with mininet installed. This network contains 6 switches, each with a host, using topology.py.This is a python code that instantiates a virtual network(mininet) independenly on any system and in no time. Mininet is a network emulator that creates a realistic virtual network, running real kernel, switch and application code, on a single machine. sudo mn is the command that brings up the switches, the hosts and the controller. The code topology.py sets up the six switches with a host connected to each. Although, a mininet can itself create a controller to control the switches in its network, yet I have made use of a remote controller (POX) at the tcp port 6633 on the loopback ip address, so as to have some additional functionalities of a learning switch and a firewall.

The POX controller is started on a separate SSH connection along with the learning algorithm, the spanning tree and the discovery modules of the openflow and my personalised firewall module, using the following commands

    cd /pox
    ./pox.py forwarding.l2_learning openflow.discovery openflow.spanning_tree --no-flood --hold-down pox.misc.firewall

With the POX contoller running up, the mininet network is executed on the first window, using the following code:

    cd /home/mininet/mininet/custom working directory
    mn --custom topology.py --topo mytopo --mac --controller=remote,ip=127.0.0.1,port=6633
    
The above command brings up all the six switches with their hosts and a remote controller. Now, when the connectivity is checked among all hosts, using the command pingall, the host having ip_0 will not be able to reach host with ip_1 and vice versa. This is in accordance with the firewallpolicies.csv. Hence, the firewall module is working appropriately on the controller.

The firewallpolicies.csv specifies which ip addresses have to be blocked. This file is being called and used by firewall.py code, which is another python code that recognises the ip addresses to be blocked from certain other ip addresses and also directs the controller to add specific flow-entries in the flow tables of the switches, so that packets from these blocked ip addresses are independently handled by the switches in future. 

The learning algorithm runs along with the POX controller that forces the switches to behave as normal switches that have learning capabilities. When a new packet reaches a switch, the switch acts according to the openflow protocol, in which it sends the packet to the controller, as the switch is unaware of the action, it needs to perform. The controller informs the switch the required action and hence the switch 'learns' the source address and its corresponding action. The specific flow entries are added in the flow tables of the switches. 

Spanning_tree module of the openflow protocol is also required to run on the POX controller, especially in this network, so that the huge number of switches are able to manage the packet flows efficiently without any loops and errors.If we are not using spanning tree algorithm along with the discovery and the spanning tree modules of openflow, the POX controller goes unmanaged and starts throwing errors like:

WARNING:openflow.of_01:<class 'pox.openflow.PacketIn'> raised on dummy OpenFlow nexus.

This issue doesn’t arise in a network of 2 or 3 switches(connected linearly). But this network is more like a mesh network where most of the hosts have direct and multiple indirect connections to other hosts. The spanning_tree component of openflow uses the discovery component of openflow to build a view of the network topology, constructs a spanning tree and then disables flooding on switch ports that aren't on the tree. Spanning_tree component uses the following options to modify the behavior of the switches:
--no-flood option disables flooding on all ports as soon as a switch connects.
--hold-down option prevents altering of flood control until a complete discovery cycle has completed and thus, all links have had an opportunity to be discovered.
The openflow.discovery component sends LLDP messages out of openflow switches so that it can discover the network topology. 

As the primary functionality of this project is to add a firewall on the POX controller, the firewall.py algorithm is started along with the POX controller, which works in accordance with the firewallpolicies.csv table.So when a packet is received by the switch from ip_0 address, it is sent to the POX, which will comply with the firewall module and push down a 'drop' flow entry to the switch for the packets to be blocked. Hence the switch will block any further packets from that source. The rest of the packets are simply forwarded and corresponding flow-entries are added by the POX controller in the flow-tables of the switches, so that any further packet is managed solely by the switches, without the need to send the packets to the controllers, thus complying with the principles of software defined network.
