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

histerese (tolerancia na volta): para o alerta FECHAR tambem eh preciso
`limiar_fechar` leituras SEGUIDAS dentro da zona; uma leitura fora zera esse
contador. evita o abre/fecha repetido quando o pet fica na borda.
com limiar_fechar = 1 o comportamento eh o anterior (uma leitura dentro fecha)
"""

ABRIR = "abrir"
RESOLVER = "resolver"
NADA = "nada"


def atualizar_contador_fora(dentro_da_zona: bool, contador_atual: int) -> int:
    """novo valor do contador de leituras seguidas fora da zona"""
    if dentro_da_zona:
        return 0
    return contador_atual + 1


def atualizar_contador_dentro(dentro_da_zona: bool, contador_atual: int) -> int:
    """novo valor do contador de leituras seguidas dentro da zona"""
    if not dentro_da_zona:
        return 0
    return contador_atual + 1


def decidir_acao_alerta(
    dentro_da_zona: bool,
    ha_alerta_aberto: bool,
    leituras_fora_consecutivas: int = 1,
    limiar: int = 1,
    leituras_dentro_consecutivas: int = 1,
    limiar_fechar: int = 1,
) -> str:
    """
    `leituras_fora_consecutivas` e `leituras_dentro_consecutivas` ja devem
    incluir a leitura atual (use os atualizar_contador_* antes). limiares
    menores que 1 sao tratados como 1
    """
    limiar = max(1, limiar)
    limiar_fechar = max(1, limiar_fechar)
    if dentro_da_zona:
        if ha_alerta_aberto and leituras_dentro_consecutivas >= limiar_fechar:
            return RESOLVER
        return NADA
    if not ha_alerta_aberto and leituras_fora_consecutivas >= limiar:
        return ABRIR
    return NADA