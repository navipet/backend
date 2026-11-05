"""testes das rotas /antena com SQLite em memória (só a tabela de antenas, sem PostGIS)"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models.models import Antena

MAC = "AA:BB:CC:DD:EE:01"
CORPO = {
    "endereco_mac": MAC,
    "latitude": -5.0892,
    "longitude": -42.8019,
    "rssi_referencia": -59,
    "expoente_perda": 2.5,
}


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Antena.__table__.create(engine)
    Sessao = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def _db():
        db = Sessao()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_criar_antena_devolve_201_e_dados(client):
    r = client.post("/antena", json=CORPO)
    assert r.status_code == 201
    assert r.json() == CORPO


def test_mac_e_normalizado_ao_criar(client):
    r = client.post("/antena", json={**CORPO, "endereco_mac": "aa-bb-cc-dd-ee-01"})
    assert r.status_code == 201
    assert r.json()["endereco_mac"] == MAC


def test_mac_duplicado_devolve_409_mesmo_com_formato_diferente(client):
    client.post("/antena", json=CORPO)
    r = client.post("/antena", json={**CORPO, "endereco_mac": "aabbccddee01"})
    assert r.status_code == 409


def test_criar_com_mac_invalido_devolve_422(client):
    r = client.post("/antena", json={**CORPO, "endereco_mac": "xyz"})
    assert r.status_code == 422


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("latitude", 91),
        ("latitude", -91),
        ("longitude", 181),
        ("rssi_referencia", 1),
        ("rssi_referencia", -128),
        ("expoente_perda", 0),
        ("expoente_perda", -1),
    ],
)
def test_valores_fora_da_faixa_devolvem_422(client, campo, valor):
    r = client.post("/antena", json={**CORPO, campo: valor})
    assert r.status_code == 422


def test_listar_vazio(client):
    r = client.get("/antena")
    assert r.status_code == 200
    assert r.json() == {"antenas": []}


def test_listar_devolve_todas_com_mac(client):
    client.post("/antena", json=CORPO)
    client.post("/antena", json={**CORPO, "endereco_mac": "AA:BB:CC:DD:EE:02"})
    r = client.get("/antena")
    assert r.status_code == 200
    macs = [a["endereco_mac"] for a in r.json()["antenas"]]
    assert macs == ["AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"]


def test_obter_por_mac_devolve_so_os_quatro_campos_do_contrato(client):
    client.post("/antena", json=CORPO)
    r = client.get(f"/antena/{MAC}")
    assert r.status_code == 200
    assert r.json() == {
        "latitude": -5.0892,
        "longitude": -42.8019,
        "rssi_referencia": -59,
        "expoente_perda": 2.5,
    }


def test_obter_aceita_mac_em_minusculas(client):
    client.post("/antena", json=CORPO)
    assert client.get("/antena/aa:bb:cc:dd:ee:01").status_code == 200


def test_obter_inexistente_devolve_404(client):
    assert client.get(f"/antena/{MAC}").status_code == 404


def test_obter_com_mac_invalido_devolve_422(client):
    assert client.get("/antena/xyz").status_code == 422


def test_atualizar_persiste_os_novos_valores(client):
    client.post("/antena", json=CORPO)
    novo = {"latitude": -5.1, "longitude": -42.9, "rssi_referencia": -62, "expoente_perda": 3.0}
    r = client.put(f"/antena/{MAC}", json=novo)
    assert r.status_code == 200
    assert client.get(f"/antena/{MAC}").json() == novo


def test_atualizar_inexistente_devolve_404(client):
    novo = {"latitude": -5.1, "longitude": -42.9, "rssi_referencia": -62, "expoente_perda": 3.0}
    assert client.put(f"/antena/{MAC}", json=novo).status_code == 404


def test_atualizar_com_valor_invalido_devolve_422(client):
    client.post("/antena", json=CORPO)
    novo = {"latitude": 200, "longitude": -42.9, "rssi_referencia": -62, "expoente_perda": 3.0}
    assert client.put(f"/antena/{MAC}", json=novo).status_code == 422


def test_remover_devolve_200_e_antena_some(client):
    client.post("/antena", json=CORPO)
    assert client.delete(f"/antena/{MAC}").status_code == 200
    assert client.get(f"/antena/{MAC}").status_code == 404


def test_remover_inexistente_devolve_404(client):
    assert client.delete(f"/antena/{MAC}").status_code == 404
