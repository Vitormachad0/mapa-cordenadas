from pathlib import Path
from typing import Optional
import re
import unicodedata

from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
import folium
import pandas as pd

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB

UPLOAD_FOLDER = Path("uploads")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

# Configurações de mapeamento de colunas
LAT_CANDIDATES = {"latitude", "lat", "y", "coordenada_lat", "coord_lat"}
LON_CANDIDATES = {"longitude", "long", "lon", "lng", "x", "coordenada_lon", "coord_lon"}
TIME_CANDIDATES = {"horario", "hora", "time", "timestamp", "data", "date", "clock"}

def normalize_text(texto: str) -> str:
    """Normaliza texto removendo acentos e convertendo para minúsculas."""
    sem_acentos = unicodedata.normalize("NFKD", str(texto))
    sem_acentos = "".join(char for char in sem_acentos if not unicodedata.combining(char))
    return sem_acentos.strip().lower()

def allowed_file(filename: str) -> bool:
    """Verifica se a extensão do arquivo é permitida."""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza os nomes das colunas."""
    df.columns = [
        normalize_text(str(col)).replace(" ", "_").replace("-", "_") for col in df.columns
    ]
    return df

def find_coordinate_columns(df: pd.DataFrame) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Detecta automaticamente as colunas de latitude, longitude e hora."""
    lat_col, lon_col, time_col = None, None, None

    # Primeira passada: Busca por nomes exatos normalizados
    for col in df.columns:
        col_clean = normalize_text(col).replace(" ", "_")
        if col_clean in LAT_CANDIDATES and lat_col is None:
            lat_col = col
        if col_clean in LON_CANDIDATES and lon_col is None:
            lon_col = col
        if col_clean in TIME_CANDIDATES and time_col is None:
            time_col = col

    # Segunda passada: Busca por tokens contidos no nome da coluna
    for col in df.columns:
        col_clean = normalize_text(col)
        if lat_col is None and any(t in col_clean for t in ("latitude", " lat", "lat_", "_lat")):
            lat_col = col
        if lon_col is None and any(t in col_clean for t in ("longitude", " lon", "lng", " long", "_lon")):
            lon_col = col
        if time_col is None and any(t in col_clean for t in ("horario", "hora", "time", "data")):
            time_col = col

    return lat_col, lon_col, time_col

def _infer_decimal_coordinate(valor: str, limite: float) -> Optional[float]:
    """Inferir coordenada decimal a partir de número inteiro grande."""
    sinal = -1 if valor.startswith("-") else 1
    digitos = re.sub(r"\D", "", valor)
    if len(digitos) < 4:
        return None
    prioridades = [2, 1] if limite == 90 else [3, 2, 1]
    for posicao in prioridades:
        if len(digitos) <= posicao:
            continue
        tentativa = float(f"{digitos[:posicao]}.{digitos[posicao:]}") * sinal
        if abs(tentativa) <= limite:
            return tentativa
    return None

def limpar_universal(valor, limite: float) -> Optional[float]:
    """Limpa e converte valores de coordenadas para formato decimal."""
    if pd.isna(valor) or str(valor).strip() == "":
        return None
    bruto = str(valor).strip().replace(",", ".")
    bruto = re.sub(r"[^0-9\.\-]", "", bruto)
    if not bruto or bruto == "-":
        return None
    if bruto.count(".") > 1:
        partes = bruto.split(".")
        bruto = f"{partes[0]}.{''.join(partes[1:])}"
    try:
        numero = float(bruto)
        if abs(numero) <= limite:
            return numero
    except ValueError:
        pass
    return _infer_decimal_coordinate(bruto, limite)

def carregar_planilha(caminho: Path) -> pd.DataFrame:
    """Carrega planilha do arquivo."""
    if caminho.suffix.lower() == ".csv":
        try:
            return pd.read_csv(caminho, sep=None, engine="python")
        except UnicodeDecodeError:
            return pd.read_csv(caminho, sep=None, engine="python", encoding="latin1")
    return pd.read_excel(caminho)

@app.route("/", methods=["GET", "POST"])
def index():
    mapa_html = None
    error_msg = None
    info_msg = None
    resumo = None

    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename:
            error_msg = "Selecione um arquivo CSV ou Excel."
        elif not allowed_file(file.filename):
            error_msg = "Formato inválido. Use .csv, .xlsx ou .xls."
        else:
            nome_seguro = secure_filename(file.filename)
            caminho = UPLOAD_FOLDER / nome_seguro
            file.save(caminho)

            try:
                df = carregar_planilha(caminho)
                if df.empty:
                    raise ValueError("A planilha está vazia.")

                df_original_cols = df.copy()
                df = normalize_columns(df)
                lat_col, lon_col, time_col = find_coordinate_columns(df)

                if lat_col and lon_col:
                    pontos_validos = []
                    descartados = 0

                    for idx, row in df.iterrows():
                        lat = limpar_universal(row[lat_col], limite=90)
                        lon = limpar_universal(row[lon_col], limite=180)
                        
                        hora_info = str(row[time_col]) if time_col and not pd.isna(row[time_col]) else None

                        # Ajuste de inversão lat/lon comum
                        if lat is not None and lon is not None and abs(lat) > 90 and abs(lon) <= 90:
                            lat, lon = lon, lat

                        if lat is not None and lon is not None:
                            pontos_validos.append({"lat": lat, "lon": lon, "hora": hora_info})
                        else:
                            descartados += 1

                    if pontos_validos:
                        coords_mapa = [[p["lat"], p["lon"]] for p in pontos_validos]
                        mapa = folium.Map(location=coords_mapa[0], zoom_start=13, control_scale=True)

                        for i, p in enumerate(pontos_validos, start=1):
                            popup_html = f"<b>Ponto:</b> {i}<br>"
                            if p['hora']:
                                popup_html += f"<b>Horário:</b> {p['hora']}<br>"
                            popup_html += f"<b>Lat:</b> {p['lat']:.6f}<br><b>Lon:</b> {p['lon']:.6f}"

                            folium.Marker(
                                location=[p["lat"], p["lon"]],
                                popup=folium.Popup(popup_html, max_width=250),
                                tooltip=f"Ponto {i} {f'({p['hora']})' if p['hora'] else ''}",
                            ).add_to(mapa)

                        if len(coords_mapa) > 1:
                            folium.PolyLine(coords_mapa, color="#145DA0", weight=3, opacity=0.8).add_to(mapa)

                        mapa.fit_bounds(coords_mapa)
                        mapa_html = mapa._repr_html_()
                        info_msg = "Mapa gerado com sucesso."
                        resumo = {
                            "arquivo": nome_seguro,
                            "linhas_total": len(df),
                            "pontos_validos": len(pontos_validos),
                            "pontos_descartados": descartados,
                            "colunas_usadas": f"lat='{lat_col}', lon='{lon_col}', hora='{time_col or 'N/A'}'",
                        }
                    else:
                        error_msg = "Nenhum ponto válido encontrado."
                else:
                    error_msg = f"Colunas de coordenadas não identificadas. Colunas: {', '.join(df.columns)}"
            except Exception as e:
                error_msg = f"Erro ao processar: {str(e)}"

    return render_template("index.html", mapa=mapa_html, error=error_msg, info=info_msg, resumo=resumo)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)