import copy

from .git import *
from . import config

# See https://tuxmake.org/architectures/
arches = {
    "x86":
    dict(arch="x86-64", prefix="x86_64-pc-linux-gnu"),
    "arm64":
    dict(arch="arm64",
         prefix="aarch64-linux-gnu",
         image="docker.io/tuxmake/arm64_gcc:latest"),
    "arm":
    dict(arch="arm",
         prefix="arm-linux-gnueabihf",
         image="docker.io/tuxmake/arm_gcc:latest"),
    "s390":
    dict(arch="s390",
         prefix="s390x-linux-gnu",
         image="docker.io/tuxmake/s390_gcc:latest"),
    "ppc64":
    dict(arch="powerpc",
         prefix="powerpc64le-linux-gnu",
         image="docker.io/tuxmake/powerpc_gcc:latest"),
    "arc":
    dict(arch="arc",
         prefix="arc-elf32",
         image="docker.io/tuxmake/arc_gcc:latest"),
}


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


def get_builddir(args):
    if args.variant:
        return f"build-{args.arch}-{args.variant}"
    return f"build-{args.arch}"


def do_linux_make(args, cmd, build_dir):
    if args.silent:
        cmd.append("-s")

    if args.make_cmd:
        cmd.append(args.make_cmd)
    else:
        compile_cmd_fn = os.path.join(build_dir, "compile_commands.json")
        if not os.path.exists(compile_cmd_fn):
            cmd.append("all")
            cmd.append("compile_commands.json")

    os.execvp(cmd[0], cmd)


def compile_linux_x86(args, **kwargs):
    tot = os.getcwd()
    build_dir = get_builddir(args)
    cc = " ".join(get_linux_compiler(args, build_dir))
    cmd = ["make", "-C", os.getcwd(), f"O={build_dir}", f"CC={cc}", get_j()]
    do_linux_make(args, cmd, build_dir)


def clang_linux(args, arch, prefix, **kwargs):
    build_dir = get_builddir(args)
    cmd = [
        "make", "-C",
        os.getcwd(), f"O={build_dir}", f"ARCH={arch}", "LD=ld.lld-15",
        f"CC=clang-15 --target={prefix}",
        get_j()
    ]
    do_linux_make(args, cmd, build_dir)


def tuxmake_linux(args, image, arch, prefix, **kwargs):
    tot = os.getcwd()
    build_dir = os.path.join(tot, get_builddir(args))
    cmd = [
        "docker", "run", "-u", f"{os.getuid()}:{os.getgid()}", "-ti", "--rm",
        "-v", f"{tot}:{tot}", image
    ]
    cmd.extend([
        "make", "-C", tot, f"O={os.path.basename(build_dir)}", f"ARCH={arch}",
        f"CROSS_COMPILE={prefix}-",
        get_j()
    ])

    if args.silent:
        cmd.append("-s")

    os.execvp(cmd[0], cmd)


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
                        choices=set(arches.keys()),
                        default="x86")
    parser.add_argument("--tuxmake",
                        action="store_true",
                        help="Use tuxmake docker containers",
                        default=False)
    parser.add_argument("--menuconfig",
                        dest="make_cmd",
                        action="store_const",
                        const="menuconfig",
                        help="Use tuxmake docker containers",
                        default=None)
    parser.add_argument("-v",
                        dest="variant",
                        action="store",
                        help="Suffix to add to the build directory",
                        default="")


def cmd_b(args):
    """Compile the current source tree properly"""
    with in_directory(git_root()):
        if is_linux():
            arch = arches[args.arch]
            if arch.get("image") is None:
                compile_linux_x86(args)
            elif args.tuxmake:
                tuxmake_linux(args, **arch)
            else:
                clang_linux(args, **arch)
        elif is_rdma_core():
            compile_rdma_core()
        else:
            raise ValueError("Don't recongize this tree")
