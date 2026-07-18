"""
Simulador de trajetórias GPS de um pet, na ausência do hardware físico.

O simulador gera um passeio aleatório (random walk) em torno de um
"território" e, com uma certa probabilidade, alterna para um segundo
território (ex: quintal do vizinho) -- útil para testar o cenário
descrito nos Resultados Esperados: pets que frequentam
múltiplos territórios não contíguos, onde se espera que a abordagem de
densidade supere raio fixo e convex hull.

Uso básico (enviando direto para a API rodando local):
    python -m scripts.simulador_trajetorias --pet-id 1 --num-pontos 300

Gerando um CSV offline, sem precisar da API rodando (bom para testar os
3 algoritmos direto em notebook/script de análise, sem banco):
    python -m scripts.simulador_trajetorias --pet-id 1 --num-pontos 300 \
        --sem-api --output dados_pet_1.csv

Simulando um pet com 2 territórios (ex: casa e casa do vizinho):
    python -m scripts.simulador_trajetorias --pet-id 1 --num-pontos 500 \
        --segundo-lat -5.0910 --segundo-lon -42.8050 \
        --prob-mudanca-territorio 0.02 --sem-api --output dados_pet_1.csv
"""

import argparse
import csv
import math
import random
from datetime import datetime, timedelta

import httpx

from app.utils.geo import deslocar_ponto

# Coordenadas padrão: Teresina - PI (mesmo ponto usado nos testes unitários)
HOME_LAT_PADRAO = -5.0892
HOME_LON_PADRAO = -42.8016


def gerar_trajetoria(
    home_lat: float,
    home_lon: float,
    num_pontos: int,
    raio_passeio_metros: float,
    segundo_territorio: tuple[float, float] | None,
    prob_mudanca_territorio: float,
    intervalo_minutos: float,
) -> list[dict]:
    """
    Gera uma lista de leituras GPS simuladas, cada uma com
    (latitude, longitude, timestamp), voltando no tempo a partir de agora.
    """
    pontos = []
    centro_atual = (home_lat, home_lon)
    timestamp_atual = datetime.utcnow()

    for i in range(num_pontos):
        # Com uma certa probabilidade, o pet "migra" para o outro território
        if segundo_territorio and random.random() < prob_mudanca_territorio:
            centro_atual = (
                segundo_territorio
                if centro_atual == (home_lat, home_lon)
                else (home_lat, home_lon)
            )

        # Passeio aleatório: distância e direção aleatórias em torno do centro atual
        distancia = random.gauss(mu=0, sigma=raio_passeio_metros / 2)
        distancia = min(abs(distancia), raio_passeio_metros)
        angulo = random.uniform(0, 2 * math.pi)

        lat, lon = deslocar_ponto(centro_atual[0], centro_atual[1], distancia, angulo)

        pontos.append(
            {
                "latitude": lat,
                "longitude": lon,
                "timestamp": timestamp_atual.isoformat(),
            }
        )

        timestamp_atual -= timedelta(minutes=intervalo_minutos)

    pontos.reverse()  # ordem cronológica (mais antigo primeiro)
    return pontos


def enviar_para_api(pontos: list[dict], api_url: str, pet_id: int) -> None:
    """Envia cada ponto para a API via POST /pets/{pet_id}/localizacoes."""
    with httpx.Client(base_url=api_url, timeout=10.0) as client:
        for i, ponto in enumerate(pontos, start=1):
            resposta = client.post(f"/pets/{pet_id}/localizacoes", json=ponto)
            if resposta.status_code >= 400:
                print(f"[{i}/{len(pontos)}] erro {resposta.status_code}: {resposta.text}")
            elif i % 50 == 0 or i == len(pontos):
                print(f"[{i}/{len(pontos)}] enviado")


def salvar_csv(pontos: list[dict], caminho: str) -> None:
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["latitude", "longitude", "timestamp"])
        writer.writeheader()
        writer.writerows(pontos)
    print(f"CSV salvo em {caminho} ({len(pontos)} pontos)")


def main():
    parser = argparse.ArgumentParser(description="Simulador de trajetórias GPS de pet")
    parser.add_argument("--pet-id", type=int, required=True)
    parser.add_argument("--num-pontos", type=int, default=200)
    parser.add_argument("--home-lat", type=float, default=HOME_LAT_PADRAO)
    parser.add_argument("--home-lon", type=float, default=HOME_LON_PADRAO)
    parser.add_argument("--raio-passeio", type=float, default=30.0, help="metros")
    parser.add_argument("--segundo-lat", type=float, default=None)
    parser.add_argument("--segundo-lon", type=float, default=None)
    parser.add_argument("--prob-mudanca-territorio", type=float, default=0.0)
    parser.add_argument("--intervalo-minutos", type=float, default=5.0)
    parser.add_argument("--api-url", type=str, default="http://localhost:8000")
    parser.add_argument("--sem-api", action="store_true", help="não envia para a API")
    parser.add_argument("--output", type=str, default=None, help="caminho do CSV de saída")
    args = parser.parse_args()

    segundo_territorio = None
    if args.segundo_lat is not None and args.segundo_lon is not None:
        segundo_territorio = (args.segundo_lat, args.segundo_lon)

    pontos = gerar_trajetoria(
        home_lat=args.home_lat,
        home_lon=args.home_lon,
        num_pontos=args.num_pontos,
        raio_passeio_metros=args.raio_passeio,
        segundo_territorio=segundo_territorio,
        prob_mudanca_territorio=args.prob_mudanca_territorio,
        intervalo_minutos=args.intervalo_minutos,
    )

    if args.output:
        salvar_csv(pontos, args.output)

    if not args.sem_api:
        enviar_para_api(pontos, args.api_url, args.pet_id)


if __name__ == "__main__":
    main()