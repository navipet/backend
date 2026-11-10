"""
regra de decisao dos alertas, isolada de banco de dados para ser testavel

filtro de persistencia: com posicao estimada por RSSI o ponto "treme"
alguns metros, entao uma unica leitura fora da zona nao basta para abrir
o alerta. o alerta so abre depois de `limiar` leituras SEGUIDAS fora da
zona; qualquer leitura dentro zera o contador.

dado se o pet esta dentro da zona, quantas leituras seguidas ja foram de
fora (contando a atual) e se ja existe um alerta de "fora da zona" em
aberto, decide o que fazer:
- fora da zona, contador >= limiar e sem alerta aberto -> ABRIR
- dentro da zona e com alerta aberto                   -> RESOLVER
- qualquer outro caso                                  -> NADA (evita
  alertas duplicados e alertas por leituras isoladas)

com limiar = 1 o comportamento eh o original (uma leitura fora ja abre)
"""

ABRIR = "abrir"
RESOLVER = "resolver"
NADA = "nada"


def atualizar_contador_fora(dentro_da_zona: bool, contador_atual: int) -> int:
    """novo valor do contador de leituras seguidas fora da zona"""
    if dentro_da_zona:
        return 0
    return contador_atual + 1


def decidir_acao_alerta(
    dentro_da_zona: bool,
    ha_alerta_aberto: bool,
    leituras_fora_consecutivas: int = 1,
    limiar: int = 1,
) -> str:
    """
    `leituras_fora_consecutivas` ja deve incluir a leitura atual (use
    atualizar_contador_fora antes). `limiar` menor que 1 eh tratado como 1
    """
    limiar = max(1, limiar)
    if dentro_da_zona:
        return RESOLVER if ha_alerta_aberto else NADA
    if not ha_alerta_aberto and leituras_fora_consecutivas >= limiar:
        return ABRIR
    return NADA
