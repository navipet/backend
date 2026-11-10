"""
experimento completo de comparação das 3 abordagens de geofencing

diferenças em relação ao scripts/rodar_comparacao.py (que faz UMA rodada):
- sementes fixas (reprodutível: mesma semente => mesmos números)
- N repetições por cenário, reportando média, desvio padrão e IC 95%
- vários cenários: território único, 2 territórios, tamanho do histórico,
  distância entre territórios, outliers de GPS, sensibilidade a parâmetros,
  ruído de posição (E7: erro gaussiano em TODAS as leituras, p.ex. RSSI)
- métricas extras que usam o "gabarito" do simulador (a gente SABE onde
  ficam os territórios verdadeiros): área da zona, IoU e pior direção de fuga
- salva tudo em disco: CSV bruto, CSV resumido, testes estatísticos,
  figuras (PDF + PNG), tabelas .tex e metadata.json (versões, semente, data)

uso (a partir da pasta backend/, com a venv ativa):
    python -m scripts.experimento_completo --rapido            # teste de fumaça (~segundos)
    python -m scripts.experimento_completo                     # experimento completo (30 reps)
    python -m scripts.experimento_completo --reps 50 --seed-base 1000
    python -m scripts.experimento_completo --experimentos e1 e2 --rodar-testes
    python -m scripts.experimento_completo --experimentos e7 --saida docs/dados_e7   # só o E7

saída padrão: docs/dados_experimentais/
"""

import argparse
import csv
import json
import math
import os
import platform
import random
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, replace
from datetime import datetime

import numpy as np
from scipy import stats
from shapely.geometry import Point
from shapely.ops import transform, unary_union

from app.algorithms.convex_hull import ConvexHull
from app.algorithms.densidade import DensidadeDBSCAN
from app.algorithms.raio_fixo import RaioFixo
from app.services.comparacao import (
    PROPORCAO_TESTE_PADRAO,
    _dividir_treino_teste,  # helper interno: reutilizado para usar EXATAMENTE o mesmo split
    avaliar_abordagem,
)
from app.utils.geo import RAIO_TERRA_METROS, deslocar_ponto
from scripts.rodar_comparacao import gerar_trajetoria_fuga
from scripts.simulador_trajetorias import (
    HOME_LAT_PADRAO,
    HOME_LON_PADRAO,
    gerar_trajetoria,
)

HOME = (HOME_LAT_PADRAO, HOME_LON_PADRAO)
METROS_POR_GRAU = RAIO_TERRA_METROS * math.pi / 180  # mesmo modelo de deslocar_ponto
ANGULOS_FUGA = [k * math.pi / 4 for k in range(8)]  # 0 = norte, pi/2 = leste (vizinho)
PASSO_FUGA_M = 5
MAX_FUGA_M = 600  # se não detectar até aqui, o valor fica "censurado" em 600 m

NOMES_BONITOS = {
    "raio_fixo": "Raio fixo",
    "convex_hull": "Convex hull",
    "densidade": "DBSCAN",
}
CORES = {"raio_fixo": "#4C78A8", "convex_hull": "#F58518", "densidade": "#54A24B"}


# --------------------------------------------------------------------------
# configuração dos cenários
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Cenario:
    experimento: str
    nome: str
    num_pontos: int = 500
    distancia_segundo_m: float | None = None  # None => território único
    prob_mudanca: float = 0.03
    prop_outliers: float = 0.0
    sigma_ruido_m: float = 0.0  # E7: desvio padrão do erro gaussiano por eixo (m), em todas as leituras
    raio_passeio_m: float = 30.0
    intervalo_min: float = 5.0
    raio_fixo_m: float = 100.0
    eps_m: float = 50.0
    min_amostras: int = 5


SIGMAS_RUIDO_M = [0, 2, 5, 10, 15]  # desvio padrão por eixo; erro radial médio = 1,25 x sigma


def montar_cenarios(experimentos: list[str]) -> list[Cenario]:
    base1 = Cenario("e1", "e1_territorio_unico")
    base2 = Cenario("e2", "e2_dois_territorios", distancia_segundo_m=400.0)
    cenarios: list[Cenario] = []

    if "e1" in experimentos:
        cenarios.append(base1)
    if "e2" in experimentos:
        cenarios.append(base2)
    if "e3" in experimentos:  # tamanho do histórico (dois territórios)
        for n in [10, 20, 50, 100, 200, 500, 1000]:
            cenarios.append(replace(base2, experimento="e3", nome=f"e3_n={n}", num_pontos=n))
    if "e4" in experimentos:  # distância entre territórios
        for d in [80, 150, 250, 400, 1000, 3000]:
            cenarios.append(
                replace(base2, experimento="e4", nome=f"e4_dist={d}", distancia_segundo_m=float(d))
            )
    if "e5" in experimentos:  # outliers de GPS (território único)
        for p in [0.0, 0.01, 0.02, 0.05, 0.10]:
            cenarios.append(
                replace(base1, experimento="e5", nome=f"e5_outliers={p}", prop_outliers=p)
            )
    if "e6" in experimentos:  # sensibilidade a parâmetros
        for r in [30, 50, 75, 100, 150, 250, 400]:
            for base in (base1, base2):
                cenarios.append(
                    replace(base, experimento="e6r", nome=f"e6r_{base.nome[:2]}_R={r}", raio_fixo_m=float(r))
                )
        for eps in [10, 20, 30, 50, 75, 100, 150]:
            for ms in [3, 5, 10, 20]:
                cenarios.append(
                    replace(base2, experimento="e6d", nome=f"e6d_eps={eps}_ms={ms}", eps_m=float(eps), min_amostras=ms)
                )
    if "e7" in experimentos:  # ruído de posição em todas as leituras (ex.: RSSI)
        for s in SIGMAS_RUIDO_M:
            cenarios.append(replace(base1, experimento="e7a", nome=f"e7a_s={s:g}", sigma_ruido_m=float(s)))
        for s in SIGMAS_RUIDO_M:
            cenarios.append(replace(base2, experimento="e7b", nome=f"e7b_s={s:g}", sigma_ruido_m=float(s)))
    return cenarios


