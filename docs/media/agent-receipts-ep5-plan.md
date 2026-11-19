# Built It. Bragging About It. · Ep. 5 — agent-receipts v0.1.0

- **Episode:** 5 · **Type:** YC gap episode · **Headline:** agent-receipts v0.1.0 (first working release, 14 Nov 2026)
- **Format:** 1920x1080, 30 fps, 38.0 s total = clip 1 (14.0 s) + clip 2 (24.0 s, of which the follow outro is the last 5.0 s)
- **Tones:** clip 1 `chaotic` (the problem) → clip 2 `polished` (the solution). Previous pairs: Ep. 3 cinematic + default, Ep. 4 deadpan + app-store.
- **Angle, clip 1:** coding agents open PRs; the diff shows what changed, not what the agent ran. The answers sit in a session log nobody reads. (From PRD.md §1 and gaps G1/G2.)
- **Angle, clip 2:** v0.1.0 turns that log into a receipt: verdict, risky steps, stated assumptions; then what's in the release and how to install it (pinned to v0.1.0, plus the Claude skill zip).
- **Honesty:** every receipt value on screen is the real `agent-receipts render examples/claude-code-session.jsonl` output from v0.1.0 (VERIFIED, 2 files, 3 commands, 1 high, 12k tokens, GIT002 force push at step 16, the stated assumption, sha256:eea237ad29ce). The diff card and the log lines are an illustrative view of the repo's synthetic example session (fictional project "acme-api"). No metrics, users or endorsements are claimed.

## Design tokens (from Design.md)
Background `#111214`, surface `#1A1C1F`, border `#2C2F33`, text `#E8E8E6`, muted `#9A9DA3`, accent `#7C93F5` (the only colour that changes week to week), verified `#51CF66`, stale `#FFB84D`, failed `#FF6B6B`, high `#FF8A4C`. Fonts: Inter (400–800) and JetBrains Mono. Series ident, end card and outro use the fixed series layout (Inter 800, Ep pill, accent underline).

## Storyboard

### Clip 1 — the problem (chaotic, 0.0–14.0 s)
| Time | Scene | On screen |
|---|---|---|
| 0.0–2.0 | Series ident | "Ep. 5" pill, "Built It. Bragging About It." words slam in, accent bar, `agent-receipts`; zooms out into the first cut |
| 2.0–5.0 | Hook | "YOUR AGENT JUST OPENED A PR." slammed word by word over scrolling log texture; chip `fix/rate-limit → main · 2 files changed` |
| 5.0–9.5 | The diff | Diff card (`src/limiter.py`) whips in; "THE DIFF SHOWS WHAT CHANGED." / "IT DOESN'T SHOW:" + three question cards: tests after the last edit? anything risky? what did it assume? |
| 9.5–12.0 | The log | Session log card (`~/.claude/projects/acme-api/…jsonl`, 19 events) punches in, lines racing past; "THE ANSWERS ARE IN THE SESSION LOG." |
| 12.0–14.0 | Tension | "NOBODY READS IT." The log decelerates to a stop, accent glow builds; snare roll into the seam |
Cuts at 2.0 / 5.0 / 9.5 / 12.0 land on beats with a soft accent flash, a small camera punch and an impact hit.

### Clip 2 — the solution (polished, 14.0–33.0 s) + outro (33.0–38.0 s)
| Time | Scene | On screen |
|---|---|---|
| 14.0–18.0 | Reveal | "NOBODY READS IT." fades; the log card stays; `agent-receipts` + "new · v0.1.0" and the one-line description fade up; a receipt prints out to the right while the matching log lines highlight (pytest, assumption, force push) |
| 18.0–23.3 | Push-in (poster at 22.5 s) | Log card exits; the receipt glides to centre-right and grows; three annotations: "Was it verified?", "Anything risky?", "What did it assume?", each outlining its section of the receipt |
| 23.3–27.3 | What's in v0.1.0 | Four cards: Claude Code + Codex CLI · 4 clear verdicts · 19 risk rules · Private by default |
| 27.3–30.8 | Get it | Terminal types `pip install "git+https://github.com/AagamS06/agent-receipts.git@v0.1.0"` then `agent-receipts render`; chips: Claude skill zip on the release · MIT · Python 3.11+ |
| 30.7–33.0 | Series end card | "Ep. 5" · "Built It. Bragging About It." · github.com/AagamS06/agent-receipts |
| 33.0–38.0 | Follow outro | Title and pill glide up; "Enjoyed this? Support the series." / "More builds on my YouTube and Facebook" / ▶ YouTube @gearhead32 · f Facebook Aagam / "Links in the post or my bio". Generic CSS glyphs in the accent colour, no platform logos |

## The seam (14.0 s, frame 420)
The session log card is the shared element: it slows to a stop at 13.4 s and stays in the same place across the cut, with "NOBODY READS IT." still on screen. Clip 2 begins by fading that line out over 0.5 s while the receipt prints next to the card, so frame 419 and frame 420 are near-identical. The whole video is one page with a global `setT(t)`; every frame is a pure function of time.

## Soundtrack
Original synth score, A minor, 120 BPM, one continuous track (bar = 2 s, progression Am–F–C–G). Clip 1: four-on-the-floor kick, 16th hats, driving 8th-note bass, chord stabs, impacts on cuts and a snare roll into the seam. The seam lands on the bar-7 downbeat (14.0 s) with a soft impact into clip 2: warm pad, plucked arpeggio, gentle kick on 1 and 3, quiet "printing" ticks and chimes on reveals. Final Am(add9) chord struck at 36.0 s and fading to silence exactly at 38.0 s. Clip files get a 0.25 s fade-out (clip 1) and 0.15 s fade-in (clip 2) at their own cut; the merged episode keeps the continuous track.
