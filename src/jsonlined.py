#!/usr/bin/python
import csv
import sys
import json
import subprocess
import argparse
import os
import io
import logging
import functools

logging.basicConfig(level=logging.INFO)


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

# TODO: Add some logging.
# TODO: Allow extraction from nested json structures.
# TODO: allow non-string and non-dict data types of return values


class RETURN_STATUS:
    pass


def build_argparser():

    parser = argparse.ArgumentParser(description="Processing a specific keyed value of a .jsonl file, line by line. Example to count words using wc:  $ cat test.jsonl | jsonlined [wc -w] id,text tokens --keep")

    parser.add_argument("file", type=argparse.FileType('r'), help=".jsonl file, or - for stdin, or else stdin (file can be omitted without ambiguity, provided ONLY the file and keys args are given before the subprocess [...].)")
    parser.add_argument('keys', type=str, help='The key, in the input jsonliens, or multiple keys separated by commas, from which to take values for processing, or key=value pairs, to filter.', default=None)
    parser.add_argument('result_keys', type=str, nargs='?', help='The new keys; if not given, old keys will be used for storing new values', default=None)
    parser.add_argument('--keep', action='store_true', help='Whether to keep the original key (only if new key is provided.')
    parser.add_argument('--flat', action='store_true', help='If result of subprocess is a json dictionary, will insert these keys (overrides result_key).')
    parser.add_argument('--id', type=str, nargs='?', help='Which key (if any) to use for ids. Only relevant if input line may map to multiple output lines.')
    parser.add_argument('--header', action='store_true', help='If no subprocess, print header prior to extracted values.')

    def parse_with_subprocess(**kwargs):
        args = []
        command = []
        command_filter = None

        is_in_command = False

        for n, a in enumerate(sys.argv):
            # TODO apply shlex.split() to the command in case it's a single "[...]" string.
            # TODO refactor with regex
            if not is_in_command and a.startswith('['):

                if n <= 2:
                    args.insert(1, '-')

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
        args.result_keys = args.result_keys.split(',') if args.result_keys else []
        args.command = command
        if command_filter is not None:
            args.command_filter = try_parse_as_json(command_filter)
            args.keep = True
            if not command_filter:
                args.command_filter = RETURN_STATUS
        else:
            args.command_filter = None
        args.result_keys = args.result_keys or (args.keys if args.keys and args.command_filter is None and not args.flat else None)

        if args.flat and args.result_keys:
            logging.warning('--flat overrides result_keys, ignoring the latter.')
            args.result_keys = None

        return args

    parser.parse_args = parse_with_subprocess       # hmmmmm :D

    return parser


def try_parse_as_json(s):
    try:
        r = json.loads(s)
    except json.JSONDecodeError:
        r = s
    # if not isinstance(r, dict) and not isinstance(r, list):
    #     r = s
    return r


def extract(file, keys, filter=None, header=False):

    if header:
        print(values_to_csv_if_multi(keys))

    for line in file:
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
        print(values_to_csv_if_multi(values))


def jsonlined():

    # TODO Refactor; overlap with jsonpiped

    parser = build_argparser()
    args = parser.parse_args()

    if not args.command:
        extract(args.file, args.keys, args.filter, args.header)
        return

    for line in args.file:
        if not line.strip():
            print()
            continue

        item = json.loads(line)

        if any((condition := args.filter.get(key)) is not None and condition != value for key, value in item.items()):
            continue

        values = [item[key] for key in args.keys]
        value = values_to_csv_if_multi(values)

        command_filled = []
        for arg in args.command:
            if arg.startswith('#'):
                command_filled.append(item[arg.lstrip('#')])
            else:
                command_filled.append(arg)

        process = subprocess.run(command_filled, input=value, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, shell=False)

        if args.command_filter == RETURN_STATUS:
            if process.returncode == 0:
                print(line, end='')
            continue

        if not args.keep:
            for key in args.keys:
                del item[key]
        old_id = item.get(args.id, None) if args.id else None

        for n, result_str in enumerate(process.stdout.splitlines()):
            result = try_parse_as_json(result_str)

            if args.command_filter and result != args.command_filter:
                continue

            if args.result_keys:
                if len(args.result_keys) == 1:
                    item[args.result_keys[0]] = result
                else:
                    result = next(csv.reader([result]))
                    item.update(dict(zip(args.result_keys, result)))

            if args.flat:
                item.update(result)

            if args.id:
                item[args.id] = f'{old_id}.{n}' if old_id else f'{n}'

            print(json.dumps(item))