def montar_algoritmos(cfg: Cenario):
    return [
        RaioFixo(raio_metros=cfg.raio_fixo_m),
        ConvexHull(),
        DensidadeDBSCAN(eps_metros=cfg.eps_m, min_amostras=cfg.min_amostras),
    ]


# --------------------------------------------------------------------------
# geração de dados (simulador do projeto + gabarito)
# --------------------------------------------------------------------------
def gerar_historico(cfg: Cenario, seed: int):
    """devolve (pontos [(lat, lon)], centros verdadeiros dos territórios)"""
    random.seed(seed)  # o simulador usa o módulo `random` global
    segundo = None
    if cfg.distancia_segundo_m:
        # vizinho a leste da casa, a `distancia_segundo_m` metros
        segundo = deslocar_ponto(HOME[0], HOME[1], cfg.distancia_segundo_m, math.pi / 2)

    brutos = gerar_trajetoria(
        home_lat=HOME[0],
        home_lon=HOME[1],
        num_pontos=cfg.num_pontos,
        raio_passeio_metros=cfg.raio_passeio_m,
        segundo_territorio=segundo,
        prob_mudanca_territorio=cfg.prob_mudanca,
        intervalo_minutos=cfg.intervalo_min,
    )
    pontos = [(p["latitude"], p["longitude"]) for p in brutos]

    if cfg.prop_outliers > 0:
        # gerador separado: a trajetória base é idêntica entre níveis de outlier
        rng = random.Random(seed + 10_000)
        for i, (lat, lon) in enumerate(pontos):
            if rng.random() < cfg.prop_outliers:
                dist = rng.uniform(100, 300)
                ang = rng.uniform(0, 2 * math.pi)
                pontos[i] = deslocar_ponto(lat, lon, dist, ang)

    if cfg.sigma_ruido_m > 0:
        # E7: erro gaussiano independente em x e y, em TODAS as leituras (treino e teste).
        # gerador separado: a trajetória base é idêntica entre níveis de ruído
        rng = random.Random(seed + 20_000)
        for i, (lat, lon) in enumerate(pontos):
            dx = rng.gauss(0, cfg.sigma_ruido_m)  # leste (m)
            dy = rng.gauss(0, cfg.sigma_ruido_m)  # norte (m)
            pontos[i] = deslocar_ponto(lat, lon, math.hypot(dx, dy), math.atan2(dx, dy))

    centros = [HOME] + ([segundo] if segundo else [])
    return pontos, centros


# --------------------------------------------------------------------------
# métricas extras (usam o gabarito)
# --------------------------------------------------------------------------
def _para_metros(geom):
    cos0 = math.cos(math.radians(HOME[0]))
    return transform(
        lambda x, y, z=None: (
            (np.asarray(x) - HOME[1]) * METROS_POR_GRAU * cos0,
            (np.asarray(y) - HOME[0]) * METROS_POR_GRAU,
        ),
        geom,
    )


def territorio_verdadeiro_m(centros, raio_m):
    """união dos discos (em metros) onde o simulador realmente passeia"""
    cos0 = math.cos(math.radians(HOME[0]))
    discos = []
    for lat, lon in centros:
        x = (lon - HOME[1]) * METROS_POR_GRAU * cos0
        y = (lat - HOME[0]) * METROS_POR_GRAU
        discos.append(Point(x, y).buffer(raio_m, quad_segs=32))
    return unary_union(discos)


def distancia_deteccao(alg, zona, origem, angulo) -> float:
    """distância (m) a partir de `origem` até o primeiro ponto fora da zona.
    se nunca sai até MAX_FUGA_M devolve MAX_FUGA_M (valor censurado)."""
    d = 0
    while d <= MAX_FUGA_M:
        ponto = deslocar_ponto(origem[0], origem[1], d, angulo)
        if not alg.esta_dentro(zona, ponto):
            return float(d)
        d += PASSO_FUGA_M
    return float(MAX_FUGA_M)


NAN = float("nan")


