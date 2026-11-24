# guided-review

A skill for reviewing finished work without reading all of it. The agent shows what was
made, tells the reviewer the few places where it differs from what they asked for, and
asks one short question at each. It then writes the review from those answers for the
reviewer to approve.

The skill gives directions: how to settle the level (outcome, design, details), what makes
a stop worth a person's minute, which ways of taking input to offer, and how to turn
answers into a review. A review looks back: what to do next is listed, never asked. The
directions name no product or host on purpose, so they stay true as those change.

## What is in the folder

| File | What it is |
|---|---|
| `SKILL.md` | The directions |
| `assets/review-page.html` | A wireframe of a review page: every part in its place, each slot labelled, no content. Its inputs, saving and copying work. Copy it and fill the slots. |
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

Answer a few stops. The bar at the bottom shows the host and file the answers were saved
to: `/tmp/review-example/answers.json`. Send marks them done.

## How answers travel

The page saves every change to the server, which writes `answers.json` in the review
folder and appends each save to `answers.log`. The server listens on its own machine only
and sends nothing anywhere else. If the page cannot reach it, the page says so and shows
the answers as text to copy.

## Evals

`evals/` is for people changing the skill. An agent using the skill never reads it.

- `evals/evals.json` defines the test in the skill-creator format: a prompt, a baseline
  prompt without the skill, and the properties a good page has.
- `evals/check_page.py` measures a page's form: how many stops, how much reading per stop,
  how the choices are worded, what is folded away. It reads the page as written and needs
  only Python.

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
The second quizzed the reviewer on findings the agent already knew. The directions now
say: tell first, ask second.
