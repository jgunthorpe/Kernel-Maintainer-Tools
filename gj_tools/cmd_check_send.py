import collections
import datetime
import re

from .git import *


class Sent(object):
    def __init__(self, branch, date, version):
        self.branch = branch
        self.date = date
        self.version = version

        self.branch_commit = git_ref_id(branch)
        self.tags = git_read_object("commit", self.branch_commit).desc
        if b"Record of sent patches:" not in self.tags[0]:
            self.tags = None
            self.branch_commit = None
            return

        for ln in self.tags:
            ln = ln.decode()
            if ln.startswith("Version:"):
                assert(int(ln.split(' ')[1]) == self.version)
            if ln.startswith("Series:"):
                self.lore_link = re.match(r".* (https*://.*)$", ln).group(1)

        self.commits = GitRange(f"{self.branch_commit}^1", f"{self.branch_commit}^2")


def get_to_list_branches():
    """Return the name of all remote branches"""
    branches = git_output(
        ["branch", "--all", "--list", "--format", '%(refname)'], mode="lines")
    res = collections.defaultdict(list)
    for I in branches:
        g = re.match(br"^refs/heads/to-list/(\d+-\d+-\d+)/([^/]+)/(\d+)$", I)
        if g is None:
            continue
        d = datetime.datetime.strptime(g.group(1).decode(), "%Y-%m-%d")
        res[g.group(2).decode()].append(Sent(I, d, int(g.group(3))))
    return res


def search_message_id(args, sent):
    if not sent.lore_link:
        return False
    msgid_stem = re.match(r".+://.*?/\d+-(.+?)@.*$", sent.lore_link).group(1)
    pattern = msgid_stem

    for tip in args.tips:
        r = GitRange(tip, sent.commits.ancestor)
        commits = git_output(["log", "--grep", pattern] + r.rev_range(),
                             mode="lines")
        if commits:
            sent.upstream_commits = commits
            return True
    return False


def args_check_send(parser):
    parser.add_argument("-n",
                        dest="num",
                        action="store",
                        help="Last N to-list series to show",
                        type=int,
                        default=0)
    parser.add_argument("--tip",
                        dest="tips",
                        action="append",
                        help="Heads to search",
                        default=["linus/master"])


def cmd_check_send(args):
    """Print out all the 'gj send' patches recorded and try to guess if they
    have been merged"""
    sent_dict = get_to_list_branches()
    sent_list = list(sent_dict.keys())
    sent_list.sort(key=lambda x: sent_dict[x][-1].date)
    if args.num:
        sent_list = sent_list[-1 * args.num:]

    for k in sent_list:
        sent = sent_dict[k][-1]
        print(f"{k} v{sent.version}")
        if not search_message_id(args, sent):
            print(f"   NOT FOUND {sent.lore_link}")
