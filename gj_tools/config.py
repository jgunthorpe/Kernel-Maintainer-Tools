import pwd
import os

# The name of the git remote that is on k.o
remote_name = "ko-rdma"

# Short plain text user name to use in various places
user_name = pwd.getpwuid(os.getuid()).pw_name

# k.o ssh string
ko_ssh_server = "git@gitolite.kernel.org"

# Remote branch that is the master branch from Linus
linus_master = "remotes/linus/master"

# Compiler to use for any compile runs
compiler = "ccache clang-13"

# Path to the shared clone of kernel.org
ko_repo = "/home/shared/kernel.org.git"

# Gerrit URL for the Linux project
gerrit_linux = "ssh://jgg@l-gerrit.mtl.labs.mlnx:29418/upstream/linux"
test_branch = "refs/for/rdma-next-mlx/jgg_testing"
test_trailer = "issue: 1308201\nChange-Id: I7e5f8170cc3185c3f3d2529c117b5d5d5004ed61\nSigned-off-by: Nobody <nobody@mellanox.com>\n"

# gmail linkage
cms_socket = os.path.expanduser("~/mail/.cms/exim/unix")
cms_user = "jgg@ziepe.ca"

def is_linus(email):
    """True if the email belongs to the owner of kernel.org's git tree."""
    return (b"Linus Torvalds" in email or b"Greg Kroah-Hartman" in email)
