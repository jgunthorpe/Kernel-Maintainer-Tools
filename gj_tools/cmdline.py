import argparse
import importlib
import inspect
import os
import sys
import gj_tools


def load_all_commands(name, top_module):
    """Load the modules containing the command implementation and then extract all
    the cmd_* functions from them."""
    module = importlib.import_module(top_module.__name__ + "." + name)
    for k in dir(module):
        fn = getattr(module, k)
        argsfn = getattr(module, "args_" + k[4:], None)
        if (argsfn is None or not k.startswith("cmd_")
                or not inspect.isfunction(fn)):
            continue
        yield (k, fn, argsfn)


def main(cmd_modules, top_module):
    parser = argparse.ArgumentParser(description='Git helper commands')
    subparsers = parser.add_subparsers(title="Sub Commands", dest="command")
    subparsers.required = True

    commands = []
    for I in cmd_modules:
        commands.extend(load_all_commands(I, top_module))
    commands.sort()

    # build sub parsers for all the loaded commands
    for k, fn, argsfn in commands:
        sparser = subparsers.add_parser(k[4:].replace('_', '-'),
                                        help=fn.__doc__)
        sparser.required = True
        argsfn(sparser)
        sparser.set_defaults(func=fn)

    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    # argparse will set 'func' to the cmd_* that executes this command
    args = parser.parse_args()
    args.func(args)
