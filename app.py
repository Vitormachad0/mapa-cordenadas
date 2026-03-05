from pathlib import Path
import re
import unicodedata
from typing import Optional

from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
import folium
import pandas as pd

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

TIME_CANDIDATES = {
    "horario", "hora", "time", "timestamp", "data", "date", "clock"
}


# -------------------------------
# UTILIDADES
# -------------------------------

def normalize_text(texto: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", str(texto))
    sem_acentos = "".join(c for c in sem_acentos if not unicodedata.combining(c))
    return sem_acentos.lower().strip()


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [
        normalize_text(col).replace(" ", "_").replace("-", "_")
        for col in df.columns
    ]
    return df


# -------------------------------
# LIMPEZA DE COORDENADAS
# -------------------------------

def _infer_decimal_coordinate(valor: str, limite: float) -> Optional[float]:

    sinal = -1 if valor.startswith("-") else 1
    digitos = re.sub(r"\D", "", valor)

    if len(digitos) < 4:
        return None

    prioridades = [2, 1] if limite == 90 else [3, 2, 1]

    for pos in prioridades:

        if len(digitos) <= pos:
            continue

        tentativa = float(f"{digitos[:pos]}.{digitos[pos:]}") * sinal

        if abs(tentativa) <= limite:
            return tentativa

    return None


def limpar_universal(valor, limite: float) -> Optional[float]:

    if pd.isna(valor):
        return None

    bruto = str(valor).strip().replace(",", ".")
    bruto = re.sub(r"[^0-9\.\-]", "", bruto)

    if not bruto:
        return None

    try:

        numero = float(bruto)

        if abs(numero) <= limite:
            return numero

    except:
        pass

    return _infer_decimal_coordinate(bruto, limite)


# -------------------------------
# EXTRAÇÃO DE COORDENADAS
# -------------------------------

def extrair_coordenadas(texto):

    if pd.isna(texto):
        return None, None

    numeros = re.findall(r"-?\d+\.\d+|-?\d+", str(texto))

    if len(numeros) >= 2:

        lat = limpar_universal(numeros[0], 90)
        lon = limpar_universal(numeros[1], 180)

        return lat, lon

    return None, None


def detectar_coordenadas(df):

    lat_col = None
    lon_col = None

    for col in df.columns:

        nome = normalize_text(col)

        if any(x in nome for x in ["lat", "latitude"]):
            lat_col = col

        if any(x in nome for x in ["lon", "lng", "long", "longitude"]):
            lon_col = col

    if lat_col and lon_col:

        return df[lat_col], df[lon_col], lat_col, lon_col

    # tentar encontrar coluna com lat,long

    for col in df.columns:

        amostra = df[col].astype(str).head(50)

        for valor in amostra:

            lat, lon = extrair_coordenadas(valor)

            if lat is not None and lon is not None:

                lats = []
                lons = []

                for v in df[col]:

                    lat, lon = extrair_coordenadas(v)

                    lats.append(lat)
                    lons.append(lon)

                return pd.Series(lats), pd.Series(lons), col, col

    return None, None, None, None


# -------------------------------
# DETECTAR TEMPO
# -------------------------------

def detectar_coluna_tempo(df):

    for col in df.columns:

        nome = normalize_text(col)

        if any(x in nome for x in TIME_CANDIDATES):
            return col

    return None


# -------------------------------
# CARREGAR PLANILHA
# -------------------------------

def carregar_planilha(caminho: Path):

    if caminho.suffix.lower() == ".csv":

        try:
            return pd.read_csv(caminho, sep=None, engine="python")

        except:
            return pd.read_csv(caminho, sep=None, engine="python", encoding="latin1")

    return pd.read_excel(caminho)


# -------------------------------
# ROTA PRINCIPAL
# -------------------------------

@app.route("/", methods=["GET", "POST"])
def index():

    mapa_html = None
    error_msg = None
    info_msg = None
    resumo = None

    if request.method == "POST":

        file = request.files.get("file")

        if not file or not file.filename:
            error_msg = "Selecione um arquivo."

        elif not allowed_file(file.filename):
            error_msg = "Formato inválido."

        else:

            nome = secure_filename(file.filename)
            caminho = UPLOAD_FOLDER / nome

            file.save(caminho)

            try:

                df = carregar_planilha(caminho)

                if df.empty:
                    raise ValueError("Planilha vazia.")

                df = normalize_columns(df)

                lat_series, lon_series, lat_col, lon_col = detectar_coordenadas(df)

                time_col = detectar_coluna_tempo(df)

                if lat_series is None:

                    error_msg = f"Não foi possível detectar coordenadas. Colunas: {', '.join(df.columns)}"
                    return render_template("index.html", error=error_msg)

                pontos_validos = []
                descartados = 0

                for i in range(len(df)):

                    lat = limpar_universal(lat_series.iloc[i], 90)
                    lon = limpar_universal(lon_series.iloc[i], 180)

                    if lat is None or lon is None:
                        descartados += 1
                        continue

                    hora = None

                    if time_col and not pd.isna(df.iloc[i][time_col]):
                        hora = str(df.iloc[i][time_col])

                    pontos_validos.append({
                        "lat": lat,
                        "lon": lon,
                        "hora": hora
                    })

                if not pontos_validos:

                    error_msg = "Nenhum ponto válido encontrado."
                    return render_template("index.html", error=error_msg)

                coords = [[p["lat"], p["lon"]] for p in pontos_validos]

                mapa = folium.Map(
                    location=coords[0],
                    zoom_start=13,
                    control_scale=True
                )

                for i, p in enumerate(pontos_validos):

                    popup = f"<b>Ponto {i+1}</b><br>"

                    if p["hora"]:
                        popup += f"<b>Hora:</b> {p['hora']}<br>"

                    popup += f"Lat: {p['lat']}<br>Lon: {p['lon']}"

                    folium.Marker(
                        location=[p["lat"], p["lon"]],
                        popup=popup,
                        tooltip=f"Ponto {i+1}"
                    ).add_to(mapa)

                if len(coords) > 1:

                    folium.PolyLine(
                        coords,
                        color="blue",
                        weight=3
                    ).add_to(mapa)

                mapa.fit_bounds(coords)

                mapa_html = mapa._repr_html_()

                info_msg = "Mapa gerado com sucesso."

                resumo = {
                    "arquivo": nome,
                    "linhas_total": len(df),
                    "pontos_validos": len(pontos_validos),
                    "descartados": descartados,
                    "colunas_detectadas": f"{lat_col}, {lon_col}"
                }

            except Exception as e:

                error_msg = str(e)

    return render_template(
        "index.html",
        mapa=mapa_html,
        error=error_msg,
        info=info_msg,
        resumo=resumo
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)