def avaliar_repeticao(cfg: Cenario, seed: int) -> list[dict]:
    pontos, centros = gerar_historico(cfg, seed)
    fuga_norte = gerar_trajetoria_fuga(HOME[0], HOME[1], 200.0, 20)
    verdade = territorio_verdadeiro_m(centros, cfg.raio_passeio_m)
    treino, _ = _dividir_treino_teste(pontos, PROPORCAO_TESTE_PADRAO)

    linhas = []
    for alg in montar_algoritmos(cfg):
        linha = {
            "experimento": cfg.experimento,
            "cenario": cfg.nome,
            "rep": seed,
            "abordagem": alg.nome,
            "num_pontos": cfg.num_pontos,
            "distancia_segundo_m": cfg.distancia_segundo_m or 0,
            "prop_outliers": cfg.prop_outliers,
            "sigma_ruido_m": cfg.sigma_ruido_m,
            "raio_fixo_m": cfg.raio_fixo_m,
            "eps_m": cfg.eps_m,
            "min_amostras": cfg.min_amostras,
        }
        try:
            r = avaliar_abordagem(alg, pontos, fuga_norte)  # métricas originais do projeto
            zona = alg.construir_zona(treino)  # determinística: mesma zona de acima
        except ValueError:
            linha.update(
                falhou=1, fp=NAN, cobertura=NAN, latencia_min=NAN, tempo_ms=NAN,
                area_m2=NAN, iou=NAN, recall_area=NAN, excesso=NAN,
                dist_media_m=NAN, dist_pior_m=NAN,
            )
            linhas.append(linha)
            continue

        zona_m = _para_metros(zona)
        inter = zona_m.intersection(verdade).area
        uniao = zona_m.union(verdade).area
        dists = [distancia_deteccao(alg, zona, HOME, a) for a in ANGULOS_FUGA]

        linha.update(
            falhou=0,
            fp=r.taxa_falsos_positivos,
            cobertura=r.cobertura_territorial,
            latencia_min=(
                r.latencia_deteccao_pontos * cfg.intervalo_min
                if r.latencia_deteccao_pontos is not None
                else NAN
            ),
            tempo_ms=r.tempo_construcao_zona_ms,
            area_m2=zona_m.area,
            iou=inter / uniao if uniao > 0 else NAN,
            recall_area=inter / verdade.area,
            excesso=zona_m.difference(verdade).area / verdade.area,
            dist_media_m=float(np.mean(dists)),
            dist_pior_m=float(np.max(dists)),
        )
        linhas.append(linha)
    return linhas


# --------------------------------------------------------------------------
# agregação estatística
# --------------------------------------------------------------------------
METRICAS = [
    "fp", "cobertura", "latencia_min", "tempo_ms",
    "area_m2", "iou", "recall_area", "excesso", "dist_media_m", "dist_pior_m",
]


def estatisticas(valores: list[float]) -> dict:
    v = np.array([x for x in valores if not math.isnan(x)], dtype=float)
    n = len(v)
    if n == 0:
        return {"media": NAN, "desvio": NAN, "ic95": NAN, "n": 0}
    media = float(v.mean())
    desvio = float(v.std(ddof=1)) if n > 1 else 0.0
    ic = float(stats.t.ppf(0.975, n - 1) * desvio / math.sqrt(n)) if n > 1 else NAN
    return {"media": media, "desvio": desvio, "ic95": ic, "n": n}


def agregar(brutos: list[dict]) -> dict:
    """{(cenario, abordagem): {metrica: stats, 'falhas': %, 'params': {...}}}"""
    grupos: dict = {}
    for linha in brutos:
        grupos.setdefault((linha["cenario"], linha["abordagem"]), []).append(linha)
    resumo = {}
    for chave, linhas in grupos.items():
        validas = [l for l in linhas if l["falhou"] == 0]
        entrada = {m: estatisticas([l[m] for l in validas]) for m in METRICAS}
        entrada["falhas"] = 100.0 * sum(l["falhou"] for l in linhas) / len(linhas)
        entrada["n_reps"] = len(linhas)
        entrada["params"] = {
            k: linhas[0][k]
            for k in ("experimento", "num_pontos", "distancia_segundo_m",
                      "prop_outliers", "sigma_ruido_m", "raio_fixo_m", "eps_m", "min_amostras")
        }
        resumo[chave] = entrada
    return resumo


def testes_pareados(brutos: list[dict], cenarios_alvo: list[str]) -> list[dict]:
    """Wilcoxon pareado (mesma semente => mesmo histórico para as 3 abordagens)"""
    saida = []
    pares = [("raio_fixo", "convex_hull"), ("raio_fixo", "densidade"), ("convex_hull", "densidade")]
    for cenario in cenarios_alvo:
        por = {}
        for l in brutos:
            if l["cenario"] == cenario and l["falhou"] == 0:
                por.setdefault(l["abordagem"], {})[l["rep"]] = l
        for a, b in pares:
            comuns = sorted(set(por.get(a, {})) & set(por.get(b, {})))
            for metrica in ["fp", "iou", "dist_pior_m"]:
                x = np.array([por[a][s][metrica] for s in comuns])
                y = np.array([por[b][s][metrica] for s in comuns])
                if len(comuns) < 5:
                    continue
                try:
                    p = float(stats.wilcoxon(x, y).pvalue)
                except ValueError:  # todas as diferenças iguais a zero
                    p = NAN
                saida.append({
                    "cenario": cenario, "a": a, "b": b, "metrica": metrica,
                    "n_pares": len(comuns), "mediana_a": float(np.median(x)),
                    "mediana_b": float(np.median(y)),
                    "mediana_dif_a_menos_b": float(np.median(x - y)), "p_wilcoxon": p,
                })
    return saida


# --------------------------------------------------------------------------
# saída: CSVs
# --------------------------------------------------------------------------
def salvar_csv_dicts(linhas: list[dict], caminho: str) -> None:
    if not linhas:
        return
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    print(f"  salvo: {caminho}")


def linhas_do_resumo(resumo: dict) -> list[dict]:
    linhas = []
    for (cenario, abordagem), e in resumo.items():
        linha = {"cenario": cenario, "abordagem": abordagem, **e["params"],
                 "n_reps": e["n_reps"], "falhas_pct": round(e["falhas"], 2)}
        for m in METRICAS:
            s = e[m]
            linha[f"{m}_media"] = s["media"]
            linha[f"{m}_desvio"] = s["desvio"]
            linha[f"{m}_ic95"] = s["ic95"]
        linhas.append(linha)
    return linhas


