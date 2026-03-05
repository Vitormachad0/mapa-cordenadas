# 🗺️ Cords — Visualizador de Rotas

Aplicação web para visualização interativa de rotas a partir de arquivos Excel ou CSV contendo coordenadas geográficas.

## ✨ Funcionalidades

- 📂 Upload de arquivos **CSV**, **XLS** e **XLSX** via drag-and-drop ou seleção manual
- 🔍 **Detecção automática** das colunas de latitude e longitude
- 🧹 **Limpeza inteligente de coordenadas** — lida com formatos numéricos comuns em planilhas brasileiras (ex.: valores inteiros grandes sem separador decimal)
- 🗺️ Mapa interativo com:
  - Marcadores numerados para cada ponto
  - Popups com todos os dados da linha ao clicar no marcador
  - Tooltips ao passar o mouse
  - Linha conectando os pontos na ordem em que aparecem na planilha
  - Zoom automático para enquadrar todos os pontos
- 🎨 Interface moderna com feedback visual de erros

## 🛠️ Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python · Flask · Pandas |
| Mapas | Folium |
| Leitura de Excel | openpyxl |
| Frontend | HTML · CSS · JavaScript |

## 📦 Instalação

**Pré-requisito:** Python 3.9+

```bash
# 1. Clone o repositório
git clone <url-do-repositorio>
cd cords

# 2. Crie e ative um ambiente virtual (recomendado)
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt
```

## 🚀 Como executar

```bash
python app.py
```

Acesse no navegador: [http://localhost:5000](http://localhost:5000)

## 📋 Formato dos arquivos

O arquivo enviado precisa conter ao menos **uma coluna de latitude** e **uma de longitude**. Os seguintes nomes de coluna são reconhecidos automaticamente (sem distinção de maiúsculas/minúsculas):

| Latitude | Longitude |
|---|---|
| `lat`, `latitude`, `y` | `lon`, `long`, `longitude`, `x` |
| `latitud` | `coordenada longitude`, `coordenada x` |
| `coordenada latitude`, `coordenada y` | |

As demais colunas da planilha são exibidas no popup de cada marcador.

### Exemplo de CSV válido

```csv
nome,lat,lon
Ponto A,-23.550520,-46.633308
Ponto B,-22.906847,-43.172896
Ponto C,-19.916681,-43.934493
```

## 📁 Estrutura do projeto

```
cords/
├── app.py              # Aplicação Flask (backend)
├── requirements.txt    # Dependências Python
├── templates/
│   └── index.html      # Interface do usuário
├── static/
│   └── style.css       # Estilos CSS
└── uploads/            # Pasta temporária de uploads (criada automaticamente)
```

## ⚙️ Configurações

As seguintes configurações podem ser ajustadas diretamente em `app.py`:

| Parâmetro | Valor padrão | Descrição |
|---|---|---|
| `MAX_CONTENT_LENGTH` | 16 MB | Tamanho máximo do arquivo enviado |
| `UPLOAD_FOLDER` | `uploads/` | Pasta de armazenamento temporário |
| `host` | `0.0.0.0` | Interface de rede do servidor |
| `port` | `5000` | Porta do servidor |

## 📄 Licença

Distribuído sob a licença MIT.
