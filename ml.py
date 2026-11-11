"""Funções de machine learning do dashboard Monitriip.

Este módulo não depende de Streamlit nem de Plotly: recebe e devolve
objetos pandas/numpy, o que facilita testar e reutilizar.

Conteúdo:
- training_mask      : define quais meses entram no treino (pandemia e meses
                       finais possivelmente incompletos ficam de fora).
- decompose          : decomposição sazonal clássica (tendência, sazonalidade
                       e resíduo).
- detect_anomalies   : detecção de meses atípicos com Isolation Forest.
- forecast_series    : previsão com seleção de modelo por backtest.
- cluster_routes     : agrupamento de rotas com K-Means.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import Ridge
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

PANDEMIC_START = pd.Timestamp("2020-03-01")
PANDEMIC_END = pd.Timestamp("2021-12-01")

Z_80 = 1.2816  # faixa de 80% de uma distribuição normal
MIN_VALID_MONTHS = 36


# ============================================================
# SÉRIES MENSAIS E MÁSCARA DE TREINO
# ============================================================
def monthly_series(df, value_col, months, date_col="data_emissao_bilhete_dt"):
    """Soma value_col por mês e preenche meses sem registro com zero."""
    series = df.groupby(date_col)[value_col].sum()
    return series.reindex(months, fill_value=0.0).astype(float)


def suggest_exclude_last(series, threshold=0.5, max_months=12):
    """Conta os meses finais com menos de `threshold` do volume do mesmo
    mês do ano anterior, sinal típico de carga de dados incompleta."""
    count = 0
    for i in range(1, max_months + 1):
        if len(series) < i + 12:
            break
        current = series.iloc[-i]
        previous = series.iloc[-i - 12]
        if previous > 0 and current / previous < threshold:
            count += 1
        else:
            break
    return count


def training_mask(index, exclude_last=0, ignore_pandemic=True):
    """True para os meses que podem ser usados no treino dos modelos."""
    mask = pd.Series(True, index=index)
    if ignore_pandemic:
        mask[(index >= PANDEMIC_START) & (index <= PANDEMIC_END)] = False
    if exclude_last > 0:
        mask.iloc[-exclude_last:] = False
    return mask


# ============================================================
# DECOMPOSIÇÃO SAZONAL
# ============================================================
def decompose(series, use_mask=None, period=12):
    """Decomposição clássica por médias móveis centradas (2x12).

    Usa o modo multiplicativo quando todos os valores são positivos
    (sazonalidade proporcional ao nível) e o aditivo nos demais casos.
    Os meses com use_mask=False não participam do cálculo dos índices
    sazonais. Nas pontas, onde a média móvel centrada não existe, a
    tendência é repetida a partir do último valor calculado.

    Retorna (DataFrame, multiplicativo). Colunas: observed, trend,
    seasonal, resid, expected.
    """
    if len(series) < 2 * period + 1:
        raise ValueError("Histórico insuficiente para decomposição.")

    y = series.astype(float).interpolate(limit_direction="both")
    multiplicative = bool((y > 0).all())

    weights = np.r_[0.5, np.ones(period - 1), 0.5] / period
    raw_trend = y.rolling(window=period + 1, center=True).apply(
        lambda values: float(np.dot(values, weights)), raw=True
    )

    if multiplicative:
        detrended = y / raw_trend
    else:
        detrended = y - raw_trend

    if use_mask is not None:
        detrended = detrended.where(use_mask)

    by_month = detrended.groupby(detrended.index.month).median()
    by_month = by_month.reindex(range(1, 13))
    neutral = 1.0 if multiplicative else 0.0
    by_month = by_month.fillna(neutral)
    if multiplicative:
        by_month = by_month / by_month.mean()
    else:
        by_month = by_month - by_month.mean()

    seasonal = pd.Series(by_month.reindex(y.index.month).to_numpy(), index=y.index)
    trend = raw_trend.ffill().bfill()

    if multiplicative:
        expected = trend * seasonal
        resid = y / expected
    else:
        expected = trend + seasonal
        resid = y - expected

    result = pd.DataFrame(
        {
            "observed": y,
            "trend": trend,
            "seasonal": seasonal,
            "resid": resid,
            "expected": expected,
        }
    )
    return result, multiplicative


# ============================================================
# DETECÇÃO DE ANOMALIAS
# ============================================================
def detect_anomalies(series, decomp, multiplicative, contamination=0.08):
    """Isolation Forest sobre três sinais de cada mês:

    - resíduo da decomposição sazonal (desvio em relação ao esperado);
    - variação em relação ao mês anterior;
    - variação em relação ao mesmo mês do ano anterior.

    O modelo sinaliza a fração `contamination` dos meses mais atípicos.
    Os 12 primeiros meses não são avaliados (faltam variações anuais).
    """
    y = series.astype(float).interpolate(limit_direction="both")
    log_y = np.log1p(y)

    if multiplicative:
        resid_signal = np.log(decomp["resid"])
    else:
        scale = float(y.std()) or 1.0
        resid_signal = decomp["resid"] / scale

    features = pd.DataFrame(
        {
            "resid": resid_signal,
            "mom": log_y.diff(),
            "yoy": log_y.diff(12),
        },
        index=y.index,
    ).dropna()

    scaled = StandardScaler().fit_transform(features)
    model = IsolationForest(
        n_estimators=300,
        contamination=contamination,
        random_state=42,
    )
    flags = model.fit_predict(scaled) == -1
    scores = -model.score_samples(scaled)

    out = pd.DataFrame(index=y.index)
    out["observed"] = y
    out["expected"] = decomp["expected"]
    out["deviation"] = np.where(
        out["expected"] > 0, out["observed"] / out["expected"] - 1, np.nan
    )
    out["is_anomaly"] = False
    out["score"] = np.nan
    out.loc[features.index, "is_anomaly"] = flags
    out.loc[features.index, "score"] = scores
    return out


# ============================================================
# PREVISÃO
# ============================================================
def _regression_features(index, origin):
    """Tendência linear (em anos) e variáveis dummy de mês."""
    months_since = (
        (index.year - origin.year) * 12 + (index.month - origin.month)
    ).to_numpy()
    columns = [months_since / 12.0]
    columns += [(index.month == m).astype(float) for m in range(2, 13)]
    return np.column_stack(columns)


def _fit_regression(y_valid):
    """Ridge sobre log(1 + y) com tendência linear e sazonalidade mensal."""
    origin = y_valid.index[0]
    model = Ridge(alpha=0.1)
    model.fit(_regression_features(y_valid.index, origin), np.log1p(y_valid))

    def predict(target_index):
        pred = model.predict(_regression_features(target_index, origin))
        return pd.Series(np.expm1(pred), index=target_index)

    return predict


def _fit_seasonal_naive(y_valid_full):
    """Mesmo mês do ano anterior, ajustado pelo crescimento recente.

    y_valid_full tem NaN nos meses que não podem ser usados.
    """
    ratios = []
    for date in y_valid_full.dropna().index[::-1]:
        previous = date - pd.DateOffset(years=1)
        if previous in y_valid_full.index and not np.isnan(y_valid_full[previous]):
            if y_valid_full[previous] > 0:
                ratios.append(y_valid_full[date] / y_valid_full[previous])
        if len(ratios) == 12:
            break
    growth = float(np.clip(np.median(ratios), 0.5, 1.5)) if ratios else 1.0

    def predict(target_index):
        values = []
        for date in target_index:
            value = np.nan
            for k in range(1, 5):
                source = date - pd.DateOffset(years=k)
                if source in y_valid_full.index and not np.isnan(
                    y_valid_full[source]
                ):
                    value = y_valid_full[source] * growth**k
                    break
            values.append(value)
        return pd.Series(values, index=target_index)

    return predict


MODELS = {
    "Regressão (tendência + sazonalidade)": "regression",
    "Sazonal ingênuo ajustado": "naive",
}


def _fit_model(kind, y_masked):
    """Treina o modelo; y_masked tem NaN nos meses fora do treino."""
    if kind == "regression":
        return _fit_regression(y_masked.dropna())
    return _fit_seasonal_naive(y_masked)


def _mape(actual, predicted):
    valid = (actual > 0) & predicted.notna()
    if valid.sum() == 0:
        return np.nan
    return float(
        (np.abs(actual[valid] - predicted[valid]) / actual[valid]).mean() * 100
    )


def forecast_series(series, use_mask, horizon=12, holdout=12):
    """Prevê os próximos `horizon` meses após o último mês de treino.

    Compara os modelos por backtest (treina até antes dos últimos
    `holdout` meses válidos e testa neles), escolhe o de menor MAPE e
    reajusta com todos os dados válidos. A faixa de 80% usa o desvio
    dos erros (em log) do backtest.

    Retorna um dict com forecast, backtest, holdout e best.
    """
    y = series.astype(float)
    y_masked = y.where(use_mask & np.isfinite(y))
    valid = y_masked.dropna()

    if len(valid) < MIN_VALID_MONTHS:
        raise ValueError(
            f"São necessários ao menos {MIN_VALID_MONTHS} meses válidos "
            f"para prever; restam {len(valid)}."
        )

    holdout = min(holdout, len(valid) // 3)
    test_index = valid.index[-holdout:]
    train_masked = y_masked.where(y_masked.index < test_index[0])

    rows = []
    holdout_table = pd.DataFrame({"actual": valid.loc[test_index]})
    log_errors = {}
    for name, kind in MODELS.items():
        predict = _fit_model(kind, train_masked)
        predicted = predict(test_index)
        holdout_table[name] = predicted
        rows.append({"Modelo": name, "MAPE (%)": _mape(holdout_table["actual"], predicted)})
        ok = predicted.notna() & (predicted > 0) & (holdout_table["actual"] > 0)
        log_errors[name] = np.log(
            holdout_table["actual"][ok] / predicted[ok]
        )

    backtest = pd.DataFrame(rows).sort_values("MAPE (%)").reset_index(drop=True)
    best = str(backtest.loc[0, "Modelo"])

    last_valid = valid.index[-1]
    target = pd.date_range(
        last_valid + pd.DateOffset(months=1), periods=horizon, freq="MS"
    )
    predict_final = _fit_model(MODELS[best], y_masked)
    pred = predict_final(target)

    # Se o modelo ingênuo não tiver referência para algum mês, usa a regressão.
    if pred.isna().any():
        fallback = _fit_model("regression", y_masked)(target)
        pred = pred.fillna(fallback)

    sigma = float(log_errors[best].std(ddof=0)) if len(log_errors[best]) > 1 else 0.1
    sigma = max(sigma, 0.05)
    forecast = pd.DataFrame(
        {
            "pred": pred,
            "lower": pred * np.exp(-Z_80 * sigma),
            "upper": pred * np.exp(Z_80 * sigma),
        }
    )

    return {
        "forecast": forecast,
        "backtest": backtest,
        "holdout": holdout_table,
        "best": best,
        "holdout_months": holdout,
        "train_months": int(len(valid)),
    }


# ============================================================
# AGRUPAMENTO DE ROTAS
# ============================================================
ROUTE_FEATURES = {
    "log_volume": "Volume (log10 da média mensal)",
    "ticket_medio": "Ticket médio (R$)",
    "cv": "Variação mensal (coef. de variação)",
    "pico_sazonal": "Pico sazonal (mês mais forte / média)",
}


def _cluster_label(z_volume, z_ticket, z_season):
    volume = "Alto volume" if z_volume > 0.5 else "Baixo volume" if z_volume < -0.5 else "Volume médio"
    ticket = "tarifa alta" if z_ticket > 0.5 else "tarifa baixa" if z_ticket < -0.5 else "tarifa média"
    label = f"{volume} · {ticket}"
    if z_season > 0.75:
        label += " · muito sazonal"
    return label


def build_route_features(df, min_months):
    """Uma linha por rota, com as quatro características usadas no K-Means."""
    d = (
        df.groupby(["rota_unica", "data_emissao_bilhete_dt"], as_index=False)[
            ["total_bilhetes", "total_arrecadacao"]
        ]
        .sum()
    )
    months_present = d.groupby("rota_unica")["data_emissao_bilhete_dt"].nunique()
    keep = months_present[months_present >= min_months].index
    d = d[d["rota_unica"].isin(keep) & (d["total_bilhetes"] > 0)].copy()

    grouped = d.groupby("rota_unica")
    mean_tickets = grouped["total_bilhetes"].mean()
    std_tickets = grouped["total_bilhetes"].std(ddof=0)
    total_tickets = grouped["total_bilhetes"].sum()
    total_revenue = grouped["total_arrecadacao"].sum()

    d["mes"] = d["data_emissao_bilhete_dt"].dt.month
    by_month = d.groupby(["rota_unica", "mes"])["total_bilhetes"].mean().unstack()
    peak = by_month.max(axis=1) / by_month.mean(axis=1)

    features = pd.DataFrame(
        {
            "log_volume": np.log10(mean_tickets),
            "ticket_medio": total_revenue / total_tickets,
            "cv": std_tickets / mean_tickets,
            "pico_sazonal": peak,
            "meses": months_present.reindex(mean_tickets.index),
            "media_mensal": mean_tickets,
        }
    )
    return features.replace([np.inf, -np.inf], np.nan).dropna()


def cluster_routes(df, k, min_months):
    """Agrupa as rotas com K-Means e projeta em 2D com PCA.

    Retorna um dict com: routes (uma linha por rota), summary (uma linha
    por grupo), silhouette, silhouette_by_k, explained (variância do PCA)
    e n_routes.
    """
    features = build_route_features(df, min_months)
    if len(features) < max(k * 3, 10):
        raise ValueError(
            f"Apenas {len(features)} rotas têm {min_months}+ meses de "
            "histórico; reduza o mínimo de meses ou o número de grupos."
        )

    cols = list(ROUTE_FEATURES)
    scaler = StandardScaler()
    X = scaler.fit_transform(features[cols])

    def fit(n_clusters):
        return KMeans(n_clusters=n_clusters, n_init=10, random_state=42).fit(X)

    model = fit(k)
    labels = model.labels_

    sil_by_k = {}
    for candidate in range(2, min(8, len(features) - 1) + 1):
        sil_by_k[candidate] = float(
            silhouette_score(X, fit(candidate).labels_)
        )

    # Numera os grupos do maior para o menor volume médio.
    volume_by_raw = features.groupby(labels)["media_mensal"].mean()
    order = volume_by_raw.sort_values(ascending=False).index.tolist()
    rename = {raw: i + 1 for i, raw in enumerate(order)}
    group = pd.Series(labels, index=features.index).map(rename)

    z = pd.DataFrame(X, index=features.index, columns=cols)
    z_means = z.groupby(group).mean()
    names = {
        g: _cluster_label(
            z_means.loc[g, "log_volume"],
            z_means.loc[g, "ticket_medio"],
            z_means.loc[g, "pico_sazonal"],
        )
        for g in z_means.index
    }

    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X)

    routes = features.copy()
    routes["grupo"] = group
    routes["perfil"] = routes["grupo"].map(names)
    routes["pc1"] = coords[:, 0]
    routes["pc2"] = coords[:, 1]
    routes = routes.sort_values("media_mensal", ascending=False)

    summary = (
        routes.groupby("grupo")
        .agg(
            rotas=("media_mensal", "size"),
            media_mensal=("media_mensal", "mean"),
            ticket_medio=("ticket_medio", "mean"),
            cv=("cv", "mean"),
            pico_sazonal=("pico_sazonal", "mean"),
        )
        .reset_index()
    )
    summary["perfil"] = summary["grupo"].map(names)

    return {
        "routes": routes.reset_index(),
        "summary": summary,
        "silhouette": float(silhouette_score(X, labels)),
        "silhouette_by_k": sil_by_k,
        "explained": float(pca.explained_variance_ratio_.sum()),
        "n_routes": int(len(features)),
    }
