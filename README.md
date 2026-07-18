# Geofencing Adaptativo — Backend

Backend do sistema IoT de rastreamento de pets com geofencing adaptativo.
Escopo individual: API REST de trajetórias + 3 abordagens de construção de zona
segura (raio fixo, convex hull, densidade) + módulo de comparação + alertas.

## Stack

- Python 3.11+
- FastAPI
- PostgreSQL + PostGIS
- SQLAlchemy + GeoAlchemy2
- shapely / scikit-learn (algoritmos de zona)
- pytest

## Como rodar (ambiente de desenvolvimento)

```bash
# 1. Subir banco de dados (Postgres + PostGIS)
docker compose up -d db

# 2. Criar ambiente virtual e instalar dependências
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Rodar migrações (quando existirem)
# alembic upgrade head

# 4. Subir a API
uvicorn app.main:app --reload
```

A documentação interativa fica em `http://localhost:8000/docs` (Swagger,
gerado automaticamente pelo FastAPI).

## Estrutura do projeto

```
app/
  api/           -> rotas/endpoints da API REST
  core/          -> configuração, settings, conexão com banco
  models/        -> modelos de dados (Pet, Localizacao, ZonaSegura)
  services/       -> lógica de negócio (ingestão, verificação de status)
  algorithms/     -> as 3 abordagens de geofencing (raio, hull, densidade)
  db/             -> setup do banco, sessão, migrações
tests/            -> testes unitários e de integração
docs/             -> anotações, resultados experimentais, diagramas
```

## Roadmap de implementação (ordem sugerida)

1. [ ] Modelos de dados + conexão com banco (Pet, Localizacao, ZonaSegura)
2. [x] Endpoint de ingestão de coordenadas GPS (`POST /pets/{id}/localizacoes`)
3. [x] Abordagem 1: raio fixo (mais simples, MVP ponta a ponta)
4. [x] Endpoint de consulta de zona + verificação dentro/fora
5. [x] Abordagem 2: convex hull
6. [x] Abordagem 3: densidade (DBSCAN/KDE)
7. [ ] Módulo de comparação experimental (falsos positivos, latência, cobertura)
8. [ ] Testes automatizados dos 3 algoritmos
9. [ ] Integração com frontend e infraestrutura (broker de mensageria)

## Métricas de avaliação (Seção 6.3 do TCC)

- Taxa de falsos positivos
- Latência de detecção
- Cobertura territorial