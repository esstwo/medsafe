"""Generate the MedSafe architecture diagram."""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as pe

fig, ax = plt.subplots(1, 1, figsize=(20, 14))
ax.set_xlim(0, 20)
ax.set_ylim(0, 14)
ax.axis('off')
fig.patch.set_facecolor('#0F1117')
ax.set_facecolor('#0F1117')

# ── colour palette ──────────────────────────────────────────────────────────
C = {
    'user':       '#1E3A5F',
    'user_bd':    '#4A9EFF',
    'iface':      '#1A3A2A',
    'iface_bd':   '#3DBA6F',
    'orch':       '#2E1F3E',
    'orch_bd':    '#9B59B6',
    'core':       '#1F2E3E',
    'core_bd':    '#4A9EFF',
    'data':       '#2A1F1A',
    'data_bd':    '#E67E22',
    'ext':        '#1A2A1A',
    'ext_bd':     '#27AE60',
    'layer_bg':   '#161B22',
    'arrow':      '#666688',
    'arrow_hi':   '#4A9EFF',
    'text':       '#E8EAF0',
    'text_dim':   '#8892A4',
    'title':      '#FFFFFF',
    'sep':        '#2A3040',
}

def box(ax, x, y, w, h, fc, ec, radius=0.25, alpha=0.95, lw=1.5):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle=f"round,pad=0,rounding_size={radius}",
                       facecolor=fc, edgecolor=ec, linewidth=lw, alpha=alpha,
                       zorder=3)
    ax.add_patch(p)
    return p

def label(ax, x, y, txt, size=9, color=None, bold=False, ha='center', va='center', zorder=4):
    color = color or C['text']
    weight = 'bold' if bold else 'normal'
    ax.text(x, y, txt, fontsize=size, color=color, ha=ha, va=va,
            fontweight=weight, zorder=zorder,
            fontfamily='DejaVu Sans')

def sublabel(ax, x, y, txt, size=7.2, color=None, ha='center', va='center'):
    color = color or C['text_dim']
    ax.text(x, y, txt, fontsize=size, color=color, ha=ha, va=va,
            zorder=4, style='italic')

def section_bg(ax, x, y, w, h, label_txt, label_color, bg_color='#161B22'):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle="round,pad=0,rounding_size=0.35",
                       facecolor=bg_color, edgecolor=C['sep'],
                       linewidth=1, alpha=0.6, zorder=1)
    ax.add_patch(p)
    ax.text(x + 0.18, y + h - 0.22, label_txt,
            fontsize=7.5, color=label_color, ha='left', va='top',
            fontweight='bold', zorder=2, alpha=0.8)

def arrow(ax, x1, y1, x2, y2, color=None, lw=1.4, style='->', bidirectional=False):
    color = color or C['arrow']
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->' if not bidirectional else '<->',
                                color=color, lw=lw,
                                connectionstyle='arc3,rad=0.0'),
                zorder=2)

def dashed_arrow(ax, x1, y1, x2, y2, color=None, lw=1.2):
    color = color or C['arrow']
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->',
                                color=color, lw=lw,
                                linestyle='dashed',
                                connectionstyle='arc3,rad=0.0'),
                zorder=2)

# ── title ────────────────────────────────────────────────────────────────────
ax.text(10, 13.55, 'MedSafe — System Architecture',
        fontsize=16, color=C['title'], ha='center', va='center',
        fontweight='bold', zorder=5)
ax.text(10, 13.15, 'FDA Drug Interaction & Safety Advisor  ·  FastAPI + React  ·  MCP Server (Claude Plugin)',
        fontsize=8.5, color=C['text_dim'], ha='center', va='center', zorder=5)

# ════════════════════════════════════════════════════════════════════════════
# LAYER 1 — USER INTERFACES  (y: 11.2 – 12.8)
# ════════════════════════════════════════════════════════════════════════════
section_bg(ax, 0.3, 11.1, 19.4, 1.65, 'LAYER 1 · USER INTERFACES', C['user_bd'])

# React Web App
box(ax, 1.0, 11.35, 4.0, 1.1, C['user'], C['user_bd'], lw=2)
label(ax, 3.0, 12.1, 'React Web App', size=10, bold=True, color=C['user_bd'])
sublabel(ax, 3.0, 11.72, 'TypeScript · Vite · Tailwind · shadcn/ui')
sublabel(ax, 3.0, 11.47, 'MedicationInput · InteractionTable · SafetyBriefing')

