"""Fill the official SIH 2026 idea template with PARAKH's content.

Edits the provided template in place rather than generating a deck from
scratch: the submission rules require that template, so its master,
theme, logo, footer bar and section titles are left exactly as supplied.
Only each slide's body is replaced.

    python tools/build_sih_ppt.py <template.pptx> <output.pptx>

Every figure here is read off the built corpus (see PROJECT_FACTS below),
not estimated. Update those in one place if the corpus is rebuilt.
"""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

EMU = 914400
SLIDE_W = 13.333
FOOTER_TOP = 6.949

# --- palette ---------------------------------------------------------------
NAVY = "1B2A4E"
NAVY_DEEP = "121D38"
AMBER = "B45309"          # accessible on white; the deck's accent
SLATE = "334155"
MUTED = "51607A"
PANEL = "F1F5F9"
BORDER = "CBD5E1"
WHITE = "FFFFFF"
TIER_A_BG, TIER_A_INK = "FFF1F2", "BE123C"
TIER_B_BG, TIER_B_INK = "FFFBEB", "B45309"

PROJECT_FACTS = {
    "works": "1,31,437",
    "flagged": "37,701",
    "flags": "55,750",
    "clean": "60,339",
    "payments": "1,09,006",
    "agencies": "769",
    "mps": "733",
    "states": "36",
    "tests": "172",
}

_id = [4000]


def next_id() -> int:
    _id[0] += 1
    return _id[0]


def emu(inches: float) -> int:
    return int(round(inches * EMU))


def run(text: str, sz: int, color: str, bold: bool = False, italic: bool = False) -> str:
    return (
        f'<a:r><a:rPr lang="en-US" sz="{sz}" b="{1 if bold else 0}" '
        f'i="{1 if italic else 0}" dirty="0">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="Arial"/><a:cs typeface="Arial"/></a:rPr>'
        f"<a:t>{escape(text)}</a:t></a:r>"
    )


def para(
    runs: str,
    align: str = "l",
    bullet: bool = False,
    space_before: int = 0,
    line_spacing: int | None = None,
) -> str:
    marl, indent, buf = (171450, -171450, '<a:buFont typeface="Arial"/><a:buChar char="•"/>') if bullet else (0, 0, "<a:buNone/>")
    ln = f'<a:lnSpc><a:spcPct val="{line_spacing}"/></a:lnSpc>' if line_spacing else ""
    return (
        f'<a:p><a:pPr algn="{align}" marL="{marl}" indent="{indent}">'
        f"{ln}<a:spcBef><a:spcPts val=\"{space_before}\"/></a:spcBef>{buf}</a:pPr>{runs}</a:p>"
    )


def box(
    x: float,
    y: float,
    w: float,
    h: float,
    paragraphs: str,
    fill: str | None = None,
    line: str | None = None,
    anchor: str = "t",
    rounded: bool = False,
    name: str = "Box",
) -> str:
    geom = (
        '<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val 8000"/></a:avLst></a:prstGeom>'
        if rounded
        else '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
    )
    fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else "<a:noFill/>"
    line_xml = (
        f'<a:ln w="9525"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
        if line
        else '<a:ln><a:noFill/></a:ln>'
    )
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{next_id()}" name="{name}"/>'
        f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>'
        f'<a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
        f"{geom}{fill_xml}{line_xml}</p:spPr><p:txBody>"
        f'<a:bodyPr wrap="square" lIns="109728" tIns="54864" rIns="109728" bIns="54864" '
        f'anchor="{anchor}"><a:noAutofit/></a:bodyPr><a:lstStyle/>{paragraphs}</p:txBody></p:sp>'
    )


def arrow(x: float, y: float, w: float, h: float) -> str:
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{next_id()}" name="Arrow"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
        f'<a:prstGeom prst="rightArrow"><a:avLst/></a:prstGeom>'
        f'<a:solidFill><a:srgbClr val="{AMBER}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>'
        f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="en-US"/></a:p></p:txBody></p:sp>'
    )


