from __future__ import print_function
import os
import sys
import collections

from . import config


class rdma(object):
    """A mini no-module compile covering the entire RDMA subsystem and its
       users"""
    enable = {
        # To get DCA, it is weird
        "INTEL_IOATDMA",
        # For hfi1
        "FAULT_INJECTION_DEBUG_FS",
        # For mlx5
        "MLX5_ESWITCH",
        # For xprtrdma
        "NFS_FS",
        "NFS_V4_1",
        "SUNRPC_BACKCHANNEL",
        "SMC",
        "SMC_DIAG",
        "BLK_DEV_RNBD_CLIENT",
        "BLK_DEV_RNBD_SERVER",
        # SMB RDMA
        "CIFS_SMB_DIRECT",
    }
    force = {}
    block = {
        "ISM",
    }

    def select(self, kconf, sym_in_file):
        # Enable all symbols in drivers/infiniband
        enable_syms = set()
        for fn, syms in sorted(sym_in_file.items()):
            if (fn.startswith("drivers/infiniband/")
                    or fn.startswith("drivers/net/ethernet/mellanox/mlx4/")
                    or fn.startswith("drivers/net/ethernet/mellanox/mlx5/")):
                enable_syms.update(syms)

        # And any other related symbols
        for sym in kconf.syms.values():
            if "INFINIBAND" in sym.name or "RDMA" in sym.name:
                enable_syms.add(sym)
        return enable_syms


class vfio(object):
    """A mini no-module compile covering the entire VFIO subsystem and its
       users"""
    enable = {
        "DRM_I915_GVT_KVMGT",
        "OMAP_IOMMU",
        "ROCKCHIP_IOMMU",
        "SUN50I_IOMMU",
        "EXYNOS_IOMMU",
        "IPMMU_VMSA",
        "APPLE_DART",
        "ARM_SMMU",
        "MTK_IOMMU",
        "QCOM_IOMMU",
        "VIRTIO_PCI",
        "VIRTIO_IOMMU",
        "SPRD_IOMMU",
    }
    force = {
        "RANDSTRUCT_FULL": "n",
        "RANDSTRUCT_NONE": "y",
    }
    block = {
        # needs s390 arch headers
        "VFIO_PCI_ZDEV_KVM",
        "VFIO_AP",
        "VFIO_CCW",

        # needs power pcc arch headers
        "VFIO_SPAPR_EEH",
        "VFIO_IOMMU_SPAPR_TCE",
        "VFIO_PCI_NVLINK2",

        "ARM_AMBA",
        "VFIO_CDX",

        "INTEL_IOMMU_BROKEN_GFX_WA",
        "IOMMUFD_VFIO_CONTAINER",
        "PREEMPT_RT",

        "GENERIC_ATOMIC64",
    }

    def select(self, kconf, sym_in_file):
        # Enable all symbols in drivers/vfio
        enable_syms = set()
        for fn, syms in sorted(sym_in_file.items()):
            if (fn.startswith("drivers/vfio/")
                    or fn.startswith("drivers/iommu/intel/")
                    or fn.startswith("drivers/iommu/amd/")
                    or fn.startswith("drivers/iommu/iommufd/")):
                for sym in syms:
                    if sym.name not in self.block:
                        enable_syms.add(sym)

        # And any other related symbols
        for sym in kconf.syms.values():
            if "_VFIO_" in sym.name:
                if sym.name not in self.block:
                    enable_syms.add(sym)
        return enable_syms


