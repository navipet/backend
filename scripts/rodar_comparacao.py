"""
roda a comparação experimental entre as 3 abordagens de geofencing, usando dados gerados
pelo simulador de trajetórias (sem precisar de API nem banco rodando)

uso básico (só imprime a tabela no terminal):
    python -m scripts.rodar_comparacao

exportando o relatório consolidado (CSV + gráfico de barras), para usar
como figura no TCC:
    python -m scripts.rodar_comparacao --num-pontos 500 \
        --output-csv docs/dados_experimentais/resultado.csv \
        --output-grafico docs/dados_experimentais/resultado.png

testando o cenário central da Seção 5.3 (2 territórios não contíguos):
    python -m scripts.rodar_comparacao --num-pontos 500 \
        --segundo-lat -5.1200 --segundo-lon -42.8400 \
        --prob-mudanca-territorio 0.03
"""

import argparse
import csv
import os

from app.algorithms.convex_hull import ConvexHull
from app.algorithms.densidade import DensidadeDBSCAN
from app.algorithms.raio_fixo import RaioFixo
from app.services.comparacao import comparar_abordagens
from app.utils.geo import deslocar_ponto
from scripts.simulador_trajetorias import (
    HOME_LAT_PADRAO,
    HOME_LON_PADRAO,
    gerar_trajetoria,
)


def gerar_trajetoria_fuga(
    lat_inicio: float, lon_inicio: float, distancia_max_metros: float, passos: int
) -> list[tuple[float, float]]:
    """simula o pet se afastando em linha reta, para medir a latência de detecção"""
    pontos = []
    for i in range(1, passos + 1):
        distancia = distancia_max_metros * i / passos
        lat, lon = deslocar_ponto(lat_inicio, lon_inicio, distancia, 0.0)
        pontos.append((lat, lon))
    return pontos


def imprimir_tabela(resultados, intervalo_minutos: float) -> None:
    cabecalho = (
        f"{'abordagem':<14}{'falsos_pos':>12}{'cobertura':>12}"
        f"{'latencia':>14}{'tempo_ms':>12}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))
    for r in resultados:
        latencia_str = (
            f"{r.latencia_deteccao_pontos * intervalo_minutos:.1f} min"
            if r.latencia_deteccao_pontos is not None
            else "n/d"
        )
        print(
            f"{r.abordagem:<14}"
            f"{r.taxa_falsos_positivos:>11.1%} "
            f"{r.cobertura_territorial:>11.1%} "
            f"{latencia_str:>13} "
            f"{r.tempo_construcao_zona_ms:>10.2f}"
        )


def salvar_csv(resultados, caminho: str, intervalo_minutos: float) -> None:
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "abordagem",
                "taxa_falsos_positivos",
                "cobertura_territorial",
                "latencia_deteccao_minutos",
                "tempo_construcao_zona_ms",
            ]
        )
        for r in resultados:
            latencia_min = (
                r.latencia_deteccao_pontos * intervalo_minutos
                if r.latencia_deteccao_pontos is not None
                else ""
            )
            writer.writerow(
                [
                    r.abordagem,
                    r.taxa_falsos_positivos,
                    r.cobertura_territorial,
                    latencia_min,
                    r.tempo_construcao_zona_ms,
                ]
            )
    print(f"CSV salvo em {caminho}")


def gerar_grafico(resultados, caminho: str) -> None:
    """gera um gráfico de barras (falsos positivos x cobertura) por abordagem"""
    import matplotlib

    matplotlib.use("Agg")  # backend sem interface gráfica, só para salvar arquivo
    import matplotlib.pyplot as plt

    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)

    nomes = [r.abordagem for r in resultados]
    falsos_positivos = [r.taxa_falsos_positivos * 100 for r in resultados]
    coberturas = [r.cobertura_territorial * 100 for r in resultados]

    posicoes = range(len(nomes))
    largura = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(
        [p - largura / 2 for p in posicoes],
        falsos_positivos,
        largura,
        label="Falsos positivos (%)",
    )
    ax.bar(
        [p + largura / 2 for p in posicoes],
        coberturas,
        largura,
        label="Cobertura territorial (%)",
    )
    ax.set_xticks(list(posicoes))
    ax.set_xticklabels(nomes)
    ax.set_ylabel("%")
    ax.set_title("Comparação experimental das abordagens de geofencing")
    ax.legend()
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    print(f"Gráfico salvo em {caminho}")


def main():
    parser = argparse.ArgumentParser(
        description="Comparação experimental das 3 abordagens de geofencing"
    )
    parser.add_argument("--num-pontos", type=int, default=300)
    parser.add_argument("--intervalo-minutos", type=float, default=5.0)
    parser.add_argument("--raio-passeio", type=float, default=30.0, help="metros")
    parser.add_argument("--distancia-fuga", type=float, default=200.0, help="metros")
    parser.add_argument("--passos-fuga", type=int, default=20)
    parser.add_argument(
        "--segundo-lat", type=float, default=None, help="ativa cenário de 2 territórios"
    )
    parser.add_argument("--segundo-lon", type=float, default=None)
    parser.add_argument("--prob-mudanca-territorio", type=float, default=0.03)
    parser.add_argument("--output-csv", type=str, default=None)
    parser.add_argument("--output-grafico", type=str, default=None)
    args = parser.parse_args()

    segundo_territorio = None
    if args.segundo_lat is not None and args.segundo_lon is not None:
        segundo_territorio = (args.segundo_lat, args.segundo_lon)

    pontos_historico = [
        (p["latitude"], p["longitude"])
        for p in gerar_trajetoria(
            home_lat=HOME_LAT_PADRAO,
            home_lon=HOME_LON_PADRAO,
            num_pontos=args.num_pontos,
            raio_passeio_metros=args.raio_passeio,
            segundo_territorio=segundo_territorio,
            prob_mudanca_territorio=args.prob_mudanca_territorio,
            intervalo_minutos=args.intervalo_minutos,
        )
    ]

    trajetoria_fuga = gerar_trajetoria_fuga(
        HOME_LAT_PADRAO, HOME_LON_PADRAO, args.distancia_fuga, args.passos_fuga
    )

    algoritmos = [RaioFixo(), ConvexHull(), DensidadeDBSCAN()]

    resultados = comparar_abordagens(algoritmos, pontos_historico, trajetoria_fuga)

    imprimir_tabela(resultados, args.intervalo_minutos)

    if args.output_csv:
        salvar_csv(resultados, args.output_csv, args.intervalo_minutos)
    if args.output_grafico:
        gerar_grafico(resultados, args.output_grafico)


if __name__ == "__main__":
    main()