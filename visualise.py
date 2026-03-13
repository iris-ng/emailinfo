"""Email visualisation: time-series bar chart + correspondence network."""

import json, base64, io, sys
from datetime import datetime, timedelta, date
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from analyze_relationships import RelationshipAnalyzer

# ── Palette ───────────────────────────────────────────────────────────────────
_BG     = '#0d1117'
_PANEL  = '#161b22'
_BORDER = '#30363d'
_TEXT   = '#e6edf3'
_MUTED  = '#8b949e'
_BLUE   = '#1f6feb'
_RED    = '#f85149'

# ── Date helpers ──────────────────────────────────────────────────────────────
def _parse_dates(df):
    out = []
    for v in df['date']:
        s = str(v).strip()
        if not s or s in ('nan', 'No Date', 'ERROR'):
            continue
        try:
            if ', ' in s:
                try:
                    out.append(datetime.strptime(s, '%Y-%m-%d, %H:%M'))
                except ValueError:
                    out.append(pd.to_datetime(s).to_pydatetime())
            else:
                out.append(pd.to_datetime(s).to_pydatetime())
        except Exception:
            pass
    return sorted(out)


def _granularity(dates):
    span = (dates[-1] - dates[0]).days
    return 'day' if span <= 90 else 'month' if span <= 730 else 'year'


def _bucket(dates, gran):
    def key(d):
        if gran == 'day':   return d.date()
        if gran == 'month': return d.replace(day=1).date()
        return d.replace(month=1, day=1).date()
    cnts = Counter(key(d) for d in dates)
    start, end = min(cnts), max(cnts)
    all_b, cur = [], start
    while cur <= end:
        all_b.append(cur)
        if gran == 'day':
            cur += timedelta(days=1)
        elif gran == 'month':
            m, y = cur.month + 1, cur.year
            if m > 12: m, y = 1, y + 1
            cur = date(y, m, 1)
        else:
            cur = date(cur.year + 1, 1, 1)
    return all_b, [cnts.get(b, 0) for b in all_b]


def _find_segments(buckets, counts, gran):
    """Return list of (lo, hi) x-ranges for non-gap segments, or None."""
    if gran == 'year':
        return None
    thresh = 14 if gran == 'day' else 2

    gaps, i = [], 0
    while i < len(counts):
        if counts[i] == 0:
            j = i + 1
            while j < len(counts) and counts[j] == 0:
                j += 1
            if j - i >= thresh:
                gaps.append((i, j - 1))
            i = j
        else:
            i += 1

    if not gaps:
        return None

    # Keep up to 4 largest gaps
    gaps = sorted(sorted(gaps, key=lambda g: g[1] - g[0], reverse=True)[:4])

    segs, prev = [], 0
    for gs, ge in gaps:
        if gs > prev:
            segs.append((prev - 0.5, gs - 0.2))
        prev = ge + 1
    if prev < len(buckets):
        segs.append((prev - 0.5, len(buckets) - 0.5))

    return segs if len(segs) > 1 else None


def _style_ax(ax):
    ax.set_facecolor(_PANEL)
    ax.tick_params(colors=_MUTED, labelsize=8)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(_BORDER)
    ax.yaxis.grid(True, color=_BORDER, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)


def _break_marks(ax_l, ax_r, fig):
    """Draw // break marks at the right boundary of ax_l.

    Uses ax_l.transAxes for both x and y so the position is immune to
    bbox_inches='tight' coordinate-system shifts.  fig.add_artist ensures
    the marks render on top of all axes content.
    """
    import matplotlib.lines as mlines, math

    bbox    = ax_l.get_position()
    fig_w, fig_h = fig.get_size_inches()
    ax_w    = bbox.width  * fig_w           # physical axis width  (inches)
    ax_h    = bbox.height * fig_h           # physical axis height (inches)

    # Short mark at each corner: ±mark_dy in axes-fraction units
    mark_dy  = 0.09
    dy_phys  = 2 * mark_dy * ax_h          # physical height of one mark
    dx_phys  = dy_phys / math.tan(math.radians(65))  # 65° from horizontal
    dx_ax    = dx_phys / ax_w              # in axes-fraction units

    sep_ax   = max(0.02, 0.11 / ax_w)     # ~0.11" gap between the two slashes

    # Draw as figure-level artists with ax_l.transAxes so they sit on top of
    # everything (including ax_r's face) and are correctly positioned at x=1.0
    kw = dict(lw=1.6, color=_TEXT, clip_on=False, zorder=20,
              transform=ax_l.transAxes)
    for y_c in (0.0, 1.0):
        for x_c in (1.0 - sep_ax / 2, 1.0 + sep_ax / 2):
            fig.add_artist(mlines.Line2D(
                (x_c - dx_ax / 2, x_c + dx_ax / 2),
                (y_c - mark_dy,   y_c + mark_dy), **kw))


