import contextlib
import datetime
import email.utils
import mailbox
import os
import re
import time
import urllib

from .cmd_pw_am_todo import form_link_header
from .git import *


def get_branches(name):
    """Return the name of all remote branches"""
    branches = git_output(
        ["branch", "--all", "--list", "--format", '%(refname)'], mode="lines")
    return set(I for I in branches
               if re.match(r"refs/heads/to-list/.*/" + name, I))


def email_list(emails):
    # Fixme: This utf-8 encodes things, maybe that is not needed anymore
    return ',\n\t'.join(
        email.utils.formataddr(epair)
        for epair in sorted(emails, key=lambda x: x[1].lower()))


class Series(object):
    message_fns = None
    cover_commit = None

    def _get_next_version(self):
        return 1

    def __init__(self, args, git_commits):
        self.git_commits = git_commits
        self.name = args.name
        self.prefix = args.prefix
        self.commits = git_commits.get_commit_list()
        self.commits.reverse()
        if git_output(["log", "-1", "--format=%s",
                       self.commits[-1]]).startswith(b"cover-letter: "):
            self.cover_commit = self.commits[-1]
            self.commits.insert(0, self.cover_commit)
            del self.commits[-1]
            self.patch_commits = GitRange(git_commits.newest + "^",
                                          git_commits.ancestor)
        else:
            self.patch_commits = git_commits

        self.to_emails = {commit: set() for commit in self.commits}
        self.cc_emails = {commit: set() for commit in self.commits}
        self.version = self._get_next_version()

        self.user_email = git_output(["config", "user.email"]).decode()

    def update_all_to(self, tos):
        for emails in self.to_emails.values():
            emails.update(tos)

    def read_commits(self):
        """Auto compute the cc list similar to how git send-email would do it,
        we do this here so we can get a chance to see and edit before the
        messages are reviewed."""
        skip_emails = set(I[1] for I in self.to_emails)
        skip_emails.add(self.user_email)
        newest_commit = 0
        for commit in self.commits:
            newest_commit = max(
                newest_commit,
                int(git_output(["log", "-1", "--format=%ct", commit])))
            for key, val in git_trailers(commit):
                val = val.decode()
                if '#' in val:
                    val = val.partition([0])
                addr = email.utils.parseaddr(val)
                if addr == ('', '') or addr[1] in skip_emails:
                    continue

                lkey = key.lower()
                if lkey.endswith("-by") or lkey in {"cc"}:
                    self.cc_emails[commit].add(addr)
                if lkey in {"to"}:
                    self.to_emails[commit].add(addr)

            serial = int(time.time() - newest_commit)
            assert (serial > 0)
            self.id_suffix = f"v{self.version}-{self.commits[-1][:12]}+{serial:x}-{self.name}_{self.user_email}"

    def _fix_cover_letter(self):
        """Extract the cover letter contents from the first cover letter
        commit and insert it into the git format-patch template"""
        fn = self.message_fns[self.cover_commit].decode()
        with open(fn,"rb") as F:
            msg = F.readlines()
        assert msg[0].startswith(f"From {self.commits[-1]}".encode())
        msg[0] = msg[0].replace(self.commits[-1].encode(),
                                self.cover_commit.encode())

        cmsg = git_read_object("commit", self.cover_commit)
        for idx,ln in enumerate(msg):
            if b"*** SUBJECT HERE ***" in ln:
                assert cmsg.desc[0].startswith(b"cover-letter: ")
                subj = cmsg.desc[0][14:]
                msg[idx] = msg[idx].replace(b"*** SUBJECT HERE ***", subj)
            if b"** BLURB HERE ***" in ln:
                msg[idx] = b"\n".join(cmsg.desc[2:]) + b"\n"

        with open(fn,"wb") as F:
            F.writelines(msg)

    def _flow_emails(self):
        cover = self.commits[0]
        # Everyone who gets the cover letter gets every patch
        for commit in self.commits:
            self.to_emails[commit].update(self.to_emails[cover])
            self.cc_emails[commit].update(self.cc_emails[cover])

        # Any extra cc's on patches get the cover letter too
        for commit in self.commits:
            self.to_emails[cover].update(self.to_emails[commit])
            self.cc_emails[cover].update(self.cc_emails[commit])

    def _fix_emails(self):
        """Use our own message-id for the threading and set the to/cc lists"""
        for idx, commit in enumerate(self.commits):
            fn = self.message_fns[commit].decode()
            with contextlib.closing(mailbox.mbox(fn)) as mb:
                _, msg = mb.popitem()
                assert commit == git_norm_id(msg.get_from().partition(' ')[0])

                msg["Message-Id"] = f"<{idx}-{self.id_suffix}>"
                if idx != 0:
                    msg["In-Reply-To"] = f"<0-{self.id_suffix}>"
                else:
                    assert "In-Reply-To" not in msg
                l = email_list(self.to_emails[commit])
                if l:
                    msg.add_header("To", l)
                l = email_list(self.cc_emails[commit])
                if l:
                    msg.add_header("Cc", l)
                mb.add(msg)

    def format_patches(self, dirname):
        """Put all the patches into mailbox files and format them with the
        cc list/etc"""
        if self.prefix:
            prefix = f"PATCH {self.prefix}"
        else:
            prefix = "PATCH"

        xargs = [
            "format-patch",
            "-o",
            dirname,
            "--no-thread",
            f"--subject-prefix={prefix}",
        ]
        if self.version != 1:
            xargs.append(f"--reroll-count={self.version}")
        if self.cover_commit:
            xargs.append("--cover-letter")

        self.message_fns = dict(
            zip(self.commits,
                git_output(xargs + self.patch_commits.rev_range(),
                           mode="lines")))
        assert len(self.message_fns) == len(self.commits)

        if self.cover_commit:
            assert b"/0000-" in self.message_fns[self.cover_commit]

        self._fix_cover_letter()
        self._flow_emails()
        self._fix_emails()

        return [self.message_fns[commit] for commit in self.commits]

    def make_commit(self, dirname):
        """Record what we created in a git commit"""
        index_fn = os.path.join(dirname, "git_index")
        env = {"GIT_INDEX_FILE": index_fn}
        for fn in self.message_fns.values():
            blob = git_output_id(["hash-object", "-w", fn], env=env)

            bfn = os.path.basename(fn).decode()
            git_output(
                ["update-index", "--add", "--cacheinfo", f"0644,{blob},{bfn}"],
                env=env)
        tree = git_output_id(["write-tree"], env=env)
        os.unlink(index_fn)

        mails_commit = git_output_id(["commit-tree", tree, "-F", "-"],
                                     input="Emails as-sent".encode())

        link = form_link_header(f"0-{self.id_suffix}")
        msg = f"""Record of sent patches: {self.name}

Series: {link}
Version: {self.version}
"""
        all_commit = git_output_id([
            "commit-tree", tree, "-p", self.git_commits.newest, "-p",
            self.git_commits.ancestor, "-p", mails_commit, "-F", "-"
        ],
                                   input=msg.encode())
        return all_commit


