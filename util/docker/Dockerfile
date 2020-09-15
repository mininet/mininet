FROM debian:stretch-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -yq
RUN apt-get install -yq \
    arping \
    git \
    hping3 \
    iputils-ping \
    net-tools \
    sudo \
    traceroute

COPY . /root/mininet
RUN sh -c "/root/mininet/util/install.sh -fnv"

RUN apt-get clean

RUN chmod +x /root/mininet/util/docker/entrypoint.sh

ENV MN_FLAGS="--controller remote --mac --switch ovsk"

ENTRYPOINT [ "sh", "-c", "/root/mininet/util/docker/entrypoint.sh"]
