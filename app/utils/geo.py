"""
Utilitários geoespaciais compartilhados entre os algoritmos de geofencing
e o simulador de trajetórias. Centralizar aqui evita duplicar a conversão
metros -> graus em vários lugares do código.
"""

import math

RAIO_TERRA_METROS = 6_371_000


def deslocar_ponto(
    lat: float, lon: float, distancia_metros: float, angulo_rad: float
) -> tuple[float, float]:
    """
    Desloca um ponto (lat, lon) por uma certa distância (em metros) em uma
    direção (ângulo em radianos, 0 = norte, sentido horário).

    Aproximação local (equirretangular) — válida para distâncias pequenas,
    como o raio de deslocamento de um pet (dezenas a centenas de metros).
    Para áreas muito grandes seria necessário usar uma fórmula geodésica
    mais precisa (ex: Vincenty), mas não é o caso aqui.
    """
    delta_lat = (distancia_metros / RAIO_TERRA_METROS) * math.cos(angulo_rad)
    delta_lon = (
        (distancia_metros / RAIO_TERRA_METROS)
        * math.sin(angulo_rad)
        / math.cos(math.radians(lat))
    )

    nova_lat = lat + math.degrees(delta_lat)
    nova_lon = lon + math.degrees(delta_lon)
    return nova_lat, nova_lon