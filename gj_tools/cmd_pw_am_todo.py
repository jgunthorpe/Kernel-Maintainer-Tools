import configparser as ConfigParser
import contextlib
import copy
import email.parser
import hashlib
import mailbox
import sys
import urllib.parse
import xmlrpc.client as xmlrpclib

import requests

from . import cmd_ack_emails, config
from .git import *

CONFIG_FILE = os.path.expanduser('~/.pwclientrc')

# -------------------------------------------------------------------------
# From pwclient


class RPC(object):
    by_project = {}

    def __init__(self, project=None):
        pwconfig = ConfigParser.ConfigParser()
        pwconfig.read([CONFIG_FILE])
        if project is None:
            project = pwconfig.get('options', 'default')
        self.project = project_str = project
        self.auther = requests.auth.HTTPBasicAuth(
            pwconfig.get(project_str, 'username'),
            pwconfig.get(project_str, 'password'))

        url = pwconfig.get(project_str, 'url')
        self.url = url.replace("/xmlrpc/", "/api/")
        self.user = pwconfig.get(project_str, 'username')
        RPC.by_project[project] = self

    def check_json(self, r: requests.Response):
        if r.status_code != 200:
            print(f"patchworks failed {r.text}")
            r.raise_for_status()
            raise ValueError("Bad patchworks response")
        return r.json()

    def patch_list(self, params):
        params = copy.copy(params)
        params["project"] = self.project
        r = requests.get(self.url + "1.2/patches/",
                         params=params,
                         auth=self.auther)
        return self.check_json(r)

    def normalize_patch_id(self, patch_idish):
        # int values are just normal IDs
        if isinstance(patch_idish, int):
            return patch_idish

        # Otherwise it must be a message ID, search for it
        if "@" in patch_idish:
            lst = self.patch_list(params={"msgid": patch_idish})
            if len(lst) != 1:
                raise ValueError(r"Bad patch id {r!patch_idish}")
            return int(lst[0]["id"])
        # Must be an int value
        return int(patch_idish)

    def get_patch(self, patch_id):
        r = requests.get(self.url + "1.1/patches/%d/" % (patch_id),
                         auth=self.auther)
        return self.check_json(r)

    def modify_patch(self, patch_id, json):
        r = requests.patch(self.url + "1.2/patches/%d/" % (patch_id),
                           json=json,
                           auth=self.auther)
        return self.check_json(r)

    def get_series(self, series_id):
        r = requests.get(self.url + "1.1/series/%d/" % (series_id),
                         auth=self.auther)
        return self.check_json(r)

    def patch_get_mbox(self, patch_id):
        return requests.get("%s/patch/%d/mbox/" %
                            (self.url.replace("/api/", ""), patch_id),
                            auth=self.auther).content

    def get_link(self, url):
        assert url.startswith(self.url)
        r = requests.get(url, auth=self.auther)
        return self.check_json(r)

    def user_list(self, params):
        params = copy.copy(params)
        params["project"] = self.project
        r = requests.get(self.url + "1.1/users/",
                         params=params,
                         auth=self.auther)
        return self.check_json(r)

def pw_am_patches(args, rpc, patches):
    """Download and write all the patches to a mbox file, then run git am on that file"""
    downloads = os.path.expanduser(args.pw_files)
    with tempfile.NamedTemporaryFile(dir=downloads) as F:
        m = hashlib.sha1()
        with contextlib.closing(mailbox.mbox(F.name, create=True)) as mb:
            for I in patches:
                m.update(b"%u" % (I))
                mbox = rpc.patch_get_mbox(I)
                msg = email.parser.BytesParser().parsebytes(mbox)
                mb.add(msg)

        bundle = os.path.join(downloads, "bundle-%s.mbox" % (m.hexdigest()))
        if os.path.exists(bundle):
            os.unlink(bundle)
        os.link(F.name, bundle)

    print("Applying bundle of %u patches %s" % (len(patches), bundle))
    git_exec(["am", "-3s", bundle])


# -------------------------------------------------------------------------


def extract_id(rpc, id_str):
    # A link for a single patch
    g = re.match(r"https://patchwork.kernel.org/patch/(\d+)/?", id_str)
    if g:
        yield rpc.normalize_patch_id(g.group(1))
        return
    g = re.match(r"https://patchwork.kernel.org/project/.+?/patch/([^/]+)/?", id_str)
    if g:
        yield rpc.normalize_patch_id(g.group(1))
        return

    # A link for a whole series
    g = re.match(
        r"https://patchwork.kernel.org/project/([^/]*)/list/\?series=(\d+)",
        id_str)
    if g:
        rpc = RPC.by_project.get(g.group(1), None)
        if rpc is None:
            rpc = RPC(g.group(1))

        patches = rpc.patch_list({
            "series": int(g.group(2)),
            "archived": False,
            "state": "new",
            "order": "date",
            "per_page": "100"
        })
        for I in patches:
            yield I["id"]
        return

    yield int(id_str)


