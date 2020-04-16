import contextlib
import datetime
import email.utils
import mailbox
import os
import re
import time

from .git import *


def get_branches(name):
    """Return the name of all remote branches"""
    branches = git_output(
        ["branch", "--all", "--list", "--format", '%(refname)'], mode="lines")
    return set(I for I in branches
               if re.match(r"refs/heads/to-list/.*/" + name, I))

def get_next_version(name):
    return 1

def format_patches(args, dirname, commits):
    if args.prefix:
        prefix = f"PATCH {args.prefix}"
    else:
        prefix = "PATCH"

    xargs = [
        "format-patch",
        "-o",
        dirname,
        "--thread",
        f"--subject-prefix={prefix}",
    ]
    if args.version != 1:
        xargs.append(f"--reroll-count={args.version}")
    return git_output(xargs + commits.rev_range(), mode="lines")

def get_aliases():
    aliases = os.path.expanduser(
        git_output(["config", "sendemail.aliasesfile"]).decode())
    res = {}
    with open(aliases) as F:
        for ln in F:
            g = re.match(r"alias (\S+) (.+)", ln.strip())
            if g is not None:
                addr = email.utils.parseaddr(g.group(2))
                if addr == ('',''):
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
            raise ValueError(f"Bad email address {i!r}")
        res.add(addr)
    return res

def compute_emails(args, to_emails, commits):
    """Auto compute the cc list similar to how git send-email would do it,
    we do this here so we can get a chance to see and edit before the messages
    are reviewed."""
    skip_emails = set(I[1] for I in to_emails)
    skip_emails.add(git_output(["config", "user.email"]).decode())
    res = {}
    newest_commit = 0
    for commit in commits.get_commit_list():
        newest_commit = max(
            newest_commit,
            int(git_output(["log", "-1", "--format=%ct", commit])))
        lres = set()
        for key, val in git_trailers(commit):
            val = val.decode()
            if '#' in val:
                val = val.partition([0])
            addr = email.utils.parseaddr(val)
            if addr == ('', '') or addr[1] in skip_emails:
                continue

            lkey = key.lower()
            if lkey.endswith("-by") or lkey in {"cc"}:
                lres.add(addr)
        res[commit] = lres
    args.newest_commit = newest_commit
    return res

def email_list(emails):
    return ', '.join(
        email.utils.formataddr(epair)
        for epair in sorted(emails, key=lambda x: x[1]))


def fix_emails(args, commits, to_emails, cc_emails, fns):
    """Use our own message-id for the threading and set the to/cc lists"""
    email = git_output(["config", "user.email"]).decode()
    serial = int(time.time() - args.newest_commit)
    assert(serial > 0)
    id_suffix = f"v{args.version}-{commits.newest[:12]}+{serial:x}-{args.name}%{email}"
    args.zero_msg_id = f"0-{id_suffix}"
    for idx, fn in enumerate(fns):
        fn = fn.decode()
        with contextlib.closing(mailbox.mbox(fn)) as mb:
            _, msg = mb.popitem()
            commit = git_norm_id(msg.get_from().partition(' ')[0])

            msg.replace_header("Message-Id", f"<{idx}-{id_suffix}>")
            if idx != 0:
                msg.replace_header("In-Reply-To", f"<{args.zero_msg_id}>")

            msg.add_header("To", email_list(to_emails))
            if idx == 0:
                cc_val = email_list(set().union(*cc_emails.values()))
            else:
                cc_val = email_list(cc_emails[commit])
            if cc_val:
                msg.add_header("Cc", cc_val)

            mb.add(msg)

def make_commit(args, dirname, commits, fns):
    """Record what we created in a git commit"""
    index_fn = os.path.join(dirname,"git_index")
    env = {"GIT_INDEX_FILE": index_fn}
    for fn in fns:
        blob = git_output_id(["hash-object", "-w", fn], env=env)

        bfn = os.path.basename(fn).decode()
        git_output(
            ["update-index", "--add", "--cacheinfo", f"0644,{blob},{bfn}"],
            env=env)
    tree = git_output_id(["write-tree"], env=env)
    os.unlink(index_fn)

    mails_commit = git_output_id(["commit-tree", tree, "-F", "-"],
                                 input="Emails as-sent".encode())

    msg = f"""Record of sent patches: {args.name}

Series: http:///lore.kernel.org/r/{args.zero_msg_id}
Version: {args.version}
"""
    all_commit = git_output_id([
        "commit-tree", tree, "-p", commits.newest, "-p", commits.ancestor,
        "-p", mails_commit, "-F", "-"
    ],
                               input=msg.encode())
    return all_commit

def args_send(parser):
    parser.add_argument(
        "--base",
        action="append",
        help="Set the 'upstream' point. Automatically all remote branches",
        default=None)
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
                        required=True)


def cmd_send(args):
    """Like git send-email but keeps a record of what it did in a branch"""
    commits = git_base_fewest_commits(args.base)
    commits.sanity_check()
    name = args.name

    to_emails = expand_to(args)
    cc_emails = compute_emails(args, to_emails, commits)
    args.version = get_next_version(name)
    with tempfile.TemporaryDirectory() as dirname:
        fns = format_patches(args, dirname, commits)
        fix_emails(args, commits, to_emails, cc_emails, fns)
        subprocess.check_call(["emacs"] + fns)
        all_commit = make_commit(args, dirname, commits, fns)
        git_call([
            "send-email",
            "--quiet",
            "--confirm=never",
            "--no-thread",
            "--no-xmailer",
            "--suppress-cc=body",
            "--suppress-cc=author",
            #"--smtp-server=/tmp/t.sh",
            "--to-cmd","printf ''",
            "--no-format-patch",
            dirname,
        ])

        date = datetime.date.today().isoformat()
        branch = f"to-list/{date}/{args.name}/{args.version}"
        git_output(["branch", "-f", branch, all_commit])
        print(f"Saved to branch {branch}")
