"""Tool specifically for working with the k.o maintainer git repository"""
from __future__ import print_function
import subprocess
import os
import shutil
import itertools
from .git import *
from . import config


def args_to_zero_day(parser):
    parser.add_argument("branch",
                        nargs="+",
                        help="The branch to generate the pull request for")


def cmd_to_zero_day(args):
    """Send a branch for zero day testing. This requires 'force pushing' to a wip/
    branch so that zero day will pick it up, since force push is disabled this will
    delete the remote branch and recreate it, but only if necessary."""

    git_call(["fetch", config.remote_name, "--prune"])

    branches = []
    force_push = []
    normal_push = []
    for I in args.branch:
        # Make sure the branch name is valid
        commit = git_commit_id(I)

        wip = "wip/%s-%s" % (config.user_name, I.split('/')[-1])
        wip_commit = git_commit_id("remotes/%s/%s" % (config.remote_name, wip),
                                   fail_is_none=True)

        if wip_commit is not None:
            # Check if the current branch is a subset of our current branch if
            # not we need to delete the remote branch..
            base = git_output_id(["merge-base", wip_commit, commit])
            if base != wip_commit:
                force_push.append(":" + wip)
        normal_push.append(I + ":" + wip)

    establish_ko_ssh()

    if force_push:
        git_call(["push", config.remote_name] + force_push)

    git_call(["push", config.remote_name] + normal_push)


# -------------------------------------------------------------------------


def show_ahead(top, base, summary_only=False):
    commits = git_output([
        "log", "--pretty=oneline", top, "^" + base, "^" + config.linus_master
    ],
                         mode="lines")
    if len(commits) == 0:
        return False

    print("%s %u ahead of %s" % (top, len(commits), base))
    if summary_only:
        return True

    for I in commits:
        print("  " + I.decode())

    return True


def show_cycle_progress(linus):
    """Find the last tag Linus created and report when and how long it has been."""
    for I in git_output(
        ["log", "-n", "2000", "--decorate=full", "--pretty=%h %D", linus],
            mode="lines"):
        g = re.search(rb"tag: (refs/tags/v[456][^, ]+)", I)
        if g is None:
            continue
        obj = git_read_object("tag", g.group(1))
        if not config.is_linus(obj.keys["tagger"]):
            continue
        break
    else:
        return

    date = extract_date(obj.keys["tagger"])
    date = date.astimezone(tz=None)
    now = datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(0)))
    now = now.astimezone(tz=None)

    print("%s released %s on %s, %.2f days ago" %
          (obj.keys["tagger"].split(b' ')[0].decode(),
           g.group(1).split(b'/')[-1].decode(), date.strftime("%B %d, %Y"),
           (now - date).total_seconds() / (60 * 60 * 24)))
    return


def is_linus_commit(commit, obj):
    # Linus creted a merge commit
    if len(obj.keys.get("parents", [])) > 1:
        return config.is_linus(obj.keys["committer"])

    # The commit is a tag from Linus
    try:
        git_output(["describe", "--exact-match", "--match=v*.*", commit],
                   null_stderr=True)
        return True
    except subprocess.CalledProcessError:
        pass

    return False


def find_linus_merged_commit(commit, base):
    """If commit is fully merged into base then we can just search backwards in
    the history to find the merge tag"""
    ids = git_output_id(
        ["rev-list", "--reverse", "--ancestry-path", base, "^" + commit],
        mode="lines")
    for I in itertools.chain([commit], ids):
        obj = git_read_object("commit", I)
        if is_linus_commit(I, obj):
            return I, obj
    raise ValueError("Could not find merge for %s" % (commit))


def find_linus_commit(commit, base):
    """Locate the oldest commit at the boundary of to ^base - this is sort of like
    what git merge-base --fork-point is supposed to do..

    Generally speaking this is not something that git can compute if there are
    merges, as we can't tell which boundary is the good one (eg merging
    branches from rc1 and rc2).. However the estimates are good enough.."""
    commits = git_output(["rev-list", "--boundary", commit, "^" + base],
                         mode="lines")
    if not commits:
        return find_linus_merged_commit(commit, base)

    oldest_linus = oldest = (None,
                             datetime.datetime.now(
                                 datetime.timezone(
                                     datetime.timedelta(minutes=0))))
    for I in commits:
        if not I.startswith(b"-"):
            continue

        I = git_norm_id(I[1:])
        obj = git_read_object("commit", I)
        committer = obj.keys["committer"]
        date = extract_date(obj.keys["committer"])
        if is_linus_commit(I, obj):
            if oldest_linus[1] > date:
                oldest_linus = (I, date, obj)
        if oldest[1] > date:
            oldest = (I, date, obj)
    if oldest_linus[0] is not None:
        oldest = oldest_linus

    if oldest[0] is None:
        return ValueError("Could not find merge base for %s" % (commit))
    return find_linus_merged_commit(oldest[0], base)


def show_last_merged(top, base):
    commit, obj = find_linus_commit(top, base)

    date = extract_date(obj.keys["committer"])
    date = date.astimezone(tz=None)
    now = datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(0)))
    now = now.astimezone(tz=None)
    try:
        commit_desc = git_output(
            ["describe", "--contains", "--match=v*.*", commit],
            null_stderr=True)
    except subprocess.CalledProcessError:
        commit_desc = git_output(["describe", "--match=v*.*", commit])

    print(" %s merged via %s on %s, %.2f days ago" %
          (obj.keys["committer"].split(b' ')[0].decode(), commit_desc.decode(),
           date.strftime("%B %d, %Y"),
           (now - date).total_seconds() / (60 * 60 * 24)))


def args_ko_status(parser):
    pass


def cmd_ko_status(args):
    branches = git_output(["branch", "--list", "--format", '%(refname)'],
                          mode="lines")
    ko_branches = set(I for I in branches if I.startswith(b"refs/heads/k.o/")
                      or I.startswith(b"refs/heads/k.o-iommufd/"))

    for I in sorted(ko_branches):
        I = I.decode()
        if "/wip/" in I:
            continue
        rbranch = I.replace("refs/heads/k.o/",
                            "refs/remotes/%s/" % (config.remote_name))
        rbranch = rbranch.replace("refs/heads/k.o-iommufd/",
                                  "refs/remotes/%s/" % ("ko-iommufd"))
        if git_ref_id(rbranch, fail_is_none=True) is None:
            continue
        assert rbranch != I
        if not show_ahead(I, config.linus_master, True):
            print("%s fully merged to %s" % (I, config.linus_master))
        show_ahead(I, rbranch)
        show_last_merged(I, config.linus_master)

    show_cycle_progress(config.linus_master)


# -------------------------------------------------------------------------


def args_ko_ssh(parser):
    pass


def cmd_ko_ssh(args):
    """Open a write authorized ssh control connection to kernel.org. This assumes
    openssh is setup with a caching control connection, and that two factor
    authentication is enabled for the user."""
    establish_ko_ssh()
