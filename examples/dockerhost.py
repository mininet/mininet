"""
This modules provides 'DockerHost', which uses docker containers
as mininet network nodes
"""

from mininet.log import debug, error
from mininet.node import Node
import os
import pty
import select
import shlex
import time


class DockerHost(Node):
    """
    This class provides docker containers to be used as host
    in the emulated network

    The images should have the following packages installed:
    - iproute2
    - iperf
    """

    from docker import from_env
    dcli = from_env()

    docker_args_default = {
        "image": "alpine",
        "tty": True,
        "detach": True,
        "stdin_open": True,
        "auto_remove": True,
        "network_mode": "bridge",
    }

    shell_cmd_default = ["sh", "-is"]

    def __init__(self, name, image=None, docker_args=None,
                 shell_cmd=None, **kwargs):
        """
        :param name:        name of this node
        :param image:       docker image to be used, overrides
                            parameter 'image' in 'docker_args'
        :param docker_args: all keyword arguments supported
                            by function 'run' of docker library [1]
        :param shell_cmd:   shell process to be started inside container

        [1] https://docker-py.readthedocs.io/en/stable/containers.html
        """
        if shell_cmd is None:
            self.shell_cmd = list(self.__class__.shell_cmd_default)
        else:
            self.shell_cmd = shlex.split(shell_cmd)

        self.docker_args = dict(self.__class__.docker_args_default)

        if docker_args is not None:
            self.docker_args.update(docker_args)

        if image is not None:
            self.docker_args["image"] = image

        if self.docker_args["image"] is None:
            raise ValueError("No image name specified!")

        self.container = None
        self.startContainer(name)

        super(DockerHost, self).__init__(name, **kwargs)

    def startContainer(self, name=None):
        """
        Start a new container and wait for it to start successfully, the
        default image to be used can be specified via 'setDefaultDockerArgs'
        as an optional constructor argument
        """
        self.__class__.dcli.images.get(self.docker_args["image"])
        self.container = self.__class__.dcli.containers.run(**self.docker_args)

        debug("Waiting for container " + name + " to start up\n")

        while not self.container.attrs["State"]["Running"]:
            time.sleep(0.1)
            self.container.reload()  # refresh information in 'attrs'

    def startShell(self, mnopts=None):
        if self.shell:
            error("%s: shell is already running\n" % self.name)
            return

        opts = '-cd' if mnopts is None else mnopts
        pid = str(self.container.attrs["State"]["Pid"])
        cmd = [ "mnexec", opts, "-e", pid,
                "env", "PS1=" + chr(127) ] + self.shell_cmd

        # Spawn a shell subprocess in a pseudo-tty, to disable buffering
        # in the subprocess and insulate it from signals (e.g. SIGINT)
        # received by the parent
        self.master, self.slave = pty.openpty()
        self.shell = self._popen(
            cmd, stdin=self.slave, stdout=self.slave,
            stderr=self.slave, close_fds=False
        )
        self.stdin = os.fdopen(self.master, 'r')
        self.stdout = self.stdin
        self.pid = self.shell.pid
        self.pollOut = select.poll()
        self.pollOut.register(self.stdout)
        # Maintain mapping between file descriptors and nodes
        # This is useful for monitoring multiple nodes
        # using select.poll()
        self.outToNode[self.stdout.fileno()] = self
        self.inToNode[self.stdin.fileno()] = self
        self.execed = False
        self.lastCmd = None
        self.lastPid = None
        self.readbuf = ''
        # Wait for prompt
        while True:
            data = self.read(1024)
            if data[ -1 ] == chr(127):
                break
            self.pollOut.poll()
        self.waiting = False
        # +m: disable job control notification
        self.cmd('unset HISTFILE; stty -echo; set +m')

    def read(self, *args, **kwargs):
        # The default shell of alpine linux (ash) sends '\x1b[6n' (get
        # cursor position) after PS1, the following code strips all characters
        # after the sentinel chr(127) as a workaround for the inherited
        # functions of class 'Node'
        buf = super(DockerHost, self).read(*args, **kwargs)
        i = buf.rfind(chr(127)) + 1
        return buf[0:i] if i else buf

    def cmd(self, *args, **kwargs):
        # Using 'ifconfig' for bringing devices up in subprocesses leads
        # to the activation of ax25 network devices on some systems,
        # iproute2 doesn't have this issue, we use the following workaround
        # until mininet is fully refactored to use iproute2
        if args[-1].endswith("up"):
            args = shlex.split(" ".join(args))
            if len(args) == 4:
                args = shlex.split("ip link set " + args[1]
                                   + " up && ip addr add " + args[2]
                                   + " dev " + args[1])
            elif len(args) == 3:
                args = shlex.split("ip link set " + args[1] + " up")
        return super(DockerHost, self).cmd(*args, **kwargs)

    def terminate(self):
        from docker.errors import NotFound
        try:
            self.container.stop()
        except NotFound:
            pass
        super(DockerHost, self).terminate()
