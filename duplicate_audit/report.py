from __future__ import annotations

import html
import json
from collections import Counter
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from .core import connected_candidate_clusters


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _safe_href(value: Any) -> str:
    raw = "" if value is None else str(value).strip()
    parsed = urlsplit(raw)
    return raw if parsed.scheme in {"http", "https"} else ""


def summarize_candidates(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(
        str(candidate.get("final_classification", "unprocessed"))
        for candidate in candidates
    )
    clusters = connected_candidate_clusters(candidates)
    return {
        "candidate_pair_count": len(candidates),
        "classification_counts": dict(sorted(counts.items())),
        "review_cluster_count": len(clusters),
        "owners_in_review_clusters": len(
            {person_id for cluster in clusters for person_id in cluster}
        ),
    }


def _string_list(values: Any) -> str:
    if not isinstance(values, list) or not values:
        return '<span class="muted">None recorded</span>'
    return "<ul>" + "".join(f"<li>{_escape(value)}</li>" for value in values) + "</ul>"


def _owner_card(card: Mapping[str, Any]) -> str:
    person_id = int(card["person_id"])
    profile_url = _safe_href(card.get("profile_url"))
    image_url = _safe_href(card.get("image_url"))
    details = card.get("details") if isinstance(card.get("details"), Mapping) else {}
    socials = card.get("social_profiles")
    social_html = '<span class="muted">None recorded</span>'
    if isinstance(socials, list) and socials:
        items = []
        for profile in socials:
            if not isinstance(profile, Mapping):
                continue
            url = _safe_href(profile.get("url"))
            label = profile.get("type") or profile.get("url")
            if url:
                items.append(
                    f'<li><a href="{_escape(url)}" target="_blank" '
                    f'rel="noreferrer">{_escape(label)}</a></li>'
                )
        if items:
            social_html = "<ul>" + "".join(items) + "</ul>"

    detail_rows = []
    for key, value in details.items():
        if str(value).strip():
            detail_rows.append(
                f"<dt>{_escape(str(key).replace('_', ' ').title())}</dt>"
                f"<dd>{_escape(value)}</dd>"
            )
    image_html = (
        f'<img class="portrait" src="{_escape(image_url)}" '
        f'alt="Profile image for {_escape(card.get("full_name"))}">'
        if image_url
        else '<div class="portrait placeholder">No image</div>'
    )
    title = _escape(card.get("full_name") or f"Person {person_id}")
    title_html = (
        f'<a href="{_escape(profile_url)}" target="_blank" rel="noreferrer">'
        f"{title}</a>"
        if profile_url
        else title
    )
    return f"""
      <article class="owner-card">
        <div class="owner-heading">{image_html}<div><h3>{title_html}</h3>
        <div class="person-id">Person ID {person_id}</div></div></div>
        <dl>{''.join(detail_rows) or '<dt>Details</dt><dd class="muted">Not enriched</dd>'}</dl>
        <h4>Aliases</h4>{_string_list(card.get('aliases'))}
        <h4>Employers</h4>{_string_list(card.get('employers'))}
        <h4>Known for</h4><p>{_escape(card.get('known_for')) or '<span class="muted">Not recorded</span>'}</p>
        <h4>Social profiles</h4>{social_html}
        <h4>Vessels</h4>{_string_list(card.get('vessels'))}
      </article>
    """


def _judgment_block(title: str, wrapper: Mapping[str, Any] | None) -> str:
    if not wrapper:
        return f'<section class="judgment"><h3>{_escape(title)}</h3><p class="muted">Not run</p></section>'
    judgment = wrapper.get("judgment")
    if not isinstance(judgment, Mapping):
        return f'<section class="judgment"><h3>{_escape(title)}</h3><p class="muted">Unavailable</p></section>'
    return f"""
      <section class="judgment">
        <h3>{_escape(title)}</h3>
        <p><span class="status {_escape(judgment.get('classification'))}">{_escape(judgment.get('classification'))}</span>
        <strong>{_escape(judgment.get('confidence'))}% confidence</strong></p>
        <p>{_escape(judgment.get('summary'))}</p>
        <div class="evidence-grid">
          <div><h4>For a match</h4>{_string_list(judgment.get('evidence_for'))}</div>
          <div><h4>Against a match</h4>{_string_list(judgment.get('evidence_against'))}</div>
          <div><h4>Missing evidence</h4>{_string_list(judgment.get('missing_evidence'))}</div>
        </div>
        <p><strong>More complete record:</strong> {_escape(judgment.get('more_complete_person_id') or 'No preference')} — {_escape(judgment.get('completeness_reason'))}</p>
      </section>
    """


def _candidate_card(candidate: Mapping[str, Any]) -> str:
    candidate_id = str(candidate["candidate_id"])
    final = str(candidate.get("final_classification", "unprocessed"))
    records = candidate.get("records")
    record_html = ""
    if isinstance(records, list):
        record_html = "".join(
            _owner_card(record) for record in records if isinstance(record, Mapping)
        )
    retrieval = candidate.get("retrieval")
    retrieval = retrieval if isinstance(retrieval, Mapping) else {}
    signals = retrieval.get("signals")
    signal_texts = []
    if isinstance(signals, list):
        for signal in signals:
            if isinstance(signal, Mapping):
                signal_texts.append(signal.get("description") or signal.get("type"))
    embedding_scores = retrieval.get("embedding_scores")
    score_html = ""
    if isinstance(embedding_scores, Mapping):
        score_html = ", ".join(
            f"{_escape(view)} {_escape(score)}" for view, score in embedding_scores.items()
        )
    processing_error = candidate.get("processing_error")
    error_html = (
        f'<p class="error"><strong>Processing error:</strong> {_escape(processing_error)}</p>'
        if processing_error
        else ""
    )
    return f"""
    <section class="candidate" id="{_escape(candidate_id)}" data-status="{_escape(final)}">
      <div class="candidate-title">
        <div><h2>{_escape(candidate_id.replace('_', ' '))}</h2>
        <p class="muted">Embedding evidence: {score_html or 'strong-field retrieval only'}</p></div>
        <span class="status {_escape(final)}">{_escape(final)}</span>
      </div>
      {error_html}
      <div class="records">{record_html}</div>
      <section class="retrieval"><h3>Why this pair was retrieved</h3>{_string_list(signal_texts)}</section>
      {_judgment_block('Primary AI review', candidate.get('primary'))}
      {_judgment_block('Independent skeptical verification', candidate.get('verifier'))}
      <section class="manual-review">
        <h3>Manual decision</h3>
        <label>Decision
          <select class="manual-decision" data-candidate="{_escape(candidate_id)}">
            <option value="unreviewed">Unreviewed</option>
            <option value="confirmed_duplicate">Confirmed duplicate</option>
            <option value="possible_duplicate">Possible duplicate</option>
            <option value="distinct_people">Distinct people</option>
            <option value="needs_research">Needs more research</option>
          </select>
        </label>
        <label>Reviewer notes
          <textarea class="manual-notes" data-candidate="{_escape(candidate_id)}" rows="3"></textarea>
        </label>
      </section>
    </section>
    """


def render_audit_report(audit: Mapping[str, Any]) -> str:
    candidates_value = audit.get("candidates")
    candidates = candidates_value if isinstance(candidates_value, list) else []
    summary_value = audit.get("summary")
    summary = summary_value if isinstance(summary_value, Mapping) else summarize_candidates(candidates)
    source_value = audit.get("source")
    source = source_value if isinstance(source_value, Mapping) else {}
    configuration_value = audit.get("configuration")
    configuration = (
        configuration_value if isinstance(configuration_value, Mapping) else {}
    )
    counts = summary.get("classification_counts", {})
    count_cards = "".join(
        f'<div class="metric"><strong>{_escape(value)}</strong><span>{_escape(key)}</span></div>'
        for key, value in counts.items()
    )
    candidate_html = "".join(
        _candidate_card(candidate)
        for candidate in candidates
        if isinstance(candidate, Mapping)
    )
    review_key = "owner-duplicate-review:" + str(
        source.get("owner_snapshot_sha256", "unknown")
    )
    source_json = _escape(json.dumps(source, ensure_ascii=False, indent=2))
    config_json = _escape(json.dumps(configuration, ensure_ascii=False, indent=2))

    prefix = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Owner duplicate audit</title>
  <style>
    :root { --ink:#17202a; --muted:#68717c; --line:#d8dee5; --paper:#fff; --wash:#f4f7f9; --navy:#0d3558; --gold:#c99b3b; }
    * { box-sizing:border-box; }
    body { margin:0; color:var(--ink); background:var(--wash); font:15px/1.48 system-ui,Segoe UI,sans-serif; }
    header { background:var(--navy); color:white; padding:28px max(24px,calc((100% - 1320px)/2)); }
    header h1 { margin:0 0 6px; font-size:30px; }
    header p { margin:3px 0; color:#dce9f3; }
    main { max-width:1320px; margin:auto; padding:24px; }
    .warning { border-left:5px solid var(--gold); background:#fff8e8; padding:14px 18px; margin-bottom:20px; }
    .metrics { display:flex; flex-wrap:wrap; gap:12px; margin:18px 0; }
    .metric { min-width:150px; padding:12px 15px; border:1px solid var(--line); background:var(--paper); border-radius:8px; }
    .metric strong,.metric span { display:block; }.metric strong { font-size:22px; }.metric span { color:var(--muted); }
    .toolbar { position:sticky; top:0; z-index:5; display:flex; gap:14px; align-items:center; flex-wrap:wrap; padding:13px; background:rgba(244,247,249,.96); border-bottom:1px solid var(--line); }
    button,select,textarea { font:inherit; } button { border:0; border-radius:6px; padding:9px 13px; color:white; background:var(--navy); cursor:pointer; }
    .candidate { margin:24px 0; padding:20px; border:1px solid var(--line); border-radius:10px; background:var(--paper); box-shadow:0 2px 8px #1d2b3810; }
    .candidate-title { display:flex; justify-content:space-between; gap:18px; align-items:start; }.candidate-title h2 { margin:0; }
    .records { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; margin:18px 0; }
    .owner-card,.judgment,.retrieval,.manual-review { border:1px solid var(--line); border-radius:8px; padding:15px; }
    .owner-heading { display:flex; gap:14px; align-items:center; }.owner-heading h3 { margin:0; }.person-id,.muted { color:var(--muted); }
    .portrait { width:84px; height:84px; border-radius:6px; object-fit:cover; background:#e9edf1; }.placeholder { display:grid; place-items:center; color:var(--muted); font-size:12px; }
    dl { display:grid; grid-template-columns:minmax(115px,35%) 1fr; gap:5px 10px; } dt { font-weight:650; } dd { margin:0; overflow-wrap:anywhere; }
    h4 { margin-bottom:4px; } ul { margin-top:4px; padding-left:21px; }
    .status { display:inline-block; padding:5px 9px; border-radius:999px; background:#e8edf2; font-weight:700; text-transform:capitalize; }
    .probable_duplicate { background:#ffd7d7; color:#7d1111; }.possible_duplicate,.needs_manual_review { background:#ffedbf; color:#714d00; }.probably_distinct { background:#dff2e4; color:#155c2a; }.insufficient_evidence,.unprocessed { background:#e8edf2; color:#45515d; }
    .evidence-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
    .manual-review { margin-top:16px; background:#f7fafc; }.manual-review label { display:block; margin:10px 0; }.manual-review select,.manual-review textarea { display:block; width:100%; margin-top:5px; padding:8px; border:1px solid #abb7c2; border-radius:5px; }
    .error { background:#fff0f0; color:#801818; padding:10px; }.technical summary { cursor:pointer; font-weight:650; }.technical pre { overflow:auto; background:#101820; color:#e7eef4; padding:12px; }
    @media (max-width:850px) { .records,.evidence-grid { grid-template-columns:1fr; } .candidate-title { display:block; } }
    @media print { .toolbar,.manual-review button { display:none; } .candidate { break-inside:avoid; box-shadow:none; } }
  </style>
</head>
<body>
"""
    body = f"""
<header><h1>Owner duplicate audit</h1>
  <p>Generated {_escape(audit.get('generated_at'))}</p>
  <p>Source owner count: {_escape(source.get('owner_count'))}; candidate pairs: {_escape(summary.get('candidate_pair_count'))}</p>
</header>
<main>
  <div class="warning"><strong>Manual-review report only.</strong> AI classifications are suggestions. This audit contains no live write or merge operation.</div>
  <div class="metrics">{count_cards}</div>
  <div class="toolbar">
    <label>Show <select id="status-filter"><option value="all">All classifications</option>
      <option value="probable_duplicate">Probable duplicates</option><option value="possible_duplicate">Possible duplicates</option>
      <option value="needs_manual_review">Needs manual review</option><option value="insufficient_evidence">Insufficient evidence</option>
      <option value="probably_distinct">Probably distinct</option></select></label>
    <button type="button" id="export-review">Export manual decisions</button>
    <span id="visible-count" class="muted"></span>
  </div>
  {candidate_html or '<p>No candidate pairs were produced.</p>'}
  <details class="technical"><summary>Technical provenance</summary><h3>Source</h3><pre>{source_json}</pre><h3>Configuration</h3><pre>{config_json}</pre></details>
</main>
"""
    suffix = """
<script>
(() => {
  const storageKey = """ + json.dumps(review_key) + """;
  const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
  document.querySelectorAll('.manual-decision').forEach((select) => {
    const id = select.dataset.candidate;
    if (saved[id]?.decision) select.value = saved[id].decision;
    select.addEventListener('change', save);
  });
  document.querySelectorAll('.manual-notes').forEach((textarea) => {
    const id = textarea.dataset.candidate;
    if (saved[id]?.notes) textarea.value = saved[id].notes;
    textarea.addEventListener('input', save);
  });
  function collect() {
    const result = {};
    document.querySelectorAll('.candidate').forEach((card) => {
      const id = card.id;
      result[id] = {
        decision: card.querySelector('.manual-decision').value,
        notes: card.querySelector('.manual-notes').value
      };
    });
    return result;
  }
  function save() { localStorage.setItem(storageKey, JSON.stringify(collect())); }
  function filter() {
    const wanted = document.getElementById('status-filter').value;
    let visible = 0;
    document.querySelectorAll('.candidate').forEach((card) => {
      const show = wanted === 'all' || card.dataset.status === wanted;
      card.hidden = !show;
      if (show) visible += 1;
    });
    document.getElementById('visible-count').textContent = `${visible} pair(s) shown`;
  }
  document.getElementById('status-filter').addEventListener('change', filter);
  document.getElementById('export-review').addEventListener('click', () => {
    save();
    const payload = { dataset:'owner_duplicate_manual_review', exported_at:new Date().toISOString(), decisions:collect() };
    const blob = new Blob([JSON.stringify(payload, null, 2) + '\\n'], {type:'application/json'});
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'owner-duplicate-manual-review.json';
    link.click();
    URL.revokeObjectURL(link.href);
  });
  filter();
})();
</script>
</body>
</html>
"""
    return prefix + body + suffix
