from abc import ABC, abstractmethod

from shapely.geometry import Point, Polygon


class AbordagemGeofencing(ABC):
    """
    interface comum às 3 abordagens comparadas:
    raio fixo, convex hull e estimativa de densidade.

    implementar essa interface para cada nova abordagem garante que o
    módulo de comparação experimental funcione igual para
    todas, trocando apenas a implementação.
    """

    nome: str

    @abstractmethod
    def construir_zona(self, pontos: list[tuple[float, float]]) -> Polygon:
        """
        recebe uma lista de (latitude, longitude) do histórico do pet
        e retorna a geometria da zona segura (shapely polygon).
        """
        raise NotImplementedError

    def esta_dentro(self, zona: Polygon, ponto: tuple[float, float]) -> bool:
        """
        verifica se um ponto está dentro da zona (incluindo a borda). usamos `covers()` em vez de `contains()`: o `contains()` do
        shapely exclui pontos exatamente na borda do polígono, e isso é um problema real aqui -- quando a zona é um convex hull (ou um cluster
        de densidade), os próprios pontos históricos usados para construir a zona ficam sobre a borda dela. com `contains()`, um pet parado
        exatamente onde ele sempre fica poderia ser marcado como "fora da zona", o que não faz sentido para geofencing.
        """
        lat, lon = ponto
        return zona.covers(Point(lon, lat))