from app.algorithms.densidade import DensidadeDBSCAN


def _territorio(lat_centro, lon_centro, n=10, passo=0.00005):
    """gera n pontos bem próximos entre si, simulando um território denso"""
    pontos = []
    for i in range(n):
        pontos.append((lat_centro + i * passo, lon_centro + i * passo))
    return pontos


def test_identifica_dois_territorios_separados():
    """
    cenário central do TCC: pet que frequenta 2 territórios não contíguos. espera-se que a densidade gere uma zona que cobre os
    dois, sem incluir a área vazia entre eles.
    """
    algoritmo = DensidadeDBSCAN(eps_metros=30.0, min_amostras=3)

    territorio_casa = _territorio(-5.0892, -42.8016)
    territorio_vizinho = _territorio(-5.1200, -42.8400)  # ~5km de distância
    pontos = territorio_casa + territorio_vizinho

    zona = algoritmo.construir_zona(pontos)

    assert algoritmo.esta_dentro(zona, territorio_casa[0])
    assert algoritmo.esta_dentro(zona, territorio_vizinho[0])

    # Ponto no meio do caminho entre os dois territórios NÃO deve estar
    # dentro da zona -- essa é a vantagem da densidade sobre convex hull.
    ponto_no_meio = (-5.1046, -42.8208)
    assert not algoritmo.esta_dentro(zona, ponto_no_meio)


def test_pontos_isolados_sem_cluster_geram_erro():
    """histórico muito esparso (todo ruído) deve avisar, não gerar zona vazia."""
    algoritmo = DensidadeDBSCAN(eps_metros=10.0, min_amostras=5)
    pontos = [
        (-5.0800, -42.7900),
        (-5.1200, -42.8300),
        (-5.1600, -42.8700),
    ]

    try:
        algoritmo.construir_zona(pontos)
        assert False, "Deveria ter levantado ValueError (nenhum cluster denso)"
    except ValueError:
        pass


def test_lista_vazia_gera_erro():
    algoritmo = DensidadeDBSCAN()
    try:
        algoritmo.construir_zona([])
        assert False, "Deveria ter levantado ValueError"
    except ValueError:
        pass

# ---------------------------------------------------------------------------
# teto de pontos (max_pontos): protege a memória com histórico longo
# ---------------------------------------------------------------------------
import random

import pytest


def _nuvem(n, lat0=-5.0892, lon0=-42.8016, espalhamento_graus=0.0002, semente=1):
    rng = random.Random(semente)
    return [
        (lat0 + rng.uniform(-espalhamento_graus, espalhamento_graus),
         lon0 + rng.uniform(-espalhamento_graus, espalhamento_graus))
        for _ in range(n)
    ]


def test_sem_teto_o_resultado_e_o_mesmo_de_antes():
    """max_pontos=None (padrão da classe, usado nos experimentos) não altera nada"""
    pontos = _nuvem(300)
    a = DensidadeDBSCAN(eps_metros=50.0, min_amostras=5)
    b = DensidadeDBSCAN(eps_metros=50.0, min_amostras=5, max_pontos=None)
    assert a.construir_zona(pontos).equals(b.construir_zona(pontos))


def test_teto_maior_que_o_historico_nao_altera_o_resultado():
    pontos = _nuvem(300)
    sem = DensidadeDBSCAN(eps_metros=50.0, min_amostras=5)
    com = DensidadeDBSCAN(eps_metros=50.0, min_amostras=5, max_pontos=1000)
    assert sem.construir_zona(pontos).equals(com.construir_zona(pontos))


def test_subamostrar_respeita_o_teto_e_mantem_extremos_e_ordem():
    algoritmo = DensidadeDBSCAN(max_pontos=100)
    pontos = [(float(i), float(i)) for i in range(1000)]
    escolhidos = algoritmo._subamostrar(pontos)
    assert len(escolhidos) == 100
    assert escolhidos[0] == pontos[0]
    assert escolhidos[-1] == pontos[-1]
    assert escolhidos == sorted(escolhidos)  # ordem cronológica preservada


def test_subamostrar_e_deterministico():
    algoritmo = DensidadeDBSCAN(max_pontos=50)
    pontos = [(float(i), 0.0) for i in range(500)]
    assert algoritmo._subamostrar(pontos) == algoritmo._subamostrar(pontos)


def test_teto_zero_ou_none_significa_sem_teto():
    pontos = [(float(i), 0.0) for i in range(500)]
    assert len(DensidadeDBSCAN(max_pontos=0)._subamostrar(pontos)) == 500
    assert len(DensidadeDBSCAN(max_pontos=None)._subamostrar(pontos)) == 500


def test_zona_com_teto_e_parecida_com_a_zona_completa():
    """um território denso, com e sem teto, gera praticamente a mesma zona"""
    pontos = _nuvem(3000)
    completa = DensidadeDBSCAN(eps_metros=50.0, min_amostras=5).construir_zona(pontos)
    com_teto = DensidadeDBSCAN(
        eps_metros=50.0, min_amostras=5, max_pontos=500
    ).construir_zona(pontos)
    inter = completa.intersection(com_teto).area
    uniao = completa.union(com_teto).area
    assert inter / uniao > 0.9


def test_teto_ainda_separa_dois_territorios():
    casa = _nuvem(1500, -5.0892, -42.8016, semente=2)
    vizinho = _nuvem(1500, -5.0892, -42.7970, semente=3)  # ~500 m a leste
    algoritmo = DensidadeDBSCAN(eps_metros=50.0, min_amostras=5, max_pontos=400)
    zona = algoritmo.construir_zona(casa + vizinho)
    assert algoritmo.esta_dentro(zona, (-5.0892, -42.8016))
    assert algoritmo.esta_dentro(zona, (-5.0892, -42.7970))
    assert not algoritmo.esta_dentro(zona, (-5.0892, -42.7993))  # vazio entre os dois


def test_historico_enorme_com_teto_roda_rapido(): 
    """regressão: sem o teto este caso estoura a memória; com o teto leva ms"""
    import time

    pontos = _nuvem(30000)
    algoritmo = DensidadeDBSCAN(eps_metros=50.0, min_amostras=5, max_pontos=1500)
    inicio = time.perf_counter()
    zona = algoritmo.construir_zona(pontos)
    assert time.perf_counter() - inicio < 5.0
    assert zona.area > 0
