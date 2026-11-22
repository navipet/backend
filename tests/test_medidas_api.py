"""testes das rotas /medida com SQLite em memória (tabelas antena e medida, sem PostGIS)"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import medidas as rota
from app.db.session import get_db
from app.main import app
from app.models.models import Antena, Medida

ANCORA = "a4:cf:12:9b:03:7e"
ANCORA_2 = "a4:cf:12:9b:07:c1"

COM_PET = {
    "numero_superquadro": 184723,
    "instante_superquadro": "2026-11-22T11:54:03.000-03:00",
    "endereco_mac_ancora": ANCORA,
    "pet_id": 1001,
    "rssi_maximo_dbm": -67,
    "rssi_mediano_dbm": -71.5,
    "rssi_medio_dbm": -72.25,
    "amostras_total": 26,
    "amostras_canal_37": 9,
    "amostras_canal_38": 9,
    "amostras_canal_39": 8,
    "sequencia_pet_primeira": 48210,
    "sequencia_pet_ultima": 48219,
    "bateria_pet": 87,
    "profundidade": 1,
    "endereco_mac_pai": "a4:cf:12:9b:11:02",
    "rssi_espnow_pai_dbm": -54,
    "vizinhos_ativos": 4,
    "tempo_varredura_ms": 948,
    "desvio_sincronismo_us": -37,
    "sequencia_espnow": 184723,
    "quadros_ambiente": 412,
    "latencia_chegada_ms": 12,
    "duracao_comunicacao_ms": 50,
    "ponto_id": "P14",
    "sessao": "S1",
}

SILENCIO = {
    **COM_PET,
    "endereco_mac_ancora": ANCORA_2,
    "pet_id": None,
    "rssi_maximo_dbm": None,
    "rssi_mediano_dbm": None,
    "rssi_medio_dbm": None,
    "amostras_total": 0,
    "amostras_canal_37": 0,
    "amostras_canal_38": 0,
    "amostras_canal_39": 0,
    "sequencia_pet_primeira": None,
    "sequencia_pet_ultima": None,
    "bateria_pet": None,
    "profundidade": 2,
    "endereco_mac_pai": ANCORA,
}


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Antena.__table__.create(engine)
    Medida.__table__.create(engine)
    Sessao = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with Sessao() as db:
        for mac in (ANCORA, ANCORA_2):
            db.add(Antena(endereco_mac=mac, latitude=-5.08, longitude=-42.8,
                          potencia_referencia_dbm=-59, expoente_perda_percurso=2.5,
                          desvio_sombreamento_db=4))
        db.commit()

    def _db():
        db = Sessao()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_lote_do_exemplo_com_pet_e_silencio_e_gravado(client):
    r = client.post("/medida", json=[COM_PET, SILENCIO])
    assert r.status_code == 201
    assert r.json() == {"recebidas": 2, "inseridas": 2, "duplicadas": 0}

    medidas = client.get("/medida").json()["medidas"]
    assert len(medidas) == 2
    primeira = {k: v for k, v in medidas[0].items() if k not in ("id", "instante_superquadro")}
    assert primeira == {k: v for k, v in COM_PET.items() if k != "instante_superquadro"}
    assert medidas[1]["pet_id"] is None


def test_reenviar_a_mesma_medida_nao_duplica(client):
    client.post("/medida", json=[COM_PET])
    r = client.post("/medida", json=[COM_PET, {**COM_PET, "numero_superquadro": 184724}])
    assert r.status_code == 201
    assert r.json() == {"recebidas": 2, "inseridas": 1, "duplicadas": 1}
    assert len(client.get("/medida").json()["medidas"]) == 2


def test_mac_da_ancora_e_normalizado(client):
    r = client.post("/medida", json=[{**COM_PET, "endereco_mac_ancora": "A4-CF-12-9B-03-7E",
                                      "endereco_mac_pai": "A4CF129B1102"}])
    assert r.status_code == 201
    m = client.get("/medida").json()["medidas"][0]
    assert m["endereco_mac_ancora"] == ANCORA
    assert m["endereco_mac_pai"] == "a4:cf:12:9b:11:02"


def test_ancora_nao_cadastrada_devolve_422_com_o_mac(client):
    r = client.post("/medida", json=[COM_PET, {**COM_PET, "endereco_mac_ancora": "00:11:22:33:44:55"}])
    assert r.status_code == 422
    assert r.json()["detail"]["enderecos_mac"] == ["00:11:22:33:44:55"]
    assert client.get("/medida").json()["medidas"] == []  # nada do lote foi gravado


def test_lote_vazio_devolve_422(client):
    assert client.post("/medida", json=[]).status_code == 422


def test_lote_acima_do_teto_devolve_422(client, monkeypatch):
    lote = [{**COM_PET, "numero_superquadro": i} for i in range(rota.MAX_MEDIDAS_POR_LOTE + 1)]
    assert client.post("/medida", json=lote).status_code == 422


def test_um_item_invalido_recusa_o_lote_inteiro(client):
    r = client.post("/medida", json=[COM_PET, {**SILENCIO, "profundidade": 0}])
    assert r.status_code == 422
    assert client.get("/medida").json()["medidas"] == []


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("numero_superquadro", -1),
        ("instante_superquadro", "2026-11-22T11:54:03"),  # sem fuso
        ("endereco_mac_ancora", "xyz"),
        ("endereco_mac_pai", "xyz"),
        ("pet_id", -1),
        ("pet_id", 4294967296),
        ("rssi_maximo_dbm", 1),
        ("rssi_maximo_dbm", -111),
        ("rssi_mediano_dbm", -110.5),
        ("rssi_medio_dbm", 0.1),
        ("sequencia_pet_primeira", 65536),
        ("sequencia_pet_ultima", -1),
        ("bateria_pet", 101),
        ("profundidade", 0),
        ("profundidade", 33),
        ("rssi_espnow_pai_dbm", 5),
        ("vizinhos_ativos", -1),
        ("tempo_varredura_ms", 2001),
        ("desvio_sincronismo_us", 1_000_001),
        ("desvio_sincronismo_us", -1_000_001),
        ("sequencia_espnow", -1),
        ("quadros_ambiente", -1),
        ("latencia_chegada_ms", -1),
        ("duracao_comunicacao_ms", 0),
        ("duracao_comunicacao_ms", 1001),
        ("ponto_id", "x" * 65),
        ("sessao", "x" * 65),
    ],
)
def test_valor_fora_da_faixa_devolve_422(client, campo, valor):
    assert client.post("/medida", json=[{**COM_PET, campo: valor}]).status_code == 422


@pytest.mark.parametrize(
    "campo",
    ["numero_superquadro", "instante_superquadro", "endereco_mac_ancora", "pet_id",
     "profundidade", "vizinhos_ativos", "tempo_varredura_ms", "desvio_sincronismo_us",
     "sequencia_espnow", "quadros_ambiente", "duracao_comunicacao_ms"],
)
def test_campo_obrigatorio_ausente_devolve_422(client, campo):
    corpo = {k: v for k, v in COM_PET.items() if k != campo}
    assert client.post("/medida", json=[corpo]).status_code == 422


def test_campos_opcionais_podem_faltar(client):
    corpo = {k: v for k, v in COM_PET.items()
             if k not in ("bateria_pet", "endereco_mac_pai", "rssi_espnow_pai_dbm",
                          "latencia_chegada_ms", "ponto_id", "sessao")}
    assert client.post("/medida", json=[corpo]).status_code == 201


def test_amostras_que_nao_somam_os_canais_devolvem_422(client):
    assert client.post("/medida", json=[{**COM_PET, "amostras_total": 27}]).status_code == 422


def test_pet_sem_amostras_devolve_422(client):
    corpo = {**SILENCIO, "pet_id": 1001}
    assert client.post("/medida", json=[corpo]).status_code == 422


def test_silencio_com_amostras_devolve_422(client):
    corpo = {**COM_PET, "pet_id": None}
    assert client.post("/medida", json=[corpo]).status_code == 422


def test_silencio_com_rssi_devolve_422(client):
    assert client.post("/medida", json=[{**SILENCIO, "rssi_maximo_dbm": -80}]).status_code == 422


def test_pet_sem_rssi_devolve_422(client):
    assert client.post("/medida", json=[{**COM_PET, "rssi_medio_dbm": None}]).status_code == 422


def test_maximo_menor_que_medio_devolve_422(client):
    corpo = {**COM_PET, "rssi_maximo_dbm": -75, "rssi_mediano_dbm": -76}
    assert client.post("/medida", json=[corpo]).status_code == 422


def test_listar_vazio(client):
    r = client.get("/medida")
    assert r.status_code == 200
    assert r.json() == {
        "medidas": [],
        "paginacao": {"retornadas": 0, "proximo_cursor": None, "tem_mais": False},
    }


def test_paginacao_por_cursor_percorre_tudo_sem_repetir(client):
    lote = [{**COM_PET, "numero_superquadro": i} for i in range(5)]
    client.post("/medida", json=lote)

    vistos, cursor, paginas = [], None, 0
    while True:
        params = {"limite": 2} | ({"cursor": cursor} if cursor is not None else {})
        corpo = client.get("/medida", params=params).json()
        paginas += 1
        vistos += [m["numero_superquadro"] for m in corpo["medidas"]]
        assert corpo["paginacao"]["retornadas"] == len(corpo["medidas"])
        if not corpo["paginacao"]["tem_mais"]:
            assert corpo["paginacao"]["proximo_cursor"] is None
            break
        cursor = corpo["paginacao"]["proximo_cursor"]
        assert cursor == corpo["medidas"][-1]["id"]

    assert vistos == list(range(5))
    assert paginas == 3


def test_pagina_exata_nao_diz_que_tem_mais(client):
    client.post("/medida", json=[COM_PET, SILENCIO])
    pag = client.get("/medida", params={"limite": 2}).json()["paginacao"]
    assert pag == {"retornadas": 2, "proximo_cursor": None, "tem_mais": False}


@pytest.mark.parametrize("params", [{"limite": 0}, {"limite": 5001}, {"cursor": -1}])
def test_parametros_de_listagem_invalidos_devolvem_422(client, params):
    assert client.get("/medida", params=params).status_code == 422