class mkt(object):
    """A mini module compile that boots in mkt"""
    enable = {
        "64BIT",
        "BINFMT_ELF",
        "BINFMT_SCRIPT",
        "COREDUMP",
        "MCORE2",
        "MODULES",
        "MODULE_UNLOAD",
        "PACKET",
        "SMP",
        "SYSVIPC",
        "UNIX",
        "ELF_CORE",
        "UTS_NS",
        "IPC_NS",
        "PID_NS",
        "PROC_SYSCTL",
        "UNIX98_PTYS",

        # From systemd README
        "DEVTMPFS",
        "CGROUPS",
        "INOTIFY_USER",
        "SIGNALFD",
        "TIMERFD",
        "EPOLL",
        "NET",
        "SYSFS",
        "PROC_FS",
        "FHANDLE",
        "CRYPTO_USER_API_HASH",
        "CRYPTO_HMAC",
        "CRYPTO_SHA256",
        "DMIID",
        "BLK_DEV_BSG",
        "NET_NS",
        "USER_NS",
        "IPV6",
        "AUTOFS4_FS",
        "TMPFS_XATTR",
        "TMPFS_POSIX_ACL",
        "SECCOMP",
        "SECCOMP_FILTER",
        "CHECKPOINT_RESTORE",
        "CGROUP_SCHED",
        "FAIR_GROUP_SCHED",
        "CFS_BANDWIDTH",
        "CGROUP_BPF",

        # For KVM
        "9P_FS",
        "ACPI",
        "CPU_IDLE",
        "DEVTMPFS_MOUNT",
        "HW_RANDOM_INTEL",
        "KVM_GUEST",
        "PARAVIRT",
        "PCI",
        "PCI_IOV",
        "PCI_MMCONFIG",
        "PCI_MSI",
        "SERIAL_8250_CONSOLE",
        "SERIAL_EARLYCON",
        "EARLY_PRINTK",
        "INTEL_IOMMU",
        "INTEL_IOMMU_SVM",
        "INTEL_IOMMU_DEFAULT_ON",
        "INTEL_IOMMU_SCALABLE_MODE_DEFAULT_ON",
        "IRQ_REMAP",

        "TRANSPARENT_HUGEPAGE",
        "TRANSPARENT_HUGEPAGE_ALWAYS",
        "HUGETLBFS",
        "VFIO_PCI",

        # For debugging
        "DEBUG_ATOMIC_SLEEP",
        "DEBUG_BUGVERBOSE",
        "DEBUG_KERNEL",
        "DEBUG_LIST",
        "DETECT_HUNG_TASK",
        "HARDLOCKUP_DETECTOR",
        "HAVE_RELIABLE_STACKTRACE",
        "KASAN",
        "MAGIC_SYSRQ_SERIAL",
        "PERF_EVENTS",
        "PRINTK_TIME",
        "PROVE_LOCKING",
        "PROVE_RCU",
        "SOFTLOCKUP_DETECTOR",
        "STACKPROTECTOR_STRONG",
        "STACK_VALIDATION",
        "UBSAN",
        "UBSAN_SANITIZE_ALL",
        "UNWINDER_FRAME_POINTER",
        "WQ_WATCHDOG",
    }

    force = {
        # From systemd
        #"SYSFS_DEPRECATED": "n",
        "UEVENT_HELPER_PATH": "",
        "FW_LOADER_USER_HELPER": "n",
        "RT_GROUP_SCHED": "n",
        # For RDMA
        "INFINIBAND": "m",
        "MLX5_CORE": "m",
        "MLX5_INFINIBAND": "m",
        "MLX5_CORE_EN": "y",

        "MEMORY_ISOLATION": "y",
        "COMPACTION": "y",
    #        "VFIO_MDEV": "m",
    #        "SAMPLE_VFIO_MDEV_MTTY": "m",
    #        "SAMPLE_VFIO_MDEV_MDPY": "m",
    #        "SAMPLE_VFIO_MDEV_MDPY_FB": "m",
    #        "SAMPLE_VFIO_MDEV_MBOCHS": "m",

        "RANDSTRUCT_FULL": "n",
        "RANDSTRUCT_NONE": "y",
    }

    block = {
        "CAIF",
        "DRM",
        "IOMMU",
        "VIRTIO_DMA_SHARED_BUFFER",
        "UID16",
        "ARCH_NO_PREEMPT",
        "VIRTIO_HARDEN_NOTIFICATION",
    }
    def select(self, kconf, sym_in_file):
        enable_syms = set()

        for fn, syms in sorted(sym_in_file.items()):
            if (fn.startswith("drivers/infiniband/Kconfig")
                    or fn.startswith("drivers/infiniband/ulp/ipoib/")
                    or fn.startswith("drivers/infiniband/sw/rxe/")
                    or fn.startswith("drivers/infiniband/sw/siw/")
                    or fn.startswith("drivers/infiniband/hw/mlx5/")):
                enable_syms.update(syms)

        # Enable all of the EXPERT menu block symbols. DEBUG_KERNEL needs
        # expert
        l = kconf.syms["EXPERT"].nodes[0].list
        while l is not None:
            if l.item._str_default() == "y" and l.item.name not in self.block:
                enable_syms.add(l.item)
            l = l.next

        for sym in kconf.syms.values():
            if "VIRTIO" in sym.name and not sym.name.startswith("ARCH_"):
                for blocked in self.block:
                    if blocked in sym.name:
                        break
                else:
                    enable_syms.add(sym)
        return enable_syms

