from __future__ import annotations
import pandas as pd
import time, random, datetime, importlib, types, copy, itertools
import streamlit as st
from bokeh.plotting import figure
from bokeh.models import (ColumnDataSource, HoverTool, NumeralTickFormatter,
                          Span, FactorRange)
from bokeh.palettes import Category20
from streamlit_bokeh import streamlit_bokeh
import logging

logging.getLogger("streamlit.runtime.scriptrunner.script_run_context").setLevel(logging.ERROR)
 
# ────────────────────────── 1  test.py import & Patches ───────────────────────
test: types.ModuleType = importlib.import_module("test")
 
if not hasattr(test, "start_datum"):
    #test.start_datum = test.datetime.datetime(2025, 11, 25)
    setattr(test, "start_datum", test.datetime.datetime(2025, 11, 25))
 
if not hasattr(test, "berechne_auftragslaufzeit"):
    def berechne_auftragslaufzeit(a, output_pro_minute=69.444444):
        m = a.bedarfsmenge / output_pro_minute
        return m, m / 60
    #test.berechne_auftragslaufzeit = berechne_auftragslaufzeit
    setattr(test, "berechne_auftragslaufzeit", berechne_auftragslaufzeit)
 
if not hasattr(test, "generiere_auftraege"):
    def generiere_auftraege(n, start, prod, fam):
        return [
            {
                "auftragsnummer": f"A{i+1}",
                "produkt": random.choice(prod),
                "bedarfstermin": start + datetime.timedelta(days=random.randint(0, 60)),
                "bedarfsmenge": random.randint(50_000, 300_000),
                "produktfamilie": random.choice(fam),
                "ruestzeit_produktfamilie": random.randint(1, 5),
                "verkaufspreis": random.randint(8, 25),
            }
            for i in range(n)
        ]
    #test.generiere_auftraege = generiere_auftraege
    setattr(test, "generiere_auftraege", generiere_auftraege)
 
# ────────────────────────── 2  Farben & CSS ───────────────────────────────────
PRIMARY = "#008450"
BASELINE_CLR = "#d62728"
ACCENT_BG = "#e1f3ec"
SALES_BG = "#e0f3f9"
SALES_TXT = "#006d8f"
NEUTRAL_BG = "#f7f7f7"
LIGHT_BG = "#F4F6F5"
 
