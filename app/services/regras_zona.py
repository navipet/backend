# regra de decisão do recalculo automatico da zona segura, isolada de banco de dados para ser testavel.

def deve_recalcular_zona(
    total_pontos: int,
    tem_zona: bool,
    ha_alerta_aberto: bool,
    min_pontos: int,
    intervalo: int,
) -> bool:
    """
    decide se a zona segura do pet deve ser (re)calculada agora

    - com alerta aberto, nunca recalcula: as posicoes recentes sao suspeitas (o pet esta fora da zona) e nao devem virar "territorio seguro" por tabela
    - antes de acumular o minimo de pontos, nao ha historico suficiente
    - sem nenhuma zona ainda, calcula assim que o minimo eh atingido
    - com zona existente, recalcula a cada `intervalo` pontos acumulados
    """
    if ha_alerta_aberto:
        return False
    if total_pontos < min_pontos:
        return False
    if not tem_zona:
        return True
    if intervalo <= 0:
        return False
    return total_pontos % intervalo == 0