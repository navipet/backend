from app.algorithms.densidade import DensidadeDBSCAN


def _territorio(lat_centro, lon_centro, n=10, passo=0.00005):
    """Gera n pontos bem próximos entre si, simulando um território denso."""
    pontos = []
    for i in range(n):
        pontos.append((lat_centro + i * passo, lon_centro + i * passo))
    return pontos


def test_identifica_dois_territorios_separados():
    """
    Cenário central do TCC (Seção 5.3): pet que frequenta 2 territórios
    não contíguos. Espera-se que a densidade gere uma zona que cobre os
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
    """Histórico muito esparso (todo ruído) deve avisar, não gerar zona vazia."""
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