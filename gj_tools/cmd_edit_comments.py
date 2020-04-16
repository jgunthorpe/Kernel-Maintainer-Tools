"""This lets you edit the commit comments directly without having to use slow rebase.
"""
from __future__ import print_function
import re
import collections
import contextlib
from .git import *

CommitItem = collections.namedtuple("Item", "commit_id fn desc keys")


def get_parents(commit):
    """Return the parent commit ids from the list of keys in commit"""
    res = []
    for I in commit.keys:
        if I[0] == b"parent":
            assert re.match(IDRE, I[1])
            res.append(I[1].decode())
    return res


def extract_commit(commit_id, dfn, seq):
    """Extract a single commit text to a file containing the commit name"""
    obj = git_read_object("commit", commit_id)
    keys = obj.raw_keys
    desc = obj.desc

    subject = desc[0].strip().decode()
    res = CommitItem(commit_id=commit_id,
                     fn=os.path.join(
                         dfn, "%03d-%s.COMMIT_EDITMSG" %
                         (seq, re.sub(r'[^\w\s-]', '-', subject))),
                     desc=[I + b'\n' for I in desc],
                     keys=keys)

    with open(res.fn, "wb") as F:
        for I in res.desc:
            F.write(I)
    return res


def same_parents(commit, commit_map):
    for k, v in commit.keys:
        if k == b"parent":
            oldid = v.decode()
            if oldid != commit_map[oldid]:
                return False
    return True


def update_commit(commit, commit_map):
    """Read the commit description back from the file and re-create the commit
    object.  Since we create the commit object directly hash-object will
    return the same value if the object has not changed."""
    with open(commit.fn, "rb") as F:
        new_desc = list(F.readlines())

    # It is tempting to just let git figure out of the commit blob is
    # different, but GPG metadata and other stuff make that hard. Directly
    # check if the two things we are editing have changed or not.
    if new_desc == commit.desc and same_parents(commit, commit_map):
        commit_map[commit.commit_id] = commit.commit_id
        return

    with tempfile.NamedTemporaryFile() as F:
        for k, v in commit.keys:
            if k == b"parent":
                v = commit_map[v.decode()].encode()
            F.write(k + b" " + v + b"\n")
        F.write(b"\n")
        for I in new_desc:
            F.write(I)
        F.flush()

        new_commit = git_output_id(
            ["hash-object", "-t", "commit", "-w", F.name])
        commit_map[commit.commit_id] = new_commit


def topo_sort(commits):
    """Topologically sort the commits into a linear order for processing"""
    idmap = {I.commit_id: I
             for I in commits}
    done = set()
    res = []
    parents = set()

    def add_commit(commit_id):
        commit = idmap.get(commit_id)
        if commit is None:
            # Must be a parent commit outside our edit set.
            done.add(commit_id)
            parents.add(commit_id)
            return

        for I in get_parents(commit):
            if I not in done:
                add_commit(I)
        assert commit.commit_id not in done
        done.add(commit.commit_id)
        res.append(commit)

    for I in commits:
        if I.commit_id not in done:
            add_commit(I.commit_id)

    assert len(set(I.commit_id for I in res)) == len(commits)
    return res, parents


@contextlib.contextmanager
def commit_editor(commits, ref):
    """Yield a list of CommitItems, and when the context closes rewrite the
    commits using the updated CommitItems"""
    commits.sanity_check()

    old_head = git_commit_id(commits.newest)

    commit_ids = commits.get_commit_list()
    if not commit_ids:
        print("No commits.")
        return

    with tempfile.TemporaryDirectory() as dirname:
        # todo is an array of CommitItems
        todo = []
        for num, I in enumerate(reversed(commit_ids)):
            todo.append(extract_commit(I, dirname, num + 1))

        yield todo

        todo, parents = topo_sort(todo)
        commit_map = {I: I
                      for I in parents}
        for I in todo:
            update_commit(I, commit_map)

    new_head = commit_map[old_head]
    if old_head == new_head:
        print("No change.")
    else:
        assert git_output(["diff-tree", "-r", old_head, new_head]) == b""
        print("Updating ref %s from %s to %s" % (ref, old_head, new_head))
        git_call(
            ["update-ref", "-m", "gj edit-comments", ref, new_head, old_head])


def args_edit_comments(parser):
    parser.add_argument(
        "--base",
        action="append",
        help="Set the 'upstream' point. Automatically all remote branches",
        default=None)


def cmd_edit_comments(args):
    """Rewrite commit comments quickly. This directly edits the comments and
    reflows the commit IDs around the changes without altering the checked out
    tree. It is very fast."""
    with commit_editor(git_base_fewest_commits(args.base), "HEAD") as todo:
        subprocess.check_call(["emacs"] + [I.fn for I in todo])
