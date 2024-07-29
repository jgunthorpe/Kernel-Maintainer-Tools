from __future__ import print_function
import os
from .git import *


def get_alternates():
    res = list()
    altfn = git_output(["rev-parse", "--git-path", "objects/info/alternates"])
    if not os.path.exists(altfn):
        return res

    with open(altfn, "rb") as F:
        for I in F.readlines():
            I = I.strip()
            if I.endswith(b"/objects"):
                gdir = I[:-8]
                if gdir not in res:
                    res.append(gdir)
    return res


def update_repo(repo):
    remotes = set()
    for I in git_output(["remote", "-v"], mode="lines"):
        if repo in I:
            remotes.add(I.partition(b'\t')[0].decode())

    with in_directory(repo):
        old_master = git_ref_id("remotes/origin/master", fail_is_none=True)
        if old_master is None:
            git_call(["fetch", "--all"])
        else:
            git_call(["fetch", "origin"])
            new_master = git_ref_id("remotes/origin/master")
            git_call(["update-ref", "-m", "git pull", "HEAD", new_master])

    if remotes:
        print("Updated %s and remotes %s" % (repo.decode(), ",".join(remotes)))
    else:
        print("Updated %s" % (repo.decode()))


def integerize(s):
    try:
        return int(s)
    except:
        return s


def sync_tags():
    """Upload tags and Linus's head to other repos"""
    tags = [
        tag
        for tag in git_output(["tag"], mode="lines")
        if re.match(rb"^v[5-6]\.\d+(-rc\d+)?$", tag)
    ]
    tags.sort(key=lambda x: list(map(integerize, re.split(rb"v|\.|-", x))))
    print(tags)
    sync_tags = tags[-9:]
    print(sync_tags)
    remotes = ["ko-rdma", "ko-iommufd", "github"]
    for remote in remotes:
        git_call(["push", remote, "linus/master:linus"] + sync_tags)


def args_update_shared(parser):
    pass


def cmd_update_shared(args):
    """Fetch the latest upstream into the shared repo listed in alternates and
    then refresh the local 'origin' branch to the lastest upstream commit"""
    sync_tags()

    for I in get_alternates():
        update_repo(I)
    git_call(["fetch", "--all"])

    print("Syncing tags")
    sync_tags()