# --------------------------------------------------------------------------
# saída: tabelas LaTeX
# --------------------------------------------------------------------------
def fmt(x: float, casas: int = 1, escala: float = 1.0) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "--"
    return f"{x * escala:.{casas}f}".replace(".", ",")


def celula(s: dict, casas: int, escala: float = 1.0) -> str:
    if s["n"] == 0:
        return "--"
    return f"{fmt(s['media'], casas, escala)} $\\pm$ {fmt(s['desvio'], casas, escala)}"


def _tabela_tex(caminho, legenda, rotulo, cabecalho, linhas, colunas="l"):
    spec = "|" + "|".join([colunas] + ["c"] * (len(cabecalho) - 1)) + "|"
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\\begin{table}[H]\n\\centering\n")
        f.write(f"\\caption{{{legenda}}}\n\\label{{{rotulo}}}\n\\footnotesize\n")
        f.write(f"\\resizebox{{\\textwidth}}{{!}}{{%\n\\begin{{tabular}}{{{spec}}}\n\\hline\n")
        f.write(" & ".join(f"\\textbf{{{c}}}" for c in cabecalho) + " \\\\\n\\hline\n")
        for l in linhas:
            f.write(" & ".join(l) + " \\\\\n\\hline\n")
        f.write("\\end{tabular}}\n\\end{table}\n")
    print(f"  salvo: {caminho}")


def gerar_tabelas(resumo: dict, reps: int, pasta: str) -> None:
    for exp, cenario, titulo in [
        ("e1", "e1_territorio_unico", "território único"),
        ("e2", "e2_dois_territorios", "dois territórios não contíguos (vizinho a 400\\,m)"),
    ]:
        if (cenario, "raio_fixo") not in resumo:
            continue
        linhas_a, linhas_b = [], []
        for ab in ["raio_fixo", "convex_hull", "densidade"]:
            e = resumo[(cenario, ab)]
            nome = NOMES_BONITOS[ab]
            falhas = fmt(e["falhas"], 1).replace("--", "0,0")
            linhas_a.append([
                nome, celula(e["fp"], 1, 100), celula(e["cobertura"], 1, 100),
                celula(e["latencia_min"], 1), celula(e["dist_pior_m"], 0), f"{falhas}\\%",
            ])
            linhas_b.append([
                nome, celula(e["area_m2"], 0), celula(e["iou"], 2),
                celula(e["recall_area"], 2), celula(e["excesso"], 1), celula(e["tempo_ms"], 2),
            ])
        _tabela_tex(
            os.path.join(pasta, f"tab_{exp}_a.tex"),
            f"Métricas de detecção -- {titulo} (média $\\pm$ desvio padrão em {reps} repetições).",
            f"tab:{exp}_a",
            ["Abordagem", "Falsos pos. (\\%)", "Cobertura (\\%)", "Latência norte (min)",
             "Detecção, pior direção (m)", "Falhas"],
            linhas_a,
        )
        _tabela_tex(
            os.path.join(pasta, f"tab_{exp}_b.tex"),
            f"Métricas geométricas contra o território verdadeiro -- {titulo} "
            f"(média $\\pm$ desvio padrão em {reps} repetições).",
            f"tab:{exp}_b",
            ["Abordagem", "Área (m$^2$)", "IoU", "Cobertura da área real",
             "Área excedente (×)", "Tempo (ms)"],
            linhas_b,
        )


def gerar_tabela_testes(testes: list[dict], pasta: str) -> None:
    alvo = [t for t in testes if t["cenario"] == "e2_dois_territorios"]
    if not alvo:
        return
    nomes_m = {"fp": "Falsos positivos (p.p.)", "iou": "IoU", "dist_pior_m": "Detecção pior dir. (m)"}
    linhas = []
    for t in alvo:
        esc = 100 if t["metrica"] == "fp" else 1
        casas = 1 if t["metrica"] in ("fp", "dist_pior_m") else 2
        p = t["p_wilcoxon"]
        ptxt = "--" if math.isnan(p) else ("$<$0,001" if p < 0.001 else fmt(p, 3))
        linhas.append([
            f"{NOMES_BONITOS[t['a']]} vs {NOMES_BONITOS[t['b']]}", nomes_m[t["metrica"]],
            fmt(t["mediana_dif_a_menos_b"], casas, esc), ptxt,
        ])
    _tabela_tex(
        os.path.join(pasta, "tab_testes.tex"),
        "Comparação pareada (Wilcoxon) no cenário de dois territórios; "
        "diferença = mediana(A) $-$ mediana(B) sobre as mesmas sementes.",
        "tab:testes", ["Comparação", "Métrica", "Mediana da diferença", "Valor-p"], linhas,
    )


