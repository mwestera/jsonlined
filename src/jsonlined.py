#!/usr/bin/python

import sys
import json
import subprocess
import argparse
import os


"""
Author: Matthijs Westera


Examples:

Get a bunch of jsonlines, extract the values under 'text', pass them into the command in square brackets, and store the result in a new key 'nwords', keeping the original text: 

$ cat tests/test.jsonl | jsonlined [wc -w] text nwords --keep

Hypothetical example, assuming one has sentencize.py for splitting a text into sentences:
 
Get a bunch of jsonlines, extract the values under 'text', split each text into sentences, output a new json line per sentence, each with 'id' field derived from the original 'id' field:

$ cat tests/test.jsonl | jsonlined [python sentencize.py] id,text sentence

Another example, for computing text embeddings:

$ cat tests/test.jsonl | jsonpiped [python embed.py] id,text embedding

Here jsonpiped is used, because embed.py requires considerable setup (loading model) -- prerequisite is that operates line-swise (not waiting for EOF like wc). 

"""


# TODO: what if subprocess output is not a plain string but to be interpreted as e.g. a list of floats?

def main():

    args = parse_args(include_piped_arg=True)

    if not args.command:
        extract(args.key)

    elif args.piped:
        del args.piped
        _jsonpiped(**args.__dict__)

    else:
        del args.piped
        _jsonlined(**args.__dict__)


def jsonlined():

    args = parse_args()

    if not args.command:
        extract(args.key)
    else:
        _jsonlined(**args.__dict__)


def jsonpiped():
    args = parse_args()
    if not args.command:
        extract(args.key)
    else:
        _jsonpiped(**args.__dict__)


def parse_args(include_piped_arg=False):

    parser = argparse.ArgumentParser(description="Processing a specific keyed value of a .jsonl file, line by line. Example to count words using wc:  $ cat test.jsonl | jsonlined [wc -w] id,text tokens --keep")

    parser.add_argument('key', type=str, help='The key; can be two comma-separated values like id,text. First will be used for identifiers.')
    # parser.add_argument('program', type=str, help='The program (required string)')
    parser.add_argument('result_key', type=str, nargs='?', help='The new key; if not given, old key will be used for new values')
    parser.add_argument('--keep', action='store_true', help='Whether to keep the original key (only if new key is provided)')
    if include_piped_arg:
        parser.add_argument('--piped', action='store_true', help='Whether to pipe into the nested process; alternatively runs a new process for each line.')

    args = []

    for a in sys.argv:
        if '[' not in a and ']' not in a:
            args.append(a)
            continue
        if a in ['[', ']']:
            args.append(a)
            continue
        if a.startswith('['):
            args.append('[')
            a = a[1:]
        if a.endswith(']'):
            args.append(a[:-1])
            args.append(']')
        else:
            args.append(a)

    if '[' in args:
        command = args[args.index('[') + 1:args.index(']')]
        args = args[:args.index('[')] + args[args.index(']')+1:]
    else:
        command = None

    args = parser.parse_args(args[1:])
    if ',' in args.key:
        args.id, args.key = args.key.split(',')
    else:
        args.id = None

    args.command = command

    return args


def extract(key):
    for line in sys.stdin:
        if not line.strip():
            continue

        dict = json.loads(line)
        value = dict[key]
        print(value)


def _jsonlined(key, result_key, keep, id, command):

    for line in sys.stdin:
        if not line.strip():
            continue

        dict = json.loads(line)
        value = dict[key]
        if not keep:
            del dict[key]
        old_id = dict.get(id, None) if id else None

        process = subprocess.run(command, input=value, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, shell=True)
        for n, outline in enumerate(process.stdout.splitlines()):
            dict[result_key] = outline
            if id:
                dict[id] = f'{old_id}.{n}' if old_id else f'{n}'
            print(json.dumps(dict))


def _jsonpiped(key, result_key, keep, id, command):
    os.environ['PYTHONUNBUFFERED'] = '1'
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, shell=True)

    for line in sys.stdin:
        if not line.strip():
            dict[result_key] = None
            print(json.dumps(dict))
            continue

        dict = json.loads(line)
        value = dict[key]

        process.stdin.write(value + '\n')
        process.stdin.flush()

        if not keep:
            del dict[key]
        old_id = dict.get(id, None) if id else None

        n = 0

        result = process.stdout.readline().rstrip()
        dict[result_key] = result
        if id:
            dict[id] = f'{old_id}.{n}' if old_id else f'{n}'
        print(json.dumps(dict))
        n += 1


    process.stdin.close()
    process.wait()


if __name__ == '__main__':
    main()