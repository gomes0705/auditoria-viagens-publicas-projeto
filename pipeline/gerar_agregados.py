"""Camada agregada para o painel, derivada do Star Schema (data/fato_viagem_*.parquet + dim_*.parquet).

Por que existe: o plano gratuito do Streamlit Cloud tem pouca memória e o app caía com várias sessões abertas.
O painel não lê nenhum dado viagem a viagem; usa só agregados:

  cubo_viagens.npz        somas e contagens por ano × mês × órgão × destino × urgência × duração × transporte ×
                          atípico (~400 mil linhas): totais, contagens, taxas, mapa e composição.
  histograma_valores.npz  quantas viagens (e quanto gasto) caem em cada uma de 240 faixas de valor, por
                          ano × órgão × escopo × urgência: medianas e curva de Pareto quando há filtro
                          (erro máximo de ~3% na mediana).
  estatisticas_exatas.json  medianas e curva de Pareto EXATAS da base completa (sem filtro), calculadas aqui
                          sobre todas as viagens: são os números do Resumo executivo, dos slides e dos relatórios.

Uso (a partir da pasta dashboard/):  python pipeline/gerar_agregados.py
"""
import json
import os
from glob import glob

import numpy as np
import pandas as pd

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
FAIXAS = np.logspace(0, 6, 241)  # limites das faixas de valor: R$ 1 a R$ 1 milhão, cada faixa ~5,9% mais larga
NB = 241                         # faixa 0 = abaixo de R$ 1 (inclui zero); faixas 1..240; a última inclui ≥ R$ 1 mi


def faixa_de(v):
    return np.clip(np.searchsorted(FAIXAS, v, side="right"), 0, NB - 1)


