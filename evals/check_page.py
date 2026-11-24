#!/usr/bin/env python3
"""Measure a review page against the form the guided-review skill asks for.

    python3 evals/check_page.py <page.html> [--json]
                                [--transcript <run.jsonl> --forbid <text> ...]

It reads the page as written (it runs no script), so it works on any page built from
assets/review-page.html. It checks form only: how many stops, how much reading, how the
choices are worded, what is folded away. It cannot tell whether the stops are the right
ones; a person still has to look.

With --transcript it also checks that the run's tool calls never mention a forbidden
text, such as the path of the original work in an eval where the research is given.
Standard library only.
"""
import argparse, json, os, re, statistics, sys
from html.parser import HTMLParser

# Pass marks. They come from one page a reviewer approved: 7 stops, a median of 70 words
# of "asked for / what is there" (longest 82), a median of 134 visible words per stop
# (longest 178), one guess-first stop, and a longest choice of 9 words. The checks on
# parts (every stop and finding in a part, a coverage view) and on time (everything in view
# fits the budget, the main part first, what needs no answer folded) came later, with the
# ideas that a review states what it covered and that a reviewer can stop anywhere; that
# page predates them.
MIN_STOPS, MAX_STOPS = 3, 10
MAX_SAID_WORDS = 100          # heading + asked for + what is there; the skill aims at about 70
MAX_VISIBLE_MEDIAN, MAX_VISIBLE_WORDS = 160, 220
MAX_GUESS_FIRST = 2
MAX_CHOICE_WORDS = 12
MIN_FINDINGS = 3
MIN_PARTS, MAX_PARTS = 3, 7
WPM, PER_STOP, PER_PART = 200, 0.3, 0.1      # the page's own time count: words a minute, minutes to answer a stop or mark a part
PLAN = re.compile(r"\b(what|when|which|how|who)\b[^?.]{0,40}\bshould\b(?!n['’]t)|\bshould (we|i|it|they|this|these)\b|\bdo next\b|\bwhat to do\b", re.I)
SLOT = re.compile(r"\[[A-Z][^\[\]]{6,}\]")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def walk(self):
        yield self
        for c in self.children:
            if isinstance(c, Node):
                yield from c.walk()

    def find(self, pred):
        return [n for n in self.walk() if n is not self and pred(n)]

    def inside(self, pred):
        p = self.parent
        while p is not None:
            if pred(p):
                return True
            p = p.parent
        return False

    def text(self, skip=lambda n: False):
        out = []
        for c in self.children:
            if isinstance(c, str):
                out.append(c)
            elif c.tag not in ("script", "style") and not skip(c):
                out.append(c.text(skip))
        return " ".join(" ".join(out).split())


class Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = self.cur = Node("root", [], None)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def words(s):
    return len(s.split())


def has(cls):
    return lambda n: cls in n.classes()


def is_tag(*tags):
    return lambda n: n.tag in tags


def timeline(wrap):
    """Minutes to the end of each stop, and for the whole page in view, the same way the page counts them."""
    c, ends = {"words": 0, "stops": 0, "parts": 0}, []
    cost = lambda: c["words"] / WPM + c["stops"] * PER_STOP + c["parts"] * PER_PART

    def walk(node):
        for ch in node.children:
            if isinstance(ch, str):
                c["words"] += len(ch.split())
                continue
            if ch.tag in ("details", "script", "style", "textarea") or "chrome" in ch.classes():
                continue
            walk(ch)
            if "part" in ch.classes():
                c["parts"] += 1
            if "stop" in ch.classes():
                c["stops"] += 1
                ends.append(cost())
    walk(wrap)
    return ends, cost()