def gerar_tabela_ruido(resumo: dict, reps: int, pasta: str) -> None:
    """E7: FP e IoU por nível de ruído, um bloco por cenário (território único / dois territórios)"""
    ab_ = ["raio_fixo", "convex_hull", "densidade"]
    for exp, prefixo, titulo in [("e7a", "e7a", "território único"), ("e7b", "e7b", "dois territórios (vizinho a 400\\,m)")]:
        cens = sorted([c for (c, a) in resumo if c.startswith(prefixo + "_") and a == "raio_fixo"],
                      key=lambda c: resumo[(c, "raio_fixo")]["params"]["sigma_ruido_m"])
        if not cens:
            continue
        linhas = []
        for c in cens:
            sg = resumo[(c, "raio_fixo")]["params"]["sigma_ruido_m"]
            linha = [f"{fmt(sg, 0)}"]
            linha += [celula(resumo[(c, a)]["fp"], 1, 100) for a in ab_]
            linha += [celula(resumo[(c, a)]["iou"], 2) for a in ab_]
            linha += [celula(resumo[(c, a)]["dist_pior_m"], 0) for a in ["convex_hull", "densidade"]]
            linhas.append(linha)
        _tabela_tex(
            os.path.join(pasta, f"tab_{exp}.tex"),
            f"E7: efeito do ruído de posição -- {titulo} (média $\\pm$ desvio padrão em {reps} repetições). "
            "$\\sigma$ = desvio padrão do erro por eixo (m).",
            f"tab:{exp}",
            ["$\\sigma$ (m)", "FP raio (\\%)", "FP hull (\\%)", "FP DBSCAN (\\%)",
             "IoU raio", "IoU hull", "IoU DBSCAN", "Detec. hull (m)", "Detec. DBSCAN (m)"],
            linhas,
        )


# --------------------------------------------------------------------------
# saída: figuras
# --------------------------------------------------------------------------
def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    return plt


def _salvar(fig, pasta, nome):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(pasta, f"{nome}.{ext}"), dpi=200, bbox_inches="tight")
    print(f"  salvo: {os.path.join(pasta, nome)}.pdf/.png")


def fig_barras(resumo, cenario, pasta, nome):
    plt = _plt()
    metricas = [("fp", "Falsos positivos (%)", 100), ("cobertura", "Cobertura (%)", 100),
                ("iou", "IoU com território real", 1), ("dist_pior_m", "Detecção, pior direção (m)", 1)]
    fig, axes = plt.subplots(1, 4, figsize=(11, 3))
    abs_ = ["raio_fixo", "convex_hull", "densidade"]
    for ax, (m, titulo, esc) in zip(axes, metricas):
        medias = [resumo[(cenario, a)][m]["media"] * esc for a in abs_]
        ics = [resumo[(cenario, a)][m]["ic95"] * esc for a in abs_]
        ics = [0 if math.isnan(i) else i for i in ics]
        ax.bar(range(3), [0 if math.isnan(x) else x for x in medias], yerr=ics, capsize=3,
               color=[CORES[a] for a in abs_])
        ax.set_xticks(range(3))
        ax.set_xticklabels([NOMES_BONITOS[a] for a in abs_], rotation=20)
        ax.set_title(titulo, fontsize=9)
    fig.tight_layout()
    _salvar(fig, pasta, nome)
    plt.close(fig)


def fig_varredura(resumo, experimento, chave_param, rotulo_x, metricas, pasta, nome, log_x=False):
    plt = _plt()
    fig, axes = plt.subplots(1, len(metricas), figsize=(3.6 * len(metricas), 3))
    cens = sorted({c for (c, _), e in resumo.items() if e["params"]["experimento"] == experimento},
                  key=lambda c: resumo[(c, "raio_fixo")]["params"][chave_param])
    xs = [resumo[(c, "raio_fixo")]["params"][chave_param] for c in cens]
    for ax, (m, titulo, esc) in zip(np.atleast_1d(axes), metricas):
        for ab in ["raio_fixo", "convex_hull", "densidade"]:
            if m == "falhas":
                ys = [resumo[(c, ab)]["falhas"] for c in cens]
                lo = hi = ys
            else:
                ys = [resumo[(c, ab)][m]["media"] * esc for c in cens]
                ic = [resumo[(c, ab)][m]["ic95"] * esc for c in cens]
                lo = [y - (0 if math.isnan(i) else i) for y, i in zip(ys, ic)]
                hi = [y + (0 if math.isnan(i) else i) for y, i in zip(ys, ic)]
            ax.plot(xs, ys, marker="o", ms=3, color=CORES[ab], label=NOMES_BONITOS[ab])
            ax.fill_between(xs, lo, hi, color=CORES[ab], alpha=0.15)
        if log_x:
            ax.set_xscale("log")
        ax.set_xlabel(rotulo_x)
        ax.set_title(titulo, fontsize=9)
    np.atleast_1d(axes)[0].legend(fontsize=7)
    fig.tight_layout()
    _salvar(fig, pasta, nome)
    plt.close(fig)


