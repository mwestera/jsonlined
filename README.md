# jsonlined #

In a JSON-lines file (`.jsonl`), each line represents a 'JSON'-formatted dictionary mapping keys to values.

Often I want to extract a value from each json line, do something with it, and store the result under a new key. For instance:

```bash
$ jsonlined some_data.jsonl text [wc -w] nwords --keep > enriched_data.jsonl
```

This will extract the values stored under the `text` key, pass them into `wc` to count words, and stores the resulting
word counts back under the new ke `nwords` (keeping the original one).

I wrote this program while in part to learn about Bash, pipes and Python's subprocess, but I ended up using it almost daily, so
perhaps you will find it useful too.


## Install ##

```bash
$ pip install git+https://github.com/mwestera/jsonlined   # or use pipx for global install
```

This will make two commands available in your shell:

- `jsonlined`: for cases where each line is processed by a separate instance of a program.
- `jsonpiped`: for cases where lines are fed one by one into a single running instance of a program.

The latter is recommended for programs with substantial buildup/teardown, like loading a large model.


## Examples ##

Suppose we have a `.jsonl` file with social media posts like this:

```
{"type": "submission", "id": "12qw3", "text": "The quick brown fox. So anyway.", "score": 0.5}
{"type": "reply", "id": "34ad5", "text": "Vintage pamphlets are fun. Buy them!", "score": 0.86}
{"type": "submission", "id": "654as", "text": "Ignorance of the law. What about it?", "score": 1.0}
```

We can extract the values under `text`, pass them into another command, like Unix' own `wc -w` for counting words, and store the 
result in a new key `n_words`, keeping the original text. The result is directed to a new file:

```bash
$ cat tests/test.jsonl | jsonlined text [wc -w] nwords --keep > tests/test_with_nwords.jsonl
```

Hypothetical example, assuming one has `sentencize.py` for splitting a text into sentences:
 
Get a bunch of jsonlines, extract the values under 'text', split each text into sentences, output a new json line per sentence, each with 'id' field derived from the original 'id' field:

```bash
$ cat tests/test.jsonl | jsonlined text [python sentencize.py] sentence --id id 
```

Or maybe we want it only for the lines where the "type" key has the value "submission":

```bash
$ cat tests/test.jsonl | jsonlined text,type=submission [python sentencize.py] sentence --id id 
```

You can also filter on the output of the subprocess, for instance to get all texts with 10 words:

```bash
$ cat tests/test.jsonl | jsonlined [wc -w]=10 text
```

Another example, for computing text embeddings (assuming we have the script `embed.py` to operate on lines of `stdin`:

```bash
$ cat tests/test.jsonl | jsonpiped text [python embed.py] embedding
```

This time, `jsonpiped` is used (instead of `jsonlined`), because embed.py requires considerable setup (loading model) -- a prerequisite is that it operates line-swise (not waiting for EOF like wc).

If subprocess outputs json format, this will be interpreted as such; otherwise literal string.

If two new keys (comma-separated) are provided, as follows, then the program will attempt to unpack the resulting string as a .csv string, and assign one value to each key:

```bash
$ cat tests/test.jsonl | jsonpiped text [python embed_and_get_similarity.py] embedding,similarity
```

In case the subprocess can output multiple new lines per original input line, either use `jsonlined`, which will work as is (as in the sentencize example above), or -- for `jsonpiped` -- set `--onetomany` and make sure the subprocess outputs double newlines between inputs.

Lastly, if the subprocess needs its `stdin` (for instance for user input, like a Textual app), you can avoid relying on `stdin` by using process substitution (for input to `jsonlined`/`jsonpiped`), and by using the placeholder `%PIPE` in the subprocess, which will be replaced by a named pipe fed into the subprocess:

```bash
$ jsonpiped <(cat tests/test.jsonl) text [python annotation.py %PIPE] embedding
```

## Related ##

There is a much more sophisticated, faster, more general-purpose JSON Stream Editor [JJ](https://github.com/tidwall/jj).