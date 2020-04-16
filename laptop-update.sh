#!/bin/bash
set -x

scp mlx:~/archive/pass*.kdbx ~/archive/
scp mlx:~/oss/kernel-maint/cmds ~/oss/kernel-maint/

git -C /home/shared/kernel.org.git/ fetch --tags ssh://mlx:/home/shared/kernel.org.git/ remotes/origin/master:remotes/origin/master
git -C /home/shared/kernel.org.git/ fetch --all

git -C /home/shared/others-kernel.org.git fetch --all

git -C /home/shared/rdma-core.git fetch --all

git -C /home/jgg/dotfiles pull ssh://mlx:/home/jgg/dotfiles master

git -C /home/jgg/email-config pull ssh://mlx:/home/jgg/email-config master

git -C /home/jgg/oss/kernel-maint fetch mlx
git -C /home/jgg/oss/kernel-maint pull mlx/master

git -C /home/jgg/oss/k.o fetch origin
git -C /home/jgg/oss/k.o fetch linus
git -C /home/jgg/oss/k.o fetch ko-rdma --tags -f
git -C /home/jgg/oss/k.o fetch --prune mlx
git -C /home/jgg/oss/k.o reset --hard mlx/k.o/for-next
scp mlx:/home/jgg/oss/k.o/.config /home/jgg/oss/k.o/
git -C /home/jgg/oss/rc-k.o reset --hard mlx/k.o/for-rc
scp mlx:/home/jgg/oss/rc-k.o/.config /home/jgg/oss/rc-k.o/
scp mlx:/home/jgg/oss/dev-k.o/.config /home/jgg/oss/dev-k.o/
scp mlx:/home/jgg/oss/kvm/.config /home/jgg/oss/kvm/
git -C /home/jgg/oss/hmm-k.o reset --hard mlx/k.o/for-rc
scp mlx:/home/jgg/oss/hmm-k.o/.config /home/jgg/oss/hmm-k.o

git -C /home/jgg/oss/rdma-core fetch origin
git -C /home/jgg/oss/rdma-core fetch --prune mlx
git -C /home/jgg/oss/rdma-core fetch --prune github

git -C /home/jgg/mlx/linux fetch origin
git -C /home/jgg/mlx/linux fetch --prune mlx
scp mlx:/home/jgg/mlx/linux/.config /home/jgg/mlx/linux/

git -C /home/jgg/mlx/rdma-core fetch origin
git -C /home/jgg/mlx/rdma-core fetch --prune mlx

git -C /home/jgg/mlx/x-tools fetch --prune mlx
git -C /home/jgg/mlx/x-tools reset --hard mlx/master
git -C /home/jgg/mlx/x-tools fetch --prune github
git -C /home/jgg/mlx/x-tools fetch --prune mgithub

git -C /home/jgg/oss/sync fetch --prune origin
git -C /home/jgg/oss/sync reset --hard origin
rsync -a mlx:~/mail/.cms/ ~/mail/.cms/
