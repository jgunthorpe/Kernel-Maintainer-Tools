"""This very complicated script supports a simple workflow
 - Read list email from gmail via imap/fetchmail/etc. Delete emails
   after reading.
 - Take patches from patchworks and apply to git
 - Recover the original sender email from gmail archive, including cover letter
   and merge that with our local information from patchworks
 - Build a mbox for mutt with these relavent messages
 - User will use mutt to generate ack messages by hand
"""

from __future__ import print_function

import base64
import collections
import contextlib
import email.parser
import mailbox
import os
import re
import socket
import subprocess
import tempfile
import time

import httplib2

from . import cmd_pw_am_todo, config
from .git import *


def google_api_get_credentials():
    """Use cloud-maildir-sync as a credentials broker for a gmail oauth
    token"""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(config.cms_socket)
        sock.sendall(f"SMTP {config.cms_user}".encode())
        sock.shutdown(socket.SHUT_WR)
        ret = sock.recv(16 * 1024).decode()
        g = re.match("user=\\S+\1auth=\\S+ (\\S+)\1\1", ret)
    if re.match("user=\\S+\1auth=\\S+ (\\S+)\1\1", ret) is None:
        raise ValueError(f"Invalid CMS server response {ret!r}")
    import oauth2client.client
    return oauth2client.client.OAuth2Credentials(access_token=g.group(1),
                                                 client_id=None,
                                                 client_secret=None,
                                                 refresh_token=None,
                                                 token_expiry=None,
                                                 token_uri=None,
                                                 user_agent=None)

def google_api_get_gmail():
    """Get a gmail service object"""
    from apiclient import discovery

    credentials = google_api_get_credentials()
    http = credentials.authorize(httplib2.Http())
    return discovery.build('gmail', 'v1', http=http)


def ListMessagesMatchingQuery(service, user_id, query=''):
    """List all Messages of the user's mailbox matching the query.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    query: String used to filter messages returned.
    Eg.- 'from:user@some_domain.com' for Messages from a particular sender.

  Returns:
    List of Messages that match the criteria of the query. Note that the
    returned list contains Message IDs, you must use get with the
    appropriate ID to get the details of a Message.
    """
    response = service.users().messages().list(userId=user_id,
                                               includeSpamTrash=True,
                                               q=query).execute()
    messages = []
    if 'messages' in response:
        messages.extend(response['messages'])
    while 'nextPageToken' in response:
        page_token = response['nextPageToken']
        response = service.users().messages().list(
            userId=user_id, q=query, pageToken=page_token).execute()
        messages.extend(response['messages'])
    return messages


def gmail_get_msg_ids(gmail, msgids, format="metadata"):
    """Given a list of message-ids fetch the emails from Google. The returned
    dict will have a mapping of message-id to either gmail response or decoded
    email.Message for format="raw"."""
    msgids = set(msgids)
    if not msgids:
        return {}

    for I in msgids:
        assert I[0] == '<' and I[-1] == '>'

    q = " OR ".join("rfc822msgid:%s" % (I, ) for I in sorted(msgids))
    ids = ListMessagesMatchingQuery(gmail, "me", q)
    gmail_ids = {I["id"]
                 for I in ids}

    res = {}

    def got_msg(request_id, response, exception):
        if exception is not None:
            raise exception

        if "raw" in response:
            # Decode a raw message into an email.Message
            m = base64.urlsafe_b64decode(response["raw"])
            response = email.parser.BytesParser().parsebytes(m)

        g_msg_id = get_header(response, "message-id")

        assert g_msg_id not in res
        assert g_msg_id in msgids
        res[g_msg_id] = response

    batch = gmail.new_batch_http_request(callback=got_msg)
    for I in gmail_ids:
        batch.add(gmail.users().messages().get(userId="me",
                                               format=format,
                                               id=I))
    batch.execute()
    return res


@contextlib.contextmanager
def invoke_mutt_on_temp_mailbox():
    """Create a temporary mbox, allow the caller to fill it, then invoke mutt on
    the result."""
    with tempfile.NamedTemporaryFile() as F:
        # Fixme doesn't erase the temp file
        F.close()
        with contextlib.closing(mailbox.mbox(F.name, create=True)) as mb:
            yield mb
        subprocess.check_call(["mutt", "-f", F.name])


