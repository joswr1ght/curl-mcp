# Curl MCP - Natural Language Curl Commander

Este proyecto permite ejecutar comandos curl usando lenguaje natural en español o inglés.

## Requisitos Previos

- Python 3.13 o superior
- curl instalado en el sistema
- Git

## Instalación

1. Clonar el repositorio:
```bash
git clone [URL_DEL_REPOSITORIO]
cd curl-mcp
```

2. Crear y activar un entorno virtual (recomendado):
```bash
python -m venv .venv
source .venv/bin/activate  # En Linux/macOS
# o
.venv\Scripts\activate     # En Windows
```

3. Instalar las dependencias:
```bash
pip install -e .
```

## Configuración

1. Copiar el archivo de configuración de ejemplo:
```bash
cp setting_example.json settings.json
```

2. El servidor MCP ya está listo para usar.

## Uso

1. Iniciar el servidor MCP:
```bash
python main.py
```

2. El servidor ahora puede recibir comandos en lenguaje natural como:
   - "Haz un POST a https://ejemplo.com/api con los datos nombre=Juan y edad=25"
   - "Descarga la página https://ejemplo.com y guárdala como pagina.html"
   - "Haz una petición GET a https://api.ejemplo.com/datos y muestra los headers"

## Ejemplos

```text
"Quiero que hagas un método POST al sitio https://sitioweb/login con los datos Jose Lopez y que cambies mi user agent al de un iPhone"
"Descarga el archivo https://ejemplo.com/archivo.pdf y guárdalo como local.pdf"
"Haz una petición GET a https://api.ejemplo.com mostrando los headers de respuesta"
```