"""
From Doug:
The PR email is easy:

1) Make note of any conflicts
2) Make note of anything dodgy in any way, and explain your justification
3) If it seems like there are just a huge number/size of patches for a
late -rc, or a surprisingly small number for an early -rc, you might
note why you think that is and whether or not you expect it to change
4) If you have some insight into coming things, like patches waiting
review that you haven't looked at, now's a good time to mention them too.
5) Otherwise just a quick summary of what's coming, with a more detailed
list of fixes in the signed tag message
6) Append the output of git request-pull <merge-base> <tag>

"""
from __future__ import print_function
import copy
import os
import subprocess
import sys
import tempfile
import time
from .git import *
from . import config

pull_url = "git://git.kernel.org/pub/scm/linux/kernel/git/rdma/rdma.git"


def write_body(F, args, branch_desc):
    print("Subject: [GIT PULL] Please pull RDMA subsystem changes", file=F)
    F.write("\n")
    print("Hi Linus,", file=F)
    F.write("\n")
    F.write(branch_desc.decode())
    F.write("\n")
    F.write("\n")
    if args.with_merged:
        F.write(
            "The tag %s with my merge resolution to your tree is also available to pull.\n"
            % (args.with_merged))
        F.write("\n")


def check_merge_tag(args, latest):
    mtag = args.tag + "-merged"
    merged_tag_commit = git_commit_id(mtag)
    commit = git_read_object("commit", merged_tag_commit)
    for I in commit.keys["parents"]:
        if git_norm_id(I) == latest:
            return mtag
    raise ValueError("Merge tag %s does not have a parent of %s" %
                     (mtag, latest))


def strip_pgp(desc):
    for idx, v in enumerate(desc):
        if v == b'-----BEGIN PGP SIGNATURE-----':
            return desc[:idx]
    return desc


def args_linus_pull_request(parser):
    parser.add_argument("--linus",
                        default=config.linus_master,
                        help="The branch for Linus's master")
    parser.add_argument("--tag",
                        default="for-linus",
                        help="The tag name to use")
    parser.add_argument("--with-merged",
                        action="store_true",
                        default=False,
                        help="Use 'tag'-merged as well")
    parser.add_argument("branch",
                        help="The branch to generate the pull request for")


def cmd_linus_pull_request(args):
    """Generate a pull request email for Linus.

    For the RDMA tree."""
    tag = "tags/" + args.tag

    linus_remote = re.match(r"remotes/(.*)/.*", args.linus).group(1)
    git_call(["fetch", linus_remote])

    branch_desc = git_output(
        ["config", "branch.%s.description" % (args.branch)])

    commits = GitRange("heads/" + args.branch, args.linus)

    to_push = [args.tag, args.branch]
    if args.with_merged:
        args.with_merged = check_merge_tag(args, commits.newest)
        to_push.append(args.with_merged)

    write_body(sys.stdout, args, branch_desc)
    print(b"\n".join(
        strip_pgp(git_read_object("tag", git_ref_id(args.tag)).desc)).decode())

    if args.with_merged:
        git_call([
            "request-pull", args.linus, pull_url,
            git_commit_id(args.with_merged)
        ])
    else:
        git_call(["request-pull", args.linus, pull_url, commits.newest])

    tag_commit = git_commit_id(tag, fail_is_none=True)
    if commits.newest != tag_commit:
        print("Create a tag first with:")
        print("  git tag -s -f %s %s" % (args.tag, commits.newest))
        commits.fork_gitk()
        sys.exit(100)

    git_push(config.remote_name, to_push, force=True)

    # Get rid of HOME from the environment. This gets rid of the default
    # .gitconfig which contains aliases for git.kernel.org that change the
    # pull request URL.
    orig_env = copy.deepcopy(os.environ)
    env = copy.deepcopy(os.environ)
    if "HOME" in env:
        del env["HOME"]

    for I in range(0, 10):
        try:
            rp = subprocess.check_output([
                "git", "request-pull", args.linus,
                "git://git.kernel.org/pub/scm/linux/kernel/git/rdma/rdma.git",
                tag
            ],
                                         env=env)
            break
        except subprocess.CalledProcessError:
            # The above goes to the kernel.org mirror network which takes a bit to catch up
            # to the push before. We doo all of
            if I != 0:
                print(
                    "Failed to produce request-pull, sleeping and trying again"
                )
                time.sleep(I)
                continue
            raise

    if args.with_merged:
        diffstat_pos = rp.rfind(b"\n\n")
        assert diffstat_pos != -1
        rp = rp[:diffstat_pos + 2]
        mb = git_base_fewest_commits([args.linus], args.with_merged).ancestor
        rp = rp + subprocess.check_output(
            ["git", "diff", "--stat", mb, args.with_merged])
        rp = rp + ("(diffstat from tag %s)\n" % (args.with_merged)).encode()

    with tempfile.NamedTemporaryFile(mode="w") as F:
        print("From %s Mon Sep 17 00:00:00 2001" % (tag_commit), file=F)
        print("From: Jason Gunthorpe <jgg@nvidia.com>", file=F)
        print(
            "To: Linus Torvalds <torvalds@linux-foundation.org>, Doug Ledford <dledford@redhat.com>",
            file=F)
        print("Cc: linux-rdma@vger.kernel.org, linux-kernel@vger.kernel.org",
              file=F)
        write_body(F, args, branch_desc)
        F.write(rp.decode())

        F.flush()
        with tempfile.NamedTemporaryFile(mode="w") as cfg:
            print("source ~/.muttrc", file=cfg)
            print("set crypt_autosign=yes", file=cfg)
            cfg.flush()
            subprocess.check_call(["mutt", "-F", cfg.name, "-H", F.name],
                                  env=orig_env)
