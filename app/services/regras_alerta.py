"""
regra de decisao dos alertas, isolada de banco de dados para ser testavel

aado se o pet esta dentro da zona e se ja existe um alerta de "fora da
zona" em aberto, decide o que fazer:
- fora da zona e sem alerta aberto  -> ABRIR (pet acabou de sair)
- dentro da zona e com alerta aberto -> RESOLVER (pet voltou)
- qualquer outro caso                -> NADA (evita alertas duplicados)
"""

ABRIR = "abrir"
RESOLVER = "resolver"
NADA = "nada"


def decidir_acao_alerta(dentro_da_zona: bool, ha_alerta_aberto: bool) -> str:
    if not dentro_da_zona and not ha_alerta_aberto:
        return ABRIR
    if dentro_da_zona and ha_alerta_aberto:
        return RESOLVER
    return NADA