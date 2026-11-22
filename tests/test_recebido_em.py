"""o servidor sempre guarda a hora em que recebeu a leitura (recebido_em),
alem do timestamp que o dispositivo mandar"""
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.api import pets as rota
from app.models.models import Localizacao
from app.models.schemas import LocalizacaoCreate, LocalizacaoOut


def _chamar(timestamp):
    db = MagicMock()
    adicionados = []
    db.add.side_effect = adicionados.append

    def fake_query(modelo):
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        if modelo is Localizacao:
            q.first.side_effect = lambda: adicionados[0]
        else:
            q.first.return_value = object()
        return q

    db.query.side_effect = fake_query
    dados = LocalizacaoCreate(latitude=-5.09, longitude=-42.8, timestamp=timestamp)
    with patch.object(rota, "avaliar_posicao"), patch.object(rota, "recalcular_zona_se_necessario"):
        rota.registrar_localizacao(1, dados, db)
    return adicionados[0]


def test_sem_timestamp_do_dispositivo_usa_hora_do_servidor_nos_dois_campos():
    loc = _chamar(None)
    assert loc.recebido_em is not None
    assert loc.timestamp == loc.recebido_em


def test_com_timestamp_do_dispositivo_guarda_as_duas_horas():
    hora_esp = datetime(2026, 11, 19, 12, 0, 0)
    loc = _chamar(hora_esp)
    assert loc.timestamp == hora_esp
    assert loc.recebido_em is not None and loc.recebido_em != hora_esp
    assert (datetime.utcnow() - loc.recebido_em).total_seconds() < 5


def test_resposta_da_api_inclui_recebido_em():
    out = LocalizacaoOut(
        id=1, pet_id=1, latitude=-5.0, longitude=-42.0,
        timestamp=datetime(2026, 11, 19, 12), recebido_em=datetime(2026, 11, 19, 12, 0, 1),
    )
    assert out.recebido_em.second == 1


def test_timestamp_com_fuso_e_convertido_para_utc_sem_fuso():
    loc = _chamar("2026-11-21T15:43:36.052-03:00")
    assert loc.timestamp == datetime(2026, 11, 21, 18, 43, 36, 52000)
    assert loc.timestamp.tzinfo is None


def test_timestamp_em_utc_com_z_e_aceito():
    loc = _chamar("2026-11-21T18:43:36.052Z")
    assert loc.timestamp == datetime(2026, 11, 21, 18, 43, 36, 52000)
