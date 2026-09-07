# Raw data — provenance and schema notes

## Source

Every file here was exported by hand from the **eSAKSHI** portal's public
citizen dashboard — `https://mplads.mospi.gov.in/digigov/dashboard.html`
— using its own Excel/CSV/PDF export buttons. No login, no scraper, no
third party. Pulled 2026-09-03/04, 18th-term data (Lok Sabha and Rajya
Sabha tabs), so `data_as_on` in eSAKSHI's own language is that date.

`legacy_16ls_pending/` is a separate, older MIS report (16th Lok Sabha,
2014–2019, "as on 21/08/2022") — kept for cross-validation and the E1
scorecard's historical context, not part of the core 18th-term corpus.

## Directory layout

```
esakshi_ls_18ls/   Lok Sabha tab,  18th term — 543 MPs
esakshi_rs_18ls/   Rajya Sabha tab, 18th term — ~233 MPs
legacy_16ls_pending/  16th LS MP-wise pending-GOI-release report (SSRS export)
```

Filenames are kept exactly as the browser produced them (including the
Lok Sabha set's trailing `" 1"` — the browser's own de-dupe suffix on a
second download). `src/parakh/config.py` maps them explicitly rather
than relying on a renamed, "clean" filename — raw/ stays a faithful
copy of what was actually downloaded.

## Row counts (confirmed against eSAKSHI's own dashboard totals)

| Export | Rajya Sabha | Lok Sabha | Combined |
|---|---:|---:|---:|
| Works Recommended | 25,177 | 106,259 | 131,436 |
| Works Sanctioned | 19,564 | 79,067 | 98,631 |
| Works Completed | 9,956 | 34,258 | 44,214 |
| Expenditure (payments) | 25,100 | 83,906 | 109,006 |
| Allocated Limit (one row per MP) | 232 | 543 | 775 |
| Calamity consent | 21 | 13 | 34 |

## Schema notes that matter for ingestion

- **Every export ends with a `"Grand Total"` footer row** — `parakh.ingest`
  filters it by checking the first column.
- **The two houses are not schema-identical.** Lok Sabha carries a
  `Constituency` column in the slot where Rajya Sabha carries
  `Elected/Nominated` (RS members have no constituency). Reconciled into
  two always-present columns, `constituency` and `elected_or_nominated`,
  each null where it doesn't apply to that house.
- **The `Work`/`WORK` column is composite**: `<work_id>-<category text>`,
  e.g. `WS/MP187/2023-2024/1199-Construction of rooms and halls in
  school and colleges`. `parakh.parse.split_work_field` splits it.
  Prefer the separate `Work category` column over the text after the
  dash where both exist — it's a clean, closed taxonomy.
- **~25% of "Works Recommended" rows carry a literal `NA` instead of a
  real work ID** — confirmed as *expected*, not corrupted: 100%
  correlated with an empty Sanction Date. eSAKSHI only allots a real
  work ID once a district authority sanctions the work; "NA" means
  "recommended, not yet sanctioned." Parsed to the `UNSANCTIONED_WORK_ID`
  sentinel, distinct from `UNPARSEABLE_WORK_ID` (a genuinely malformed
  ID — confirmed rare, <1%) — conflating the two would have hidden real
  parse failures inside a large, benign bucket.
- **A separate, real corruption does exist**: a literal tab-plus-space
  injected between `WS/` and `MP<code>` for a batch of MPs (e.g. MP620,
  MP443) — confirmed in both the composite `Work` field and the
  Expenditure export's own separate `Work ID` column for the same
  works. `parakh.parse.normalize_work_id` strips it from both sides so
  the join key still lines up; without this fix, ~35K real work
  records (MP620/443's entire body of work) would have silently fallen
  out of every peer-comparison and agency detector.
- **The `IDA` field is also composite**: `<district>(<agency name>)`,
  e.g. `SAMBHAL(DISTRICT MAGISTRAE BHIMNAGAR SAMBHAL_IDA)`.
  `parakh.parse.split_ida` splits it; a value with no parenthesised
  agency degrades to `district_raw` = the whole string, `agency` = null.
- **`Work Status` (Sanctioned export) is a real six-stage pipeline**,
  not the three stages assumed in the original plan:
  `Sanction → Time Estimation → Vendor Identification →
  Physical Inspection → Work partially Completed → Work Completed`.
- **The dedicated `Work category` column is nearly useless for
  peer-grouping** — confirmed against the full corpus: 98% of rows are
  `Normal/Others`. The taxonomy that's actually usable ("Construction
  of roads...", "Street lights", "Purchase of ambulances...", etc.)
  lives in the text after the dash in the composite `Work`/`WORK`
  field. The canonical `works` table's `category` column is that
  parsed text (`category_from_work_field`), not the raw `Work category`
  column (kept as `category_broad` in case it's useful for something
  else) — get this backwards and every B1/B2-style peer-relative
  detector groups almost everything into one bucket.
- **The Completed export's `Image` column** (`Images` / `N/A` / blank)
  is real, confirmed geotagged-photo-evidence metadata — this is
  detector A5 (unverified completion).
- **The Expenditure export is transaction-level, not work-level.** A
  single `work_id` can have multiple payment rows (installments) —
  confirmed directly (e.g. work `WS/MP139/2026-2027/229075` has two
  separate payments to the same vendor). A1's ledger-contradiction
  check must sum per `work_id`, never read one row as the full spend.
- **Amounts are plain numeric strings**, no thousands separators, but
  **blank cells occur** (confirmed: one MP's row in the Allocated
  export has an empty amount). `parakh.parse.parse_amount` turns blank
  into null rather than casting it to 0.
- **Dates are `DD-Mon-YYYY`** (e.g. `14-Jun-2023`).
- **Devanagari-script descriptions are lossy in the export**: verified
  at the byte level (not a decoding artifact) that Hindi text comes
  through as literal `?` characters, e.g. `"P.C.C ??? ?? ???????"`.
  `parakh.parse.flag_description_corruption` flags any description
  containing `??` (two or more consecutive `?`) as corrupted, so the
  quantity-extraction pipeline can skip it explicitly rather than
  silently mis-parsing it. Unit-extraction coverage should be reported
  split by state so this doesn't hide inside a national average.

## What's not here yet

17th-Lok-Sabha-and-earlier terms have *not* been confirmed to have the
same per-tile citizen export — worth checking the dashboard's tenure
toggle before assuming multi-term data is available the same way.