def measure(path):
    b = Builder()
    b.feed(open(path, encoding="utf-8", errors="replace").read())
    root, here = b.root, os.path.dirname(os.path.abspath(path))
    wraps = root.find(has("wrap"))
    wrap = wraps[0] if wraps else root
    folded = is_tag("details")
    stops = []
    for s in root.find(has("stop")):
        said = s.find(has("said"))
        options = [l.text() for l in s.find(is_tag("label"))
                   if "chip" not in l.classes() and l.find(lambda n: n.tag == "input" and n.attrs.get("type") in ("radio", "checkbox"))]
        heads = s.find(is_tag("h2", "h3"))
        figures = [n for n in s.find(lambda n: n.tag in ("figure", "img", "table") or {"rows", "bar", "tbl"} & set(n.classes()))
                   if not n.inside(folded) and not n.inside(is_tag("fieldset"))]
        title = heads[0].text() if heads else ""
        stops.append({
            "id": s.attrs.get("data-id", "?"),
            "part": s.attrs.get("data-part"),
            "title": title,
            "said_words": words(title) + words(said[0].text()) if said else None,
            "visible_words": words(s.text(skip=lambda n: n.tag == "details" or "extras" in n.classes())),
            "guess_first": bool(s.find(lambda n: {"guess", "show"} & set(n.classes()))),
            "options": options,
            "questions": [l.text() for l in s.find(is_tag("legend"))],
            "asked_and_there": bool(said and len(said[0].find(is_tag("dd"))) >= 2)
                               or bool(re.search(r"asked for", s.text(), re.I) and re.search(r"what is there", s.text(), re.I)),
            "figure_in_view": bool(figures),
            "evidence_folded": bool(s.find(folded)),
            "pre_in_view": len([p for p in s.find(is_tag("pre")) if not p.inside(folded)]),
        })
    visible = root.text()
    parts = root.find(has("part"))
    part_ids = [p.attrs.get("data-part") for p in parts]
    items = [li for f in root.find(has("findings")) for li in f.find(is_tag("li"))]
    in_part = lambda li: next((p.attrs.get("data-part") for p in parts if li in list(p.walk())), None)
    lists = {}
    for h in root.find(is_tag("h2")):
        name = next((k for k, pat in (("not looked at", r"not looked"), ("decisions", r"decisions"), ("checked", r"checked for you")) if re.search(pat, h.text(), re.I)), None)
        if name:
            sib = [c for c in h.parent.children if not isinstance(c, str)]
            nxt = sib[sib.index(h) + 1] if sib.index(h) + 1 < len(sib) else None
            lists[name] = bool(nxt is not None and nxt.tag == "details")
    try:
        budget = float(wrap.attrs.get("data-budget") or 10)
    except ValueError:
        budget = 10.0
    ends, total = timeline(wrap)
    images = [n.attrs.get("src", "") for n in root.find(is_tag("img"))]
    local = [s for s in images if s and not re.match(r"[a-z]+:", s)]
    ids = {n.attrs.get("id") for n in root.walk() if n.attrs.get("id")}
    script = " ".join(str(c) for n in root.find(is_tag("script")) for c in n.children if isinstance(c, str))
    return {
        "stops": stops,
        "findings": len(items),
        "findings_folded_in_parts": sum(1 for li in items if li.inside(folded) and in_part(li)),
        "parts": len(parts),
        "part_ids": part_ids,
        "parts_shown": len([p for p in parts if p.find(lambda n: n.tag == "img" or "big" in n.classes())]),
        "decisions_listed": "decisions" in lists,
        "lists_folded": lists,
        "budget": budget,
        "minutes_to_last_stop": round(ends[-1], 1) if ends else None,
        "minutes_in_view": round(total, 1),
        "shows_cost_and_reach": sorted({"time-total", "coverage"} & ids),
        "hand_back": sorted({"save", "send", "copy", "record"} & ids),
        "posts_answers": "fetch(" in script,
        "slots_left": len(SLOT.findall(visible)) + len(root.find(has("slot"))),
        "missing_pictures": [s for s in local if not os.path.exists(os.path.join(here, s))],
        "pictures": len(images),
        "radio_groups": len({n.attrs.get("name") for n in root.find(lambda n: n.tag == "input" and n.attrs.get("type") == "radio")}),
        "words": words(visible),
    }