def args_pw_am_id(parser):
    parser.add_argument(
        "--pw_files",
        action="store",
        help="Directory where the patchworks files were downloaded to",
        default="~/Downloads")
    parser.add_argument("--project",
                        action="store",
                        help="Project to use",
                        default=None)
    parser.add_argument("ID",
                        nargs="+",
                        action="store",
                        help="Patchworks IDs to git-am")


def cmd_pw_am_id(args):
    """Apply a list of patches from patchworks using their IDs"""
    rpc = RPC(args.project)
    ids = []
    for I in args.ID:
        ids.extend(extract_id(rpc, I))
    pw_am_patches(args, rpc, ids)


# -------------------------------------------------------------------------
def args_internal_applypatch_msg(parser):
    parser.add_argument("commit_fn",
                        action="store",
                        help="Commit Message filename")


def form_link_header(msg_id):
    # RFC 2396 section 3.3
    url = urllib.parse.quote(msg_id, safe="/;=?:@&=+$,")
    return f"Link: https://lore.kernel.org/r/{url}"


def cmd_internal_applypatch_msg(args):
    """Edit the commit message from git am to change the Message-Id header into a
    proper Link header in the right place."""
    with open(args.commit_fn, "rb") as F:
        lines = F.readlines()

    lines.reverse()
    link_hdr = None;
    for I in range(len(lines)):
        if not lines[I].strip():
            break

        m = re.match(rb'^Message-I[dD]:\s*<?([^>]+)>?$', lines[I])
        if m:
            del lines[I]
            n_link_hdr = form_link_header(m.group(1)).encode()
            if link_hdr is not None:
                if n_link_hdr != link_hdr:
                    print(f"Mismatch {n_link_hdr!r} {link_hdr!r}")
            link_hdr = n_link_hdr

        m = re.match(rb'^Link:\s+http.*$', lines[I])
        if m:
            n_link_hdr = lines[I].strip()
            del lines[I]
            if link_hdr is not None:
                if n_link_hdr != link_hdr:
                    print(f"Mismatch {n_link_hdr!r} {link_hdr!r}")
            else:
                link_hdr = n_link_hdr

    if link_hdr is None:
        print(
            "No message id in patch commit, set 'git config am.messageid true' ?\n",
            file=sys.stderr)
        sys.exit(100)

    for end_trailers, I in enumerate(lines):
        if not I.strip():
            break
    else:
        print("Bad commit message format\n")

    while lines[end_trailers - 1].startswith(b"Fixes"):
        end_trailers = end_trailers - 1
    lines.insert(end_trailers, link_hdr + b"\n")

    # Remove duplicated merger signed-off-by lines.
    for ln, I in enumerate(lines):
        if ln != 0 and I == lines[0]:
            del lines[ln]
            break

    with open(args.commit_fn, "wb") as F:
        for I in reversed(lines):
            F.write(I)

# -------------------------------------------------------------------------
def args_pw_mark_applied(parser):
    parser.add_argument(
        "--pw_files",
        action="store",
        help="Directory where the patchworks files were downloaded to",
        default="~/Downloads")
    parser.add_argument(
        "--base",
        action="append",
        help="Set the 'upstream' point. Automatically all remote branches",
        default=None)
    parser.add_argument("--project",
                        action="store",
                        help="Project to use",
                        default=None)


def cmd_pw_mark_applied(args):
    """Using the Link: header mark all the patches since base as applied on
    patchworks"""
    commits = git_base_fewest_commits(args.base)
    commits.sanity_check()

    # Load the messages from the commits and extract the patchworks IDs
    msgs = cmd_ack_emails.get_pw_messages(args.pw_files, commits)
    to_ack = set()
    for I in msgs:
        if I.patchworks_msg is None:
            continue
        pwid = cmd_ack_emails.get_header(I.patchworks_msg, "X-Patchwork-Id")
        to_ack.add(int(pwid))

    rpc = RPC(args.project)

    my_user = rpc.user_list({"q": config.cms_user})[0]
    applied = {'state': "accepted", 'delegate': my_user["id"]}
    for I in sorted(to_ack):
        r = rpc.modify_patch(I, applied)
        print(f"Updated {r['name']!r} <- {applied!r}")
