from app.algorithms.densidade import DensidadeDBSCAN
from app.core.config import Settings
from app.services import zona as servico_zona


def test_padroes_dos_parametros_do_dbscan():
    s = Settings()
    assert s.zona_dbscan_eps_metros == 50.0
    assert s.zona_dbscan_min_amostras == 5
    assert s.zona_max_pontos == 2000


def test_variaveis_de_ambiente_sobrescrevem_os_parametros(monkeypatch):
    monkeypatch.setenv("ZONA_DBSCAN_EPS_METROS", "20")
    monkeypatch.setenv("ZONA_DBSCAN_MIN_AMOSTRAS", "30")
    monkeypatch.setenv("ZONA_MAX_PONTOS", "1000")
    s = Settings()
    assert s.zona_dbscan_eps_metros == 20.0
    assert s.zona_dbscan_min_amostras == 30
    assert s.zona_max_pontos == 1000


def test_servico_monta_o_dbscan_com_a_configuracao(monkeypatch):
    monkeypatch.setattr(servico_zona.settings, "zona_dbscan_eps_metros", 25.0)
    monkeypatch.setattr(servico_zona.settings, "zona_dbscan_min_amostras", 12)
    monkeypatch.setattr(servico_zona.settings, "zona_max_pontos", 800)
    algoritmo = servico_zona.construir_algoritmo("densidade")
    assert isinstance(algoritmo, DensidadeDBSCAN)
    assert algoritmo.eps_metros == 25.0
    assert algoritmo.min_amostras == 12
    assert algoritmo.max_pontos == 800


def test_teto_zero_na_configuracao_desliga_o_teto(monkeypatch):
    monkeypatch.setattr(servico_zona.settings, "zona_max_pontos", 0)
    assert servico_zona.construir_algoritmo("densidade").max_pontos is None
