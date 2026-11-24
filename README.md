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
| `example/index.html` | A wireframe of a review page: every part in its place, each slot labelled, no content. Its inputs, saving and copying work. Copy it and fill the slots. |
| `serve.py` | A small server that serves one review folder and saves the answers to a file. Python standard library only. |

## Install

Clone it, then link or copy the folder into your agent's skills folder. For Claude Code:

```sh
git clone https://github.com/carbonscott/guided-review ~/codes/guided-review
ln -s ~/codes/guided-review ~/.claude/skills/guided-review
```

Then say "help me review this", or type `/guided-review`.

## Try the example

```sh
cp -r example /tmp/review-example
python3 serve.py /tmp/review-example            # then open http://localhost:8765/
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

## Status

Draft. The server and the wireframe are tested, with a headless browser for the page.
Two reviews of real work shaped the directions. The first asked mostly about next steps.
The second quizzed the reviewer on findings the agent already knew. The directions now
say: tell first, ask second.
