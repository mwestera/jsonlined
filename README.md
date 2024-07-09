# jsonlined #

I work a lot with jsonlines files (`.jsonl`), in which each line represents a `json`-formatted 'dictionary' mapping keys to values.

For instance, I may have a large file with tweets, each tweet a dictionary storing number of likes, tweet text, time of tweeting, etc.

Sometimes I want to extract a value from each json line (say, the tweet's text under the key `text`), do something with it 
(like count the number of words, split it into sentences, or categorize its sentiment), and store the result under a new
key in the original json dictionary.

I wrote this small module to make this easier. Perhaps you will find it useful. 

It uses Python's `suprocess` module, which is probably not ideal compared to relying on `bash` itself. I'm not an expert in bash/pipes/streams/subprocess/json/operating systems. No guarantees about it working correctly anywhere other than my own computer.



## Install ##

`pip install git+https://github.com/mwestera/jsonlined`

This will make two commands available in your shell:

- `jsonlined`: for cases where each line is processed by a separate instance of a program.
- `jsonpiped`: for cases where lines are fed one by one into a single running instance of a program.

The latter is especially recommended for programs with substantial buildup/teardown.


## Examples ##

Suppose we have a `.jsonl` file with social media posts like this:

```
{"type": "submission", "id": "12qw3", "text": "The quick brown fox. So anyway.", "score": 0.5}
{"type": "reply", "id": "34ad5", "text": "Vintage pamphlets are fun. Buy them!", "score": 0.86}
{"type": "submission", "id": "654as", "text": "Ignorance of the law. What about it?", "score": 1.0}
```

We can extract the values under `text`, pass them into another command, like Unix' own `wc -w` for counting words, and store the 
result in a new key `n_words`, keeping the original text:

```bash
$ cat tests/test.jsonl | jsonlined [wc -w] text nwords --keep
```

Hypothetical example, assuming one has `sentencize.py` for splitting a text into sentences:
 
Get a bunch of jsonlines, extract the values under 'text', split each text into sentences, output a new json line per sentence, each with 'id' field derived from the original 'id' field:

```bash
$ cat tests/test.jsonl | jsonlined [python sentencize.py] text sentence --id id 
```

Another example, for computing text embeddings (assuming we have the script `embed.py` to operate on lines of `stdin`:

```bash
$ cat tests/test.jsonl | jsonpiped [python embed.py] text embedding
```

Here jsonpiped is used, because embed.py requires considerable setup (loading model) -- prerequisite is that operates line-swise (not waiting for EOF like wc). 

If subprocess outputs json format, this will be interpreted as such; otherwise literal string.

In case the subprocess can output multiple new lines per original input line, either use `jsonlined`, or -- for `jsonpiped` -- set `--onetomany` and make sure the subprocess outputs double newlines between inputs.


## Related ##

More or less the same can be achieved, with a bit of bash scripting, by using the much more sophisticated, faster, more general-purpose JSON Stream Editor [JJ](https://github.com/tidwall/jj).