# docker build public-inbox/ -t lei
FROM ubuntu:jammy
RUN apt-get -qq update -y && apt-get -qq upgrade # 1
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    libdbd-sqlite3-perl \
    libdbi-perl \
    libemail-address-xs-perl \
    libemail-mime-perl \
    libencode-perl \
    libgit2-dev \
    libinline-c-perl \
    libio-compress-perl \
    liblinux-inotify2-perl \
    libmail-imapclient-perl \
    libnet-server-perl \
    libparse-recdescent-perl \
    libplack-middleware-reverseproxy-perl \
    libplack-perl \
    libsearch-xapian-perl \
    libtimedate-perl \
    liburi-perl \
    make \
    nano \
    pkg-config \
    sqlite3 \
    xapian-tools

RUN mkdir -p /opt/ && \
    git -C /opt/ clone https://public-inbox.org/public-inbox.git && \
    git -C /opt/public-inbox/ reset --hard v1.9.0

RUN mkdir -p /root/.cache/public-inbox/inline-c/

RUN cd /opt/public-inbox && \
    perl Makefile.PL && \
    make && \
    make install

#RUN cd /opt/public-inbox && \
#    make test
