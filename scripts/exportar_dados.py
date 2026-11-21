"""
Exporta os dados de um pet da API do NaviPet para CSV, para a analise offline
depois do teste de campo.

Gera, na pasta de saida:
  historico.csv  (id, timestamp, recebido_em, latitude, longitude)  -- TODAS as leituras
                 timestamp = hora do dispositivo (ou do servidor, se ele nao mandou)
                 recebido_em = hora (UTC) em que o servidor recebeu
  alertas.csv    (id, tipo, criado_em, resolvido, mensagem)
  zona_atual.json                                     -- ultima zona calculada
  resumo.txt     (quantas leituras, janela de tempo, leituras por minuto)

Uso (de dentro da pasta backend):
  python -m scripts.exportar_dados --pet-id 7 --api-url https://SEU-APP.onrender.com --saida teste_18_11
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime

import httpx


def _t(txt: str) -> datetime:
    return datetime.fromisoformat(txt.replace("Z", "+00:00"))


def exportar(client: httpx.Client, pet_id: int, saida: str) -> int:
    os.makedirs(saida, exist_ok=True)

    r = client.get(f"/pets/{pet_id}/historico", params={"limite": 1_000_000})
    r.raise_for_status()
    leituras = r.json()
    with open(os.path.join(saida, "historico.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "timestamp", "recebido_em", "latitude", "longitude"])
        for x in leituras:
            w.writerow([x["id"], x["timestamp"], x.get("recebido_em") or "", x["latitude"], x["longitude"]])

    r = client.get(f"/pets/{pet_id}/alertas")
    r.raise_for_status()
    alertas = sorted(r.json(), key=lambda a: a["criado_em"])
    with open(os.path.join(saida, "alertas.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "tipo", "criado_em", "resolvido", "mensagem"])
        for a in alertas:
            w.writerow([a["id"], a["tipo"], a["criado_em"], a["resolvido"], a["mensagem"]])

    r = client.get(f"/pets/{pet_id}/zona-segura")
    if r.status_code == 200:
        with open(os.path.join(saida, "zona_atual.json"), "w", encoding="utf-8") as f:
            json.dump(r.json(), f, ensure_ascii=False)
        zona = "zona_atual.json salva"
    else:
        zona = f"sem zona (HTTP {r.status_code})"

    linhas = [f"leituras: {len(leituras)}", f"alertas: {len(alertas)}", zona]
    if len(leituras) >= 2:
        ts = [_t(x["timestamp"]) for x in leituras]
        dur = (max(ts) - min(ts)).total_seconds()
        linhas.append(f"primeira: {min(ts)}  ultima: {max(ts)}  (UTC, {dur / 60:.1f} min)")
        if dur > 0:
            linhas.append(f"taxa media: {len(leituras) / (dur / 60):.1f} leituras/min (esperado ~30 se 1 a cada 2 s)")
        folgas = sorted((b - a).total_seconds() for a, b in zip(ts, ts[1:]))
        linhas.append(f"maior intervalo entre leituras: {folgas[-1]:.0f} s | mediana: {folgas[len(folgas) // 2]:.1f} s")
    texto = "\n".join(linhas)
    with open(os.path.join(saida, "resumo.txt"), "w", encoding="utf-8") as f:
        f.write(texto + "\n")
    print(texto)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pet-id", type=int, required=True)
    ap.add_argument("--api-url", default="http://localhost:8000")
    ap.add_argument("--saida", default="dados_teste")
    args = ap.parse_args()
    with httpx.Client(base_url=args.api_url, timeout=120.0) as c:
        return exportar(c, args.pet_id, args.saida)


if __name__ == "__main__":
    sys.exit(main())