def fig_parametros(resumo, pasta):
    plt = _plt()
    fig, axes = plt.subplots(2, 2, figsize=(9, 6))
    # linha 1: raio fixo vs R, em e1 e e2
    for base, estilo, rot in (("e1", "-", "território único"), ("e2", "--", "dois territórios")):
        cens = sorted([c for (c, a) in resumo if c.startswith(f"e6r_{base}_") and a == "raio_fixo"],
                      key=lambda c: resumo[(c, "raio_fixo")]["params"]["raio_fixo_m"])
        xs = [resumo[(c, "raio_fixo")]["params"]["raio_fixo_m"] for c in cens]
        axes[0][0].plot(xs, [resumo[(c, "raio_fixo")]["fp"]["media"] * 100 for c in cens],
                        estilo, marker="o", ms=3, color=CORES["raio_fixo"], label=rot)
        axes[0][1].plot(xs, [resumo[(c, "raio_fixo")]["iou"]["media"] for c in cens],
                        estilo, marker="o", ms=3, color=CORES["raio_fixo"], label=rot)
    axes[0][0].set_title("Raio fixo: falsos positivos (%) vs R", fontsize=9)
    axes[0][1].set_title("Raio fixo: IoU vs R", fontsize=9)
    for ax in axes[0]:
        ax.set_xlabel("raio R (m)")
        ax.legend(fontsize=7)
    # linha 2: DBSCAN vs eps, uma linha por min_amostras (dois territórios)
    for ms in sorted({e["params"]["min_amostras"] for (c, a), e in resumo.items()
                      if c.startswith("e6d_") and a == "densidade"}):
        cens = sorted([c for (c, a), e in resumo.items()
                       if c.startswith("e6d_") and a == "densidade" and e["params"]["min_amostras"] == ms],
                      key=lambda c: resumo[(c, "densidade")]["params"]["eps_m"])
        xs = [resumo[(c, "densidade")]["params"]["eps_m"] for c in cens]
        axes[1][0].plot(xs, [resumo[(c, "densidade")]["fp"]["media"] * 100 for c in cens],
                        marker="o", ms=3, label=f"min_amostras={ms}")
        axes[1][1].plot(xs, [resumo[(c, "densidade")]["iou"]["media"] for c in cens],
                        marker="o", ms=3, label=f"min_amostras={ms}")
    axes[1][0].set_title("DBSCAN: falsos positivos (%) vs eps", fontsize=9)
    axes[1][1].set_title("DBSCAN: IoU vs eps", fontsize=9)
    for ax in axes[1]:
        ax.set_xlabel("eps (m)")
        ax.legend(fontsize=7)
    fig.tight_layout()
    _salvar(fig, pasta, "fig_parametros")
    plt.close(fig)


def fig_ruido(resumo, pasta):
    """E7: linha de cima = território único, linha de baixo = dois territórios"""
    plt = _plt()
    metricas = [("fp", "Falsos positivos (%)", 100), ("iou", "IoU com território real", 1),
                ("dist_pior_m", "Detecção, pior direção (m)", 1)]
    fig, axes = plt.subplots(2, 3, figsize=(11, 6))
    for i, (prefixo, rot) in enumerate((("e7a", "território único"), ("e7b", "dois territórios"))):
        cens = sorted([c for (c, a) in resumo if c.startswith(prefixo + "_") and a == "raio_fixo"],
                      key=lambda c: resumo[(c, "raio_fixo")]["params"]["sigma_ruido_m"])
        xs = [resumo[(c, "raio_fixo")]["params"]["sigma_ruido_m"] for c in cens]
        for j, (m, titulo, esc) in enumerate(metricas):
            ax = axes[i][j]
            for ab in ["raio_fixo", "convex_hull", "densidade"]:
                ys = [resumo[(c, ab)][m]["media"] * esc for c in cens]
                ic = [resumo[(c, ab)][m]["ic95"] * esc for c in cens]
                lo = [y - (0 if math.isnan(k) else k) for y, k in zip(ys, ic)]
                hi = [y + (0 if math.isnan(k) else k) for y, k in zip(ys, ic)]
                ax.plot(xs, ys, marker="o", ms=3, color=CORES[ab], label=NOMES_BONITOS[ab])
                ax.fill_between(xs, lo, hi, color=CORES[ab], alpha=0.15)
            ax.set_xlabel("ruído de posição, sigma por eixo (m)")
            ax.set_title(f"{titulo} -- {rot}", fontsize=9)
    axes[0][0].legend(fontsize=7)
    fig.tight_layout()
    _salvar(fig, pasta, "fig_ruido")
    plt.close(fig)


def fig_mapa(pasta, seed):
    """uma rodada ilustrativa: pontos, zona de cada abordagem e território real"""
    plt = _plt()
    cenarios = [Cenario("e1", "e1_territorio_unico"),
                Cenario("e2", "e2_dois_territorios", distancia_segundo_m=400.0)]
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.2))
    for i, cfg in enumerate(cenarios):
        pontos, centros = gerar_historico(cfg, seed)
        treino, teste = _dividir_treino_teste(pontos, PROPORCAO_TESTE_PADRAO)
        verdade = territorio_verdadeiro_m(centros, cfg.raio_passeio_m)
        pm = lambda pts: np.array([_para_metros(Point(lon, lat)).coords[0] for lat, lon in pts])
        xt, xe = pm(treino), pm(teste)
        for j, alg in enumerate(montar_algoritmos(cfg)):
            ax = axes[i][j]
            ax.scatter(xt[:, 0], xt[:, 1], s=4, c="#999999", label="treino")
            ax.scatter(xe[:, 0], xe[:, 1], s=6, c="#E45756", label="teste")
            for g in getattr(verdade, "geoms", [verdade]):
                ax.plot(*g.exterior.xy, "k--", lw=0.8)
            try:
                zona_m = _para_metros(alg.construir_zona(treino))
                for g in getattr(zona_m, "geoms", [zona_m]):
                    ax.fill(*g.exterior.xy, color=CORES[alg.nome], alpha=0.25)
                    ax.plot(*g.exterior.xy, color=CORES[alg.nome], lw=1.2)
            except ValueError:
                ax.text(0.5, 0.5, "falhou (sem cluster)", transform=ax.transAxes, ha="center")
            ax.set_aspect("equal", adjustable="datalim")
            ax.set_title(f"{NOMES_BONITOS[alg.nome]} -- "
                         f"{'território único' if i == 0 else 'dois territórios'}", fontsize=9)
            ax.set_xlabel("x (m)")
            ax.set_ylabel("y (m)")
    axes[0][0].legend(fontsize=7, markerscale=2)
    fig.tight_layout()
    _salvar(fig, pasta, "fig_mapa_zonas")
    plt.close(fig)