def grade(m):
    out, stops = [], m["stops"]

    def expect(text, passed, evidence):
        out.append({"text": text, "passed": bool(passed), "evidence": evidence})

    if not stops:
        expect("The page is built from stops that can be measured", False,
               f"no element with class 'stop': {m['radio_groups']} radio groups, {m['words']} words, {m['pictures']} pictures")
    else:
        n = len(stops)
        said = [s["said_words"] for s in stops if s["said_words"] is not None]
        vis = [s["visible_words"] for s in stops]
        guess = [s["id"] for s in stops if s["guess_first"]]
        loaded = [(s["id"], o) for s in stops for o in s["options"] if ":" in o or words(o) > MAX_CHOICE_WORDS]
        plans = [(s["id"], q) for s in stops for q in s["questions"] + [s["title"]] if PLAN.search(q)]
        expect(f"The page has {MIN_STOPS} to {MAX_STOPS} stops", MIN_STOPS <= n <= MAX_STOPS, f"{n} stops")
        expect("Every stop puts what was asked beside what is there", all(s["asked_and_there"] for s in stops),
               "missing in: " + (", ".join(s["id"] for s in stops if not s["asked_and_there"]) or "none"))
        expect(f"No stop needs more than {MAX_SAID_WORDS} words for its heading, what was asked and what is there",
               len(said) == n and max(said) <= MAX_SAID_WORDS,
               f"median {statistics.median(said):.0f}, longest {max(said)}" if said else "not measurable: no 'said' block")
        expect(f"Visible text per stop: median at most {MAX_VISIBLE_MEDIAN} words, none above {MAX_VISIBLE_WORDS}",
               statistics.median(vis) <= MAX_VISIBLE_MEDIAN and max(vis) <= MAX_VISIBLE_WORDS,
               f"median {statistics.median(vis):.0f}, longest {max(vis)}, total {sum(vis)}")
        expect(f"At most {MAX_GUESS_FIRST} stops are guess-first", len(guess) <= MAX_GUESS_FIRST,
               f"{len(guess)} guess-first" + (": " + ", ".join(guess) if guess else ""))
        expect(f"Choices are bare: no colon, at most {MAX_CHOICE_WORDS} words", not loaded,
               f"{len(loaded)} loaded choices" + (", e.g. " + loaded[0][0] + " '" + loaded[0][1][:70] + "'" if loaded else ""))
        expect("No stop asks what should happen next", not plans,
               f"{len(plans)} planning questions" + (", e.g. " + plans[0][0] + " '" + plans[0][1][:70] + "'" if plans else ""))
        expect("Every stop shows a figure in view", all(s["figure_in_view"] for s in stops),
               "missing in: " + (", ".join(s["id"] for s in stops if not s["figure_in_view"]) or "none"))
        homeless = [s["id"] for s in stops if not s["part"] or s["part"] not in m["part_ids"]]
        expect("Every stop belongs to a part shown in the overview", not homeless,
               "without a part: " + (", ".join(homeless) or "none"))
        expect("Raw evidence is folded away in every stop",
               all(s["evidence_folded"] and not s["pre_in_view"] for s in stops),
               f"{sum(s['pre_in_view'] for s in stops)} raw blocks in view; no fold in: "
               + (", ".join(s["id"] for s in stops if not s["evidence_folded"]) or "none"))
        main = m["part_ids"][0] if m["part_ids"] else None
        expect("The first stop is on the main part, the first in the overview", main and stops[0]["part"] == main,
               f"first stop {stops[0]['id']} is on {stops[0]['part']}; main part is {main}")
    expect(f"Everything in view fits the budget ({WPM} words a minute, {PER_STOP * 60:.0f} s a stop, {PER_PART * 60:.0f} s a part)",
           m["minutes_in_view"] <= m["budget"],
           f"{m['minutes_in_view']} min in view, {m['minutes_to_last_stop']} min to the last stop; budget {m['budget']:g} min")
    expect(f"Findings beyond the stops: at least {MIN_FINDINGS}", m["findings"] >= MIN_FINDINGS, f"{m['findings']} findings")
    expect("Findings are folded inside their parts", m["findings"] and m["findings_folded_in_parts"] == m["findings"],
           f"{m['findings_folded_in_parts']} of {m['findings']} folded inside a part")
    expect(f"The overview shows every part: {MIN_PARTS} to {MAX_PARTS}, each with an id", MIN_PARTS <= m["parts"] <= MAX_PARTS
           and all(m["part_ids"]) and len(set(m["part_ids"])) == m["parts"], f"{m['parts']} parts, ids: {', '.join(str(i) for i in m['part_ids'])}")
    expect("Every part in the overview shows a picture or a number", m["parts"] >= 2 and m["parts_shown"] == m["parts"],
           f"{m['parts_shown']} of {m['parts']} parts")
    expect("Plans are listed, not asked: a decisions list exists", m["decisions_listed"], "heading found" if m["decisions_listed"] else "no such heading")
    lf = m["lists_folded"]
    expect("Not looked at, decisions and checks are each folded behind one line", len(lf) == 3 and all(lf.values()),
           ", ".join(f"{k}: {'folded' if v else 'in view'}" for k, v in lf.items()) or "none found")
    expect("The page shows its own cost and what the answers reach", len(m["shows_cost_and_reach"]) == 2,
           "present: " + (", ".join(m["shows_cost_and_reach"]) or "none"))
    expect("The page can take answers and hand them back", len(m["hand_back"]) == 4 and m["posts_answers"],
           "present: " + (", ".join(m["hand_back"]) or "none") + ("; posts answers" if m["posts_answers"] else "; does not post answers"))
    expect("No wireframe slot is left unfilled", m["slots_left"] == 0, f"{m['slots_left']} slots left")
    expect("Every picture the page points to is beside it", not m["missing_pictures"],
           "missing: " + (", ".join(m["missing_pictures"]) or "none") + f" ({m['pictures']} pictures)")
    return out


