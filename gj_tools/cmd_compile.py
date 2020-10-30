from .git import *
from . import config


def is_linux():
    return (os.path.isdir("Documentation") and os.path.isfile("Kconfig")
            and os.path.isfile("Makefile"))


def get_linux_compiler(args):
    """Figure out what the last compiler used to build this tree was and keep
    using it"""
    if args.ccache:
        return config.compiler.split()
    if not os.path.exists("init/.main.o.cmd"):
        return config.compiler.split()[-1:]
    with open("init/.main.o.cmd") as F:
        ln = F.readline()
        cmd = ln.partition(":=")[2].strip().split(' ')
        for idx, I in enumerate(cmd):
            if I.startswith("-"):
                return cmd[:idx]
    return config.compiler.split()[-1:]


def compile_linux(args):
    cmd = [
        "make",
        "CC=%s" % (" ".join(get_linux_compiler(args))), "-j8", "-C",
        os.path.join(os.getcwd())
    ]
    if args.silent:
        cmd.append("-s")

    if (not os.path.exists("compile_commands.json")
            and os.path.exists("scripts/clang-tools/gen_compile_commands.py")):
        cmd.append("all")
        cmd.append("compile_commands.json")

    os.execvp(cmd[0], cmd)

# -------------------------------------------------------------------------


def is_rdma_core():
    return (os.path.isdir("buildlib") and os.path.isdir("kernel-headers")
            and os.path.isdir("rdma-ndd"))


def compile_rdma_core():
    if not os.path.isdir("build"):
        subprocess.check_call(["./build.sh"])
    os.execvp(
        "ninja",
        ["ninja", "-C", os.path.join(os.getcwd(), "build")])


# -------------------------------------------------------------------------


def args_b(parser):
    parser.add_argument("--ccache",
                        action="store_true",
                        help="Enable ccache for the build",
                        default=False)
    parser.add_argument("-s",
                        dest="silent",
                        action="store_true",
                        help="Silent build",
                        default=False)


def cmd_b(args):
    """Compile the current source tree properly"""
    with in_directory(git_root()):
        if is_linux():
            compile_linux(args)
        elif is_rdma_core():
            compile_rdma_core()
        else:
            raise ValueError("Don't recongize this tree")