def panel(x: float, y: float, w: float, h: float, heading: str, bullets: list[str], sz: int = 1100) -> str:
    """A titled card: navy header strip over a bordered body."""
    head_h = 0.40
    out = box(
        x, y, w, head_h,
        para(run(heading, 1200, WHITE, bold=True), align="ctr"),
        fill=NAVY, anchor="ctr", name="PanelHead",
    )
    body = "".join(para(run(b, sz, SLATE), bullet=True, space_before=500) for b in bullets)
    out += box(x, y + head_h, w, h - head_h, body, fill=WHITE, line=BORDER, name="PanelBody")
    return out


def metric(x: float, y: float, w: float, h: float, value: str, label: str) -> str:
    paras = para(run(value, 2000, NAVY, bold=True), align="ctr") + para(
        run(label, 1000, MUTED), align="ctr", space_before=200
    )
    return box(x, y, w, h, paras, fill=PANEL, line=BORDER, anchor="ctr", rounded=True, name="Metric")


def band(x: float, y: float, w: float, h: float, lead: str, text: str, fill: str = NAVY_DEEP) -> str:
    paras = para(run(lead, 1200, "F2C14E", bold=True)) + para(run(text, 1150, WHITE), space_before=300)
    return box(x, y, w, h, paras, fill=fill, anchor="ctr", name="Band")


def strip(x: float, y: float, w: float, h: float, text: str) -> str:
    return box(
        x, y, w, h,
        para(run(text, 1300, WHITE, bold=True), align="ctr"),
        fill=NAVY, anchor="ctr", name="Strip",
    )


# --- slide bodies ----------------------------------------------------------

L, R = 0.35, 12.98
FULL = R - L


def slide2() -> str:
    out = strip(L, 1.26, FULL, 0.58,
                "PARAKH — a review queue for MPLADS implementation records. Not a verdict.")

    cols = [
        ("THE PROBLEM", [
            f"MPLADS funds ₹5 crore of local works per MP each year — {PROJECT_FACTS['works']} works this term",
            "Sanctions, payments and completion status sit in separate exports that are never joined",
            "No single place a citizen, auditor or ministry can see the scheme whole",
            "Manual audit reaches a small sample, years after the money moved",
            "An automated tool that names culprits is a defamation engine, not oversight",
        ]),
        ("OUR SOLUTION", [
            "A batch pipeline joins the exports into one queryable corpus",
            "13 detectors surface works that warrant a second look",
            "Every flag states its evidence in one plain, checkable sentence",
            "Every flag carries a plausible innocent explanation, shown by default",
            "Reviewers close a flag with a note — suppressed, never deleted, always reversible",
        ]),
        ("INNOVATION AND UNIQUENESS", [
            "Flags attach to works. Members of Parliament are never ranked",
            "Two tiers, always visible: A is arithmetic, B is peer-relative",
            "Detectors abstain below 30 peers instead of guessing on noise",
            "Restraint enforced by tests in CI, not promised in a slide",
            "Ships 13 of 16 planned detectors — and says so inside the product",
        ]),
    ]
    w = 4.03
    for i, (head, bullets) in enumerate(cols):
        out += panel(L + i * (w + 0.27), 2.02, w, 2.62, head, bullets)

    metrics = [
        (PROJECT_FACTS["works"], "works ingested, 18th term"),
        ("13", "detectors: 5 deterministic, 8 statistical"),
        ("5", "independent validation methods"),
        ("0", "rankings of any Member of Parliament"),
    ]
    mw = 3.00
    for i, (v, lab) in enumerate(metrics):
        out += metric(L + i * (mw + 0.21), 4.84, mw, 0.92, v, lab)

    out += band(L, 5.92, FULL, 0.80, "Why this is hard to copy:",
                "The restraint is executable. A test in the build greps the whole codebase for a fixed list of "
                "accusatory words, and the assistant refuses to rank members at all — so the guarantee survives "
                "contact with a demo, a judge, or a rushed reviewer.")
    return out