def transcript_mentions(path, forbidden):
    hits = []
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        msg = d.get("message") if isinstance(d, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                call = json.dumps(block.get("input"))
                hits += [f"{block.get('name')}: {call[:120]}" for f in forbidden if f in call]
    return hits


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("page")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    ap.add_argument("--transcript", help="the run's transcript, one JSON object per line")
    ap.add_argument("--forbid", action="append", default=[], help="a text no tool call may mention; repeat as needed")
    args = ap.parse_args()
    m = measure(args.page)
    expectations = grade(m)
    if args.transcript:
        hits = transcript_mentions(args.transcript, args.forbid)
        expectations.append({"text": "The run touched nothing it was told to leave alone", "passed": not hits,
                             "evidence": f"{len(hits)} tool calls" + (", e.g. " + hits[0] if hits else "")})
    passed = sum(e["passed"] for e in expectations)
    result = {"expectations": expectations,
              "summary": {"passed": passed, "failed": len(expectations) - passed, "total": len(expectations),
                          "pass_rate": round(passed / len(expectations), 2)},
              "metrics": m}
    if args.json:
        print(json.dumps(result, indent=2))
        return
    for e in expectations:
        print(f"{'PASS' if e['passed'] else 'FAIL'}  {e['text']}\n      {e['evidence']}")
    print(f"\n{passed} of {len(expectations)} passed")
    for s in m["stops"]:
        print(f"  {s['id']:>5}  {str(s['part']):>4}  said {str(s['said_words']):>4}  visible {s['visible_words']:>4}  "
              f"{'guess-first ' if s['guess_first'] else ''}{s['title'][:70]}")


if __name__ == "__main__":
    main()
