import pytest

from app.utils.mac import normalizar_mac


@pytest.mark.parametrize(
    "entrada",
    [
        "AA:BB:CC:DD:EE:FF",
        "aa:bb:cc:dd:ee:ff",
        "aa-bb-cc-dd-ee-ff",
        "aabb.ccdd.eeff",
        "aabbccddeeff",
        "  AA:BB:CC:DD:EE:FF  ",
    ],
)
def test_formatos_validos_viram_o_mesmo_mac_normalizado(entrada):
    assert normalizar_mac(entrada) == "AA:BB:CC:DD:EE:FF"


@pytest.mark.parametrize(
    "entrada",
    ["", "AA:BB:CC:DD:EE", "AA:BB:CC:DD:EE:FF:00", "GG:BB:CC:DD:EE:FF", "não é um mac"],
)
def test_mac_invalido_levanta_erro(entrada):
    with pytest.raises(ValueError):
        normalizar_mac(entrada)