def slide3() -> str:
    out = strip(L, 1.26, FULL, 0.52,
                "Python · Polars · DuckDB · scikit-learn · LightGBM · NetworkX · FastAPI · "
                "Next.js + TypeScript — entirely open source")

    stages = [
        ("1  INGEST", "eSAKSHI CSV exports → Polars → clean Parquet. Hand-downloaded, no scraper."),
        ("2  DETECT", "13 detectors and peer distributions computed offline into DuckDB."),
        ("3  SERVE", "FastAPI, read-only. Every endpoint is a SELECT; nothing is computed live."),
        ("4  REVIEW", "Next.js queue: evidence, benign explanation, reversible overrides."),
    ]
    w, gap = 2.85, 0.35
    for i, (head, text) in enumerate(stages):
        x = L + i * (w + gap)
        paras = para(run(head, 1250, WHITE, bold=True)) + para(run(text, 1000, WHITE), space_before=300)
        out += box(x, 1.94, w, 1.34, paras, fill=NAVY, anchor="ctr", rounded=True, name="Stage")
        if i < 3:
            out += arrow(x + w + 0.06, 2.46, 0.23, 0.30)

    tier_a = [
        "A1  Ledger contradiction — payment exceeds its sanction",
        "A2  Phantom completion — complete, almost nothing paid",
        "A3  Duplicate record — same work ID twice in the export",
        "A4  Orphan sanction — missing agency, state or category",
        "A5  Unverified completion — no photo evidence on file",
    ]
    tier_b = [
        "B1 Peer cost outlier      B2 Cost-per-unit outlier",
        "B3 Stalled vs category P95      B4 Threshold bunching",
        "B5 Work splitting      B6 Agency concentration",
        "B7 Year-end bunching      B8 Near-duplicate funding",
        "Always states its peer group and n; abstains below 30 peers",
    ]
    pw = 6.18
    out += box(L, 3.42, pw, 0.38,
               para(run("TIER A — DETERMINISTIC INTEGRITY  (5)", 1150, TIER_A_INK, bold=True), align="ctr"),
               fill=TIER_A_BG, anchor="ctr", name="TierAHead")
    out += box(L, 3.80, pw, 1.62,
               "".join(para(run(t, 1050, SLATE), space_before=400) for t in tier_a),
               fill=WHITE, line=BORDER, name="TierABody")
    out += box(L + pw + 0.27, 3.42, pw, 0.38,
               para(run("TIER B — PEER-RELATIVE STATISTICAL  (8)", 1150, TIER_B_INK, bold=True), align="ctr"),
               fill=TIER_B_BG, anchor="ctr", name="TierBHead")
    out += box(L + pw + 0.27, 3.80, pw, 1.62,
               "".join(para(run(t, 1050, SLATE), space_before=400) for t in tier_b),
               fill=WHITE, line=BORDER, name="TierBBody")

    out += band(L, 5.58, FULL, 1.10, "Reproducible by construction:",
                "Raw CSV → Parquet → DuckDB is one command and a few seconds. The same input always yields the "
                f"same flags, so any reviewer can re-run the pipeline and reproduce every number. {PROJECT_FACTS['tests']} "
                "automated tests cover the detectors, the validation methods and the restraint rules themselves.")
    return out


