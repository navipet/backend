import numpy as np
from shapely.geometry import MultiPoint, Polygon
from shapely.ops import unary_union
from sklearn.cluster import DBSCAN

from app.algorithms.base import AbordagemGeofencing

# aproximações de conversão grau -> metro perto do equador, usadas só para dar escala em metros ao parâmetro eps do DBSCAN
METROS_POR_GRAU_LAT = 110_540
METROS_POR_GRAU_LON_NO_EQUADOR = 111_320

BUFFER_DEGENERADO_METROS = 5.0
GRAUS_POR_METRO_APROX = 1 / 111_320


class DensidadeDBSCAN(AbordagemGeofencing):
    """
    abordagem baseada em densidade:
    identifica regiões de alta concentração de pontos via DBSCAN e constrói a zona segura 
    como a união dos polígonos (convex hull) de cada cluster denso encontrado.

    diferente de raio fixo e convex hull, essa abordagem consegue gerar múltiplos "territórios" separados 
    (ex: a casa do tutor + o quintal do vizinho), que é justamente o cenário onde se espera que ela tenha menor taxa de
    falsos positivos.

    limitação conhecida: maior custo computacional; requer histórico mínimo (pontos "ruído", isolados, não formam cluster e ficam de fora
    da zona segura).
    """

    nome = "densidade"

    def __init__(self, eps_metros: float = 50.0, min_amostras: int = 5):
        self.eps_metros = eps_metros
        self.min_amostras = min_amostras

    def construir_zona(self, pontos: list[tuple[float, float]]) -> Polygon:
        if not pontos:
            raise ValueError("É necessário ao menos um ponto para construir a zona")

        coordenadas_metros = self._projetar_para_metros(pontos)

        clustering = DBSCAN(eps=self.eps_metros, min_samples=self.min_amostras).fit(
            coordenadas_metros
        )
        rotulos = clustering.labels_

        rotulos_validos = set(rotulos) - {-1}  # -1 = ruído no DBSCAN
        if not rotulos_validos:
            raise ValueError(
                "Nenhum cluster denso encontrado. Histórico insuficiente ou "
                "muito esparso para os parâmetros eps/min_amostras informados."
            )

        poligonos_dos_clusters = []
        for rotulo in rotulos_validos:
            pontos_do_cluster = [
                pontos[i] for i in range(len(pontos)) if rotulos[i] == rotulo
            ]
            poligonos_dos_clusters.append(self._hull_do_cluster(pontos_do_cluster))

        return unary_union(poligonos_dos_clusters)

    def _projetar_para_metros(
        self, pontos: list[tuple[float, float]]
    ) -> np.ndarray:
        """
        projeta (lat, lon) para um plano local em metros, usando o primeiroponto como origem. aproximação equirretangular, 
        suficiente para a escala de deslocamento de um pet (não para grandes distâncias).
        """
        lat0, lon0 = pontos[0]
        coordenadas = []
        for lat, lon in pontos:
            x = (lon - lon0) * METROS_POR_GRAU_LON_NO_EQUADOR * np.cos(np.radians(lat0))
            y = (lat - lat0) * METROS_POR_GRAU_LAT
            coordenadas.append([x, y])
        return np.array(coordenadas)

    def _hull_do_cluster(self, pontos_do_cluster: list[tuple[float, float]]) -> Polygon:
        """convex hull de um único cluster (mesma lógica de degenerescência da ConvexHull)."""
        multiponto = MultiPoint([(lon, lat) for lat, lon in pontos_do_cluster])
        hull = multiponto.convex_hull

        if not isinstance(hull, Polygon):
            raio_graus = BUFFER_DEGENERADO_METROS * GRAUS_POR_METRO_APROX
            hull = hull.buffer(raio_graus)

        return hull