class syzkaller(mkt):
    enable = mkt.enable | {
        "KCOV",
        "KCOV_INSTRUMENT_ALL",
        "KCOV_ENABLE_COMPARISONS",
        "DEBUG_FS",
        "DEBUG_KMEMLEAK",
        "DEBUG_INFO",
        "DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT",
        "KALLSYMS",
        "KALLSYMS_ALL",
        "NAMESPACES",
        "UTS_NS",
        "IPC_NS",
        "PID_NS",
        "NET_NS",
        "CGROUP_PIDS",
        "MEMCG",
        "USER_NS",
        "CONFIGFS_FS",
        "SECURITYFS",
        "CMDLINE_BOOL",
        "KASAN",
        "KASAN_INLINE",
        "FAULT_INJECTION",
        "FAULT_INJECTION_DEBUG_FS",
        "FAULT_INJECTION_USERCOPY",
        "FAILSLAB",
        "FAIL_PAGE_ALLOC",
        "FAIL_MAKE_REQUEST",
        "FAIL_IO_TIMEOUT",
        "FAIL_FUTEX",
        "LOCKDEP",
        "PROVE_LOCKING",
        "DEBUG_ATOMIC_SLEEP",
        "PROVE_RCU",
        "DEBUG_VM",
        "FORTIFY_SOURCE",
        "HARDENED_USERCOPY",
        "LOCKUP_DETECTOR",
        "SOFTLOCKUP_DETECTOR",
        "HARDLOCKUP_DETECTOR",
        "BOOTPARAM_HARDLOCKUP_PANIC",
        "DETECT_HUNG_TASK",
        "WQ_WATCHDOG",

        # From kernel/configs/kvm_guest.config
        "NET",
        "NET_CORE",
        "NETDEVICES",
        "BLOCK",
        "BLK_DEV",
        "NETWORK_FILESYSTEMS",
        "INET",
        "TTY",
        "SERIAL_8250",
        "SERIAL_8250_CONSOLE",
        "IP_PNP",
        "IP_PNP_DHCP",
        "BINFMT_ELF",
        "PCI",
        "PCI_MSI",
        "DEBUG_KERNEL",
        "VIRTUALIZATION",
        "HYPERVISOR_GUEST",
        "PARAVIRT",
        "KVM_GUEST",
        "VIRTIO",
        "VIRTIO_MENU",
        "VIRTIO_PCI",
        "VIRTIO_BLK",
        "VIRTIO_CONSOLE",
        "VIRTIO_NET",
        "9P_FS",
        "NET_9P",
        "NET_9P_VIRTIO",
        "SCSI_LOWLEVEL",
        "SCSI_VIRTIO",
        "VIRTIO_INPUT",
        "EXT4_FS",
        "ATA_PIIX",
        "E1000",
        "BLK_DEV_SD",

        "IOMMUFD",
        "IOMMUFD_TEST",
    }
    force = mkt.force  | {
        "CMDLINE": "net.ifnames=0",
    }
#CONFIG_RANDOMIZE_BASE

class hmm(object):
    enable = {
        "64BIT",
        "MTRR",
        "X86_PAT",
        "HSA_AMD",
        "DRM_RADEON_USERPTR",
        "INFINIBAND_ON_DEMAND_PAGING",
        "MLX5_INFINIBAND",
        "SGI_GRU",
        "DRM_NOUVEAU_SVM",
        "DRM_AMDGPU_USERPTR",
        "NVDIMM_TEST_BUILD",
        "ZONE_DEVICE",
    }
    force = {}

    def select(self, kconf, sym_in_file):
        enable_syms = set()
        for sym in kconf.syms.values():
            if "HFI1" in sym.name:
                enable_syms.add(sym)
        return enable_syms