def slide4() -> str:
    out = strip(L, 1.26, FULL, 0.52,
                f"Already running end to end on the full public corpus — {PROJECT_FACTS['works']} works, not a mock-up.")

    out += panel(L, 1.92, 5.55, 2.28, "WHY IT IS FEASIBLE", [
        f"Runs today on the complete 18th-term corpus: {PROJECT_FACTS['works']} works, {PROJECT_FACTS['payments']} payments",
        "Batch and deterministic — no GPU, no per-query model cost, no network at run time",
        "Open-source stack throughout; no licence, quota or vendor lock-in",
        "Rebuilds in seconds, so a reviewer can re-run it and reproduce every flag",
        f"{PROJECT_FACTS['tests']} automated tests, including the restraint guarantees",
    ], sz=1100)

    risks = [
        "Naming individuals would defame  →  flags attach to works; ranking members is refused in code",
        "Sparse source fields (quantity 4.9%, photos 23.8%)  →  detectors abstain rather than infer",
        "No labelled ground truth exists  →  five independent validation methods, results published in full",
        "Small peer groups mislead  →  Tier B abstains below 30 peers",
        "Benign patterns look irregular  →  every flag ships its innocent explanation alongside",
    ]
    out += panel(6.20 + 0.10, 1.92, 6.68, 2.28, "RISKS AND HOW WE HANDLE THEM", risks, sz=1050)

    out += band(L, 4.36, FULL, 0.98, "Applied to ourselves:",
                "We did not build the planned third tier — an Isolation Forest, a Local Outlier Factor model and a "
                "composite 0–100 priority score. 13 of 16 planned detectors shipped, and that is stated on the "
                "product's own Methodology page, not only in this deck.")

    chips = [
        ("FEASIBLE TODAY", "Working software on real public data"),
        ("SCALABLE NATIONWIDE", "Same pipeline covers every state and both Houses"),
        ("LOW COST TO RUN", "Commodity hardware, open source, offline"),
    ]
    cw = 4.03
    for i, (head, sub) in enumerate(chips):
        paras = para(run(head, 1200, NAVY, bold=True), align="ctr") + para(
            run(sub, 950, MUTED), align="ctr", space_before=200)
        out += box(L + i * (cw + 0.27), 5.52, cw, 0.98, paras, fill=PANEL, line=BORDER,
                   anchor="ctr", rounded=True, name="Chip")
    return out


def slide5() -> str:
    out = strip(L, 1.26, FULL, 0.52,
                f"From {PROJECT_FACTS['works']} scattered records to a queue a human can actually work through.")

    who = [
        ("MoSPI AND DISTRICTS", "A worklist ordered by evidence rather than by hunch or by complaint"),
        ("AUDITORS", "A reproducible shortlist with the arithmetic already shown and citable"),
        ("CITIZENS AND PRESS", "The same public data, finally joined and searchable in one place"),
        ("IMPLEMENTING AGENCIES", "A chance to explain an ordinary pattern before anything escalates"),
    ]
    w = 3.00
    for i, (head, text) in enumerate(who):
        paras = para(run(head, 1100, WHITE, bold=True), align="ctr") + para(
            run(text, 950, WHITE), align="ctr", space_before=250)
        out += box(L + i * (w + 0.21), 1.92, w, 1.30, paras, fill=NAVY, anchor="ctr",
                   rounded=True, name="Audience")

    out += panel(L, 3.36, 6.18, 1.92, "BEFORE", [
        "Sanctions, payments and completion never joined",
        "Oversight by small sample, years after the spending",
        "Irregularities surface as allegations about people",
        "No way to show a pattern was ordinary after all",
    ], sz=1050)
    out += panel(L + 6.18 + 0.27, 3.36, 6.18, 1.92, "AFTER", [
        f"One corpus: {PROJECT_FACTS['works']} works, {PROJECT_FACTS['payments']} payments, {PROJECT_FACTS['agencies']} agencies",
        f"{PROJECT_FACTS['flagged']} works flagged with evidence attached",
        f"{PROJECT_FACTS['clean']} examined by every detector and cleared",
        "Reviewers close flags with a note — reversible, and audited",
    ], sz=1050)

    benefits = [
        ("GOVERNANCE", "Scrutiny that is traceable, reproducible and contestable"),
        ("ECONOMIC", "Attention aimed at the works where evidence justifies it"),
        ("SOCIAL", "Public money made legible without accusing anyone"),
        ("NATIONAL SCALE", f"{PROJECT_FACTS['states']} states, {PROJECT_FACTS['mps']} MPs, both Houses, one pipeline"),
    ]
    bw = 3.00
    for i, (head, text) in enumerate(benefits):
        paras = para(run(head, 1050, AMBER, bold=True), align="ctr") + para(
            run(text, 950, SLATE), align="ctr", space_before=200)
        out += box(L + i * (bw + 0.21), 5.42, bw, 1.05, paras, fill=PANEL, line=BORDER,
                   anchor="ctr", rounded=True, name="Benefit")

    out += box(L, 6.52, FULL, 0.36,
               para(run("We do not tell anyone who is at fault. We show which records do not add up, "
                        "what would explain them, and let a human decide.", 1000, MUTED, italic=True), align="ctr"),
               name="Kicker")
    return out