# ── Time chart ────────────────────────────────────────────────────────────────
def build_time_chart(df):
    dates = _parse_dates(df)
    if len(dates) < 2:
        return None

    gran = _granularity(dates)
    buckets, counts = _bucket(dates, gran)
    segs = _find_segments(buckets, counts, gran)
    xs = list(range(len(buckets)))
    trend = np.maximum(np.poly1d(np.polyfit(xs, counts, 1))(xs), 0)
    ymax = max(counts) * 1.12

    if gran == 'day':
        fmt = '%#d %b %y' if sys.platform == 'win32' else '%-d %b %y'
    elif gran == 'month':
        fmt = '%b %Y'
    else:
        fmt = '%Y'
    labels = [b.strftime(fmt) for b in buckets]
    step = max(1, len(buckets) // 12)
    tpos, tlbl = xs[::step], labels[::step]

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'text.color': _TEXT})
    fig = plt.figure(figsize=(14, 4.5), facecolor=_BG)

    if segs:
        spans = [hi - lo for lo, hi in segs]
        gs = gridspec.GridSpec(1, len(segs), figure=fig,
                               width_ratios=spans, wspace=0.0)
        axes = [fig.add_subplot(gs[i]) for i in range(len(segs))]

        for i, (ax, (lo, hi)) in enumerate(zip(axes, segs)):
            _style_ax(ax)

            # Bars within this segment
            seg_xs = [x for x in xs if lo - 0.5 < x < hi + 0.5]
            # Trend only between points strictly inside the xlim
            trend_xs = [x for x in xs if lo <= x <= hi]
            if seg_xs:
                ax.bar(seg_xs, [counts[x] for x in seg_xs],
                       color=_BLUE, alpha=0.85, width=0.75, zorder=3)
            if trend_xs:
                ax.plot(trend_xs, [trend[x] for x in trend_xs],
                        color=_RED, lw=1.4, ls='--', dashes=(6, 3), zorder=4)

            # Set limits AFTER plotting so autoscale doesn't override them
            ax.set_xlim(lo, hi)
            ax.set_ylim(0, ymax)

            # Y-axis: only on leftmost
            if i == 0:
                ax.set_ylabel('Emails', color=_MUTED, labelpad=8, fontsize=9)
            else:
                ax.yaxis.set_visible(False)
                ax.spines['left'].set_visible(False)

            # X tick labels — pick from bars actually inside this segment
            seg_pos = [x for x in xs if lo <= x <= hi]
            local_step = max(1, len(seg_pos) // 8)
            vis_pos = seg_pos[::local_step]
            if vis_pos:
                ax.set_xticks(vis_pos)
                ax.set_xticklabels([labels[p] for p in vis_pos], rotation=35,
                                   ha='right', fontsize=8, color=_MUTED)
            else:
                ax.set_xticks([])

    else:
        ax = fig.add_subplot(111)
        _style_ax(ax)
        ax.bar(xs, counts, color=_BLUE, alpha=0.85, width=0.75, zorder=3)
        ax.plot(xs, trend, color=_RED, lw=1.4, ls='--', dashes=(6, 3), zorder=4)
        ax.set_ylim(0, ymax)
        ax.set_ylabel('Emails', color=_MUTED, labelpad=8, fontsize=9)
        ax.set_xticks(tpos)
        ax.set_xticklabels(tlbl, rotation=35, ha='right', fontsize=8, color=_MUTED)

    fig.suptitle('Email Volume Over Time', color=_TEXT, fontsize=12,
                 fontweight='semibold', y=1.02)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        plt.tight_layout(pad=1.2)

    # Draw break marks after tight_layout so axis positions are finalised
    if segs:
        for i in range(len(axes) - 1):
            _break_marks(axes[i], axes[i + 1], fig)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor=_BG, edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


# ── Network data ──────────────────────────────────────────────────────────────
def build_network_data(excel_path, top_n=25):
    analyzer = RelationshipAnalyzer(excel_path)
    analyzer.analyze()

    all_ids = set(analyzer.sender_counts) | set(analyzer.recipient_counts)
    activity = {p: analyzer.sender_counts.get(p, 0) + analyzer.recipient_counts.get(p, 0)
                for p in all_ids}

    top_ids = {p for p, _ in
               sorted(activity.items(), key=lambda x: x[1], reverse=True)[:top_n]}

    max_act = max(activity[p] for p in top_ids)
    min_act = min(activity[p] for p in top_ids)

    def norm_size(a):
        if max_act == min_act:
            return 40
        return 22 + 58 * (a - min_act) / (max_act - min_act)

    nodes = []
    for pid in top_ids:
        sent  = analyzer.sender_counts.get(pid, 0)
        recv  = analyzer.recipient_counts.get(pid, 0)
        total = activity[pid]
        name  = analyzer.person_registry.get_display_name(pid)
        label = (name[:22] + '…') if len(name) > 22 else name
        ratio = sent / total if total else 0.5
        color = '#1f6feb' if ratio > 0.6 else '#f0883e' if ratio < 0.4 else '#8b949e'
        nodes.append({'data': {
            'id': pid, 'label': label, 'fullName': name,
            'sent': sent, 'received': recv, 'total': total,
            'size': round(norm_size(total), 1), 'color': color,
        }})

    weights = [w for (s, r), w in analyzer.relationships.items()
               if s in top_ids and r in top_ids and s != r]
    max_w = max(weights) if weights else 1

    edges = []
    for (s, r), w in analyzer.relationships.items():
        if s not in top_ids or r not in top_ids or s == r:
            continue
        edges.append({'data': {
            'source': s, 'target': r,
            'weight': w, 'width': round(1 + 7 * (w / max_w), 2),
        }})

    stats = {
        'unique_people': len(analyzer.person_registry.identifier_to_names),
        'unique_pairs':  len(analyzer.relationships),
        'top_sender':    analyzer.person_registry.get_display_name(
                             analyzer.sender_counts.most_common(1)[0][0])
                         if analyzer.sender_counts else 'N/A',
    }
    return nodes, edges, stats


# ── HTML template ─────────────────────────────────────────────────────────────
_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Email Analysis Report</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0d1117; color: #e6edf3;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14px; line-height: 1.5;
  }}
  a {{ color: #58a6ff; }}
  header {{
    background: #161b22; border-bottom: 1px solid #30363d;
    padding: 24px 40px;
  }}
  header h1 {{ font-size: 20px; font-weight: 600; color: #e6edf3; margin-bottom: 16px; }}
  .stats {{
    display: flex; gap: 32px; flex-wrap: wrap;
  }}
  .stat {{
    display: flex; flex-direction: column; gap: 2px;
  }}
  .stat-value {{
    font-size: 22px; font-weight: 600; color: #58a6ff;
  }}
  .stat-label {{
    font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.06em;
  }}
  main {{ padding: 32px 40px; display: flex; flex-direction: column; gap: 40px; }}
  .card {{
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    overflow: hidden;
  }}
  .card-header {{
    padding: 16px 20px; border-bottom: 1px solid #30363d;
    font-size: 13px; font-weight: 600; color: #8b949e;
    text-transform: uppercase; letter-spacing: 0.07em;
  }}
  .card-body {{ padding: 20px; }}
  .chart-img {{ width: 100%; display: block; border-radius: 4px; }}
  /* Network */
  #cy {{
    width: 100%; height: 600px;
    background: #0d1117; border-radius: 4px;
  }}
  .net-controls {{
    display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;
    align-items: center;
  }}
  .btn {{
    background: #21262d; border: 1px solid #30363d; color: #e6edf3;
    padding: 5px 14px; border-radius: 6px; cursor: pointer; font-size: 12px;
    transition: background 0.15s;
  }}
  .btn:hover {{ background: #30363d; }}
  .net-legend {{
    display: flex; gap: 20px; margin-top: 12px; flex-wrap: wrap;
  }}
  .legend-item {{
    display: flex; align-items: center; gap: 6px; font-size: 12px; color: #8b949e;
  }}
  .legend-dot {{
    width: 11px; height: 11px; border-radius: 50%; flex-shrink: 0;
  }}
  /* Tooltip */
  #tooltip {{
    position: fixed; display: none; pointer-events: none;
    background: #1c2128; border: 1px solid #30363d; border-radius: 6px;
    padding: 10px 14px; font-size: 12px; line-height: 1.7;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5); z-index: 9999; max-width: 240px;
  }}
  #tooltip strong {{ color: #58a6ff; display: block; margin-bottom: 4px; }}
  #tooltip span {{ color: #8b949e; }}
  #tooltip .val {{ color: #e6edf3; font-weight: 500; }}
</style>
</head>
<body>

<header>
  <h1>Email Analysis Report</h1>
  <div class="stats">
    <div class="stat">
      <span class="stat-value">{total_emails}</span>
      <span class="stat-label">Total Emails</span>
    </div>
    <div class="stat">
      <span class="stat-value">{date_range}</span>
      <span class="stat-label">Date Range</span>
    </div>
    <div class="stat">
      <span class="stat-value">{unique_people}</span>
      <span class="stat-label">Unique People</span>
    </div>
    <div class="stat">
      <span class="stat-value">{unique_pairs}</span>
      <span class="stat-label">Sender–Recipient Pairs</span>
    </div>
    <div class="stat">
      <span class="stat-value" style="font-size:15px;padding-top:4px">{top_sender}</span>
      <span class="stat-label">Most Active Sender</span>
    </div>
  </div>
</header>

<main>
  <div class="card">
    <div class="card-header">Email Volume Over Time</div>
    <div class="card-body">
      <img class="chart-img" src="data:image/png;base64,{chart_b64}" alt="Email volume chart">
    </div>
  </div>

  <div class="card">
    <div class="card-header">Correspondence Network &mdash; Top {top_n} People</div>
    <div class="card-body">
      <div class="net-controls">
        <button class="btn" id="btn-fit">Fit to screen</button>
        <button class="btn" id="btn-reset">Reset layout</button>
        <button class="btn" id="btn-clear">Clear selection</button>
      </div>
      <div id="cy"></div>
      <div class="net-legend">
        <div class="legend-item">
          <div class="legend-dot" style="background:#1f6feb"></div>
          Primarily sends
        </div>
        <div class="legend-item">
          <div class="legend-dot" style="background:#f0883e"></div>
          Primarily receives
        </div>
        <div class="legend-item">
          <div class="legend-dot" style="background:#8b949e"></div>
          Balanced
        </div>
        <div class="legend-item" style="margin-left:12px; color:#8b949e">
          Node size = total activity &nbsp;|&nbsp; Edge width = email count
        </div>
      </div>
    </div>
  </div>
</main>

<div id="tooltip"></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
<script>
const NODES = {nodes_json};
const EDGES = {edges_json};

const LAYOUT_OPTS = {{
  name: 'cose',
  idealEdgeLength: 120,
  nodeOverlap: 16,
  refresh: 20,
  fit: true,
  padding: 40,
  randomize: false,
  componentSpacing: 120,
  nodeRepulsion: 450000,
  edgeElasticity: 100,
  nestingFactor: 5,
  gravity: 80,
  numIter: 1000,
  initialTemp: 200,
  coolingFactor: 0.95,
  minTemp: 1.0,
}};

const cy = cytoscape({{
  container: document.getElementById('cy'),
  elements: {{ nodes: NODES, edges: EDGES }},
  style: [
    {{
      selector: 'node',
      style: {{
        'background-color': 'data(color)',
        'width':  'data(size)',
        'height': 'data(size)',
        'label':  'data(label)',
        'color':  '#c9d1d9',
        'font-size': '10px',
        'font-family': 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
        'font-weight': '500',
        'text-valign': 'center',
        'text-halign': 'center',
        'text-outline-color': '#0d1117',
        'text-outline-width': '2px',
        'border-width': '1.5px',
        'border-color': '#30363d',
        'transition-property': 'opacity, border-color, border-width',
        'transition-duration': '0.15s',
      }}
    }},
    {{
      selector: 'edge',
      style: {{
        'width': 'data(width)',
        'line-color': '#388bfd',
        'opacity': 0.35,
        'curve-style': 'bezier',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#388bfd',
        'arrow-scale': 0.75,
        'transition-property': 'opacity',
        'transition-duration': '0.15s',
      }}
    }},
    {{
      selector: 'node:selected',
      style: {{
        'border-color': '#f0883e',
        'border-width': '3px',
      }}
    }},
    {{
      selector: '.highlighted',
      style: {{ 'opacity': 1 }}
    }},
    {{
      selector: '.faded',
      style: {{ 'opacity': 0.08 }}
    }},
  ],
  layout: LAYOUT_OPTS,
}});

// ── Tooltip ──────────────────────────────────────────────────────────────────
const tip = document.getElementById('tooltip');

cy.on('mouseover', 'node', function(e) {{
  const d = e.target.data();
  tip.innerHTML =
    `<strong>${{d.fullName}}</strong>` +
    `<span>Sent</span>     <span class="val">${{d.sent}}</span><br>` +
    `<span>Received</span> <span class="val">${{d.received}}</span><br>` +
    `<span>Total</span>    <span class="val">${{d.total}}</span>`;
  tip.style.display = 'block';
}});

cy.on('mouseout', 'node', () => {{ tip.style.display = 'none'; }});

cy.on('mousemove', function(e) {{
  tip.style.left = (e.originalEvent.clientX + 16) + 'px';
  tip.style.top  = (e.originalEvent.clientY - 10) + 'px';
}});

// ── Click to highlight neighbours ────────────────────────────────────────────
cy.on('tap', 'node', function(e) {{
  const node = e.target;
  cy.elements().addClass('faded');
  node.addClass('highlighted');
  node.neighborhood().addClass('highlighted').removeClass('faded');
}});

cy.on('tap', function(e) {{
  if (e.target === cy) {{
    cy.elements().removeClass('faded highlighted');
  }}
}});

// ── Controls ─────────────────────────────────────────────────────────────────
document.getElementById('btn-fit').onclick   = () => cy.fit(undefined, 40);
document.getElementById('btn-clear').onclick = () => cy.elements().removeClass('faded highlighted');
document.getElementById('btn-reset').onclick = () => {{
  cy.elements().removeClass('faded highlighted');
  cy.layout(LAYOUT_OPTS).run();
}};
</script>
</body>
</html>
"""


# ── Entry point ───────────────────────────────────────────────────────────────
def run(output_dir='output', top_n=25):
    out        = Path(output_dir)
    excel_path = out / 'results.xlsx'
    output_path = out / 'report.html'

    if not excel_path.exists():
        print(f"Error: {excel_path} not found. Run -d first to generate it.")
        return

    print("Loading email data...")
    df = pd.read_excel(excel_path)

    print("Generating time series chart...")
    chart_b64 = build_time_chart(df) or ''

    print("Analysing relationships...")
    nodes, edges, net_stats = build_network_data(excel_path, top_n=top_n)

    # Date range from parsed dates
    dates = _parse_dates(df)
    if len(dates) >= 2:
        date_range = f"{dates[0].strftime('%b %Y')} – {dates[-1].strftime('%b %Y')}"
    elif len(dates) == 1:
        date_range = dates[0].strftime('%b %Y')
    else:
        date_range = 'N/A'

    print("Rendering HTML report...")
    html = _HTML.format(
        total_emails  = len(df),
        date_range    = date_range,
        unique_people = net_stats['unique_people'],
        unique_pairs  = net_stats['unique_pairs'],
        top_sender    = net_stats['top_sender'],
        top_n         = top_n,
        chart_b64     = chart_b64,
        nodes_json    = json.dumps(nodes),
        edges_json    = json.dumps(edges),
    )

    Path(output_path).write_text(html, encoding='utf-8')
    print(f"Done. Report saved to {output_path}")
