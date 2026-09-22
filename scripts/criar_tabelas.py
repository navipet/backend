"""
script simples para criar as tabelas no banco (sem alembic ainda).
use isto no início do projeto; depois migre para alembic quando
precisar versionar alterações de schema

rodar com: python -m scripts.criar_tabelas
"""

from sqlalchemy import text

from app.db.session import Base, engine
from app.models import models  # noqa: F401  (garante que os modelos sejam registrados)


def main():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()

    Base.metadata.create_all(bind=engine)
    print("Tabelas criadas com sucesso.")


if __name__ == "__main__":
    main()