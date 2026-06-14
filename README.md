# text-to-mp3

Convierte archivos de texto largos a MP3 usando **Edge TTS** — la voz neuronal de Microsoft Edge, gratuita y sin API key. Por defecto usa `es-ES-AlvaroNeural`, una voz masculina española de alta naturalidad.

## Características

- Voz neuronal natural (sin la robotización de gTTS)
- Divide textos largos en fragmentos inteligentemente (respeta párrafos y frases)
- Barra de progreso con ETA en tiempo real
- Reintentos automáticos ante fallos de red
- Control de velocidad (`--lento`, `--velocidad`)
- Pausa configurable entre párrafos
- Entorno reproducible con Nix Flakes

## Requisitos

**Con Nix (recomendado):**
```bash
nix develop      # activa el entorno con todas las dependencias
```

**Con pip:**
```bash
pip install edge-tts pydub
# también necesitas ffmpeg instalado en el sistema
```

## Uso

```bash
# Conversión básica
python3 texto_a_mp3.py -i capitulo1.txt

# Especificar carpeta de salida
python3 texto_a_mp3.py -i libro.txt -o ~/audios/

# Voz femenina española
python3 texto_a_mp3.py -i libro.txt --voz es-ES-ElviraNeural

# Voz más lenta
python3 texto_a_mp3.py -i libro.txt --lento

# Control fino de velocidad
python3 texto_a_mp3.py -i libro.txt --velocidad -30%

# Todas las opciones
python3 texto_a_mp3.py --help
```

## Opciones

| Opción | Descripción | Por defecto |
|---|---|---|
| `-i / --input` | Archivo de texto de entrada | *(obligatorio)* |
| `-o / --output` | Carpeta de salida | misma carpeta que `-i` |
| `--voz` | Nombre de voz Edge TTS | `es-ES-AlvaroNeural` |
| `--lento` | Velocidad reducida (−20 %) | desactivado |
| `--velocidad` | Ajuste de velocidad (`+10%`, `-30%`...) | `+0%` |
| `--pausa` | Silencio entre párrafos (ms) | `600` |
| `--max-chars` | Máx. caracteres por fragmento | `5000` |

## Voces disponibles

Algunas voces en español de calidad:

| Voz | Género | Variante |
|---|---|---|
| `es-ES-AlvaroNeural` | Hombre | España |
| `es-ES-ElviraNeural` | Mujer | España |
| `es-MX-JorgeNeural` | Hombre | México |
| `es-MX-DaliaNeural` | Mujer | México |
| `es-AR-TomasNeural` | Hombre | Argentina |
| `es-AR-ElenaNeural` | Mujer | Argentina |

Para ver todas las voces disponibles:
```bash
edge-tts --list-voices | grep es-
```

## Con Nix Flakes

```bash
# Entrar al entorno de desarrollo
nix develop

# O ejecutar directamente sin entrar al entorno
nix run . -- -i libro.txt -o ~/audios/
```
