# Four bugs that looked like results

*Draft. Written against `indic-reg-bench` at commit `9c89173` and after. Numbers
are reproducible from the repo; every one was measured, not estimated.*

I am building a benchmark for Indian regulatory document understanding: 2,006
SEBI adjudication orders, five tasks, a gold set that does not exist yet. In
the course of getting it to the point where labelling could start, four bugs
turned up. What they have in common is that none of them threw an error at the
moment they mattered, and all four would have produced a number I would have
published.

That is the interesting property. A crash is a bug you find. These are the
other kind.

---

## 1. The gold set was about to be sampled by the spelling of "April"

The labelling CLI drew its queue with `ORDER BY url`, then took the first N.

SEBI URLs embed the month as a word: `/apr-2009/`, `/sep-2025/`. Sorting URLs
alphabetically therefore sorts by *month abbreviation*. The first fifty orders
in that queue were all April, all between 2009 and 2014, drawn from a corpus
spanning 2005 to 2026 at roughly a hundred orders a year.

The bucket mix went with it. "No penalty imposed" — a real disposition, where
proceedings are abated on a noticee's death or an SCN is disposed of without
imposition — is 19% of the corpus. In the first fifty it was 2%. That is the
exact category the abstention task draws its items from.

**Why it would have published.** Fifty labelled orders is fifty labelled
orders. The file would have been the right size, the labels would each have
been individually correct, and the agreement statistics would have looked fine,
because a second pass over the same skewed sample agrees with itself. Nothing
downstream inspects *which* orders got labelled.

The fix is a seeded shuffle. The lesson is that a sort key you did not choose
is still a sort key, and `ORDER BY url` is never a neutral order — it is
whatever the URL happens to encode, which here was the calendar.

---

## 2. A temporal split moves document formats, not just dates

The split is temporal by design: train on orders before 2023, test on 2023
onward. A random split leaks badly here, because SEBI issues near-identical
orders to many noticees in one matter, and temporal also matches how such a
system is really used — built on past orders, run on new ones.

What the split code reported was the year counts. What it did not report was
what was *in* the years. Adding that:

```
train    test
 1.7%   16.1%   penalty present but table-scrambled (label from PDF)
10.2%    0.7%   unclassified
 3.0%    0.2%   no text layer
```

The table-scrambled bucket is the finding. By year:

| Years | Table-scrambled |
|---|---|
| 2005–2023 | 0–6% every year |
| 2024 | **27.7%** |
| 2025 | 10.5% |
| 2026 | **29.1%** |

SEBI began issuing multi-noticee penalties as tables around 2024. Text
extraction scrambles those columns — the amount lands before the noticee
number, which lands before the name — so they are the single hardest layout for
penalty attribution, and they are almost entirely on one side of the cut.

**Why it would have published.** Every number would have been real. A system
trained on prose orders scores badly on test, and the writeup says "temporal
generalisation is hard", which is true but is not the mechanism. The mechanism
is that 2024 changed the document format. Attributing a format shift to
temporal drift is not a wrong number; it is a wrong *explanation* with correct
numbers underneath, which is much harder to catch later.

I kept the split. It is a fair test of what the benchmark claims to measure.
But it is now declared, and the composition prints on every run, because the
version of this that goes badly is a leaderboard submitter discovering it
before I do.

---

## 3. The labelling tool died on the rupee sign, on the first order it serves

I had never run the labelling CLI end to end. I had tested its components. The
first time I actually started a session, order 1 of 200:

```
UnicodeEncodeError: 'charmap' codec can't encode character '₹'
```

Windows consoles default to cp1252, which has no ₹. Printing the operative
paragraph — the thing the label is read from — kills the session. Measured
across the labelling pool: **215 of 408 orders, 52.7%.** Not only ₹, either:
extraction arrows (U+2192, 62 orders), Symbol-font bullets (U+F0E0, 60), and a
plain U+2010 hyphen.

