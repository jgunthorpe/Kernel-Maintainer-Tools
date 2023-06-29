import re
import socket
import sys

import requests

from . import config


def authorize_interactive(args):
    import msal

    app = msal.PublicClientApplication("122f4826-adf9-465d-8e84-e9d00bc9f234")
    token = app.acquire_token_interactive(["Tasks.ReadWrite"],
                                          login_hint=args.user)

    return token['access_token']

def authorize_cms(args):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(args.cms_sock)
        sock.sendall(f"TODO {args.user}".encode())
        sock.shutdown(socket.SHUT_WR)
        ret = sock.recv(16 * 1024).decode()
        g = re.match("user=\\S+\1auth=(\\S+ \\S+)\1\1", ret)
        if g is None:
            raise ValueError(f"Invalid CMS server response {ret!r}")
        return g.group(1)


def get_tasklistid(token, name="defaultList"):
    r = requests.get(f"https://graph.microsoft.com/v1.0/me/todo/lists",
                     headers={'Authorization': token})
    for item in r.json()["value"]:
        if item["wellknownListName"] == name:
            return item["id"]
    raise ValueError(f"Could not find list {name}")


def get_msgid_from_stdin():
    if sys.stdin.isatty():
        raise ValueError("Bad message on stdin")

    from email.parser import BytesParser
    message = BytesParser().parsebytes(sys.stdin.buffer.read(),
                                        headersonly=True)
    msgid = message.get('Message-ID', None)
    if not msgid:
        raise ValueError("Bad message on stdin")
    msgid = msgid.strip('<>')
    return (msgid, message.get('Subject', None))


def args_todo(parser):
    parser.add_argument(
        "--cms_sock",
        required=True,
        help="The path to the cloud-mdir-sync CredentialServer UNIX socket")
    parser.add_argument(
        "--user",
        required=True,
        help="The username to use with oauth")


def cmd_todo(args):
    """Add an email piped to stdin as a task in O365 with a lore link"""
    msg_id,subject = get_msgid_from_stdin()

    #token = authorize(args)
    token = authorize_cms(args)

    tasklistid = get_tasklistid(token)

    new_task = {
        "title": f"{subject}\nhttp://lore.kernel.org/r/{msg_id}",
        "linkedResources": [{
            "webUrl": f"http://lore.kernel.org/r/{msg_id}",
            "applicationName": "lore.kernel.org",
            "displayName": "On Lore"
        }]
    }

    r = requests.post(
        f"https://graph.microsoft.com/v1.0/me/todo/lists/{tasklistid}/tasks",
        json=new_task,
        headers={'Authorization': token})
