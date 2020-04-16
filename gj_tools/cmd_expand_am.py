from __future__ import print_function
import re
import os
from .git import *
from . import config


def args_expand_am(parser):
    parser.add_argument("FN", action="store", help="Patch mbox file")


def cmd_expand_am(args):
    """This takes in a mbox file of patches similar to 'git am' and arranges to
    apply them to a temporary git tree that contains a tree that exactly
    matches the start point(s) of the patch series.

    This allows git am to operate precisely with no fuzz and as it runs
    through the patch series it rebuilds in the local repository all of the
    original blobs that were used to form the patch.

    This means that a future 'git am' has access to the original blobs and can
    perform merge conflict resolution instead of failing to apply patches."""
    with open(args.FN) as F:
        patches = F.read()

    # Read all the files and blobs in the patch mbox
    files = collections.defaultdict(list)
    for I in re.finditer(
            r"^diff --git a/(.*) b/(.*)\nindex ([0-9a-f]+)\.\.([0-9a-f]+) [0-9]+$",
            patches, re.MULTILINE):
        afn, bfn, ablob, bblob = I.groups()
        assert afn == bfn
        blobs = files[afn]
        if not blobs:
            blobs.append(ablob)
        assert blobs[-1] == ablob
        blobs.append(bblob)

    # Create a commit with the dummy starting point
    with git_temp_worktree():
        #os.environ["GIT_INDEX_FILE"] = "tmpindex";
        for fn, blobs in sorted(files.items()):
            blobs[0] = git_ref_id(blobs[0])
            git_call([
                "update-index", "--add", "--cacheinfo",
                "0644,%s,%s" % (blobs[0], fn)
            ])
        tree = git_output_id(["write-tree"])
        commit = git_output_id(["commit-tree", tree + "^{tree}", "-F", "-"],
                               input=("Dummy git am for %s" %
                                      (args.FN)).encode())
        git_call(["reset", "--hard", commit])
        git_call(["am", "-s", args.FN])
        print("Done rebuilding dummy patch series, final dummy commit is %s" %
              (git_ref_id("HEAD")))
