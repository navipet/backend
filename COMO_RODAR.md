# Como rodar o NaviPet Backend

Guia de referência rápida — do zero até rodando, e a rotina do dia a dia.

## Conectar o DBeaver no banco

Dados de conexão (vêm do `docker-compose.yml`):

- **Host**: `localhost`
- **Port**: `5432`
- **Database**: `geofencing`
- **Username**: `geofencing`
- **Password**: `geofencing`

Passos: `File` → `New Database Connection` → `PostgreSQL` → preenche os dados acima → marca **"Save password"** → `Test Connection` → `Finish`.

As tabelas do projeto ficam em `geofencing` → `Schemas` → **`public`** (os schemas `tiger`, `tiger_data` e `topology` são componentes internos do PostGIS, não fazem parte do projeto — pode ignorar).

---

## Primeira vez configurando a máquina (só uma vez)

```bash
# 1. Docker
sudo apt update
sudo apt install -y docker.io curl
mkdir -p ~/.docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o ~/.docker/cli-plugins/docker-compose
chmod +x ~/.docker/cli-plugins/docker-compose
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo cp ~/.docker/cli-plugins/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose

# 2. Grupo docker (evita sudo toda vez) -- precisa reiniciar sessão depois
sudo usermod -aG docker $USER

# 3. Python 3.12
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev libpq-dev
```

## Primeira vez configurando o projeto (só uma vez, depois de clonar)

```bash
cd ~/Documents/backend-navipet/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # se ainda não tiver um .env
sudo docker compose up -d db
python -m alembic upgrade head
```

## Toda vez que for trabalhar no projeto (rotina do dia a dia)

```bash
cd ~/Documents/backend-navipet/backend
source .venv/bin/activate       # ativa o ambiente Python
sudo docker compose up -d db    # sobe o banco (se já não estiver rodando)
uvicorn app.main:app --reload   # sobe a API
```

Depois disso: `http://localhost:8000/docs` para testar pelo Swagger.

## Quando for parar de trabalhar

```bash
Ctrl+C                       # para o uvicorn (no terminal onde ele está rodando)
sudo docker compose stop db  # pausa o banco (não apaga os dados)
deactivate                   # sai da venv
```

Não precisa apagar nada — os dados ficam salvos no volume `pgdata` entre uma sessão e outra.

## Comandos úteis do dia a dia

| O que você quer | Comando |
|---|---|
| Rodar os testes | `python -m pytest tests/ -v` |
| Gerar dados falsos de GPS | `python -m scripts.simulador_trajetorias --pet-id 1 --num-pontos 100` |
| Rodar a comparação experimental | `python -m scripts.rodar_comparacao --num-pontos 500` |
| Ver logs do banco | `sudo docker compose logs -f db` |
| Resetar o banco do zero (apaga tudo!) | `sudo docker compose down -v` e depois `up -d db` + `python -m alembic upgrade head` de novo |

## Se der erro de módulo não encontrado (`ModuleNotFoundError`)

99% das vezes é porque a venv não está ativa. Confere se o prompt do terminal mostra `(.venv)` no começo; se não, roda `source .venv/bin/activate`.

## Se o Alembic reclamar de `No module named 'app'`

Roda como módulo em vez de executável direto:

```bash
python -m alembic upgrade head
```
