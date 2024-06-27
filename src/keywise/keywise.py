#!/usr/bin/python

import sys
import json
import subprocess
import argparse

"""
Example:

Get a bunch of jsonlines, extract the values under 'text', pass them into the command in square brackets, and store the result in a new key 'nwords', keeping the original text: 

$ cat tests/test.jsonl | keywise [wc -w] text nwords --keep

Hypothetical example, assuming one has sentencize.py for splitting a text into sentences:
 
Get a bunch of jsonlines, extract the values under 'text', split each text into sentences, output a new json line per sentence, each with 'id' field derived from the original 'id' field:

$ cat tests/test.jsonl | keywise [python sentencize.py] id,text sentence | less

"""

def main():

    args = parse_args()
    do_work(**args.__dict__)


def parse_args():


    parser = argparse.ArgumentParser(description="Keywise processing a .jsonl file! Example:  $ cat test.jsonl | keywise [wc] id,text tokens --keep")

    parser.add_argument('key', type=str, help='The key; can be two comma-separated values like id,text. First will be used for identifiers.')
    # parser.add_argument('program', type=str, help='The program (required string)')
    parser.add_argument('result_key', type=str, nargs='?', help='The new key; if not given, old key will be used for new values')
    parser.add_argument('--keep', action='store_true', help='Whether to keep the original key (only if new key is provided)')

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

    args = parser.parse_args(args[1:])
    if ',' in args.key:
        args.id, args.key = args.key.split(',')
    else:
        args.id = None

    args.command = command

    return args


def do_work(key, result_key, keep, id, command):

    for line in sys.stdin:
        dict = json.loads(line)
        value = dict[key]
        if not keep:
            del dict[key]
        old_id = dict.get(id, None) if id else None

        if command:
            process = subprocess.run(command, input=value, text=True, capture_output=True)
            for n, outline in enumerate(process.stdout.splitlines()):
                dict[result_key] = outline
                if id:
                    dict[id] = f'{old_id}.{n}' if old_id else f'{n}'
                print(json.dumps(dict))
        else:
            print(value)