def macros_de_resultados(resumo: dict) -> list[str]:
    """macros LaTeX com os números citados no TEXTO do relatório, para que o texto
    se atualize sozinho quando o experimento for rodado de novo"""
    def v(nome, cenario, ab, metrica, escala=1.0, casas=1):
        e = resumo.get((cenario, ab))
        if e is None or e[metrica]["n"] == 0:
            return f"\\newcommand{{\\{nome}}}{{?}}"
        return f"\\newcommand{{\\{nome}}}{{{fmt(e[metrica]['media'], casas, escala)}}}"

    e1, e2 = "e1_territorio_unico", "e2_dois_territorios"
    r, h, d = "raio_fixo", "convex_hull", "densidade"
    L = [
        v("EumFPRaio", e1, r, "fp", 100), v("EumFPHull", e1, h, "fp", 100), v("EumFPDens", e1, d, "fp", 100),
        v("EumIoURaio", e1, r, "iou", 1, 2), v("EumIoUHull", e1, h, "iou", 1, 2), v("EumIoUDens", e1, d, "iou", 1, 2),
        v("EumAreaRaio", e1, r, "area_m2", 1, 0), v("EumAreaHull", e1, h, "area_m2", 1, 0),
        v("EumPiorRaio", e1, r, "dist_pior_m", 1, 0), v("EumPiorHull", e1, h, "dist_pior_m", 1, 0),
        v("EdoisFPRaio", e2, r, "fp", 100), v("EdoisFPHull", e2, h, "fp", 100), v("EdoisFPDens", e2, d, "fp", 100),
        v("EdoisIoURaio", e2, r, "iou", 1, 2), v("EdoisIoUHull", e2, h, "iou", 1, 2), v("EdoisIoUDens", e2, d, "iou", 1, 2),
        v("EdoisAreaHull", e2, h, "area_m2", 1, 0), v("EdoisAreaDens", e2, d, "area_m2", 1, 0),
        v("EdoisPiorHull", e2, h, "dist_pior_m", 1, 0), v("EdoisPiorDens", e2, d, "dist_pior_m", 1, 0),
        v("EtresFPHullDez", "e3_n=10", h, "fp", 100), v("EtresFPDensDez", "e3_n=10", d, "fp", 100),
        v("EtresIoUDensCem", "e3_n=100", d, "iou", 1, 2), v("EtresIoUDensMil", "e3_n=1000", d, "iou", 1, 2),
        v("EquatroIoUHullOitenta", "e4_dist=80", h, "iou", 1, 2), v("EquatroIoUDensOitenta", "e4_dist=80", d, "iou", 1, 2),
        v("EquatroIoUDensCento", "e4_dist=150", d, "iou", 1, 2),
        v("EquatroIoUHullMil", "e4_dist=1000", h, "iou", 1, 2), v("EquatroIoUHullTresMil", "e4_dist=3000", h, "iou", 1, 2),
        v("EcincoIoUHullUm", "e5_outliers=0.01", h, "iou", 1, 2), v("EcincoIoUDensUm", "e5_outliers=0.01", d, "iou", 1, 2),
        v("EcincoIoUHullDez", "e5_outliers=0.1", h, "iou", 1, 2), v("EcincoIoUDensDez", "e5_outliers=0.1", d, "iou", 1, 2),
        v("EcincoFPHullDez", "e5_outliers=0.1", h, "fp", 100), v("EcincoFPDensDez", "e5_outliers=0.1", d, "fp", 100),
        v("EseteIoUHullCinco", "e7b_s=5", h, "iou", 1, 2), v("EseteIoUDensCinco", "e7b_s=5", d, "iou", 1, 2),
        v("EseteIoUHullDez", "e7b_s=10", h, "iou", 1, 2), v("EseteIoUDensDez", "e7b_s=10", d, "iou", 1, 2),
        v("EseteFPDensDez", "e7b_s=10", d, "fp", 100), v("EseteFPHullDez", "e7b_s=10", h, "fp", 100),
        v("EseteIoUDensQuinze", "e7b_s=15", d, "iou", 1, 2), v("EseteIoUHullQuinze", "e7b_s=15", h, "iou", 1, 2),
        v("EseteaFPHullDez", "e7a_s=10", h, "fp", 100), v("EseteaIoUHullDez", "e7a_s=10", h, "iou", 1, 2),
        v("EseisIoURTrinta", "e6r_e1_R=30", r, "iou", 1, 2), v("EseisFPRTrinta", "e6r_e1_R=30", r, "fp", 100),
        v("EseisFPDoisRDuzCinq", "e6r_e2_R=250", r, "fp", 100), v("EseisIoUDoisRQuatroc", "e6r_e2_R=400", r, "iou", 1, 2),
    ]
    return L

# --------------------------------------------------------------------------
# metadata e macros
# --------------------------------------------------------------------------
def versao_git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "indisponível"


def rodar_pytest(pasta: str) -> int | None:
    print("rodando pytest ...")
    r = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"], capture_output=True, text=True)
    with open(os.path.join(pasta, "pytest.txt"), "w", encoding="utf-8") as f:
        f.write(r.stdout + r.stderr)
    m = re.search(r"(\d+) passed", r.stdout)
    falhou = re.search(r"(\d+) failed", r.stdout)
    print("  " + (r.stdout.strip().splitlines() or ["(sem saída)"])[-1])
    return int(m.group(1)) if m and not falhou else None