def curva_pareto(v, pontos=400):
    """Pontos (% das viagens, % acumulado do gasto), das mais caras para as mais baratas."""
    s = np.sort(v)[::-1]
    cum = np.cumsum(s) / s.sum()
    idx = np.unique(np.geomspace(1, len(s), pontos).astype(int)) - 1
    return {"x": ((idx + 1) / len(s)).round(6).tolist(), "y": cum[idx].round(6).tolist(),
            "top1": float(cum[len(s) // 100 - 1]), "top10": float(cum[len(s) // 10 - 1])}


def main():
    fato = pd.concat([pd.read_parquet(a) for a in sorted(glob(os.path.join(DATA, "fato_viagem_*.parquet")))], ignore_index=True)
    dt = pd.read_parquet(os.path.join(DATA, "dim_tempo.parquet")).set_index("sk_tempo")
    dd = pd.read_parquet(os.path.join(DATA, "dim_destino.parquet")).sort_values("sk_destino")
    fato["ano"] = dt["ano"].reindex(fato["sk_tempo"]).to_numpy().astype("int16")
    fato["mes"] = dt["mes"].reindex(fato["sk_tempo"]).to_numpy().astype("int8")
    dsi = dt["dia_semana"].reindex(fato["sk_tempo"]).to_numpy()
    fator = dt["fator_ipca"].reindex(fato["sk_tempo"]).to_numpy()
    dur = fato["dur"].to_numpy()

    fato["n"] = 1
    fato["total"] = fato["diarias"].astype(float) + fato["passagens"] + fato["outros"]
    fato["real"] = fato["total"] * fator
    fato["fds"] = ((dur >= 7) | ((dsi + dur - 1) >= 5)).astype("int32")      # viagem inclui sábado ou domingo
    fato["curta"] = (dur <= 3).astype("int32")                                # viagem de até 3 dias
    fato["curta_fds"] = ((dur <= 3) & (dsi >= 5)).astype("int32")            # ... iniciada no fim de semana

    for a in (glob(os.path.join(DATA, "cubo_viagens.*")) + glob(os.path.join(DATA, "valores_viagens*"))
              + glob(os.path.join(DATA, "histograma_valores.*")) + glob(os.path.join(DATA, "estatisticas_exatas.*"))):
        os.remove(a)

    # ---- 1) cubo: somas e contagens
    chaves = ["ano", "mes", "sk_orgao", "sk_destino", "urgente", "sk_duracao", "sk_modal", "outlier"]
    medidas = ["n", "real", "total", "diarias", "passagens", "outros", "fds", "curta", "curta_fds"]
    cubo = fato.groupby(chaves, observed=True)[medidas].sum().reset_index()
    for c in ["sk_orgao", "sk_destino", "sk_duracao", "sk_modal"]:
        cubo[c] = cubo[c].astype("int16")
    for c in ["n", "fds", "curta", "curta_fds"]:
        cubo[c] = cubo[c].astype("int32")
    for c in ["real", "total", "diarias", "passagens", "outros"]:
        cubo[c] = cubo[c].astype("float64")
    # NumPy comprimido (.npz), e não Parquet: carrega direto em arrays, sem o pool de memória do Arrow
    np.savez_compressed(os.path.join(DATA, "cubo_viagens.npz"), **{c: cubo[c].to_numpy() for c in cubo.columns})

    # ---- 2) histograma de valores por célula (ano × órgão × escopo × urgência), para medianas/Pareto com filtro
    escopos = sorted(dd["escopo"].unique())
    cod_esc = dd["escopo"].map({e: i for i, e in enumerate(escopos)}).to_numpy()
    esc = cod_esc[fato["sk_destino"].to_numpy() - 1]
    chave = pd.DataFrame({"ano": fato["ano"], "org": fato["sk_orgao"].astype("int16"), "esc": esc, "urg": fato["urgente"]})
    g = chave.groupby(["ano", "org", "esc", "urg"])
    celula = g.ngroup().to_numpy()
    cel = g.size().index.to_frame(index=False)
    ncel = len(cel)
    hist = {"faixas": FAIXAS, "escopos": np.array(escopos), "cel_ano": cel["ano"].to_numpy(np.int16),
            "cel_org": cel["org"].to_numpy(np.int16), "cel_esc": cel["esc"].to_numpy(np.int8), "cel_urg": cel["urg"].to_numpy(bool)}
    for col in ["real", "total"]:
        v = fato[col].to_numpy()
        plano = celula.astype(np.int64) * NB + faixa_de(v)
        hist[f"n_{col}"] = np.bincount(plano, minlength=ncel * NB).reshape(ncel, NB).astype(np.int32)
        hist[f"s_{col}"] = np.bincount(plano, weights=v, minlength=ncel * NB).reshape(ncel, NB)
    np.savez_compressed(os.path.join(DATA, "histograma_valores.npz"), **hist)

    # ---- 3) estatísticas exatas da base completa (sem filtro)
    exatas = {}
    for col in ["real", "total"]:
        v = fato[col].to_numpy()
        exatas[col] = {
            "mediana": float(np.median(v)),
            "mediana_ano": {str(k): float(x) for k, x in fato.groupby("ano")[col].median().items()},
            "mediana_orgao": {str(k): float(x) for k, x in fato.groupby("sk_orgao")[col].median().items()},
            "pareto": curva_pareto(v),
        }
    json.dump(exatas, open(os.path.join(DATA, "estatisticas_exatas.json"), "w", encoding="utf-8"))

    # ---- conferências
    assert int(cubo["n"].sum()) == len(fato) == int(hist["n_real"].sum())
    assert abs(cubo["total"].sum() - fato["total"].sum()) < 1
    assert abs(hist["s_total"].sum() - fato["total"].sum()) < 1
    print(f"cubo: {len(cubo):,} linhas | histograma: {ncel:,} células × {NB} faixas | "
          f"total conferido: R$ {cubo['total'].sum() / 1e9:.3f} bi | mediana real exata: R$ {exatas['real']['mediana']:.2f}")


if __name__ == "__main__":
    main()
