import re

_SEPARADORES = re.compile(r"[:\-.\s]")
_HEX_12 = re.compile(r"^[0-9A-F]{12}$")


def normalizar_mac(valor: str) -> str:
    """Normaliza um endereço MAC para o formato AA:BB:CC:DD:EE:FF.

    Aceita separadores ':', '-' ou '.', letras maiúsculas ou minúsculas, ou sem
    separador (aabbccddeeff). Levanta ValueError se não tiver exatamente 12 dígitos
    hexadecimais. Assim a mesma antena é sempre reconhecida, não importa como o
    firmware formata o MAC.
    """
    limpo = _SEPARADORES.sub("", valor.strip()).upper()
    if not _HEX_12.match(limpo):
        raise ValueError("endereço MAC inválido (esperado 12 dígitos hexadecimais)")
    return ":".join(limpo[i : i + 2] for i in range(0, 12, 2))
