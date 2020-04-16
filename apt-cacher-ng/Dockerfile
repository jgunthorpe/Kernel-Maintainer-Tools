# apt-cacher-ng will cache rpms and deb downloads for container building.
# Set the relavent proxy variable to point to 3142 on the local machine.

# docker build -t apt-cacher-ng apt-cacher-ng/
# docker volume create apt-cacher-ng
# docker run -d -p 3142:3142 --mount source=apt-cacher-ng,target=/var/cache/apt-cacher-ng --name apt-cacher-ng apt-cacher-ng
FROM        ubuntu:cosmic

VOLUME      ["/var/cache/apt-cacher-ng"]
RUN apt-get update && apt-get install -y apt-cacher-ng

ADD https://www.centos.org/download/full-mirrorlist.csv /tmp/centos-mirrors.csv
ADD https://mirrors.fedoraproject.org/mirrorlist?repo=epel-7&arch=x86_64 /tmp/epel-mirrors.txt

RUN \
  echo "VfilePatternEx: (^/\?release=[0-9]+&arch=)|(^/metalink\?repo=epel-[0-9]+&arch=)|(/suse/setup/descr/)|(/gpg-pubkey-.*.asc)" >> /etc/apt-cacher-ng/acng.conf && \
  echo "Remap-centos: file:centos_mirrors /centos" >> /etc/apt-cacher-ng/acng.conf && \
  echo "Remap-epel: file:epel_mirrors /epel" >> /etc/apt-cacher-ng/acng.conf && \
  sed 's/^.*"http:/http:/' < /tmp/centos-mirrors.csv | sed 's/".*$//' | grep ^http > /etc/apt-cacher-ng/centos_mirrors && \
  grep '^http://' /tmp/epel-mirrors.txt | sed 's|^\(http://.*\)/7/x86_64/|\1|g' > /etc/apt-cacher-ng/epel_7_x86_64_mirrors

EXPOSE 3142
CMD chmod 777 /var/cache/apt-cacher-ng && /etc/init.d/apt-cacher-ng start && tail -f /var/log/apt-cacher-ng/*