def main():
    ap = argparse.ArgumentParser(description="Experimento completo de geofencing")
    ap.add_argument("--reps", type=int, default=30, help="repetições por cenário")
    ap.add_argument("--seed-base", type=int, default=2026)
    ap.add_argument("--experimentos", nargs="+", default=["e1", "e2", "e3", "e4", "e5", "e6", "e7"],
                    choices=["e1", "e2", "e3", "e4", "e5", "e6", "e7"])
    ap.add_argument("--saida", default="docs/dados_experimentais")
    ap.add_argument("--rapido", action="store_true", help="3 repetições, só para testar")
    ap.add_argument("--rodar-testes", action="store_true", help="roda pytest e salva a saída")
    args = ap.parse_args()

    reps = 3 if args.rapido else args.reps
    os.makedirs(args.saida, exist_ok=True)
    cenarios = montar_cenarios(args.experimentos)
    print(f"{len(cenarios)} cenários x {reps} repetições x 3 abordagens")

    # aquecimento: a 1ª chamada do sklearn/shapely é mais lenta e contaminaria o tempo_ms
    avaliar_repeticao(cenarios[0], args.seed_base - 1)

    brutos: list[dict] = []
    for k, cfg in enumerate(cenarios, start=1):
        for i in range(reps):
            brutos.extend(avaliar_repeticao(cfg, args.seed_base + i))
        print(f"  [{k}/{len(cenarios)}] {cfg.nome}")

    resumo = agregar(brutos)
    testes = testes_pareados(brutos, ["e1_territorio_unico", "e2_dois_territorios", "e7b_s=5", "e7b_s=10"])

    print("salvando dados:")
    salvar_csv_dicts(brutos, os.path.join(args.saida, "brutos.csv"))
    salvar_csv_dicts(linhas_do_resumo(resumo), os.path.join(args.saida, "resumo.csv"))
    salvar_csv_dicts(testes, os.path.join(args.saida, "testes_pareados.csv"))

    print("gerando tabelas .tex:")
    gerar_tabelas(resumo, reps, args.saida)
    gerar_tabela_testes(testes, args.saida)
    if "e7" in args.experimentos:
        gerar_tabela_ruido(resumo, reps, args.saida)

    print("gerando figuras:")
    if "e1" in args.experimentos:
        fig_barras(resumo, "e1_territorio_unico", args.saida, "fig_barras_e1")
    if "e2" in args.experimentos:
        fig_barras(resumo, "e2_dois_territorios", args.saida, "fig_barras_e2")
    if "e1" in args.experimentos and "e2" in args.experimentos:
        fig_mapa(args.saida, args.seed_base)
    if "e3" in args.experimentos:
        fig_varredura(resumo, "e3", "num_pontos", "pontos no histórico",
                      [("fp", "Falsos positivos (%)", 100), ("iou", "IoU", 1), ("falhas", "Falhas (%)", 1)],
                      args.saida, "fig_historico", log_x=True)
    if "e4" in args.experimentos:
        fig_varredura(resumo, "e4", "distancia_segundo_m", "distância entre territórios (m)",
                      [("fp", "Falsos positivos (%)", 100), ("iou", "IoU", 1),
                       ("dist_pior_m", "Detecção, pior direção (m)", 1)],
                      args.saida, "fig_distancia", log_x=True)
    if "e5" in args.experimentos:
        fig_varredura(resumo, "e5", "prop_outliers", "proporção de outliers de GPS",
                      [("fp", "Falsos positivos (%)", 100), ("iou", "IoU", 1),
                       ("area_m2", "Área da zona (m²)", 1)],
                      args.saida, "fig_outliers")
    if "e6" in args.experimentos:
        fig_parametros(resumo, args.saida)
    if "e7" in args.experimentos:
        fig_ruido(resumo, args.saida)

    n_testes = rodar_pytest(args.saida) if args.rodar_testes else None

    meta = {
        "data_execucao": datetime.now().isoformat(timespec="seconds"),
        "comando": " ".join(sys.argv),
        "reps": reps, "seed_base": args.seed_base, "experimentos": args.experimentos,
        "split_teste": PROPORCAO_TESTE_PADRAO, "max_fuga_m": MAX_FUGA_M,
        "git_commit": versao_git(),
        "python": platform.python_version(), "so": platform.platform(),
        "numpy": np.__version__,
        "shapely": __import__("shapely").__version__,
        "scikit_learn": __import__("sklearn").__version__,
        "scipy": __import__("scipy").__version__,
        "testes_passaram": n_testes,
        "cenarios": [asdict(c) for c in cenarios],
    }
    with open(os.path.join(args.saida, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    with open(os.path.join(args.saida, "macros.tex"), "w", encoding="utf-8") as f:
        f.write(f"\\newcommand{{\\NumReps}}{{{reps}}}\n")
        f.write(f"\\newcommand{{\\SeedBase}}{{{args.seed_base}}}\n")
        f.write(f"\\newcommand{{\\NumTestes}}{{{n_testes if n_testes is not None else '?'}}}\n")
        f.write(f"\\newcommand{{\\DataExperimento}}{{{datetime.now().strftime('%d/%m/%Y')}}}\n")
        f.write("\n".join(macros_de_resultados(resumo)) + "\n")
    print(f"pronto. tudo em {args.saida}/")


if __name__ == "__main__":
    main()