def args_kconfig_gen(parser):
    parser.add_argument("mode",
                        action="store",
                        help="Type of configuration content to generate for",
                        choices={"mkt", "rdma", "hmm", "vfio", "syzkaller"})


def set_x86():
    os.environ["ARCH"] = "x86"
    os.environ["SRCARCH"] = "x86"
    os.environ["CC"] = config.compiler.split()[-1]
    os.environ["CLANG_FLAGS"] = "-fintegrated-as"
    os.environ["HOSTCXX"] = os.environ["CC"].replace("clang", "clang++")
    os.environ["LD"] = "ld"

def cmd_kconfig_gen(args):
    """Generate a kconfig for the given ruleset"""
    sys.path.append(
        os.path.normpath(
            os.path.join(os.path.dirname(__file__),
                         "../../../tools/Kconfiglib")))
    import kconfiglib

    os.environ["srctree"] = "."
    set_x86()

    kconf = kconfiglib.Kconfig(warn_to_stderr=False)

    sym_in_file = collections.defaultdict(set)
    for sym in kconf.syms.values():
        # 'allnoconfig'
        sym.set_value(2 if sym.is_allnoconfig_y else 0)

        for node in sym.nodes:
            sym_in_file[node.filename].add(sym)

    if args.mode == "rdma":
        mode = rdma()
    elif args.mode == "mkt":
        mode = mkt()
    elif args.mode == "hmm":
        mode = hmm()
    elif args.mode == "vfio":
        mode = vfio()
    elif args.mode == "syzkaller":
        mode = syzkaller()

    done_syms = set(kconf.const_syms.values())
    # These cannot be changed, just ingore them
    for name, sym in kconf.syms.items():
        if (name.startswith("CC_HAS_") or name.startswith("HAVE_ARCH_") or
            name.endswith("_LLVM") or name.endswith("_CLANG")):
            done_syms.add(sym)

    enable_syms = mode.select(kconf, sym_in_file)
    enable_syms.update(kconf.syms[I] for I in mode.enable)
    enable_syms.update(kconf.syms[I] for I in mode.force.keys())
    orig_enable = set(enable_syms)
    for _ in range(0, 10):
        for I in sorted(enable_syms - done_syms, key=lambda x: x.name):
            if I.type not in kconfiglib._BOOL_TRISTATE:
                if I.name in mode.force:
                    I.set_value(mode.force[I.name])
                done_syms.add(I)
                continue

            val = mode.force.get(I.name, "y")
            if I.str_value == val and I not in orig_enable:
                done_syms.add(I)
                continue

            I.set_value(val)
            if (I.str_value == val or (val == "y" and I.str_value == "y")
                    or (val == "y" and I.str_value == "m")):
                done_syms.add(I)
            else:
                if I.name == "KASAN":
                    continue
                # If a value could not be enabled naively enable all the
                # dependencies.
                for J in kconfiglib.expr_items(I.direct_dep):
                    if J.name is None:
                        done_syms.add(J)
                    if J.name in mode.block or J.name == "y":
                        continue
                    enable_syms.add(J)
        if not (enable_syms - done_syms):
            break
    else:
        print("Could not set deps")
        for I in sorted(enable_syms - done_syms, key=lambda x: x.name):
            print("  ", I.name, I.str_value,
                  [node.filename for node in I.nodes])
            print("  ", I)
            if I.choice:
                print(I.choice)
        sys.exit(100)

    # Check that all requested settings were realized
    for I in sorted(orig_enable, key=lambda x: x.name):
        val = mode.force.get(I.name, "y")
        if (I.str_value == val or (val == "y" and I.str_value == "y")
                or (val == "y" and I.str_value == "m")):
            continue
        print("  ", I.name, I.str_value, [node.filename for node in I.nodes])

    kconf.write_config(".config")
    print("Wrote .config")
