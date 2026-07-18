import math

from shapely.geometry import Polygon

from app.algorithms.base import AbordagemGeofencing
from app.utils.geo import deslocar_ponto


class RaioFixo(AbordagemGeofencing):
    """
    Abordagem baseline (Seção 2.4 / Tabela 2 do TCC):
    círculo de raio R em torno do centroide das trajetórias históricas.

    Limitação conhecida: não se adapta ao formato real do território
    habitual do pet.
    """

    nome = "raio_fixo"

    def __init__(self, raio_metros: float = 100.0, num_vertices: int = 32):
        self.raio_metros = raio_metros
        self.num_vertices = num_vertices

    def construir_zona(self, pontos: list[tuple[float, float]]) -> Polygon:
        if not pontos:
            raise ValueError("É necessário ao menos um ponto para construir a zona")

        centroide_lat = sum(p[0] for p in pontos) / len(pontos)
        centroide_lon = sum(p[1] for p in pontos) / len(pontos)

        return self._circulo_geodesico(centroide_lat, centroide_lon, self.raio_metros)

    def _circulo_geodesico(
        self, lat_centro: float, lon_centro: float, raio_metros: float
    ) -> Polygon:
        """
        Gera um polígono aproximando um círculo geodésico ao redor do
        centro, usando o util compartilhado de deslocamento de coordenadas.
        """
        pontos_circulo = []
        for i in range(self.num_vertices):
            angulo = 2 * math.pi * i / self.num_vertices
            lat, lon = deslocar_ponto(lat_centro, lon_centro, raio_metros, angulo)
            pontos_circulo.append((lon, lat))  # shapely usa (x=lon, y=lat)

        return Polygon(pontos_circulo)