# Claude Desktop / claude.ai
box(ax, 7.5, 11.35, 4.2, 1.1, C['user'], C['user_bd'], lw=2)
label(ax, 9.6, 12.1, 'Claude Desktop / claude.ai', size=10, bold=True, color=C['user_bd'])
sublabel(ax, 9.6, 11.72, 'MCP Client  ·  stdio transport')
sublabel(ax, 9.6, 11.47, 'Claude acts as the conversational UI')

# Patient / Caregiver persona box
box(ax, 14.2, 11.35, 4.6, 1.1, '#1A1A2E', '#555577', lw=1.2)
label(ax, 16.5, 12.1, 'Users', size=10, bold=True, color='#8899BB')
sublabel(ax, 16.5, 11.77, 'Patient (polypharmacy)')
sublabel(ax, 16.5, 11.57, 'Caregiver  ·  Health-conscious adult')
sublabel(ax, 16.5, 11.4, 'Free-text medication list + symptoms')

# arrows from users to interfaces
arrow(ax, 14.2, 11.9, 11.7, 11.9, color=C['user_bd'], lw=1.6)
arrow(ax, 14.2, 11.9, 5.0, 11.9, color=C['user_bd'], lw=1.6)

# ════════════════════════════════════════════════════════════════════════════
# LAYER 2 — INTERFACE LAYER  (y: 9.2 – 10.85)
# ════════════════════════════════════════════════════════════════════════════
section_bg(ax, 0.3, 9.1, 19.4, 1.7, 'LAYER 2 · INTERFACE LAYER', C['iface_bd'])

# FastAPI REST API
box(ax, 1.0, 9.35, 4.0, 1.1, C['iface'], C['iface_bd'], lw=2)
label(ax, 3.0, 10.1, 'FastAPI REST API', size=10, bold=True, color=C['iface_bd'])
sublabel(ax, 3.0, 9.72, 'Python 3.12  ·  Pydantic  ·  async')
sublabel(ax, 3.0, 9.47, '/medications  /analysis  /briefing  /drugs')

# MCP Server
box(ax, 7.5, 9.35, 4.2, 1.1, C['iface'], C['iface_bd'], lw=2)
label(ax, 9.6, 10.1, 'MCP Server', size=10, bold=True, color=C['iface_bd'])
sublabel(ax, 9.6, 9.72, 'mcp Python SDK  ·  stdio transport')
sublabel(ax, 9.6, 9.47, 'tools · resources · prompts')

# down arrows from layer 1 to layer 2
arrow(ax, 3.0, 11.35, 3.0, 10.45, color=C['iface_bd'], lw=1.8)
arrow(ax, 9.6, 11.35, 9.6, 10.45, color=C['iface_bd'], lw=1.8)

# ════════════════════════════════════════════════════════════════════════════
# LAYER 3 — ORCHESTRATION  (y: 7.35 – 8.9)  (FastAPI path only)
# ════════════════════════════════════════════════════════════════════════════
section_bg(ax, 0.3, 7.25, 8.4, 1.7, 'LAYER 3 · ORCHESTRATION  (FastAPI path only)', C['orch_bd'])

# LLM Orchestrator
box(ax, 1.0, 7.5, 6.8, 1.2, C['orch'], C['orch_bd'], lw=2)
label(ax, 4.4, 8.35, 'LLM Orchestrator  (Claude claude-sonnet-4-6)', size=10, bold=True, color=C['orch_bd'])
sublabel(ax, 4.4, 8.0, 'Query Classifier  ·  Execution Planner  ·  Agentic Replanning Loop')
sublabel(ax, 4.4, 7.75,
         'FULL_ANALYSIS · INCREMENTAL_ADD · SYMPTOM_CHECK · DRUG_DEEP_DIVE · GENERAL_QUESTION')

# MCP bypass note
ax.text(9.0, 8.15, 'MCP path:\nClaude IS the\norchestrator',
        fontsize=7.5, color='#9B59B6', ha='left', va='center',
        style='italic', zorder=4)
ax.annotate('', xy=(9.0, 8.15), xytext=(9.6, 9.35),
            arrowprops=dict(arrowstyle='->', color='#9B59B6', lw=1.2,
                            linestyle='dashed', connectionstyle='arc3,rad=0.15'),
            zorder=2)

