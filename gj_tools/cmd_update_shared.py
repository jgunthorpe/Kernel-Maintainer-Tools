from __future__ import print_function
import os
from .git import *


def get_alternates():
    res = set()
    altfn = git_output(["rev-parse", "--git-path", "objects/info/alternates"])
    if not os.path.exists(altfn):
        return res

    with open(altfn, "rb") as F:
        for I in F.readlines():
            I = I.strip()
            if I.endswith(b"/objects"):
                res.add(I[:-8])
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

    for I in remotes:
        git_call(["fetch", I])

    if remotes:
        print("Updated %s and remotes %s" % (repo.decode(), ",".join(remotes)))
    else:
        print("Updated %s" % (repo.decode()))


def args_update_shared(parser):
    parser.add_argument("--fetch",
                        action="store_true",
                        help="Fetch remotes in the local repository as well",
                        default=False)


def cmd_update_shared(args):
    """Fetch the latest upstream into the shared repo listed in alternates and
    then refresh the local 'origin' branch to the lastest upstream commit"""

    for I in get_alternates():
        update_repo(I)
    if args.fetch:
        git_call(["fetch", "--all"])
