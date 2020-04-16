from .git import *


def args_root(parser):
    pass


def cmd_root(args):
    """Display the absolute path to the top of the checkout'd git repository"""
    print(git_root())


def args_open_conflicts(parser):
    pass


def cmd_open_conflicts(args):
    """Open files with merge conflicts in an editor"""
    files = set(
        ln.partition(b'\t')[-1]
        for ln in git_output(["ls-files", "-u"], mode="lines"))
    os.execvp("emacs", ["emacs"] + sorted(files))
