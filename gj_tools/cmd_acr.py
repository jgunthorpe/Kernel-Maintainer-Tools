"""Tool specifically for working with the k.o maintainer git repository"""
from __future__ import print_function
import subprocess
import json


def acr_cmd(args, opts):
    j = subprocess.check_output([
        "az", "acr", "repository", opts[0], "--name", args.name, "--output",
        "json"
    ] + opts[1:])
    if not j.strip():
        return None
    return json.loads(j)


def args_acr_cleanup(parser):
    parser.add_argument("--name",
                        default="ucfconsort",
                        help="The registry to refer to")


def cmd_acr_cleanup(args):
    """Remove untagged manifests from the ACR registry"""
    # See https://docs.microsoft.com/en-us/azure/container-registry/container-registry-delete
    print("Getting repositories")
    repositories = acr_cmd(args, ["list"])
    repositories.sort()

    to_clean = set()
    for repo in repositories:
        print("Checking manifests for %r" % (repo))
        manifests = acr_cmd(args, ["show-manifests", "--repository", repo])
        for image in manifests:
            if not image['tags']:
                to_clean.add("%s@%s" % (repo, image['digest']))
        for image in manifests:
            if image['tags']:
                break
        else:
            raise ValueError("No tagged image in %r\n" % (repo))
    print("Deleting %u untagged images" % (len(to_clean)))
    for image in sorted(to_clean):
        print(image)
        acr_cmd(args, ["delete", "--image", image, "--yes"])