def get_aliases():
    aliases = os.path.expanduser(
        git_output(["config", "sendemail.aliasesfile"]).decode())
    res = {}
    with open(aliases) as F:
        for ln in F:
            g = re.match(r"alias (\S+) (.+)", ln.strip())
            if g is not None:
                addr = email.utils.parseaddr(g.group(2))
                if addr == ('', ''):
                    continue
                res[g.group(1)] = addr
    return res


def expand_to(args):
    aliases = get_aliases()
    res = set()
    for I in args.to:
        if I in aliases:
            res.add(aliases[I])
            continue

        addr = email.utils.parseaddr(I)
        if addr == ('', ''):
            raise ValueError(f"Bad email address {I!r}")
        res.add(addr)
    return res


def args_send(parser):
    parser.add_argument(
        "--base",
        action="append",
        help="Set the 'upstream' point. Automatically all remote branches",
        default=None)
    parser.add_argument("--head",
                        action="store",
                        help="Top most commit to send",
                        default="HEAD")
    parser.add_argument("--name",
                        action="store",
                        help="series name",
                        required=True)
    parser.add_argument("--prefix",
                        action="store",
                        help="Patch prefix, without version")
    parser.add_argument("--to",
                        action="append",
                        help="To email address",
                        default=[])


def cmd_send(args):
    """Like git send-email but keeps a record of what it did in a branch"""
    commits = git_base_fewest_commits(args.base, args.head)
    commits.sanity_check()

    series = Series(args, commits)
    series.update_all_to(expand_to(args))
    series.read_commits()

    with tempfile.TemporaryDirectory() as dirname:
        fns = series.format_patches(dirname)

        subprocess.check_call(["emacs"] + fns)

        all_commit = series.make_commit(dirname)
        date = datetime.date.today().isoformat()
        branch = f"to-list/{date}/{series.name}/{series.version}"
        git_call([
            "send-email",
            "--quiet",
            "--confirm=never",
            "--no-thread",
            "--no-xmailer",
            "--suppress-cc=body",
            "--suppress-cc=author",
            #"--smtp-server=/tmp/t.sh",
            "--to-cmd",
            "printf ''",
            "--no-format-patch",
            dirname,
        ])

        git_output(["branch", "-f", branch, all_commit])
        print(f"Saved to branch {branch}")
