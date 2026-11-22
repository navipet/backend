"""testes das rotas /antena com SQLite em memória (só a tabela de antenas, sem PostGIS)"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db
from app.main import app
from app.models.models import Antena

MAC = "aa:bb:cc:dd:ee:01"
CAMPOS = {
    "latitude": -5.0892,
    "longitude": -42.8019,
    "potencia_referencia_dbm": -59.0,
    "expoente_perda_percurso": 2.5,
    "desvio_sombreamento_db": 4.0,
}
CORPO = {"endereco_mac": MAC, **CAMPOS}


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
    r = client.post("/antena", json={**CORPO, "endereco_mac": "AA-BB-CC-DD-EE-01"})
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
        ("longitude", -181),
        ("potencia_referencia_dbm", -100.5),
        ("potencia_referencia_dbm", 0.5),
        ("potencia_referencia_dbm", "abc"),
        ("expoente_perda_percurso", 0.9),
        ("expoente_perda_percurso", 6.1),
        ("desvio_sombreamento_db", 0),
        ("desvio_sombreamento_db", 30),
        ("desvio_sombreamento_db", -1),
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
    assert macs == ["aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:02"]


def test_obter_por_mac_devolve_campos_novos_e_nomes_antigos(client):
    client.post("/antena", json=CORPO)
    r = client.get(f"/antena/{MAC}")
    assert r.status_code == 200
    esperado = {**CAMPOS, "rssi_referencia": -59, "expoente_perda": 2.5}
    assert r.json() == esperado


def test_criar_sem_campo_obrigatorio_devolve_422(client):
    corpo = {k: v for k, v in CORPO.items() if k != "desvio_sombreamento_db"}
    assert client.post("/antena", json=corpo).status_code == 422


def test_coordenada_zero_zero_devolve_422(client):
    r = client.post("/antena", json={**CORPO, "latitude": 0, "longitude": 0})
    assert r.status_code == 422


@pytest.mark.parametrize("lat,lon", [(0, -42.8), (-5.08, 0)])
def test_so_uma_coordenada_zerada_e_aceita(client, lat, lon):
    r = client.post("/antena", json={**CORPO, "latitude": lat, "longitude": lon})
    assert r.status_code == 201


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("potencia_referencia_dbm", -100),
        ("potencia_referencia_dbm", 0),
        ("expoente_perda_percurso", 1.0),
        ("expoente_perda_percurso", 6.0),
        ("desvio_sombreamento_db", 29.5),
    ],
)
def test_limites_inclusivos_sao_aceitos(client, campo, valor):
    assert client.post("/antena", json={**CORPO, campo: valor}).status_code == 201


def test_obter_aceita_mac_em_maiusculas(client):
    client.post("/antena", json=CORPO)
    assert client.get("/antena/AA:BB:CC:DD:EE:01").status_code == 200


def test_obter_inexistente_devolve_404(client):
    assert client.get(f"/antena/{MAC}").status_code == 404


def test_obter_com_mac_invalido_devolve_422(client):
    assert client.get("/antena/xyz").status_code == 422


def test_atualizar_persiste_os_novos_valores(client):
    client.post("/antena", json=CORPO)
    novo = {**CAMPOS, "latitude": -5.1, "longitude": -42.9, "expoente_perda_percurso": 3.0,
            "desvio_sombreamento_db": 6.0}
    r = client.put(f"/antena/{MAC}", json=novo)
    assert r.status_code == 200
    assert r.json() == {"endereco_mac": MAC, **novo}
    guardado = client.get(f"/antena/{MAC}").json()
    assert {k: guardado[k] for k in novo} == novo


def test_atualizar_inexistente_devolve_404(client):
    assert client.put(f"/antena/{MAC}", json=CAMPOS).status_code == 404


def test_atualizar_com_valor_invalido_devolve_422(client):
    client.post("/antena", json=CORPO)
    assert client.put(f"/antena/{MAC}", json={**CAMPOS, "latitude": 200}).status_code == 422


def test_atualizar_para_zero_zero_devolve_422(client):
    client.post("/antena", json=CORPO)
    r = client.put(f"/antena/{MAC}", json={**CAMPOS, "latitude": 0, "longitude": 0})
    assert r.status_code == 422


def test_remover_devolve_200_e_antena_some(client):
    client.post("/antena", json=CORPO)
    assert client.delete(f"/antena/{MAC}").status_code == 200
    assert client.get(f"/antena/{MAC}").status_code == 404


def test_remover_inexistente_devolve_404(client):
    assert client.delete(f"/antena/{MAC}").status_code == 404