def jsonpiped():

    parser = build_argparser()
    parser.add_argument('--onetomany', action='store_true', help='Whether the subprocess can yield multiple outputs for a single input -- if so, the blocks must be separated by empty lines (double newlines).')
    # TODO: This argument makes sense for jsonlined, too.

    args = parser.parse_args()

    if not args.command:
        extract(args.file, args.keys, args.filter, args.header)
        return

    if args.command_filter == RETURN_STATUS:
        logging.warning('Filtering subprocess on return status (... [subprocess]= ...) ignored; for this, use jsonlined instead.')
        args.command_filter = None

    os.environ['PYTHONUNBUFFERED'] = '1'

    process = subprocess.Popen(args.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, shell=False)
    os.set_blocking(process.stdout.fileno(), False)  ## https://stackoverflow.com/a/59291466

    inputs_fed = []
    process_outputs = functools.partial(process_outputs_match_to_inputs, inputs_fed, process.stdout, onetomany=args.onetomany, id=args.id, command_filter=args.command_filter, result_keys=args.result_keys, flat=args.flat)

    for line in args.file:

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

        process.stdin.write(value + '\n')
        process.stdin.flush()

        inputs_fed.append(dict)

        for result in process_outputs():
            print(json.dumps(result))


    os.set_blocking(process.stdout.fileno(), True)
    process.stdin.close()
    while True:
        try:
            process.wait(.5)
        except subprocess.TimeoutExpired:
            pass
        for result in process_outputs():
            print(json.dumps(result))
        if process.poll() is not None:
            break


n_outputs_for_current_input = 0 # for numbering the outputs per input (--id)

def process_outputs_match_to_inputs(inputs_given, output_buffer, onetomany=False, id=None, command_filter=None, result_keys=None, flat=False):
    global n_outputs_for_current_input

    while line := output_buffer.readline():

        line_stripped = line.rstrip('\n')
        if onetomany:
            if not line_stripped:
                inputs_given.pop(0) # empty line means outputs correspond to new input!
                n_outputs_for_current_input = 0
            stored_input = inputs_given[0].copy()    # TODO: If outputs end with empty line (no new inputs available), this crashes.
        else:
            stored_input = inputs_given.pop(0).copy()

        old_id = stored_input.get(id, None) if id else None

        result = try_parse_as_json(line_stripped)

        if onetomany and not result:    # not sure why the first is always empty...
            continue

        if command_filter and result != command_filter:
            continue
        if result_keys:
            if len(result_keys) == 1:
                stored_input[result_keys[0]] = result
            else:
                result = next(csv.reader([result]))
                stored_input.update(dict(zip(result_keys, result)))
        if flat:
            stored_input.update(result)
        if id:
            stored_input[id] = f'{old_id}.{n_outputs_for_current_input}' if old_id else f'{n_outputs_for_current_input}'

        yield stored_input

        n_outputs_for_current_input += 1


def make_csv_writer():

    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer)

    def values_to_csv_if_multi(values):

        if len(values) == 1:
            return str(values[0])

        csv_writer.writerow(values)
        value = csv_buffer.getvalue().strip()

        csv_buffer.seek(0)
        csv_buffer.truncate(0)

        return value

    return values_to_csv_if_multi


values_to_csv_if_multi = make_csv_writer()