def slide6() -> str:
    out = strip(L, 1.26, FULL, 0.52,
                "Public data, published methods, and a repository anyone can run.")

    cols = [
        ("DATA AND GOVERNMENT SOURCES", [
            "eSAKSHI — MPLADS citizen dashboard, mplads.mospi.gov.in (all works, payments and completion exports)",
            "MPLADS Guidelines, Ministry of Statistics and Programme Implementation",
            "Comptroller and Auditor General of India — performance audit reports on MPLADS",
            "Lok Sabha and Rajya Sabha member directories, sansad.in",
        ]),
        ("METHODS AND LITERATURE", [
            "Leys et al., robust outlier detection with the median absolute deviation",
            "Blondel et al., fast unfolding of communities in large networks (Louvain)",
            "Ke et al., LightGBM: a highly efficient gradient boosting decision tree",
            "Saito and Rehmsmeier, precision-recall over ROC on imbalanced data",
            "Benford-style bunching and threshold-avoidance in public procurement",
        ]),
        ("TECHNOLOGY", [
            "DuckDB — duckdb.org  ·  Polars — pola.rs",
            "scikit-learn — scikit-learn.org  ·  NetworkX — networkx.org",
            "FastAPI — fastapi.tiangolo.com  ·  Next.js — nextjs.org",
            "LightGBM — lightgbm.readthedocs.io",
        ]),
    ]
    w = 4.03
    for i, (head, items) in enumerate(cols):
        out += panel(L + i * (w + 0.27), 1.92, w, 3.30, head, items, sz=1000)

    out += band(L, 5.36, FULL, 1.05, "Source code and reproducible build:",
                "github.com/Kartik-Garg-13/mplad_sih  —  the full pipeline, the 13 detectors, the five validation "
                f"methods and {PROJECT_FACTS['tests']} tests. Clone it, run two commands, and every figure in this "
                "deck rebuilds from the published source data.")
    return out


TITLE_LINES = [
    ("Problem Statement ID – SIH26102", True),
    ("Problem Statement Title – Fraud & Anomaly Detection in MPLADS Scheme", True),
    ("Theme – <<fill from the SIH portal>>", False),
    ("PS Category – Software", True),
    ("Team ID – <<fill from the SIH portal>>", False),
    ("Team Name – <<registered team name>>", False),
]


def slide1_body() -> str:
    paras = para(
        run("PARAKH — a review queue, not a verdict", 1600, NAVY, bold=True),
        space_before=0,
    )
    paras += para(
        run("Anomaly flagging for MPLADS implementation records", 1200, MUTED),
        space_before=300,
    )
    for text, filled in TITLE_LINES:
        paras += para(
            run(text, 1400, SLATE if filled else AMBER, bold=True),
            bullet=True,
            space_before=900,
        )
    return paras


# --- template surgery ------------------------------------------------------


def drop_shape(xml: str, name: str) -> str:
    """Remove the whole <p:sp> whose cNvPr carries `name`."""
    marker = xml.find(f'name="{name}"')
    if marker == -1:
        raise SystemExit(f"shape {name!r} not found")
    start = xml.rfind("<p:sp>", 0, marker)
    end = xml.find("</p:sp>", marker)
    if start == -1 or end == -1:
        raise SystemExit(f"could not bound shape {name!r}")
    return xml[:start] + xml[end + len("</p:sp>") :]


def body_shape_name(xml: str) -> str:
    m = re.search(r'name="(TextBox \d+)"', xml)
    if not m:
        raise SystemExit("no body TextBox found")
    return m.group(1)


def replace_paragraphs(xml: str, shape_name: str, paragraphs: str) -> str:
    marker = xml.find(f'name="{shape_name}"')
    start = xml.find("<p:txBody>", marker)
    end = xml.find("</p:txBody>", start)
    head_end = xml.find("<a:lstStyle/>", start) + len("<a:lstStyle/>")
    return xml[:head_end] + paragraphs + xml[end:]


