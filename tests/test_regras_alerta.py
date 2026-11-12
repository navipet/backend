from app.services.regras_alerta import (
    ABRIR,
    NADA,
    RESOLVER,
    atualizar_contador_dentro,
    atualizar_contador_fora,
    decidir_acao_alerta,
)


def test_pet_saiu_da_zona_sem_alerta_aberto_abre_alerta():
    assert decidir_acao_alerta(dentro_da_zona=False, ha_alerta_aberto=False) == ABRIR


def test_pet_continua_fora_com_alerta_aberto_nao_duplica():
    assert decidir_acao_alerta(dentro_da_zona=False, ha_alerta_aberto=True) == NADA


def test_pet_voltou_para_zona_resolve_alerta():
    assert decidir_acao_alerta(dentro_da_zona=True, ha_alerta_aberto=True) == RESOLVER


def test_pet_dentro_da_zona_sem_alerta_nao_faz_nada():
    assert decidir_acao_alerta(dentro_da_zona=True, ha_alerta_aberto=False) == NADA

# --- filtro de persistencia ---


def test_contador_zera_quando_volta_para_dentro():
    assert atualizar_contador_fora(dentro_da_zona=True, contador_atual=4) == 0


def test_contador_incrementa_quando_fora():
    assert atualizar_contador_fora(dentro_da_zona=False, contador_atual=2) == 3


def test_leitura_fora_abaixo_do_limiar_nao_abre():
    acao = decidir_acao_alerta(
        dentro_da_zona=False, ha_alerta_aberto=False,
        leituras_fora_consecutivas=4, limiar=5,
    )
    assert acao == NADA


def test_leitura_fora_no_limiar_abre():
    acao = decidir_acao_alerta(
        dentro_da_zona=False, ha_alerta_aberto=False,
        leituras_fora_consecutivas=5, limiar=5,
    )
    assert acao == ABRIR


def test_limiar_invalido_tratado_como_um():
    acao = decidir_acao_alerta(
        dentro_da_zona=False, ha_alerta_aberto=False,
        leituras_fora_consecutivas=1, limiar=0,
    )
    assert acao == ABRIR


def _simular(sequencia_dentro, limiar):
    """aplica a regra a uma sequencia de leituras; devolve as acoes"""
    contador, aberto, acoes = 0, False, []
    for dentro in sequencia_dentro:
        contador = atualizar_contador_fora(dentro, contador)
        acao = decidir_acao_alerta(dentro, aberto, contador, limiar)
        if acao == ABRIR:
            aberto = True
        elif acao == RESOLVER:
            aberto = False
        acoes.append(acao)
    return acoes


def test_leituras_isoladas_fora_nao_geram_alerta():
    # ruido perto da borda: fora, dentro, fora, fora, dentro...
    seq = [False, True, False, False, True, False, True]
    assert ABRIR not in _simular(seq, limiar=5)


def test_fuga_real_abre_uma_vez_e_resolve_ao_voltar():
    seq = [False] * 8 + [True]
    acoes = _simular(seq, limiar=5)
    assert acoes.index(ABRIR) == 4  # quinta leitura seguida fora
    assert acoes.count(ABRIR) == 1
    assert acoes[-1] == RESOLVER


def test_limiar_um_mantem_comportamento_original():
    assert _simular([False], limiar=1) == [ABRIR]


# --- histerese (tolerancia na volta) ---


def _simular_h(sequencia_dentro, limiar, limiar_fechar):
    fora, dentro_c, aberto, acoes = 0, 0, False, []
    for dentro in sequencia_dentro:
        fora = atualizar_contador_fora(dentro, fora)
        dentro_c = atualizar_contador_dentro(dentro, dentro_c)
        acao = decidir_acao_alerta(
            dentro, aberto, fora, limiar,
            leituras_dentro_consecutivas=dentro_c, limiar_fechar=limiar_fechar,
        )
        if acao == ABRIR:
            aberto = True
        elif acao == RESOLVER:
            aberto = False
        acoes.append(acao)
    return acoes


def test_contador_dentro_incrementa_e_zera():
    assert atualizar_contador_dentro(True, 2) == 3
    assert atualizar_contador_dentro(False, 4) == 0


def test_uma_leitura_dentro_nao_fecha_com_histerese():
    acao = decidir_acao_alerta(
        True, True, leituras_dentro_consecutivas=1, limiar_fechar=5
    )
    assert acao == NADA


def test_fecha_ao_atingir_limiar_de_leituras_dentro():
    acao = decidir_acao_alerta(
        True, True, leituras_dentro_consecutivas=5, limiar_fechar=5
    )
    assert acao == RESOLVER


def test_limiar_fechar_invalido_tratado_como_um():
    assert decidir_acao_alerta(
        True, True, leituras_dentro_consecutivas=1, limiar_fechar=0
    ) == RESOLVER


def test_pet_na_borda_gera_um_alerta_so_com_histerese():
    # 5 fora (abre), depois balanca: dentro, fora x5 (sem histerese: reabre)
    seq = [False] * 5 + [True, False, False, False, False, False, True, False]
    sem = _simular_h(seq, limiar=5, limiar_fechar=1)
    com = _simular_h(seq, limiar=5, limiar_fechar=5)
    assert sem.count(ABRIR) == 2 and sem.count(RESOLVER) >= 1
    assert com.count(ABRIR) == 1 and com.count(RESOLVER) == 0


def test_volta_de_verdade_fecha_depois_de_n_leituras_dentro():
    seq = [False] * 5 + [True] * 5
    acoes = _simular_h(seq, limiar=5, limiar_fechar=5)
    assert acoes.count(ABRIR) == 1
    assert acoes[-1] == RESOLVER and acoes.index(RESOLVER) == 9


def test_leitura_fora_zera_contagem_de_dentro():
    seq = [False] * 5 + [True] * 4 + [False] + [True] * 4
    assert RESOLVER not in _simular_h(seq, limiar=5, limiar_fechar=5)