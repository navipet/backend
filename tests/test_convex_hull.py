from app.algorithms.convex_hull import ConvexHull


def test_ponto_central_esta_dentro_do_hull():
    algoritmo = ConvexHull()
    # 4 pontos formando um quadrado ao redor de Teresina, PI
    pontos = [
        (-5.0880, -42.8030),
        (-5.0880, -42.8000),
        (-5.0910, -42.8030),
        (-5.0910, -42.8000),
    ]

    zona = algoritmo.construir_zona(pontos)

    centro = (-5.0895, -42.8015)
    assert algoritmo.esta_dentro(zona, centro)


def test_ponto_fora_do_quadrado_fica_fora_do_hull():
    algoritmo = ConvexHull()
    pontos = [
        (-5.0880, -42.8030),
        (-5.0880, -42.8000),
        (-5.0910, -42.8030),
        (-5.0910, -42.8000),
    ]

    zona = algoritmo.construir_zona(pontos)

    ponto_distante = (-5.2000, -42.9000)
    assert not algoritmo.esta_dentro(zona, ponto_distante)


def test_dois_pontos_nao_quebra_e_gera_area_minima():
    """histórico degenerado (só 2 pontos) não deve levantar exceção"""
    algoritmo = ConvexHull()
    pontos = [(-5.0892, -42.8016), (-5.0893, -42.8017)]

    zona = algoritmo.construir_zona(pontos)

    assert zona.area > 0


def test_lista_vazia_gera_erro():
    algoritmo = ConvexHull()
    try:
        algoritmo.construir_zona([])
        assert False, "Deveria ter levantado ValueError"
    except ValueError:
        pass