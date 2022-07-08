"""Various tools for locally checking out the kernel source tree"""
from __future__ import print_function
import subprocess
import os
import shutil
import stat
import shlex
import sys
from .git import *
from . import config


def args_linus_check_merge(parser):
    parser.add_argument("--linus",
                        default="remotes/origin/master",
                        help="The branch for Linus's master")
    parser.add_argument("refs",
                        nargs="+",
                        help="The refs to check mergability for")


def cmd_linus_check_merge(args):
    """Check that the given tag merges and compiles with Linus's tree without
    problems."""
    to_test = [git_commit_id(I) for I in args.refs]
    linus = git_commit_id(args.linus)
    dot_config = os.path.abspath(".config")
    if not os.path.exists(dot_config):
        dot_config = os.path.abspath("build-x86/.config")

    # Construct a trial merge between the two trees to evaluate conflicts
    with git_temp_worktree():
        git_call(["reset", "--hard", linus])

        linus_ref = git_output(["describe", "--all", linus])
        for I in to_test:
            test_ref = git_output(["describe", "--all", I])
            git_call([
                "merge", "-m",
                "automatic merge of %r and %r" % (linus_ref, test_ref),
                "--no-rerere-autoupdate", "--no-edit", linus, I
            ])

        merge_commit = git_commit_id("HEAD")

        print("Merge completed, commit is %s" % (merge_commit))

        compile_test(dot_config,
                     GitRange(merge_commit, linus).get_changed_files())


# -------------------------------------------------------------------------
def get_patch_commit(fn):
    with open(fn, "rb") as F:
        for ln in F.readlines():
            g = re.match(b"From ([0-9a-f]*) .*", ln)
            return git_norm_id(g.group(1))
    return None


def is_tree_ancestor(commit):
    """True if the commit is an ancestor of something we recognize as part of our
    canonical tree."""
    for I in [
            "origin/master", config.linus_master,
            "%s/for-next" % (config.remote_name),
            "%s/for-rc" % (config.remote_name)
    ]:
        try:
            git_call(["merge-base", "--is-ancestor", commit, I])
            return True
        except subprocess.CalledProcessError:
            pass
    return False


def args_internal_check_patch(parser):
    parser.add_argument("-C",
                        action="store",
                        help="git base directory",
                        required=True,
                        dest="git_dir")
    parser.add_argument("--commit",
                        action="store",
                        help="git commit directory",
                        required=True)
    parser.add_argument("patch_fn",
                        action="store",
                        help="Input patch filename")
    parser.add_argument("stamp_fn", action="store", help="Stamp filename")


def cmd_internal_check_patch(args):
    commit = get_patch_commit(args.patch_fn)
    if commit is not None:
        assert commit == args.commit

    with in_directory(args.git_dir):
        trailers = git_trailers(args.commit)

        for I in trailers:
            if I[0].lower() != "fixes":
                continue

            # Check the the commit being fixed is part of Linus's tree
            fcid = git_commit_id(I[1].partition(b' ')[0])
            if not is_tree_ancestor(fcid):
                print("E: Invalid Fixes line (not ancestor) %r" % (I, ))
                sys.exit(100)

            # Check if the Fixes line is cannonically formed
            expected = git_output(["fixes", fcid])
            got = b"%s: %s" % (I[0].encode(), I[1])
            if expected != got:
                print("E: Bad fixes line: %s vs %s" % (expected, got))
                sys.exit(100)

    with open(args.stamp_fn, "w") as F:
        pass


# -------------------------------------------------------------------------


def format_patches(commits, dfn):
    """Format all the patches and map the commit IDs to the filenames"""
    commit_ids = commits.get_commit_list()
    res = []
    for num, I in enumerate(reversed(commit_ids)):
        obj = git_read_object("commit", I)
        subject = obj.desc[0].strip().decode()
        fn = "%04d-%s.patch" % (num + 1, re.sub(r'[^\w]+', '-', subject))
        fn = os.path.join(dfn, fn)
        with open(fn, "wb") as F:
            F.write(git_output(["format-patch", "--stdout", I + "^!"]))
        res.append((I, fn))
    return res


def args_check_patch(parser):
    parser.add_argument(
        "--base",
        action="append",
        help="Set the 'upstream' point. Automatically all remote branches",
        default=None)


def cmd_check_patch(args):
    """Run checkpatch over patches at the top of this branch. The patch range is automatically to be
    patches that have not been sent to a remote. Use --base to set a different starting point"""
    commits = git_base_fewest_commits(args.base)
    commits.sanity_check()
    gdir = git_root()
    cwd = os.getcwd()

    with tempfile.TemporaryDirectory() as dfn:
        patches = format_patches(commits, dfn)
        if len(patches) == 0:
            return

        common_opts = ["--emacs", "--mailback", "--quiet", "--no-summary"]
        checkpatch = [
            "perl",
            os.path.abspath("scripts/checkpatch.pl"), "--root",
            os.path.abspath(".")
        ]
        if not os.path.exists(checkpatch[1]):
            nckp = os.path.join(dfn, "checkpatch.pl")
            with open(nckp, "w") as F:
                subprocess.check_call([
                    "git", "-C", config.ko_repo, "show",
                    "origin/master:scripts/checkpatch.pl"
                ],
                                      stdout=F)
            with open(os.path.join(dfn, "spelling.txt"), "w") as F:
                subprocess.check_call([
                    "git", "-C", config.ko_repo, "show",
                    "origin/master:scripts/spelling.txt"
                ],
                                      stdout=F)
            os.symlink(
                os.path.join(git_root(), "buildlib/const_structs.checkpatch"),
                os.path.join(dfn, "const_structs.checkpatch"))

            # for rdma-core, see buildlib/travis-checkpatch
            checkpatch = [
                "perl", nckp, "--no-tree", "--ignore",
                "PREFER_KERNEL_TYPES,FILE_PATH_CHANGES,EXECUTE_PERMISSIONS,USE_NEGATIVE_ERRNO,CONST_STRUCT"
            ]

        checkpatch.extend(common_opts)
        with open(os.path.join(dfn, "build.ninja"), "w") as F:
            print("rule checkpatch", file=F)
            print(" command = cd %r && %s $in && touch $out" %
                  (gdir, " ".join(shlex.quote(I) for I in checkpatch)),
                  file=F)
            print(" description=checkpatch for $in", file=F)

            print("rule gj_check", file=F)
            print(
                " command = %s %s internal-check-patch -C %s --commit $git_commit $in $out"
                % (shlex.quote(sys.executable), shlex.quote(
                    sys.argv[0]), shlex.quote(cwd)),
                file=F)
            print(" description=gj check for $in", file=F)

            for commit, fn in patches:
                checkpatch_stamp = fn + ".stamp"
                gj_stamp = fn + ".gj.stamp"
                print("build %s : gj_check %s" % (gj_stamp, fn), file=F)
                print("   git_commit = %s" % (commit), file=F)
                print("build %s : checkpatch %s | %s" %
                      (checkpatch_stamp, fn, gj_stamp),
                      file=F)
                print("default %s" % (checkpatch_stamp), file=F)
        subprocess.check_call(
            ["ninja", "-k", "%u" % (len(patches) * 2 + 1)], cwd=dfn)
