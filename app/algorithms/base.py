from abc import ABC, abstractmethod

from shapely.geometry import Point, Polygon


class AbordagemGeofencing(ABC):
    """
    Interface comum às 3 abordagens comparadas no TCC (Tabela 2):
    raio fixo, convex hull e estimativa de densidade.

    Implementar essa interface para cada nova abordagem garante que o
    módulo de comparação experimental (Seção 6.3) funcione igual para
    todas, trocando apenas a implementação.
    """

    nome: str

    @abstractmethod
    def construir_zona(self, pontos: list[tuple[float, float]]) -> Polygon:
        """
        Recebe uma lista de (latitude, longitude) do histórico do pet
        e retorna a geometria da zona segura (shapely Polygon).
        """
        raise NotImplementedError

    def esta_dentro(self, zona: Polygon, ponto: tuple[float, float]) -> bool:
        """
        Verifica se um ponto (lat, lon) está dentro da zona (incluindo a
        borda). Usamos `covers()` em vez de `contains()`: o `contains()` do
        shapely exclui pontos exatamente na borda do polígono, e isso é um
        problema real aqui -- quando a zona é um convex hull (ou um cluster
        de densidade), os próprios pontos históricos usados para construir
        a zona ficam sobre a borda dela. Com `contains()`, um pet parado
        exatamente onde ele sempre fica poderia ser marcado como "fora da
        zona", o que não faz sentido para geofencing.
        """
        lat, lon = ponto
        return zona.covers(Point(lon, lat))