# guided-review

A skill for reviewing finished work you did not watch being made. Anyone can put the same
model on the same work; what makes one review better than another is the reviewer. So the
agent does the reading and checking, shows every part of the work, tells the reviewer where
it differs from what they asked for, and asks only what they alone can answer: what they
meant, what they pictured, whether it looks right. Their answers become a review that
states what it covered, part by part: judged, glanced, could not judge, left to the maker,
or not reached.

Six principles carry it:

1. The reviewer is the instrument.
2. Tell what you can check; ask only what they alone hold.
3. Glance at everything, stop at a few, and let them stop anywhere.
4. Read their grasp from their answers, part by part; never test them.
5. The review says what it covered; the page only records what was answered. Never score
   the person.
6. Start with nothing asked.

The page runs from most to least needed: a glance at every part (findings folded inside),
then the stops, the main part first and the rest by distance from the request, then the
lists that need no answer, folded. The page counts its own reading time and marks it
between the stops, so wherever the reviewer stops, they hold the best review that time
could buy, and the coverage view says how far they got.

A review looks back: what to do next is listed, never asked. The directions name no product
or host on purpose, so they stay true as those change.

## What is in the folder

| File | What it is |
|---|---|
| `SKILL.md` | The directions |
| `assets/review-page.html` | A wireframe of a review page: every part in its place, each slot labelled, no content. Its marks, folds, time marks, saving, copying and the coverage view work. Copy it and fill the slots. |
| `scripts/serve.py` | A small server that serves one review folder and saves the answers to a file. Python standard library only. |
| `evals/` | The test definition and a script that checks a page's form. For people changing the skill. |

## Install

Clone it, then link or copy the folder into your agent's skills folder. For Claude Code:

```sh
git clone https://github.com/carbonscott/guided-review ~/codes/guided-review
ln -s ~/codes/guided-review ~/.claude/skills/guided-review
```

Then say "help me review this", or type `/guided-review`.

## Try the example

```sh
mkdir /tmp/review-example
cp assets/review-page.html /tmp/review-example/index.html
python3 scripts/serve.py /tmp/review-example     # then open http://localhost:8765/
```

From another machine, forward the port first:

```sh
ssh -L 8765:127.0.0.1:8765 <the host>
```

Answer a few stops and mark a part. The coverage view near the end shows, part by part, what
the answers cover so far. The bar at the bottom shows the host and file the answers were
saved to: `/tmp/review-example/answers.json`. Send marks them done.

## How answers travel

The page saves every change to the server, which writes `answers.json` in the review
folder, coverage included, and appends each save to `answers.log`. The server listens on its own machine only
and sends nothing anywhere else. If the page cannot reach it, the page says so and shows
the answers as text to copy.

## Evals

`evals/` is for people changing the skill. An agent using the skill never reads it.

- `evals/evals.json` defines the test in the skill-creator format: a prompt, a baseline
  prompt without the skill, and the properties a good page has.
- Eval 1, `page-from-frozen-research`, builds a page. Eval 2, `review-from-answers`, writes
  the review from a page and a set of sent answers; a person or an agent grades it by reading.
- `evals/check_page.py` measures a page's form: how many stops, how much reading per stop
  and for the whole page against the budget, whether the main part comes first, how the
  choices are worded, what is folded away. It counts time the same way the page does, reads
  the page as written and needs only Python.

```sh
python3 evals/check_page.py path/to/index.html
```

A run starts from a case folder that holds the research already done, so it spends its
time on the page and not on reading the work. No case ships here yet; the first one is
private. The checks measure form only. Whether the stops are the right ones is still for a
person to judge.

## Status

Draft. The server and the wireframe are tested, with a headless browser for the page.
Two reviews of real work shaped the directions. The first asked mostly about next steps.
The second quizzed the reviewer on findings the agent already knew. Then came: tell first,
ask second. Then parts and coverage, so that a review says how much of the work the
reviewer's judgment reached. The latest round holds the whole page to the reviewer's time:
pages had passed every check on their stops while the text around them doubled.
