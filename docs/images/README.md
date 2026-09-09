# Screenshot capture guide

**Audience:** whoever is taking the screenshots.

**Status: no screenshots have been captured yet.** This directory holds the guide and
the naming convention. Nothing here is a mock-up, and nothing should be. If an image
appears in this directory it is a real capture of the running application.

## Why this guide exists

Screenshots are the first thing most readers look at and the easiest place to leak
something. A capture taken from a working session can contain a session token in a URL,
an API key in a settings panel, a real hostname, or an unrelated browser tab with the
photographer's email address in the title.

Every image in this directory must be reproducible from the seeded demo database by
someone who has never seen your machine.

## Before you capture anything

Set up a clean, deterministic state:

```bash
make reset      # or: make setup, on a fresh database
make api
make ui
make pipeline   # only if you want the executed-rule alerts in the shots
make smoke      # confirm six passes before you start
```

Then:

- Use a **private or guest browser window**. No extensions, no bookmarks bar, no other
  tabs, no profile avatar.
- Size the window to **1440 by 900**. Consistent framing makes the set look like a set.
- Confirm `.env` is not open in any visible editor or terminal.
- Do not capture the terminal where `make setup` printed the generated password.

## Naming

`NN-view-what-it-shows.png`, lowercase, hyphens only. The number is the order in
[docs/demo.md](../demo.md), so the set reads as the story.

```
01-dashboard-critical-alerts.png
02-investigations-critical-filter.png
03-alert-detail-evidence.png
04-alert-detail-mitre.png
05-alert-ai-triage.png
06-case-detail-activity.png
07-case-report-draft.png
08-audit-history.png
```

## The set

| File | View | Required data state | What the reader should notice |
|---|---|---|---|
| `01-dashboard-critical-alerts.png` | Dashboard | Seeded database | The critical alert count and severity breakdown. This is the README's header image, so it must look composed. |
| `02-investigations-critical-filter.png` | Investigations, severity filtered to Critical | Seeded database | Exactly two rows: `ALERT-0006` and `ALERT-0005`. |
| `03-alert-detail-evidence.png` | `ALERT-0005`, Timeline/Evidence tab | Seeded database | Three linked events at 02:08:00, 02:08:15, 02:08:30. The evidence is attached to the alert, not summarised away. |
| `04-alert-detail-mitre.png` | `ALERT-0005`, MITRE tab | Seeded database | T1098.004, Account Manipulation: SSH Authorized Keys, Persistence tactic. |
| `05-alert-ai-triage.png` | `ALERT-0005`, AI triage result | `AI_ENABLED=true`, `AI_PROVIDER=fake`, triage already requested | The citation list, not the prose. Five evidence IDs, all from the alert's own context. Crop to include them. |
| `06-case-detail-activity.png` | `CASE-2026-0004`, Activity tab | Case escalated, note added, status and priority changed | Four entries: `case_created`, `note`, `status_change`, `priority_change`. Three were recorded automatically. |
| `07-case-report-draft.png` | `CASE-2026-0004`, report draft | Report generated | The seven sections, and that evidence references are present. |
| `08-audit-history.png` | Audit history, as Admin | Full narrative completed | Eight actions attributed to `demo-admin`, in order, each with an outcome. |

Follow [docs/demo.md](../demo.md) in order and each shot presents itself.

## Secret hygiene checklist

Run through this for **every** image before committing it. Open the file and look; do
not go from memory.

- [ ] No session token, bearer token, or API key anywhere, including in a URL
- [ ] No `.env` contents, and no settings panel showing a populated secret field
- [ ] No real hostname, public IP, or internal domain. The seeded values
      (`ubuntu-target-01`, `192.168.64.2`, `192.168.64.8`) are synthetic and fine
- [ ] No real person's name or email address, including in a browser profile chip,
      window title, or notification
- [ ] No bookmarks bar, no extension icons, no unrelated tabs
- [ ] No local filesystem path that reveals a home directory
- [ ] The data shown is seeded demo data, not anything from a real environment

## A decision to make first

The seeded dataset uses `mollysohaney` as the compromised username, defined at
`db/seed.py:40`. It appears in alert titles, event messages, and file paths such as
`/home/mollysohaney/.ssh/authorized_keys`, so it will be visible in most of these
screenshots.

That is the repository owner's own name. It is not a leak, and it is a reasonable choice
for a personal portfolio project. But it should be a deliberate choice rather than an
accident, because it is the one identifier in the demo that refers to a real person.

Changing it means editing `db/seed.py` and the tests that assert on it, so decide before
capturing rather than after.

## Format and size

PNG. Keep each file under roughly 300 KB; run them through `pngquant`, `oxipng`, or an
equivalent before committing. These are read on a phone as often as a laptop, so
legibility at half size matters more than pixel count.

## After capturing

1. Open every image and walk the checklist above.
2. Commit the images.
3. Update the screenshot placeholder in [the README](../../README.md) to reference
   `docs/images/01-dashboard-critical-alerts.png`.
4. Add the others to [docs/demo.md](../demo.md) at the steps they illustrate.

## Related

- [docs/demo.md](../demo.md) — the narrative these images follow
- [README](../../README.md) — where the header image goes
- [docs/release-readiness.md](../release-readiness.md) — finding S1, the seeded username
