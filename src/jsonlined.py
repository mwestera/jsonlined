#!/usr/bin/python
import csv
import sys
import json
import subprocess
import argparse
import os
import io


"""
Author: Matthijs Westera


Examples:

Get a bunch of jsonlines, extract the values under 'text', pass them into the command in square brackets, and store the result in a new key 'nwords', keeping the original text: 

$ cat tests/test.jsonl | jsonlined [wc -w] text nwords --keep

Hypothetical example, assuming one has sentencize.py for splitting a text into sentences:
 
Get a bunch of jsonlines, extract the values under 'text', split each text into sentences, output a new json line per sentence, each with 'id' field derived from the original 'id' field:

$ cat tests/test.jsonl | jsonlined [python sentencize.py] text sentence --id id 

Another example, for computing text embeddings:

$ cat tests/test.jsonl | jsonpiped [python embed.py] text embedding

Here jsonpiped is used, because embed.py requires considerable setup (loading model) -- prerequisite is that operates line-swise (not waiting for EOF like wc). 

If subprocess outputs json format, this will be interpreted as such; otherwise literal string.

In case the subprocess can output multiple new lines per original input line, make sure the bunches are separated by an empty line (double newline)...

"""


# TODO: With multiple input keys,


def build_argparser():

    parser = argparse.ArgumentParser(description="Processing a specific keyed value of a .jsonl file, line by line. Example to count words using wc:  $ cat test.jsonl | jsonlined [wc -w] id,text tokens --keep")

    parser.add_argument('keys', type=str, help='The key, in the input jsonliens, or multiple keys separated by commas, from which to take values for processing.')
    parser.add_argument('result_key', type=str, nargs='?', help='The new key; if not given, old key (or first one, if multiple provided) will be used for new values')
    parser.add_argument('--keep', action='store_true', help='Whether to keep the original key (only if new key is provided.')
    parser.add_argument('--id', type=str, nargs='?', help='Which key (if any) to use for ids. Only relevant if input line may map to multiple output lines.')

    def parse_with_subprocess():
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
        args = argparse.ArgumentParser.parse_args(parser, args[1:]) # TODO pass kwargs
        args.command = command

        args.keys = args.keys.split(',')
        args.result_key = args.result_key or args.keys[0]

        return args

    parser.parse_args = parse_with_subprocess       # hmmmmm :D

    return parser


def extract(keys):

    for line in sys.stdin:
        if not line.strip():
            print()
            continue

        dict = json.loads(line)
        values = [dict[key] for key in keys]
        print(values_to_csv_if_multi(values))


def jsonlined():

    parser = build_argparser()
    args = parser.parse_args()

    if not args.command:
        extract(args.keys)
        return

    for line in sys.stdin:
        if not line.strip():
            dict[args.result_key] = None
            print(json.dumps(dict))
            continue

        dict = json.loads(line)

        values = [dict[key] for key in args.keys]
        value = values_to_csv_if_multi(values)

        if not args.keep:
            for key in args.keys:
                del dict[key]
        old_id = dict.get(args.id, None) if args.id else None

        command_filled = []
        for arg in args.command:
            if arg.startswith('#'):
                command_filled.append(dict[arg.lstrip('#')])
            else:
                command_filled.append(arg)

        process = subprocess.run(command_filled, input=value, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, shell=False)
        for n, outline in enumerate(process.stdout.splitlines()):
            try:
                result = json.loads(outline)
            except json.JSONDecodeError:
                result = outline
            dict[args.result_key] = result
            if args.id:
                dict[args.id] = f'{old_id}.{n}' if old_id else f'{n}'
            print(json.dumps(dict))


def jsonpiped():

    parser = build_argparser()
    parser.add_argument('--onetomany', action='store_true', help='Whether the subprocess can yield multiple outputs for a single input -- if so, the blocks must be separated by empty lines (doubel newlines).')

    args = parser.parse_args()

    if not args.command:
        extract(args.keys)
        return

    os.environ['PYTHONUNBUFFERED'] = '1'

    process = subprocess.Popen(args.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, shell=False)

    for line in sys.stdin:
        if not line.strip():
            dict[args.result_key] = None
            print(json.dumps(dict))
            continue

        dict = json.loads(line)

        values = [dict[key] for key in args.keys]
        value = values_to_csv_if_multi(values)

        if not args.keep:
            for key in args.keys:
                del dict[key]

        old_id = dict.get(args.id, None) if args.id else None

        process.stdin.write(value + '\n')
        process.stdin.flush()

        if args.onetomany:
            result_strings = process.stdout
        else:
            result_strings = [process.stdout.readline()]

        for n, result_str in enumerate(result_strings):
            result_str = result_str.rstrip('\n')
            if not result_str:
                break
            try:
                result = json.loads(result_str)
            except json.JSONDecodeError:
                result = result_str
            dict[args.result_key] = result
            if args.id:
                dict[args.id] = f'{old_id}.{n}' if old_id else f'{n}'
            print(json.dumps(dict))


    process.stdin.close()
    process.wait()


def make_csv_writer():

    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer)

    def values_to_csv_if_multi(values):


        if len(values) == 1:
            return values[0]

        csv_writer.writerow(values)
        value = csv_buffer.getvalue().strip()

        csv_buffer.seek(0)
        csv_buffer.truncate(0)

        return value

    return values_to_csv_if_multi


values_to_csv_if_multi = make_csv_writer()