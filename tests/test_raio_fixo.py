from app.algorithms.raio_fixo import RaioFixo


def test_ponto_no_centro_esta_dentro_da_zona():
    algoritmo = RaioFixo(raio_metros=100.0)
    pontos = [(-5.0892, -42.8016), (-5.0895, -42.8020)]  # Teresina, PI

    zona = algoritmo.construir_zona(pontos)

    centroide = (-5.08935, -42.8018)
    assert algoritmo.esta_dentro(zona, centroide)


def test_ponto_muito_distante_fica_fora_da_zona():
    algoritmo = RaioFixo(raio_metros=50.0)
    pontos = [(-5.0892, -42.8016)]

    zona = algoritmo.construir_zona(pontos)

    ponto_distante = (-5.2000, -42.9000)  # vários km de distância
    assert not algoritmo.esta_dentro(zona, ponto_distante)


def test_lista_vazia_de_pontos_gera_erro():
    algoritmo = RaioFixo()
    try:
        algoritmo.construir_zona([])
        assert False, "Deveria ter levantado ValueError"
    except ValueError:
        pass