# down arrow FastAPI → Orchestrator
arrow(ax, 3.0, 9.35, 3.0, 8.7, color=C['orch_bd'], lw=1.8)

# ════════════════════════════════════════════════════════════════════════════
# LAYER 4 — SHARED CORE  (y: 4.6 – 7.05)
# ════════════════════════════════════════════════════════════════════════════
section_bg(ax, 0.3, 4.5, 19.4, 2.65, 'LAYER 4 · SHARED CORE  (used by both FastAPI and MCP)', C['core_bd'])

core_boxes = [
    (0.55, 4.75, 3.5, 'Tools Layer',      '#4A9EFF',
     'rxnorm.py\nopenfda.py\ndailymed.py\ninteraction_checker.py\nsymptom_attributor.py'),
    (4.3,  4.75, 3.5, 'RAG Pipeline',     '#4A9EFF',
     'ingest.py\nretriever.py (dense+BM25+RRF)\nreranker.py (cross-encoder)\nChromaDB vector store'),
    (8.05, 4.75, 3.5, 'Guardrails',       '#FF6B6B',
     'input_guards.py\n(emergency · PII · injection)\noutput_guards.py\n(citations · hallucination · prescribing)'),
    (11.8, 4.75, 3.5, 'Data Models',      '#4A9EFF',
     'Medication\nInteraction\nSafetyBriefing\nAttribution · FAERSResult'),
    (15.55,4.75, 3.5, 'Eval Framework',   '#F0B429',
     'Normalization accuracy\nInteraction recall/precision\nLLM-as-judge\n(faithfulness · readability)'),
]

for (bx, by, bw, btitle, bcolor, btext) in core_boxes:
    box(ax, bx, by, bw, 2.05, C['core'], bcolor, lw=1.8)
    label(ax, bx + bw/2, by + 1.88, btitle, size=8.5, bold=True, color=bcolor)
    for i, line in enumerate(btext.split('\n')):
        label(ax, bx + bw/2, by + 1.56 - i*0.32, line, size=7, color=C['text_dim'])

# down arrows into shared core
arrow(ax, 4.4, 7.5,  4.4, 6.8,  color=C['core_bd'], lw=1.5)   # orchestrator → tools
arrow(ax, 9.6, 9.35, 9.76, 6.8, color=C['core_bd'], lw=1.5)   # MCP → core

# ════════════════════════════════════════════════════════════════════════════
# LAYER 5 — DATA STORES  (y: 2.65 – 4.3)
# ════════════════════════════════════════════════════════════════════════════
section_bg(ax, 0.3, 2.55, 9.0, 1.75, 'LAYER 5 · LOCAL DATA STORES', C['data_bd'])

data_boxes = [
    (0.55, 2.8, 3.8, 'ChromaDB  (Vector Store)',  C['data_bd'],
     'FDA label chunks (section-level)\nDrugBank descriptions\nNIH ODS supplements · MedlinePlus'),
    (4.6,  2.8, 4.4, 'SQLite  (Structured)',       C['data_bd'],
     'DrugBank interaction records\n(rxcui_a, rxcui_b, severity, mechanism)\nRxNorm local cache'),
]

for (bx, by, bw, btitle, bcolor, btext) in data_boxes:
    box(ax, bx, by, bw, 1.35, C['data'], bcolor, lw=1.8)
    label(ax, bx + bw/2, by + 1.18, btitle, size=8.5, bold=True, color=bcolor)
    for i, line in enumerate(btext.split('\n')):
        label(ax, bx + bw/2, by + 0.85 - i*0.28, line, size=7, color=C['text_dim'])

# ════════════════════════════════════════════════════════════════════════════
# LAYER 5b — EXTERNAL APIs  (y: 2.65 – 4.3)
# ════════════════════════════════════════════════════════════════════════════
section_bg(ax, 9.6, 2.55, 10.1, 1.75, 'LAYER 5 · EXTERNAL APIs  (live queries)', C['ext_bd'])

ext_boxes = [
    (9.85,  2.8, 2.2, 'RxNorm\n(NLM)',      C['ext_bd'], 'Fuzzy name match\nRxCUI lookup'),
    (12.25, 2.8, 2.2, 'openFDA\nFAERS',     C['ext_bd'], 'Adverse events\nOutcome counts'),
    (14.65, 2.8, 2.2, 'DailyMed\n(NLM)',    C['ext_bd'], 'FDA label XML\nBulk download'),
    (17.05, 2.8, 2.35,'DrugBank\n(open)',   '#E67E22',   'Interaction pairs\nCC BY-NC 4.0'),
]

