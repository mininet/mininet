Mininet: Rapid Prototyping for Software Defined Networks
========================================================
*The best way to emulate almost any network on your laptop!*

Mininet 2.3.0d6

[![Build Status][1]](https://travis-ci.org/mininet/mininet)

### What is Mininet?

Mininet emulates a complete network of hosts, links, and switches
on a single machine.  To create a sample two-host, one-switch network,
just run:

  `sudo mn`

Mininet is useful for interactive development, testing, and demos,
especially those using OpenFlow and SDN.  OpenFlow-based network
controllers prototyped in Mininet can usually be transferred to
hardware with minimal changes for full line-rate execution.

### How does it work?

Mininet creates virtual networks using process-based virtualization
and network namespaces - features that are available in recent Linux
kernels.  In Mininet, hosts are emulated as `bash` processes running in
a network namespace, so any code that would normally run on a Linux
server (like a web server or client program) should run just fine
within a Mininet "Host".  The Mininet "Host" will have its own private
network interface and can only see its own processes.  Switches in
Mininet are software-based switches like Open vSwitch or the OpenFlow
reference switch.  Links are virtual ethernet pairs, which live in the
Linux kernel and connect our emulated switches to emulated hosts
(processes).

### Features

Mininet includes:

* A command-line launcher (`mn`) to instantiate networks.

* A handy Python API for creating networks of varying sizes and
  topologies.

* Examples (in the `examples/` directory) to help you get started.

* Full API documentation via Python `help()` docstrings, as well as
  the ability to generate PDF/HTML documentation with `make doc`.

* Parametrized topologies (`Topo` subclasses) using the Mininet
  object.  For example, a tree network may be created with the
  command:

  `mn --topo tree,depth=2,fanout=3`

* A command-line interface (`CLI` class) which provides useful
  diagnostic commands (like `iperf` and `ping`), as well as the
  ability to run a command to a node. For example,

  `mininet> h11 ifconfig -a`

  tells host h11 to run the command `ifconfig -a`

* A "cleanup" command to get rid of junk (interfaces, processes, files
  in /tmp, etc.) which might be left around by Mininet or Linux. Try
  this if things stop working!

  `mn -c`

### New features in this release

This is primarily a performance improvement and bug fix release.

- Batch startup has been implemented for Open vSwitch, improving
  startup performance.

- OVS patch links have been implemented via OVSLink and --link ovs

  Warning! These links have *serious limitations* compared to
  virtual Ethernet pairs: they are not attached to real Linux
  interfaces so you cannot use tcpdump or wireshark with them;
  they also cannot be used in long chains - we don't recommend more
  than 64 OVSLinks, for example --linear,64. However, they can offer
  significantly better performance than veth pairs, for certain
  configurations.

- You can now easily install Mininet on a Raspberry Pi ;-)

- Additional information for this release and previous releases
  may be found in the release notes on docs.mininet.org

### Installation

See `INSTALL` for installation instructions and details.

### Documentation

In addition to the API documentation (`make doc`), much useful
information, including a Mininet walkthrough and an introduction
to the Python API, is available on the
[Mininet Web Site](http://mininet.org).
There is also a wiki which you are encouraged to read and to
contribute to, particularly the Frequently Asked Questions (FAQ.)

### Support

Mininet is community-supported. We encourage you to join the
Mininet mailing list, `mininet-discuss` at:

<https://mailman.stanford.edu/mailman/listinfo/mininet-discuss>

### Join Us

Thanks again to all of the Mininet contributors!

Mininet is an open source project and is currently hosted
at <https://github.com/mininet>.  You are encouraged to download
the code, examine it, modify it, and submit bug reports, bug fixes,
feature requests, new features and other issues and pull requests.
Thanks to everyone who has contributed code to the Mininet project
(see CONTRIBUTORS for more info!) It is because of everyone's
hard work that Mininet continues to grow and improve.

### Enjoy Mininet

Best wishes, and we look forward to seeing what you can do with
Mininet to change the networking world!

Bob Lantz
Mininet Core Team

[1]: https://travis-ci.org/mininet/mininet.svg?branch=master
