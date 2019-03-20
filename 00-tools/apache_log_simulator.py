#!/usr/bin/env python3
from __future__ import print_function

try:
    from itertools import imap as map
except ImportError:
    pass

import sys
from argparse import ArgumentParser
from contextlib import contextmanager
from os.path import isfile, getsize
from random import randint
import itertools
import time


@contextmanager
def protect_position(f):
    try:
        l = f.tell()
        yield f
    finally:
        if not f.closed:
            f.seek(l)


def get_arg_parser():
    parser = ArgumentParser(
        'log_simulator',
        description='simulate log outputting'
    )
    interval = parser.add_mutually_exclusive_group()
    interval.add_argument(
        '--random-interval', nargs=2,
        metavar=('min', 'max'),
        help='range of randomized interval (second), default: 1s~3s',
        type=int,
        default=(1, 3)
    )
    interval.add_argument(
        '--interval', nargs=1,
        help='fixed interval (second)'
    )
    seek = parser.add_mutually_exclusive_group()
    seek.add_argument(
        '--continue', action='store_true', default=True, dest='continue_',
        help='start outputting from next line of last executing. '
             'Note: log_simulator use line number based offset so if LOG_PIPE '
             'or content in source log changes between executions this option '
             'may not work as supposed'
    )
    seek.add_argument(
        '--restart', action='store_true', default=False,
        help='start outputting from first line of first source file, may cause '
             'duplication in the destination files'
    )
    seek.add_argument(
        '--truncate', action='store_true', default=False,
        help='start outputting from first line of first source file, and !!REMOVE!! '
             'all content in the destination files before starting'
    )
    parser.add_argument(
        'log_pipe', nargs='+',
        help='log source files and destination file joined with pipe ("|"), '
             'e.g. "access_log_1|access_log_2|mock_log.log" concatenate two access_log '
             'files into one output file. Use "-" as output will send logs to STDOUT',
        type=log_pipe,
    )
    return parser


def print_error(*args, **kwargs):
    kwargs['file'] = sys.stderr
    print(*args, **kwargs)


def can_open_file(filename, mode):
    if 'r' in mode and not isfile(filename):
        return False
    try:
        with open(filename, mode):
            return True
    except IOError:
        return False


def log_pipe(pipe):
    pipe = tuple(p.strip() for p in pipe.split('|'))
    if len(pipe) < 2:
        print_error('invalid pipe format, at least one source file and exactly one destination file required')
        raise ValueError()
    sources, dest = pipe[:-1], pipe[-1]
    for s in sources:
        if not can_open_file(s, 'rb'):
            print_error('source file "%s" is not readable' % (s,))
            raise ValueError()
    if dest != '-' and not can_open_file(dest, 'ab'):
        print_error('cannot create or write destination file "%s"' % (dest,))
    return (sources, dest)


def line_count(f):
    i = -1
    with protect_position(f) as f:
        for i, l in enumerate(f):
            pass
    return i + 1


def move_to_line(filenames, line):
    for idx, filename in enumerate(filenames):
        f = open(filename, 'r')
        try:
            for i, l in enumerate(f):
                if i + 1 == line:
                    return f, l, filenames[idx + 1:]
            else:
                f.close()
        except:
            f.close()
            raise
    raise ValueError('line number exceeds all file content')


def output(args, pipe):
    sources, destination = pipe
    truncate = args.truncate
    restart = args.restart
    continue_ = args.continue_
    if destination == '-':
        restart = True

    if truncate or restart:
        o = open(destination, 'w') if destination != '-' else sys.stdout
        i = open(sources[0], 'r')
        sources = sources[1:]
        if truncate:
            o.truncate(0)
    elif continue_:
        i, sources = align_offset(destination, sources)
        o = open(destination, 'a')
    else:
        raise RuntimeError('at least one open mode shall be specified')
    if args.interval is not None:
        interval = lambda: args.interval
    else:
        interval = lambda: randint(*args.random_interval)

    try:
        while True:
            for line in i:
                o.write(line)
                o.flush()
                time.sleep(interval())
            i.close()
            if not sources:
                break
            else:
                i = open(sources.pop(), 'r')
    finally:
        o.close()
        i.close()


def align_offset(destination, sources):
    if getsize(destination) == 0:
        return open(sources[0], 'r'), sources[1:]

    with open(destination, 'r') as o:
        i, l, sources = move_to_line(sources, line_count(o))
        # compatibility for Windows
        o.seek(getsize(destination) - len(l) - 1, 0)
        ol = o.read(len(l))
        if ol != l:
            print_error(
                'last output line does not match the offset in sources'
            )
            print_error(
                'output:\n>>> %s\nsource:\n>>> %s\n' % (
                    ol, l
                )
            )
            i.close()
            raise Exception('pipe content changed')
    return i, sources


def main():
    parser = get_arg_parser()
    args = parser.parse_args()
    output(args, args.log_pipe[0])


if __name__ == '__main__':
    main()
