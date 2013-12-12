Mininet: Rapid Prototyping for Software Defined Networks
========================================================

*The best way to emulate almost any network on your laptop!*

Version 2.1.0+

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

### New features in 2.1.0+

Mininet 2.1.0+ provides a number of bug fixes as well as
several new features, including:

* Convenient access to `Mininet()` as a dict of nodes
* X11 tunneling (wireshark in Mininet hosts, finally!)
* Accurate reflection of the `Mininet()` object in the CLI
* Automatically detecting and adjusting resource limits
* Automatic cleanup on failure of the `mn` command
* Preliminary support for running OVS in user space mode
* Preliminary support (`IVSSwitch()`) for the Indigo Virtual Switch
* support for installing the OpenFlow 1.3 versions of the reference
  user switch and NOX from CPqD
* The ability to import modules from `mininet.examples`

We have provided several new examples (which can easily be
imported to provide useful functionality) including:

* Modeling separate control and data networks: `mininet.examples.controlnet`
* Connecting Mininet hosts the internet (or a LAN) using NAT: `mininet.examples.nat`
* Creating per-host custom directories using bind mounts: `mininet.examples.bind`

Note that examples contain experimental features which might
"graduate" into mainline Mininet in the future, but they should 
not be considered a stable part of the Mininet API!

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

### Contributing

Mininet is an open source project and is currently hosted
at <https://github.com/mininet>.  You are encouraged to download
the code, examine it, modify it, and submit bug reports, bug fixes,
feature requests, new features and other issues and pull requests.
Thanks to everyone who has contributed to the project
(see CONTRIBUTORS for more info!)

Best wishes, and we look forward to seeing what you can do with
Mininet to change the networking world!

### Credits

The Mininet 2.1.0+ Team:

* Bob Lantz
* Brian O'Connor
