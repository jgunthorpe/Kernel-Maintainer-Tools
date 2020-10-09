import collections

from .git import *


def args_fixup(parser):
    parser.add_argument("-n",
                        action="store_true",
                        dest="no_act",
                        help="Do not create the commits")
    parser.add_argument("-d",
                        action="store",
                        type=int,
                        dest="depth",
                        default=1,
                        help="Skip N commits")
    parser.add_argument(
        "files",
        nargs='*',
        help="The message ID to respond to, usually comes from patchwork")


def cmd_fixup(args):
    """Generate fixup commits for the given files that merge the files
       with the last commit of that file."""
    if len(args.files) == 0:
        args.files = [I.decode() for I in git_output(["ls-files", "-m"], mode="lines")]

    real_commit = {}
    commits = collections.defaultdict(set)
    for I in args.files:
        res = git_output([
            "log", "-n",
            str(args.depth), "--pretty=oneline", "HEAD", "^origin/master",
            "--", I
        ]).strip().decode()
        if len(res) != 0:
            res = res.splitlines()[-1]
        res = res.partition(" ")
        if res in real_commit:
            res = real_commit[res]
        else:
            while res[2].startswith("fixup!") or res[2].startswith("squash!"):
                other = res[2].partition("! ")[2]
                nres = None
                if re.match("^[0-9a-fA-F]+$", other):
                    try:
                        nres = git_output([
                            "log", "-n", "1", "--pretty=oneline", other, "--"
                        ]).strip().decode()
                    except subprocess.CalledProcessError:
                        nres = None
                if not nres:
                    other = re.escape(other)
                    res = git_output([
                        "log", "-n", "1", "--pretty=oneline",
                        "%s^^{/%s}" % (res[0], other), "--"
                    ]).decode().strip()
                else:
                    res = nres
                res = res.partition(" ")
            if not res or not res[0]:
                res = None
            real_commit[res] = res

        if res is not None:
            commits[res].add(I)

    for k, v in commits.items():
        print(k[0], k[2])
        print("  ", " ".join(v))
        if args.no_act:
            continue

        git_call(["add"] + list(v))
        git_call(["commit", "--fixup=%s" % (k[0])])
