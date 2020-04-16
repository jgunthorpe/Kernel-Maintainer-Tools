"""This is a simple tool to aid the code reviewing process.
"""
from __future__ import print_function
import tempfile
import subprocess
import time
from .git import *


def get_remote_branches():
    branches = git_output(
        ["branch", "--all", "--list", "--format", '%(refname)'], mode="lines")
    return set(I for I in branches if I.startswith(b"refs/remotes"))


def get_merge_base(reference, head="HEAD"):
    """"Return the best ancestor commit for a list of branches."""
    # FIXME: this should iterate and pick the shortest instead
    if reference is None:
        reference = get_remote_branches()

    if isinstance(reference, str):
        reference = [reference]

    return git_output_id(["merge-base", head] + reference)


def is_dirty():
    """False if the working tree is clean.. FIXME could use git describe --dirty"""
    try:
        git_call(["diff-index", "--quiet", "--cached", "HEAD", "--"])
        git_call(["diff-files", "--quiet"])
    except subprocess.CalledProcessError:
        return True
    return False


def create_commit_file(fn, commits):
    with tempfile.NamedTemporaryFile() as F:
        F.write(b"-*- mode: mail; fill-column: 74 -*-\n")
        F.flush()
        git_output_to_file(["log", "--format=email"] + commits.rev_range(),
                           file=F)
        F.flush()
        msgs_id = git_output_id(["hash-object", "-w", F.name])

        if not os.path.isfile(fn):
            shutil.copy(F.name, fn)

    git_call(
        ["update-index", "--add", "--cacheinfo",
         "0644,%s,%s" % (msgs_id, fn)])


# -------------------------------------------------------------------------


def args_review(parser):
    parser.add_argument(
        "--base",
        action="append",
        help="Set the 'upstream' point. Automatically all remote branches",
        default=None)
    parser.add_argument("--commits",
                        action="store_true",
                        help="Do not write the commits.txt file",
                        default=False)


def cmd_review(args):
    """Review stuff.

    Compute what commits are unique in the current branch, then with those
    commits:

    - open a display of them in gitk.

    - Write out the commit messages to the file 'commit' and add it to the
      index, this makes it easy to revise the commit language and produce a
      diff

    - Diff the entire change and set it up so emacs's goto-line in the diff
      works properly

    - Open emacs on all files touched by the commits, the diff and the commits
      file.
    """
    commits = git_base_fewest_commits(args.base)
    commits.sanity_check()

    git_top = git_root()
    if git_top[-1] != '/':
        git_top = git_top + '/'

    with tempfile.TemporaryDirectory() as dirname:
        changed_files = commits.get_changed_files()

        diff = os.path.join(dirname, "all.diff")
        with open(diff, "wt") as F:
            git_output_to_file(["diff", "--stat"] + commits.rev_range(),
                               file=F)
            F.write("\n")
            F.write("\n")
            git_output_to_file(
                ["diff", "--src-prefix", git_top, "--dst-prefix", git_top] +
                commits.rev_range(),
                file=F)
        if args.commits:
            create_commit_file("commits.txt", commits)
            changed_files.append("commits.txt")
        commits.fork_gitk()

        time.sleep(0.4)
        subprocess.call(["emacs"] + changed_files + [diff])


# -------------------------------------------------------------------------


def args_finish_review(parser):
    pass


def cmd_finish_review(args):
    """Archive the review commit into a unique branch"""
    assert not is_dirty()
    branch = git_output(["rev-parse", "--abbrev-ref", "HEAD"])
    assert branch.startswith(b"review/")
    topic = branch[7:].decode()

    nbranch = "reviewed/%s/%s" % (time.strftime("%Y-%m-%d-%H%M"), topic)

    git_call(["branch", nbranch, "HEAD"])
    print("Recorded review in ", nbranch)
