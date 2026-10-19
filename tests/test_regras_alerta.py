from app.services.regras_alerta import ABRIR, NADA, RESOLVER, decidir_acao_alerta


def test_pet_saiu_da_zona_sem_alerta_aberto_abre_alerta():
    assert decidir_acao_alerta(dentro_da_zona=False, ha_alerta_aberto=False) == ABRIR


def test_pet_continua_fora_com_alerta_aberto_nao_duplica():
    assert decidir_acao_alerta(dentro_da_zona=False, ha_alerta_aberto=True) == NADA


def test_pet_voltou_para_zona_resolve_alerta():
    assert decidir_acao_alerta(dentro_da_zona=True, ha_alerta_aberto=True) == RESOLVER


def test_pet_dentro_da_zona_sem_alerta_nao_faz_nada():
    assert decidir_acao_alerta(dentro_da_zona=True, ha_alerta_aberto=False) == NADA