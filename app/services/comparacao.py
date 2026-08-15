"""
Módulo de comparação experimental entre as 3 abordagens de geofencing
(Objetivo Específico 3 / Seção 6.3 do pré-projeto).

Metodologia adotada:
- O histórico de localizações é dividido em treino/teste. A zona é
  construída só com o treino.
- Taxa de falsos positivos: proporção de pontos de TESTE (localizações
  reais e legítimas do pet, não usadas para construir a zona) que caem
  FORA da zona construída. Isso corresponde exatamente à definição da
  Seção 6.3: "proporção de alertas emitidos quando o animal se
  encontrava, de fato, em área segura".
- Cobertura territorial: proporção dos pontos de TREINO contidos na
  zona gerada.
- Latência de detecção: dado uma trajetória de "fuga" simulada (o pet se
  afastando da zona), quantos pontos até o primeiro ser detectado como
  fora da zona. Retorna None se a fuga não foi longe o suficiente para
  escapar dentro do numero de passos fornecido.
- Tempo de construção da zona (ms): custo computacional do algoritmo,
  relevante para a expectativa (Seção 5.3) de que densidade seja mais
  lenta que as abordagens geométricas simples.
"""

import time
from dataclasses import dataclass

from app.algorithms.base import AbordagemGeofencing

PROPORCAO_TESTE_PADRAO = 0.2


@dataclass
class ResultadoComparacao:
    abordagem: str
    taxa_falsos_positivos: float
    cobertura_territorial: float
    latencia_deteccao_pontos: int | None
    tempo_construcao_zona_ms: float


def _dividir_treino_teste(
    pontos: list[tuple[float, float]], proporcao_teste: float
) -> tuple[list, list]:
    n_teste = max(1, int(len(pontos) * proporcao_teste))
    treino = pontos[:-n_teste]
    teste = pontos[-n_teste:]
    if not treino:
        treino = pontos
    return treino, teste


def _taxa_falsos_positivos(algoritmo, zona, pontos_teste) -> float:
    if not pontos_teste:
        return 0.0
    fora = sum(0 if algoritmo.esta_dentro(zona, p) else 1 for p in pontos_teste)
    return fora / len(pontos_teste)


def _cobertura_territorial(algoritmo, zona, pontos_treino) -> float:
    if not pontos_treino:
        return 0.0
    dentro = sum(1 if algoritmo.esta_dentro(zona, p) else 0 for p in pontos_treino)
    return dentro / len(pontos_treino)


def _latencia_deteccao(algoritmo, zona, trajetoria_fuga) -> int | None:
    for i, ponto in enumerate(trajetoria_fuga):
        if not algoritmo.esta_dentro(zona, ponto):
            return i
    return None


def avaliar_abordagem(
    algoritmo: AbordagemGeofencing,
    pontos_historico: list[tuple[float, float]],
    trajetoria_fuga: list[tuple[float, float]] | None = None,
    proporcao_teste: float = PROPORCAO_TESTE_PADRAO,
) -> ResultadoComparacao:
    """Avalia uma única abordagem sobre um histórico de localizações."""
    treino, teste = _dividir_treino_teste(pontos_historico, proporcao_teste)

    inicio = time.perf_counter()
    zona = algoritmo.construir_zona(treino)
    tempo_ms = (time.perf_counter() - inicio) * 1000

    return ResultadoComparacao(
        abordagem=algoritmo.nome,
        taxa_falsos_positivos=_taxa_falsos_positivos(algoritmo, zona, teste),
        cobertura_territorial=_cobertura_territorial(algoritmo, zona, treino),
        latencia_deteccao_pontos=(
            _latencia_deteccao(algoritmo, zona, trajetoria_fuga)
            if trajetoria_fuga
            else None
        ),
        tempo_construcao_zona_ms=tempo_ms,
    )


def comparar_abordagens(
    algoritmos: list[AbordagemGeofencing],
    pontos_historico: list[tuple[float, float]],
    trajetoria_fuga: list[tuple[float, float]] | None = None,
    proporcao_teste: float = PROPORCAO_TESTE_PADRAO,
) -> list[ResultadoComparacao]:
    """
    Avalia várias abordagens sobre o mesmo histórico, para comparação
    direta. Se uma abordagem falhar (ex: densidade sem cluster suficiente),
    o erro não derruba a comparação inteira -- entra como resultado NaN,
    o que já é um dado relevante (ela precisa de mais histórico).
    """
    resultados = []
    for algoritmo in algoritmos:
        try:
            resultados.append(
                avaliar_abordagem(
                    algoritmo, pontos_historico, trajetoria_fuga, proporcao_teste
                )
            )
        except ValueError:
            resultados.append(
                ResultadoComparacao(
                    abordagem=algoritmo.nome,
                    taxa_falsos_positivos=float("nan"),
                    cobertura_territorial=float("nan"),
                    latencia_deteccao_pontos=None,
                    tempo_construcao_zona_ms=float("nan"),
                )
            )
    return resultados