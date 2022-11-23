Mininet Examples
========================================================

These examples are intended to help you get started using
Mininet's Python API.

========================================================

#### baresshd.py:

This example uses Mininet's medium-level API to create an sshd
process running in a namespace. Doesn't use OpenFlow.

#### bind.py:

This example shows how you can create private directories for each
node in a Mininet topology.

#### cluster.py:

This example contains all of the code for experimental cluster
edition. Remote classes and MininetCluster can be imported from
here to create a topology with nodes on remote machines.

#### clusterSanity.py:

This example runs cluster edition locally as a sanity check to test
basic functionality.

#### clustercli.py:

This example contains a CLI for experimental cluster edition.

#### clusterdemo.py:

This example is a basic demo of cluster edition on 3 servers with
a tree topology of depth 3 and fanout 3.

#### consoles.py:

This example creates a grid of console windows, one for each node,
and allows interaction with and monitoring of each console, including
graphical monitoring.

#### controllers.py:

This example creates a network with multiple controllers, by
using a custom `Switch()` subclass.

#### controllers2.py:

This example creates a network with multiple controllers by
creating an empty network, adding nodes to it, and manually
starting the switches.

#### controlnet.py:

This examples shows how you can model the control network as well
as the data network, by actually creating two Mininet objects.

#### cpu.py:

This example tests iperf bandwidth for varying CPU limits.

#### emptynet.py:

This example demonstrates creating an empty network (i.e. with no
topology object) and adding nodes to it.

#### hwintf.py:

This example shows how to add an interface (for example a real
hardware interface) to a network after the network is created.

#### intfoptions.py:

This example reconfigures a TCIntf during runtime with different
traffic control commands to test bandwidth, loss, and delay.

#### limit.py:

This example shows how to use link and CPU limits.

#### linearbandwidth.py:

This example shows how to create a custom topology programatically
by subclassing Topo, and how to run a series of tests on it.

#### linuxrouter.py:

This example shows how to create and configure a router in Mininet
that uses Linux IP forwarding.

#### miniedit.py:

This example demonstrates creating a network via a graphical editor.

#### mobility.py:

This example demonstrates detaching an interface from one switch and
attaching it another as a basic way to move a host around a network.

#### multiLink.py:

This example demonstrates the creation of multiple links between
nodes using a custom Topology class.

#### multiping.py:

This example demonstrates one method for
monitoring output from multiple hosts, using `node.monitor()`.

#### multipoll.py:

This example demonstrates monitoring output files from multiple hosts.

#### multitest.py:

This example creates a network and runs multiple tests on it.

#### nat.py:

This example shows how to connect a Mininet network to the Internet
using NAT. It also answers the eternal question "why can't I ping
`google.com`?"

#### natnet.py:

This example demonstrates how to create a network using a NAT node
to connect hosts to the internet.

#### numberedports.py:

This example verifies the mininet ofport numbers match up to the ovs port numbers.
It also verifies that the port numbers match up to the interface numbers

#### popen.py:

This example monitors a number of hosts using `host.popen()` and
`pmonitor()`.

#### popenpoll.py:

This example demonstrates monitoring output from multiple hosts using
the `node.popen()` interface (which returns `Popen` objects) and `pmonitor()`.

#### scratchnet.py, scratchnetuser.py:

These two examples demonstrate how to create a network by using the lowest-
level Mininet functions. Generally the higher-level API is easier to use,
but scratchnet shows what is going on behind the scenes.

#### simpleperf.py:

A simple example of configuring network and CPU bandwidth limits.

#### sshd.py:

This example shows how to run an `sshd` process in each host, allowing
you to log in via `ssh`. This requires connecting the Mininet data network
to an interface in the root namespace (generally the control network
already lives in the root namespace, so it does not need to be explicitly
connected.)

#### tree1024.py:

This example attempts to create a 1024-host network, and then runs the
CLI on it. It may run into scalability limits, depending on available
memory and `sysctl` configuration (see `INSTALL`.)

#### treeping64.py:

This example creates a 64-host tree network, and attempts to check full
connectivity using `ping`, for different switch/datapath types.

#### vlanhost.py:

An example of how to subclass Host to use a VLAN on its primary interface.