st.set_page_config("Produktionsplanungs­optimierung", "🧬", layout="wide")
st.markdown(
    f"""
    <style>
      .stApp {{ background:{LIGHT_BG}; }}
      h1,h2,h3,h4,.stMetric-value {{ color:{PRIMARY}; }}
      .stProgress > div > div {{ background:{PRIMARY}; }}
      .kpiCard {{ border-radius:8px; padding:.8rem 1rem; margin-bottom:.6rem;
                  font-weight:600; font-size:1.05rem; }}
      .kpiLabel {{ font-size:.8rem; opacity:.8; }}
      .deltaPos {{ color:#008000; font-weight:600; }}
      .deltaNeg {{ color:#c00000; font-weight:600; }}
      table.weeks td {{ padding:2px 6px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

#st.image("logo.png", width=160)
st.title("Produktionsplanungs­optimierung – beste Produktionsreihenfolge finden")
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)  # Abstand nach oben
    st.image("logo.png", width=200)
# ────────────────────────── 3  Problem erzeugen ───────────────────────────────
def init_problem():
    random.seed(42)
    start = test.datetime.date(2025, 11, 25)
    prod  = [f"Produkt{c}" for c in "ABCDEFGHIJKL"]
    fam   = [f"Familie{i}" for i in range(1, 13)]
    data  = test.generiere_auftraege(200, start, prod, fam)
 
    st.session_state.auftraege = {d["auftragsnummer"]: test.Produktionsauftrag(**d) for d in data}
    st.session_state.original_bedarfsmengen = {nr: a.bedarfsmenge for nr, a in st.session_state.auftraege.items()}
    st.session_state.lagerkosten            = {p: 0.015 for p in prod}
    st.session_state.max_pro_tag            = 100_000
 
# ────────────────────────── 4  Umsatz-Helper ──────────────────────────────────
def revenues(order:list[str]) -> tuple[int,list[int]]:
    cp = {nr: copy.deepcopy(a) for nr, a in st.session_state.auftraege.items()}
    _, w1, w2, w3, w4 = _simulate(cp, order)
    return w1+w2+w3+w4, [w1, w2, w3, w4]
 
def _simulate(orders, seq):
    start = datetime.datetime(2025,11,25); end = start + datetime.timedelta(days=28)
    cur = start; last = None; cap = st.session_state.max_pro_tag; rev = {}
    for nr in seq:
        a = orders[nr]
        if last and a.produktfamilie != last:
            cur += datetime.timedelta(hours=a.ruestzeit_produktfamilie)
        last = a.produktfamilie
        qty = min(a.bedarfsmenge, cap)
        if cur.date() <= a.bedarfstermin:
            rev.setdefault(cur.date(),0); rev[cur.date()] += qty*a.verkaufspreis
        cur += datetime.timedelta(days=1)
        if cur > end: break
    weeks = [0,0,0,0]
    for d,v in rev.items():
        idx = ((d - start.date()).days)//7
        if 0 <= idx < 4: weeks[idx] += int(v)
    return None,*weeks
 
# ────────────────────────── 5  GA-Hilfen ───────────────────────────────────────
def score_population(pop):
    ss = st.session_state
    return [
        test.bewerte_reihenfolge(r, ss.auftraege, ss.original_bedarfsmengen,
                                 ss.lagerkosten, ss.max_pro_tag,
                                 ss.w1, ss.w2, ss.w3)
        for r in pop
    ]
 
def ga_generation() -> float:
    ss = st.session_state
    scores = score_population(ss.population)
    bi = max(range(len(scores)), key=scores.__getitem__)
    best_sc, best_ord = scores[bi], ss.population[bi]
    ss.best_history.append(best_sc)
 
    if best_sc > ss.best_overall_score:
        ss.best_overall_score = best_sc
        ss.best_order = best_ord
        ss.best_total_rev, ss.best_week_revs = revenues(best_ord)
 
    parents = test.selektion(ss.population, scores, ss.parents)
    new_pop = parents[:]
    while len(new_pop) < ss.pop_size:
        child = test.kreuzung(parents); child = test.mutation(child, ss.mutation); new_pop.append(child)
    ss.population = new_pop; ss.generation += 1
    return best_sc
 
# ────────────────────────── 6  Sidebar ────────────────────────────────────────
with st.sidebar:
    st.header("GA-Parameter")
    pop_size = st.slider("Populationsgröße", 20, 300, 120, 10)
    parents  = st.slider("Eltern (Selektion)", 2, 50, 20, 1)
    mutation = st.slider("Mutationsrate", 0.0, 1.0, 0.05, 0.01)
    speed    = st.slider("Sek./Generation", 0.05, 1.0, 0.15, 0.01)
    max_gen  = st.number_input("Max. Generationen", 1, 5000, 250, 10)
    w1 = st.slider("Gewicht Umsatz w₁", 0.0, 1.0, 0.7, 0.05)
    w2 = st.slider("Gewicht Lager w₂", 0.0, 1.0, 0.1, 0.05)
    w3 = st.slider("Gewicht OEE   w₃", 0.0, 1.0, 0.2, 0.05)
    c1, c2, c3 = st.columns(3)
    start = c1.button("▶️ Start", use_container_width=True)
    pause = c2.button("⏸️ Pause", use_container_width=True)
    reset = c3.button("🔄 Reset", use_container_width=True)
 
# ────────────────────────── 7  State-Init / Reset ─────────────────────────────
if "population" not in st.session_state or reset:
    init_problem()
    ss = st.session_state
    ss.pop_size, ss.parents, ss.mutation = pop_size, parents, mutation
    ss.w1, ss.w2, ss.w3 = w1, w2, w3
 
    ss.population = test.generiere_population(ss.auftraege, pop_size)
    base_scores = score_population(ss.population)
    bi = max(range(len(base_scores)), key=base_scores.__getitem__)
    ss.baseline_score = base_scores[bi]
    ss.baseline_order = ss.population[bi]
    ss.baseline_total, ss.baseline_weeks = revenues(ss.baseline_order)
 
    ss.generation = 0
    ss.best_history = []
    ss.best_overall_score = ss.baseline_score
    ss.best_order = ss.baseline_order
    ss.best_total_rev = ss.baseline_total
    ss.best_week_revs = ss.baseline_weeks
 
    ss.src_best = ColumnDataSource(dict(gen=[], best=[]))
    fig = figure(
        height=320,
        background_fill_color=LIGHT_BG,
        x_axis_label="Generation",
        y_axis_label="Bewertung",
        title="Max-Bewertung vs. Baseline",
        sizing_mode="stretch_width",
    )
    fig.yaxis.formatter = NumeralTickFormatter(format="0,0")
    # ► Baseline als durchgängiger Span
    baseline_span = Span(location=ss.baseline_score, dimension="width",
                         line_color=BASELINE_CLR, line_dash="dashed",
                         line_width=3)
    fig.add_layout(baseline_span)
    fig.line("gen", "best", source=ss.src_best,
             line_width=3, color=PRIMARY, legend_label="Aktuell")
    fig.add_tools(HoverTool(tooltips=[("Gen", "@gen"),
                                      ("Bewertung", "@best{0,0}")]))
    fig.legend.location = "top_left"
    ss.fig_hist = fig
    ss.running  = False
else:
    ss = st.session_state
    ss.pop_size, ss.parents, ss.mutation = pop_size, parents, mutation
    ss.w1, ss.w2, ss.w3 = w1, w2, w3
 
if start: ss.running = True
if pause: ss.running = False
 
# ────────────────────────── 8  GA-Loop ─────────────────────────────────────────
if ss.running and ss.generation < max_gen:
    v = ga_generation()
    ss.src_best.stream({"gen": [ss.generation-1], "best": [v]}, rollover=1000)
 
# ────────────────────────── 9  Layout ──────────────────────────────────────────
plot_col, kpi_col = st.columns([4, 1])
with plot_col:
    streamlit_bokeh(ss.fig_hist, use_container_width=True,
                    theme="streamlit", key="hist")
 
with kpi_col:
    delta_score = ss.best_overall_score - ss.baseline_score
    cls = "deltaPos" if delta_score >= 0 else "deltaNeg"
    st.markdown(
        f"""
        <div class='kpiCard' style='background:{ACCENT_BG};'>
           <div class='kpiLabel'>Beste&nbsp;Bewertung</div>
           <div style='font-size:1.45rem;'>{ss.best_overall_score:,.0f}</div>
           <div class='{cls}'>{delta_score:+,.0f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    delta_tot = ss.best_total_rev - ss.baseline_total
    cls2 = "deltaPos" if delta_tot >= 0 else "deltaNeg"
    st.markdown(
        f"""
        <div class='kpiCard' style='background:{SALES_BG}; color:{SALES_TXT};'>
          <div class='kpiLabel'>Gesamtumsatz&nbsp;(4&nbsp;Wo.)</div>
          <div style='font-size:1.45rem;'>{ss.best_total_rev:,.0f} €</div>
          <div class='{cls2}'>
            {"+" if delta_tot>=0 else ""}{delta_tot/1_000_000:,.1f}&nbsp;Mio
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    rows = "".join(
        f"<tr><td>KW&nbsp;{i}</td><td style='text-align:right'>{v:,.0f} €</td>"
        f"<td style='text-align:right' class={'deltaPos' if v-b>=0 else 'deltaNeg'}>"
        f"{v-b:+,.0f} €</td></tr>"
        for i, (v, b) in enumerate(zip(ss.best_week_revs, ss.baseline_weeks), 1)
    )
    st.markdown(
        f"""
        <div class='kpiCard' style='background:{NEUTRAL_BG}; color:#333;'>
          <div class='kpiLabel'>Umsätze je Woche</div>
          <table class='weeks' style='width:100%; font-size:.83rem;'>
            {rows}
          </table>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(min(ss.generation / max_gen, 1.0),
                f"{ss.generation}/{max_gen}")
 
st.markdown("---")
 
# ────────────────────────── 10  Timeline-Plot (4-Wochen) ──────────────────────
def build_schedule(best_order: list[str], limit:int = 50) -> dict[str, list]:
    orders = [st.session_state.auftraege[nr] for nr in best_order[:limit]]
    start_dt = datetime.datetime(2025, 11, 25)
    end_dt   = start_dt + datetime.timedelta(days=28)
    cur = start_dt; last_pf = None
    rate_h = st.session_state.max_pro_tag / 24
    palette = itertools.cycle(Category20[20]); pf_col={}
    d={"y":[], "start":[], "end":[], "color":[],
       "auftrag":[], "produkt":[], "familie":[], "menge":[]}
    for idx, o in enumerate(orders, 1):
        if last_pf and o.produktfamilie!=last_pf:
            cur += datetime.timedelta(hours=o.ruestzeit_produktfamilie)
        last_pf = o.produktfamilie
        run_h = o.bedarfsmenge / rate_h
        s, e = cur, cur + datetime.timedelta(hours=run_h)
        if s > end_dt: break
        if e > end_dt: e = end_dt
        pf_col.setdefault(o.produktfamilie, next(palette))
        d["y"].append(idx); d["start"].append(s); d["end"].append(e)
        d["color"].append(pf_col[o.produktfamilie])
        d["auftrag"].append(o.auftragsnummer); d["produkt"].append(o.produkt)
        d["familie"].append(o.produktfamilie); d["menge"].append(o.bedarfsmenge)
        cur = e
    return d
 
if ss.best_order:
    st.subheader("Beste Produktionsreihenfolge – Zeitplan (bis 4 Wo.)")
    # sched = build_schedule(ss.best_order)
    # if sched["y"]:
    #     src = ColumnDataSource(sched)
    #     h   = 14*len(sched["y"]) + 100
    #     p   = figure(height=h, y_range=(0, len(sched["y"])+1),
    #                  x_axis_type="datetime",
    #                  toolbar_location=None,
    #                  sizing_mode="stretch_width",
    #                  title="Gantt-Übersicht")
    #     p.hbar(y="y", left="start", right="end", height=0.8,
    #            color="color", source=src)
    #     p.add_tools(HoverTool(tooltips=[
    #         ("Auftrag", "@auftrag"), ("Produkt", "@produkt"),
    #         ("Familie", "@familie"), ("Menge", "@menge{0,0}"),
    #         ("Start", "@start{%d.%m %H:%M}"), ("Ende", "@end{%d.%m %H:%M}")
    #     ], formatters={"@start":"datetime","@end":"datetime"}))
    #     p.yaxis.visible = False
    #     p.xaxis.axis_label = "Datum / Uhrzeit"
    #     p.xgrid.grid_line_color = None; p.ygrid.grid_line_color = None
    #     streamlit_bokeh(p, use_container_width=True,
    #                     theme="streamlit", key="timeline")
sched = build_schedule(ss.best_order)
sched = pd.DataFrame(sched).to_dict(orient="list")  # <--- KORREKTUR

# if sched["y"]:
#     src = ColumnDataSource(sched)
#     h   = 14 * len(sched["y"]) + 100
#     p   = figure(height=h, y_range=(0, len(sched["y"])+1),
#                  x_axis_type="datetime",
#                  toolbar_location=None,
#                  sizing_mode="stretch_width",
#                  title="Gantt-Übersicht")
#     p.hbar(y="y", left="start", right="end", height=0.8,
#            color="color", source=src)
#     p.add_tools(HoverTool(tooltips=[
#         ("Auftrag", "@auftrag"), ("Produkt", "@produkt"),
#         ("Familie", "@familie"), ("Menge", "@menge{0,0}"),
#         ("Start", "@start{%d.%m %H:%M}"), ("Ende", "@end{%d.%m %H:%M}")
#     ], formatters={"@start":"datetime","@end":"datetime"}))
#     p.yaxis.visible = False
#     p.xaxis.axis_label = "Datum / Uhrzeit"
#     p.xgrid.grid_line_color = None
#     p.ygrid.grid_line_color = None
#     streamlit_bokeh(p, use_container_width=True,
#                     theme="streamlit", key="timeline")
from bokeh.models import Range1d
if sched["y"]:
    src = ColumnDataSource(sched)
    h = 14 * len(sched["y"]) + 100
    p = figure(
        height=h,
        y_range=Range1d(0, len(sched["y"]) + 1),  # <-- Korrektur: Range1d statt (0, ...)
        x_axis_type="datetime",
        toolbar_location=None,
        sizing_mode="stretch_width",
        title="Gantt-Übersicht"
    )
    p.hbar(
        y="y", left="start", right="end", height=0.8,
        color="color", source=src
    )
    p.add_tools(HoverTool(tooltips=[
        ("Auftrag", "@auftrag"), ("Produkt", "@produkt"),
        ("Familie", "@familie"), ("Menge", "@menge{0,0}"),
        ("Start", "@start{%d.%m %H:%M}"), ("Ende", "@end{%d.%m %H:%M}")
    ], formatters={"@start": "datetime", "@end": "datetime"}))
    p.yaxis.visible = False
    p.xaxis.axis_label = "Datum / Uhrzeit"
    p.xgrid.grid_line_color = None
    p.ygrid.grid_line_color = None
    streamlit_bokeh(
        p,
        use_container_width=True,
        theme="streamlit",
        key="timeline"
    )
 
# ────────────────────────── 11  Auto-Refresh ──────────────────────────────────
if ss.running and ss.generation < max_gen:
    time.sleep(speed); st.rerun()
elif ss.running and ss.generation >= max_gen:
    ss.running = False
    st.toast("Maximale Generation erreicht.", icon="✅")
 
# ────────────────────────── 12  Footer ────────────────────────────────────────
st.markdown(
    f"<div style='text-align:center; color:#666; margin-top:1rem;'>"
    f"© {datetime.datetime.now().year} – GA-Dashboard</div>",
    unsafe_allow_html=True,
)