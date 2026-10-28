from app.services.regras_zona import deve_recalcular_zona

MIN = 30
INTERVALO = 50


def _decidir(total, tem_zona=False, alerta=False):
    return deve_recalcular_zona(total, tem_zona, alerta, MIN, INTERVALO)


def test_nao_calcula_antes_do_minimo_de_pontos():
    assert _decidir(total=29) is False


def test_calcula_primeira_zona_ao_atingir_o_minimo():
    assert _decidir(total=30, tem_zona=False) is True


def test_tenta_de_novo_a_cada_ponto_enquanto_nao_houver_zona():
    assert _decidir(total=37, tem_zona=False) is True


def test_com_zona_nao_recalcula_fora_do_intervalo():
    assert _decidir(total=77, tem_zona=True) is False


def test_com_zona_recalcula_a_cada_intervalo():
    assert _decidir(total=100, tem_zona=True) is True


def test_nunca_recalcula_com_alerta_aberto():
    assert _decidir(total=100, tem_zona=True, alerta=True) is False
    assert _decidir(total=30, tem_zona=False, alerta=True) is False


def test_intervalo_zero_so_calcula_a_primeira_zona():
    assert deve_recalcular_zona(100, True, False, MIN, 0) is False
    assert deve_recalcular_zona(100, False, False, MIN, 0) is True