def set_text(xml: str, old: str, new: str) -> str:
    return xml.replace(f"<a:t>{old}</a:t>", f"<a:t>{escape(new)}</a:t>")


def main(template: str, output: str) -> None:
    work = Path(output).with_suffix(".work")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    with zipfile.ZipFile(template) as z:
        names = z.namelist()
        z.extractall(work)

    slides_dir = work / "ppt" / "slides"
    builders = {2: slide2, 3: slide3, 4: slide4, 5: slide5, 6: slide6}

    for n in range(1, 7):
        path = slides_dir / f"slide{n}.xml"
        xml = path.read_text(encoding="utf-8")

        if n == 1:
            xml = replace_paragraphs(xml, body_shape_name(xml), slide1_body())
        else:
            name = body_shape_name(xml)
            xml = drop_shape(xml, name)
            xml = xml.replace("</p:spTree>", builders[n]() + "</p:spTree>")
            # Sized explicitly: the oval inherits a size that wraps
            # "PARAKH" onto two lines inside its narrow ellipse.
            xml = xml.replace(
                '<a:r><a:rPr lang="en-US" dirty="0"/><a:t>Your Team Name</a:t></a:r>',
                f'<a:r><a:rPr lang="en-US" sz="1400" b="1" dirty="0">'
                f'<a:solidFill><a:srgbClr val="{NAVY}"/></a:solidFill>'
                f'</a:rPr><a:t>PARAKH</a:t></a:r>',
            )

        # Kept short: the footer placeholder is 3.5in wide, and the fuller
        # wording wrapped onto a second line over the blue bar.
        xml = set_text(xml, "@SIH Idea submission- Template", "PARAKH  ·  SIH26102  ·  MoSPI")
        path.write_text(xml, encoding="utf-8")

    # Slide 7 is the template's own instruction page; the instructions say
    # to delete it before uploading.
    remove_slide(work, 7)

    if Path(output).exists():
        Path(output).unlink()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for name in names:
            src = work / name
            if src.exists():
                z.write(src, name)
    shutil.rmtree(work)
    print(f"wrote {output}")


def remove_slide(work: Path, n: int) -> None:
    """Drop a slide and every reference the package keeps to it."""
    pres = work / "ppt" / "presentation.xml"
    rels = work / "ppt" / "_rels" / "presentation.xml.rels"

    rels_xml = rels.read_text(encoding="utf-8")
    m = re.search(rf'<Relationship Id="([^"]+)"[^>]*Target="slides/slide{n}\.xml"[^>]*/>', rels_xml)
    if not m:
        return
    rid = m.group(1)
    rels.write_text(rels_xml.replace(m.group(0), ""), encoding="utf-8")

    pres_xml = pres.read_text(encoding="utf-8")
    pres_xml = re.sub(rf'<p:sldId id="\d+" r:id="{rid}"/>', "", pres_xml)
    pres.write_text(pres_xml, encoding="utf-8")

    # The slide's own notes page goes with it — leaving it behind is a
    # dangling reference back to a slide that no longer exists, which
    # PowerPoint reports as a corrupt file.
    dead_parts = [f"ppt/slides/slide{n}.xml"]
    slide_rels = work / "ppt" / "slides" / "_rels" / f"slide{n}.xml.rels"
    if slide_rels.exists():
        for target in re.findall(r'Target="\.\./(notesSlides/notesSlide\d+\.xml)"',
                                 slide_rels.read_text(encoding="utf-8")):
            dead_parts.append(f"ppt/{target}")

    ct = work / "[Content_Types].xml"
    ct_xml = ct.read_text(encoding="utf-8")
    for part in dead_parts:
        ct_xml = re.sub(rf'<Override PartName="/{re.escape(part)}"[^>]*/>', "", ct_xml)
    ct.write_text(ct_xml, encoding="utf-8")

    for part in dead_parts:
        p = work / part
        p.unlink(missing_ok=True)
        (p.parent / "_rels" / f"{p.name}.rels").unlink(missing_ok=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
