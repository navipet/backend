from shapely.geometry import MultiPoint, Polygon

from app.algorithms.base import AbordagemGeofencing

"""se o histórico tiver poucos pontos (ou pontos colineares), o convex hull
    degenera para um point ou lineString em vez de um polygon. nesse caso,
    aplicamos um buffer pequeno (em graus, aproximando metros) só para
    garantir uma área mínima navegável -- não é uma abordagem "correta" de
    geofencing, é só uma salvaguarda para não quebrar em cenários com pouco
    histórico (tabela 2, TCC)."""
BUFFER_DEGENERADO_METROS = 5.0
GRAUS_POR_METRO_APROX = 1 / 111_320  # aproximação simples perto do equador


class ConvexHull(AbordagemGeofencing):
    """
    abordagem baseline:
    menor polígono convexo que envolve todos os pontos históricos.

    limitação conhecida: sensível a outliers; pode incluir áreas nunca
    visitadas pelo animal (ex: se o pet visita dois cantos opostos do
    quintal, o hull inclui tudo o que está no meio).
    """

    nome = "convex_hull"

    def construir_zona(self, pontos: list[tuple[float, float]]) -> Polygon:
        if not pontos:
            raise ValueError("É necessário ao menos um ponto para construir a zona")

        # shapely usa (x=lon, y=lat)
        multiponto = MultiPoint([(lon, lat) for lat, lon in pontos])
        hull = multiponto.convex_hull

        if not isinstance(hull, Polygon):
            # degenerado: 1 ou 2 pontos (ou todos colineares). aplica um buffer pequeno para retornar uma área mínima válida.
            raio_graus = BUFFER_DEGENERADO_METROS * GRAUS_POR_METRO_APROX
            hull = hull.buffer(raio_graus)

        return hull