# -------------------------------------------------------------------------


class Commit(object):
    """A single commit we are building an ack email for"""
    patchworks_msg = None
    cover_msg_id = None
    gmail_message = None

    def __init__(self, commit_id, subject, msg_id):
        self.commit_id = commit_id
        self.git_subject = subject
        self.msg_id = msg_id


def unfold_header(s):
    # Hrm, I wonder if this is the right way to normalize a header?
    return re.sub(r"\n[ \t]+", " ", s)


def get_header(msg, header):
    """Get a header out of an email.Message"""
    if isinstance(msg, email.message.Message):
        if header not in msg:
            raise ValueError("No mail header %r" % (header))
        return unfold_header(msg[header])
    else:
        # Otherwise it is a gmail dict
        for I in msg["payload"]["headers"]:
            if I["name"].lower() == header:
                return I["value"]
        raise ValueError("No gmail header %r" % (header))


def match_msg(msgs, mbox_msg):
    """Match the subject of a mbox message against the commit list"""
    subject = get_header(mbox_msg, "subject").encode()
    for I in msgs:
        msg_id = get_header(mbox_msg, "message-id").strip()
        if msg_id != I.msg_id and I.git_subject not in subject:
            continue

        if (I.patchworks_msg is not None
                and I.patchworks_msg_id != get_header(mbox_msg, "message-id")):
            print("Duplicate message in patchworks %r" % (subject))
            continue

        I.patchworks_msg = mbox_msg
        I.patchworks_msg_id = get_header(mbox_msg, "message-id").strip()


def read_mbox_messages(search_dir, msgs):
    """Look in search_dir for files downloaded from patchworks that might contain
    the patchworks version of email messages that were git am'd into commits"""
    search_dir = os.path.expanduser(search_dir)
    fns = []
    for fn in os.listdir(search_dir):
        if not (fn.endswith(".mbox") or fn.endswith(".patch")):
            continue
        fn = os.path.join(search_dir, fn)
        fns.append((os.stat(fn).st_mtime, fn))
    fns.sort(reverse=True)
    for _, fn in fns:
        with contextlib.closing(mailbox.mbox(fn, create=False)) as mb:
            for msg in mb.values():
                match_msg(msgs, msg)


def get_first_in_thread(msgid, msg_data):
    """Follow the in-reply-to chain up to the last message."""
    saw = {msgid}
    while True:
        if msgid not in msg_data:
            return None

        try:
            msgid = get_header(msg_data[msgid], "in-reply-to")
        except ValueError:
            return msgid

        assert msgid not in saw
        saw.add(msgid)

    return None


def read_gmail_messages(gmail, msgs):
    msg_data = gmail_get_msg_ids(gmail, [I.patchworks_msg_id for I in msgs])

    # Fetching everything 'in-reply-to' will also fetch the cover letters.
    done = set()
    while True:
        todo = set()
        for I in msg_data.values():
            try:
                todo.add(get_header(I, "in-reply-to"))
            except ValueError:
                pass

        todo.difference_update(done)
        todo.difference_update(set(msg_data.keys()))
        if not todo:
            break

        done.update(todo)
        msg_data.update(gmail_get_msg_ids(gmail, todo, format="raw"))

    for I in msgs:
        I.gmail_message = msg_data[I.patchworks_msg_id]
        g_subject = get_header(I.gmail_message, "subject").encode()
        if I.git_subject not in g_subject:
            print("gmail returned the wrong message subject %r != %r" %
                  (g_subject, I.git_subject))

        cover_msg_id = get_first_in_thread(I.patchworks_msg_id, msg_data)
        if cover_msg_id is not None and cover_msg_id != I.patchworks_msg_id:
            I.cover_msg_id = cover_msg_id
            I.gmail_cover_message = msg_data[I.cover_msg_id]