for (bx, by, bw, btitle, bcolor, btext) in ext_boxes:
    box(ax, bx, by, bw, 1.35, C['ext'], bcolor, lw=1.8)
    label(ax, bx + bw/2, by + 1.1, btitle, size=8, bold=True, color=bcolor)
    for i, line in enumerate(btext.split('\n')):
        label(ax, bx + bw/2, by + 0.7 - i*0.28, line, size=7, color=C['text_dim'])

# arrows shared core → data stores
arrow(ax, 2.3,  4.75, 2.3,  4.15, color=C['data_bd'], lw=1.4)
arrow(ax, 6.05, 4.75, 6.05, 4.15, color=C['data_bd'], lw=1.4)
# arrows tools → external APIs
arrow(ax, 1.85, 4.75, 11.0, 4.15, color=C['ext_bd'],  lw=1.4)
arrow(ax, 1.85, 4.75, 13.4, 4.15, color=C['ext_bd'],  lw=1.4)
arrow(ax, 1.85, 4.75, 15.7, 4.15, color=C['ext_bd'],  lw=1.4)
arrow(ax, 5.5,  4.75, 18.2, 4.15, color='#E67E22',    lw=1.4)

# ════════════════════════════════════════════════════════════════════════════
# LEGEND
# ════════════════════════════════════════════════════════════════════════════
legend_items = [
    (C['user_bd'],  'User interface'),
    (C['iface_bd'], 'Interface layer'),
    (C['orch_bd'],  'Orchestration'),
    (C['core_bd'],  'Shared core'),
    ('#FF6B6B',     'Guardrails'),
    (C['data_bd'],  'Data store'),
    (C['ext_bd'],   'External API'),
]

lx, ly = 0.5, 2.2
for i, (color, txt) in enumerate(legend_items):
    box(ax, lx + i*2.6, ly - 0.18, 0.35, 0.28, color, color, radius=0.06)
    label(ax, lx + i*2.6 + 0.55, ly - 0.04, txt, size=7.5,
          color=C['text_dim'], ha='left')

# ════════════════════════════════════════════════════════════════════════════
# GUARDRAIL CALLOUT
# ════════════════════════════════════════════════════════════════════════════
box(ax, 12.4, 7.5, 7.0, 1.2, '#1A1A1A', '#FF6B6B', lw=1.5, alpha=0.85)
label(ax, 15.9, 8.35, 'Safety Guardrails (non-negotiable)', size=8.5, bold=True, color='#FF6B6B')
guard_lines = [
    'Input:  emergency detection · PII strip · self-prescribing block · injection reject',
    'Output: no prescribing language · no "safe" assertions · all claims cited · hallucination check',
]
for i, line in enumerate(guard_lines):
    label(ax, 15.9, 8.05 - i*0.32, line, size=7, color=C['text_dim'])

# dashed arrow from guardrails core box to callout
ax.annotate('', xy=(12.4, 8.1), xytext=(11.8, 5.8),
            arrowprops=dict(arrowstyle='->', color='#FF6B6B', lw=1.2,
                            linestyle='dashed', connectionstyle='arc3,rad=-0.2'),
            zorder=2)

# ════════════════════════════════════════════════════════════════════════════
# PROMPT CACHING NOTE
# ════════════════════════════════════════════════════════════════════════════
ax.text(0.5, 1.55,
        'Cost optimisation:  Prompt caching on system prompt (tool defs + instructions) saves ~35% per session  ·  '
        'Two-tier LLM: Haiku 4.5 for mechanical steps, Sonnet 4.6 for judgment saves ~60–70%',
        fontsize=7.5, color='#556677', ha='left', va='center', zorder=4, style='italic')

plt.tight_layout(pad=0.3)
out_path = '/Users/sumedhps/100x-playground/medsafe/architecture.jpg'
plt.savefig(out_path, dpi=180, format='jpeg',
            facecolor=fig.get_facecolor(), bbox_inches='tight',
            pil_kwargs={'quality': 95})
print(f'Saved → {out_path}')
plt.close()
