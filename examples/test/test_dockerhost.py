"""
This modules provides test routines for 'DockerHost' and also
serves as usage example thereof
"""

from mininet.examples.dockerhost import DockerHost
from mininet.log import setLogLevel, info
from mininet.topo import LinearTopo
from mininet.net import Mininet
from mininet.node import OVSBridge
import contextlib
import docker
import functools
import tempfile
import unittest


def docker_pull_image(image):
    info("Pulling docker image '%s'...\n" % str(image))
    try:
        DockerHost.dcli.images.get(image)
        info("'%s' is already up to date!\n" % str(image))
    except docker.errors.ImageNotFound:
        DockerHost.dcli.images.pull(image)


def docker_create_image_ubunet():
    info("Building docker image 'ubunet'...\n")
    try:
        DockerHost.dcli.images.get("ubunet")
        info("'ubunet' is already up to date!\n")
        return
    except docker.errors.ImageNotFound:
        pass

    docker_pull_image("ubuntu:18.04")

    dockerfile_ubunet = b"""FROM ubuntu:18.04
RUN apt-get update && apt-get install -y --no-install-recommends \
iputils-ping \
iproute2 \
iperf \
&& rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["/bin/bash"]
"""
    with tempfile.TemporaryFile() as tmp:
        tmp.write(dockerfile_ubunet)
        tmp.seek(0)
        DockerHost.dcli.images.build(fileobj=tmp, tag="ubunet")


@contextlib.contextmanager
def create_mininet(image):
    DockerHostCustom = functools.partial(
        DockerHost,
        image=image,
    )
    net = Mininet(
        topo=LinearTopo(3),
        switch=OVSBridge,
        controller=None,
        host=DockerHostCustom,
    )
    try:
        net.start()
        yield net
    finally:
        net.stop()


class TestDockerHost(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        setLogLevel("info")
        info("Preparing docker environment...\n")
        docker_pull_image("alpine:3.10")
        docker_create_image_ubunet()

    def test_image_ubunet(self):
        with create_mininet(image="ubunet") as net:
            res = net.pingAll()
            self.assertEqual(res, 0.0)

    def test_image_alpine(self):
        with create_mininet(image="alpine:3.10") as net:
            res = net.pingAll()
            self.assertEqual(res, 0.0)


if __name__ == "__main__":
    unittest.main()
