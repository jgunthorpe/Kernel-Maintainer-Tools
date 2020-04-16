"""Various tools for doing things with gerrit"""
from __future__ import print_function
import textwrap
from .git import *
from . import config
from . import cmd_edit_comments


def args_jenkins_test(parser):
    parser.add_argument("rev",
                        nargs="?",
                        help="The rev to send to gerrit",
                        default="HEAD")


def cmd_jenkins_test(args):
    """Take the given rev and send it to the special testing change on gerrit so
    Jenkins will pick it up"""
    git_call([
        "fetch", "--no-tags", "-f", config.gerrit_linux,
        "rdma-next-mlx:refs/remotes/gerrit/rdma-next-mlx"
    ])
    base = git_output_id(
        ["merge-base", args.rev, "refs/remotes/gerrit/rdma-next-mlx"])

    lst = GitRange(args.rev, base)

    # And now create the commit
    msg = "Jason's for-testing\n\n"
    msg = msg + "This commit and topic is only to be able to run driver test. Contains\n\n"

    msg = msg + "\n".join(
        textwrap.fill(ln.decode(), width=74) for ln in
        git_output(["log", "--abbrev=12", '--format=commit %h ("%s")'] +
                   lst.rev_range(),
                   mode="lines"))
    msg = msg + "\n\n" + config.test_trailer

    commit = git_output_id(
        ["commit-tree", args.rev + "^{tree}", "-p", base, "-F", "-"],
        input=msg.encode())

    git_call(
        ["push", config.gerrit_linux,
         "%s:%s" % (commit, config.test_branch)])
    print(git_output(["show", "--no-patch", commit]).decode())


# -------------------------------------------------------------------------


def args_gerrit_add_tags(parser):
    parser.add_argument(
        "--base",
        action="append",
        help="Set the 'upstream' point. Automatically all remote branches",
        default=None)
    parser.add_argument("issue",
                        action="store",
                        help="The gerrit issue to set")


def cmd_gerrit_add_tags(args):
    """Rewrite the commit history to add gerrit issue and change id tags"""
    with cmd_edit_comments.commit_editor(git_base_fewest_commits(args.base),
                                         "HEAD") as todo:
        for I in todo:
            trailers = git_trailers(I.commit_id)
            if any(True for I in trailers if I[0].lower() == "change-id"):
                continue
            for lineno in range(len(I.desc) - 1, 0, -1):
                if not I.desc[lineno].strip():
                    I.desc.insert(lineno + 1,
                                  b"Change-Id: I%s\n" % (I.commit_id.encode()))
                    I.desc.insert(lineno + 1,
                                  b"issue: %s\n" % (args.issue.encode()))
                    break
            else:
                raise ValueError("Invalid description for %s" % (I.commit_id))

            with open(I.fn, "wb") as F:
                for ln in I.desc:
                    F.write(ln)
                del I.desc[:]


# -------------------------------------------------------------------------


def args_gerrit_remove_tags(parser):
    parser.add_argument(
        "--base",
        action="append",
        help="Set the 'upstream' point. Automatically all remote branches",
        default=None)


def cmd_gerrit_remove_tags(args):
    """Rewrite the commit history to remove gerrit issue and change id tags"""
    with cmd_edit_comments.commit_editor(git_base_fewest_commits(args.base),
                                         "HEAD") as todo:
        for I in todo:
            for lineno in range(len(I.desc) - 1, 0, -1):
                if not I.desc[lineno].strip():
                    break
                if (I.desc[lineno].startswith(b"Change-Id: ")
                        or I.desc[lineno].startswith(b"issue: ")):
                    del I.desc[lineno]

            with open(I.fn, "wb") as F:
                for ln in I.desc:
                    F.write(ln)
                del I.desc[:]
