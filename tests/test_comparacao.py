from app.algorithms.densidade import DensidadeDBSCAN
from app.algorithms.raio_fixo import RaioFixo
from app.services.comparacao import avaliar_abordagem, comparar_abordagens


def _pontos_proximos(n=20):
    """Pontos bem próximos entre si, simulando um único território denso."""
    return [(-5.0892 + i * 0.00001, -42.8016 + i * 0.00001) for i in range(n)]


def test_avaliar_abordagem_retorna_metricas_no_intervalo_valido():
    algoritmo = RaioFixo(raio_metros=50.0)
    pontos = _pontos_proximos()

    resultado = avaliar_abordagem(algoritmo, pontos)

    assert resultado.abordagem == "raio_fixo"
    assert 0.0 <= resultado.taxa_falsos_positivos <= 1.0
    assert 0.0 <= resultado.cobertura_territorial <= 1.0
    assert resultado.tempo_construcao_zona_ms >= 0.0


def test_latencia_deteccao_encontra_ponto_fora_da_zona():
    algoritmo = RaioFixo(raio_metros=20.0)
    pontos = _pontos_proximos()
    fuga = [(-5.1200, -42.8400 + i * 0.001) for i in range(10)]

    resultado = avaliar_abordagem(algoritmo, pontos, trajetoria_fuga=fuga)

    assert resultado.latencia_deteccao_pontos == 0


def test_latencia_deteccao_none_quando_fuga_nao_escapa():
    algoritmo = RaioFixo(raio_metros=1000.0)
    pontos = _pontos_proximos()
    fuga = [(-5.0893, -42.8017)]

    resultado = avaliar_abordagem(algoritmo, pontos, trajetoria_fuga=fuga)

    assert resultado.latencia_deteccao_pontos is None


def test_comparar_abordagens_lida_com_erro_sem_quebrar():
    """Uma abordagem que falha (ex: densidade sem cluster) não deve derrubar as outras."""
    pontos = [(-5.0800, -42.7900), (-5.1200, -42.8300)]
    algoritmos = [RaioFixo(), DensidadeDBSCAN(eps_metros=5.0, min_amostras=5)]

    resultados = comparar_abordagens(algoritmos, pontos)

    assert len(resultados) == 2
    nomes = [r.abordagem for r in resultados]
    assert "raio_fixo" in nomes
    assert "densidade" in nomes