def construct_msg(mb, commit, done):
    """Construct the mbox contents for a single commit"""
    # Include the cover letter first if we found it.
    if commit.cover_msg_id and commit.cover_msg_id not in done:
        done.add(commit.cover_msg_id)
        if isinstance(commit.gmail_cover_message, email.message.Message):
            mb.add(commit.gmail_cover_message)

    mboxmsg = commit.patchworks_msg
    if commit.gmail_message is not None:
        del mboxmsg["Subject"]
        # Patchworks mangles the subject, this one line is what this entire
        # script is really all about..
        # Note new patchworks retains the original mbox now, so none of this is needed
        mboxmsg["Subject"] = get_header(commit.gmail_message, "subject")
        try:
            # Including the reply-to means mutt will thread the patch series properly
            mboxmsg["In-Reply-To"] = get_header(commit.gmail_message,
                                                "in-reply-to")
        except ValueError:
            pass

    mb.add(mboxmsg)


def construct_reply_mbox(msgs):
    """Invoke mutt on all the messages we found for the commits"""
    done = set()
    with invoke_mutt_on_temp_mailbox() as mb:
        for I in msgs:
            construct_msg(mb, I, done)


# -------------------------------------------------------------------------


def args_ack_emails(parser):
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


def get_pw_messages(pw_files, commits):
    msgs = []
    for I in git_output(["log", "--pretty=format:%H\t%s"] +
                        commits.rev_range(),
                        mode="lines"):
        commit, _, subject = I.partition(b'\t')
        commit = git_norm_id(commit)
        trailers = git_trailers(commit)
        msg_id = None
        for hdr, value in trailers:
            if hdr == "Link" and value.startswith(
                    b"https://lore.kernel.org/r/"):
                msg_id = "<" + value[26:].decode() + ">"
                break

        msgs.append(Commit(commit, subject, msg_id))
    read_mbox_messages(pw_files, msgs)
    return msgs

def cmd_ack_emails(args):
    """Generate a mbox for mutt with the emails from patchworks&gmail that were
    applied to the local git"""
    commits = git_base_fewest_commits(args.base)
    commits.sanity_check()

    # Figure out the commits we are acking
    msgs = get_pw_messages(args.pw_files, commits)

    if not msgs:
        print("No new commits?")
        return
    for I in msgs:
        if I.patchworks_msg is None:
            print("No messages found in the patchworks directory matching %r" %
                  (I.git_subject))
    msgs = [I for I in msgs if I.patchworks_msg is not None]

    gmail = google_api_get_gmail()
    read_gmail_messages(gmail, msgs)

    construct_reply_mbox(msgs)


# -------------------------------------------------------------------------


def get_msg_ids(args, arg):
    g = re.match(r"https://patchwork.kernel.org/patch/(\d+)/?", arg)
    if g:
        rpc = cmd_pw_am_todo.RPC()
        p = rpc.get_patch(int(g.group(1)))
        for I in p.get('series', []):
            series = rpc.get_link(I['url'])
            if series.get("cover_letter"):
                yield series["cover_letter"]["msgid"]
        yield p["msgid"]
        return

    # A message ID encoded in a URL
    g = re.match(r"https://patchwork.kernel.org/project/.+?/patch/([^/]+)/?",
                 arg)
    if g:
        yield "<" + g.group(1) + ">"
        return

    # A link for a whole series
    g = re.match(
        r"https://patchwork.kernel.org/project/([^/]*)/list/\?series=(\d+)",
        arg)
    if g:
        rpc = cmd_pw_am_todo.RPC(g.group(1))
        series = rpc.get_series(int(g.group(2)))
        if series["cover_letter"]:
            yield series["cover_letter"]["msgid"]
        for I in series["patches"]:
            yield I["msgid"]
        return

    # Raw message ID
    if arg[0] == '<' and arg[-1] == '>':
        yield arg
        return

    # Assume the string is a message ID without <>, ie as displayed by patchwork
    yield "<%s>" % (arg)


def args_reply_email(parser):
    parser.add_argument(
        "msg_id",
        nargs='+',
        help="The message ID to respond to, usually comes from patchwork")


def cmd_reply_email(args):
    """Fetch messages from gmail and open mutt"""
    gmail = google_api_get_gmail()
    msg_ids = []
    for I in args.msg_id:
        msg_ids.extend(get_msg_ids(args, I))
    msgs = gmail_get_msg_ids(gmail, msg_ids, format="raw")

    with invoke_mutt_on_temp_mailbox() as mb:
        for msg in msgs.values():
            mb.add(msg)
