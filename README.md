# jsonlined #

I work a lot with jsonlines files (`.jsonl`), in which each line represents a `json`-formatted 'dictionary' mapping keys to values.

For instance, I may have a large file with tweets, each tweet a dictionary storing number of likes, tweet text, time of tweeting, etc.

Sometimes I want to extract a value from each json line (say, the tweet's text under the key `text`), do something with it 
(like count the number of words, split it into sentences, or categorize its sentiment), and store the result under a new
key in the original json dictionary.

I wrote this small module to make this easier. Perhaps you will find it useful. I'm not an expert on bash/pipes/streams/subprocess/operating systems. No guarantees about it working correctly anywhere other than my own systems.

Suggestions, issues, pull requests welcome!


## Install ##

`pip install git+https://github.com/mwestera/jsonlined`

This will make two commands available in your shell:

- `jsonlined`: for cases where each line is processed by a separate instance of a program.
- `jsonpiped`: for cases where lines are fed one by one into a single running instance of a program.

The latter is especially recommended for programs with substantial buildup/teardown.


## Examples: ##

Suppose we have a `.jsonl` file with social media posts like this:

```
{"type": "submission", "id": "12qw3", "text": "The quick brown fox. So anyway.", "score": 0.5}
{"type": "reply", "id": "34ad5", "text": "Vintage pamphlets are fun. Buy them!", "score": 0.86}
{"type": "submission", "id": "654as", "text": "Ignorance of the law. What about it?", "score": 1.0}
```

We can extract the values under `text`, pass them into another command, like Unix' own `wc -w` for counting words, and store the 
result in a new key `n_words`, keeping the original text:

```bash
$ cat test.jsonl | jsonlined [wc -w] text n_words --keep
```

Note the square brackets around the command that we want to execute 'per line'.

Or, assuming we have a script `sentencize.py` for splitting a text into sentences, one can easily obtain a new json line
per sentence, each with an `id` field derived from the original `id` field:

```bash
$ cat test.jsonl | jsonpiped [python sentencize.py] id,text sentence | less
```

Here jsonpiped is used, because sentence.py operates on lines (not waiting for EOF). This is especially recommended
for programs with considerable buildup/teardown cost, e.g., loading a language model.

