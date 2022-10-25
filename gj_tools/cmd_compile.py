import copy

from .git import *
from . import config


def is_linux():
    return (os.path.isdir("Documentation") and os.path.isfile("Kconfig")
            and os.path.isfile("Makefile"))


def get_linux_compiler(args, build_dir):
    """Figure out what the last compiler used to build this tree was and keep
    using it"""
    if args.ccache:
        return config.compiler.split()
    main_cmd_fn = os.path.join(build_dir, "init/.main.o.cmd")
    if not os.path.exists(main_cmd_fn):
        return config.compiler.split()[-1:]
    with open(main_cmd_fn) as F:
        ln = F.readline()
        cmd = ln.partition(":=")[2].strip().split(' ')
        for idx, I in enumerate(cmd):
            if I.startswith("-"):
                return cmd[:idx]
    return config.compiler.split()[-1:]


def get_j():
    # sort of fuzzy way to deal with efficiency cores
    if os.cpu_count() > 16:
        return "-j14" # 8 way hyperthreaded
    return "-j8"

def compile_linux_x86(args):
    tot = os.getcwd()
    build_dir = tot
    cmd = ["make", "-C", tot]
    if os.path.exists(os.path.join(tot, "build-x86")):
        cmd.append("O=build-x86")
        build_dir = os.path.join(tot, "build-x86")

    cmd.extend(
        ["CC=%s" % (" ".join(get_linux_compiler(args, build_dir))), get_j()])

    if args.silent:
        cmd.append("-s")

    compile_cmd_fn = os.path.join(build_dir, "compile_commands.json")
    if not os.path.exists(compile_cmd_fn):
        cmd.append("all")
        cmd.append("compile_commands.json")

    os.execvp(cmd[0], cmd)


def tuxmake_linux(args, image, arch, prefix):
    tot = os.getcwd()
    build_dir = os.path.join(tot, f"build-{args.arch}")
    cmd = [
        "docker", "run", "-u", f"{os.getuid()}:{os.getgid()}", "-ti", "--rm",
        "-v", f"{tot}:{tot}", image
    ]
    cmd.extend([
        "make", "-C", tot, f"O={os.path.basename(build_dir)}", f"ARCH={arch}",
        f"CROSS_COMPILE={prefix}", get_j()
    ])

    if args.silent:
        cmd.append("-s")

    os.execvp(cmd[0], cmd)

# See https://tuxmake.org/architectures/
cross_linux = {
    "x86":
    compile_linux_x86,
    "arm64":
    lambda args: tuxmake_linux(args,
                               image="docker.io/tuxmake/arm64_gcc:latest",
                               arch="arm64",
                               prefix="aarch64-linux-gnu-"),
    "s390":
    lambda args: tuxmake_linux(args,
                               image="docker.io/tuxmake/s390_gcc:latest",
                               arch="s390",
                               prefix="s390x-linux-gnu-"),
    "ppc64":
    lambda args: tuxmake_linux(args,
                               image="docker.io/tuxmake/powerpc_gcc:latest",
                               arch="powerpc",
                               prefix="powerpc64le-linux-gnu-"),
}

# -------------------------------------------------------------------------


def is_rdma_core():
    return (os.path.isdir("buildlib") and os.path.isdir("kernel-headers")
            and os.path.isdir("rdma-ndd"))


def compile_rdma_core():
    if not os.path.isdir("build"):
        env = copy.copy(os.environ)
        env["EXTRA_CMAKE_FLAGS"] = "-DCMAKE_EXPORT_COMPILE_COMMANDS=true"
        env["CC"] = config.compiler.split()[-1]
        subprocess.check_call(["./build.sh"], env=env)
    os.execvp("ninja", ["ninja", "-C", os.path.join(os.getcwd(), "build")])


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
    parser.add_argument("--arch",
                        action="store",
                        help="Architecture to build for",
                        choices=set(cross_linux.keys()),
                        default="x86")


def cmd_b(args):
    """Compile the current source tree properly"""
    with in_directory(git_root()):
        if is_linux():
            cross_linux[args.arch](args)
        elif is_rdma_core():
            compile_rdma_core()
        else:
            raise ValueError("Don't recongize this tree")
