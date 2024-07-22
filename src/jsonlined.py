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

# TODO: Refactor jsonlined and jsonpiped, considerable overlap
# TODO: Allow filtering directly on subprocss stdout?  jsonlined [lastchar]=? question


def build_argparser():

    parser = argparse.ArgumentParser(description="Processing a specific keyed value of a .jsonl file, line by line. Example to count words using wc:  $ cat test.jsonl | jsonlined [wc -w] id,text tokens --keep")

    parser.add_argument('keys', type=str, help='The key, in the input jsonliens, or multiple keys separated by commas, from which to take values for processing, or key=value pairs, to filter.', default=None)
    parser.add_argument('result_key', type=str, nargs='?', help='The new key; if not given, old key (or first one, if multiple provided) will be used for new values', default=None)
    parser.add_argument('--keep', action='store_true', help='Whether to keep the original key (only if new key is provided.')
    parser.add_argument('--id', type=str, nargs='?', help='Which key (if any) to use for ids. Only relevant if input line may map to multiple output lines.')

    def parse_with_subprocess(**kwargs):
        args = []
        command = []
        command_filter = None

        is_in_command = False

        for a in sys.argv:
            if not is_in_command and a.startswith('['):
                if a.endswith(']'):
                    command.append(a[1:-1])
                    continue
                elif ']=' in a:
                    b, command_filter = a[1:].split(']=')
                    command.append(b)
                    continue
                elif len(a) > 1:
                    command.append(a[1:])
                is_in_command = True
                continue

            elif is_in_command and a.endswith(']') or ']=' in a:

                if ']=' in a:
                    b, command_filter = a.split(']=')
                    if b:
                        command.append(b)
                elif len(a) > 1:
                    command.append(a[:-1])
                is_in_command = False
                continue

            if is_in_command:
                command.append(a)
            else:
                args.append(a)

        args = argparse.ArgumentParser.parse_args(parser, args[1:], **kwargs)

        keys_raw = args.keys.split(',') if args.keys else []
        args.filter = dict(a.split('=') for a in keys_raw if '=' in a)
        args.keys = [k for k in keys_raw if '=' not in k]
        args.command = command
        if command_filter:
            try:
                args.command_filter = json.loads(command_filter)
            except json.JSONDecodeError:
                args.command_filter = command_filter
            args.keep = True
        else:
            args.command_filter = None
        args.result_key = args.result_key or (args.keys[0] if args.keys and args.command_filter is None else None)

        return args

    parser.parse_args = parse_with_subprocess       # hmmmmm :D

    return parser


def extract(keys, filter=None):

    for line in sys.stdin:
        if not line.strip():
            print()
            continue

        dict = json.loads(line)

        if any((condition := filter.get(key)) is not None and condition != value for key, value in dict.items()):
            continue

        if not keys:
            print(line, end='')
            continue

        values = [dict[key] for key in keys]
        print(values_to_csv_if_multi(values))   # TODO: Probably want to allow jsonl output too?


def jsonlined():

    parser = build_argparser()
    args = parser.parse_args()

    if not args.command:
        extract(args.keys, args.filter)
        return

    for line in sys.stdin:
        if not line.strip():
            print()
            continue

        dict = json.loads(line)

        if any((condition := args.filter.get(key)) is not None and condition != value for key, value in dict.items()):
            continue


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
        for n, result_str in enumerate(process.stdout.splitlines()):
            try:
                result = json.loads(result_str)
            except json.JSONDecodeError:
                result = result_str

            if args.command_filter and result != args.command_filter:
                continue

            if args.result_key:
                dict[args.result_key] = result

            if args.id:
                dict[args.id] = f'{old_id}.{n}' if old_id else f'{n}'

            print(json.dumps(dict))


def jsonpiped():

    parser = build_argparser()
    parser.add_argument('--onetomany', action='store_true', help='Whether the subprocess can yield multiple outputs for a single input -- if so, the blocks must be separated by empty lines (doubel newlines).')

    args = parser.parse_args()

    if not args.command:
        extract(args.keys, args.filter)
        return

    os.environ['PYTHONUNBUFFERED'] = '1'

    process = subprocess.Popen(args.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, shell=False)

    for line in sys.stdin:
        if not line.strip():
            print()
            continue

        dict = json.loads(line)

        if any((condition := args.filter.get(key)) is not None and condition != value for key, value in dict.items()):
            continue

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

            if args.command_filter and result != args.command_filter:
                continue

            if args.result_key:
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