The same repo already had the fix. The crawler carries a stdout reconfigure
guard, added after this identical error killed a fetch at document 1,087 of
2,000. It was never applied to the labelling tool, where it matters more,
because there the unprintable character is usually the currency symbol attached
to the number being labelled.

**Why it would have published.** This one is the exception — it crashes loudly.
But it had sat undetected through a passing test suite, a documentation pass
and a sampling fix, because *unit tests do not print to a console*. The bug
lived exactly in the gap between "the function returns the right string" and "a
person can read it". Nothing short of running the thing finds that.

The related fix I did *not* make: page headers interleave with body text, so
the operative sentence is routinely cut in half by the order's own title.

> ...I, hereby **Adjudication Order in respect of Bajaj Pratisthan Pvt Ltd ...
> Page 15 of 16** impose monetary penalty of ₹ 5,00,000/-...

`hereby` and `impose`, 120 characters apart. This is 90.9% of the labelling
pool, so it is the normal case. I left it in: a filter aggressive enough to
strip a running header also eats the order title where it is genuinely quoted,
and every scored system faces the same text.

---

## 4. The scorer graded formatting and called it comprehension

With a local model wired up as a baseline, the abstention task returned
`answerable_accuracy` of 0.0. The model looked bad. What it actually answered:

```
gold: "500000"
pred: "` 5,00,000/-(Rupees Five Lakh only)"
```

That is the operative text, verbatim, correct, including the backtick that a
quarter of these PDFs render the rupee sign as. It scored zero because the
scorer compared `str(p).strip() == str(g).strip()`.

The docstring said "exact match on the value". The code did exact match on the
*string*. Amounts appear in this corpus in at least four surface forms —
`500000`, `5,00,000`, `` ` 5,00,000/- ``, `Rupees Five Lakh only` — and the
repo already had a numeral module built precisely because of that. The scorer
did not use it.

**Why it would have published.** This is the worst of the four. It deflates
every system in the same direction, so the *ranking* stays plausible and only
the absolute numbers are wrong. A leaderboard where everything scores 40% looks
like a hard benchmark. It reads as a finding — "these tasks are difficult" —
and the finding is an artifact of string comparison.

Fixing it moved that baseline from 0.0 to 1.0 on both the numeric task and the
answerable half of abstention, on a synthetic smoke fixture built to exercise
the path. Nothing about the model changed. (Those are fixture numbers, not
benchmark results — the gold set is still empty. The attribution task stayed at
0.0, which is the model genuinely getting it wrong: it answered
`cited_precedent` for a settlement plea and `scn_proposed` for the imposed
penalty. That one is a real result and the reason the task exists.)

The guard against over-correcting is a test that the normalisation stays
strict: `"45 days"` must not equal `45`, abstaining must not count as
answering, and the settlement-plea amount must not equal the imposed one.

---

## What connects them

Every one was found by running something rather than reading something.

- The sampling bug: by printing which orders the queue actually contained.
- The split composition: by asking what was in the years, not how many.
- The encoding crash: by starting a real labelling session.
- The scoring bug: by pointing a model at it and disbelieving the first bad
  number.

Three of the four had passing tests over the exact code involved. The tests
were not wrong. They were checking the thing that was easy to check —
`classify()` returns the right bucket, `operative_window()` finds the right
paragraph, `score_numeric()` counts matches correctly — while the defect lived
one level up, in which inputs got selected, what the console could render, and
what "match" meant.

The uncomfortable version: I would have shipped all four, and every one of them
would have come out as a number with a sensible story attached. The benchmark's
headline claim — that naive first-amount extraction disagrees with the
operative paragraph in 48.6% of orders — has survived two extraction bug fixes
and an 80× increase in sample size. I trust that number *because* it survived
those, not because it was right the first time. It was not right the first
time. It said 24%.

---

*Everything here is reproducible: `github.com/siddharthgaur1/indic-reg-bench`.
The gold set is still empty, which is the honest status of the project. The
leaderboard is empty by design and will stay that way until there is something
real to put in it.*
