#!/usr/bin/env python3
"""
texto_a_mp3.py — Conversor de texto largo a MP3 con Edge TTS (AlvaroNeural)

Uso:
    python3 texto_a_mp3.py -i capitulo1.txt
    python3 texto_a_mp3.py -i capitulo1.txt -o /ruta/salida/
    python3 texto_a_mp3.py -i libro.txt --voz es-ES-ElviraNeural
    python3 texto_a_mp3.py -i libro.txt --lento
    python3 texto_a_mp3.py --help

Argumentos:
    -i / --input       Archivo de texto de entrada (obligatorio)
    -o / --output      Carpeta de salida (opcional, por defecto: misma carpeta que -i)
    --voz              Voz de Edge TTS (por defecto: es-ES-AlvaroNeural)
    --lento            Velocidad reducida (-20%)
    --velocidad        Ajuste de velocidad: +10%, -20%... (por defecto: +0%)
    --pausa            Milisegundos de silencio entre párrafos (por defecto: 600)
    --max-chars        Máx. caracteres por fragmento (por defecto: 5000)

Requisitos (NixOS):
    nix-shell -p python3Packages.edge-tts python3Packages.pydub ffmpeg
"""

import asyncio
import os
import sys
import time
import tempfile
import argparse
import shutil


# ── Dependencias opcionales ────────────────────────────────────────────────────
def check_deps():
    missing = []
    try:
        import edge_tts  # noqa
    except ImportError:
        missing.append(("edge-tts", "python3Packages.edge-tts", "pip install edge-tts"))
    try:
        from pydub import AudioSegment  # noqa
    except ImportError:
        missing.append(("pydub", "python3Packages.pydub + ffmpeg", "pip install pydub"))
    if missing:
        print("❌ Faltan dependencias:\n")
        for name, nix, pip in missing:
            print(f"   {name}")
            print(f"     NixOS : nix-shell -p {nix}")
            print(f"     pip   : {pip}\n")
        sys.exit(1)

check_deps()

import edge_tts
from pydub import AudioSegment


# ── Barra de progreso ─────────────────────────────────────────────────────────
class Progreso:
    ANCHO = 35

    def __init__(self, total_frags):
        self.total   = total_frags
        self.inicio  = time.time()
        self._actual = 0

    def _eta(self, fraccion):
        if fraccion <= 0:
            return "--:--"
        elapsed   = time.time() - self.inicio
        remaining = elapsed / fraccion * (1 - fraccion)
        m, s = divmod(int(remaining), 60)
        return f"{m:02d}:{s:02d}"

    def _render(self, fraccion, label):
        relleno = int(fraccion * self.ANCHO)
        barra   = "█" * relleno + "░" * (self.ANCHO - relleno)
        pct     = int(fraccion * 100)
        eta     = self._eta(fraccion)
        elapsed = int(time.time() - self.inicio)
        m, s    = divmod(elapsed, 60)
        print(
            f"\r  [{barra}] {pct:3d}%  {label}  ⏱ {m:02d}:{s:02d}  ETA {eta}   ",
            end="", flush=True
        )

    def tick(self, n=1, label=""):
        self._actual += n
        frac = min(self._actual / self.total, 1.0)
        lbl  = label or f"frag {self._actual}/{self.total}"
        self._render(frac, lbl)

    def done(self, label="✅ Completo"):
        self._render(1.0, label)
        print()


# ── Lectura de texto ──────────────────────────────────────────────────────────
def leer_texto(path):
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"No se pudo leer '{path}' con ningún encoding conocido.")


# ── División en fragmentos ────────────────────────────────────────────────────
def dividir_en_fragmentos(texto, max_chars):
    """Divide respetando párrafos → frases → palabras. Nunca corta a mitad."""
    parrafos   = [p.strip() for p in texto.split("\n") if p.strip()]
    fragmentos = []
    actual     = ""

    def flush():
        nonlocal actual
        if actual:
            fragmentos.append(actual.strip())
            actual = ""

    def add(chunk, sep="\n"):
        nonlocal actual
        if len(actual) + len(chunk) + 1 <= max_chars:
            actual += (sep if actual else "") + chunk
        else:
            flush()
            actual = chunk

    for parrafo in parrafos:
        if len(parrafo) <= max_chars:
            add(parrafo)
        else:
            frases, inicio = [], 0
            for i, c in enumerate(parrafo):
                if c in ".!?" and i + 1 < len(parrafo) and parrafo[i + 1] == " ":
                    frases.append(parrafo[inicio:i + 1])
                    inicio = i + 2
            if inicio < len(parrafo):
                frases.append(parrafo[inicio:])

            for frase in frases:
                if len(frase) <= max_chars:
                    add(frase, " ")
                else:
                    for palabra in frase.split():
                        add(palabra, " ")

    flush()
    return fragmentos


# ── Generación de audio ───────────────────────────────────────────────────────
async def fragmento_a_audio(texto, voz, velocidad, ruta, intentos=3):
    for intento in range(1, intentos + 1):
        try:
            communicate = edge_tts.Communicate(texto, voz, rate=velocidad)
            await communicate.save(ruta)
            return
        except Exception as e:
            if intento == intentos:
                raise
            await asyncio.sleep(1.5 * intento)


def unir_audios(archivos, pausa_ms, salida, progreso):
    silencio  = AudioSegment.silent(duration=pausa_ms)
    resultado = AudioSegment.empty()
    n         = len(archivos)

    for i, archivo in enumerate(archivos, 1):
        resultado += AudioSegment.from_mp3(archivo)
        if i < n:
            resultado += silencio
        progreso.tick(1, f"uniendo {i}/{n}")

    resultado.export(salida, format="mp3", bitrate="128k")


# ── Argumentos CLI ────────────────────────────────────────────────────────────
def parse_args():
    p = argparse.ArgumentParser(
        description="Convierte texto largo a MP3 usando Edge TTS (AlvaroNeural).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    p.add_argument("-i", "--input",      required=True,
                   help="Archivo de texto de entrada (.txt)")
    p.add_argument("-o", "--output",     default=None,
                   help="Carpeta de salida (por defecto: misma carpeta que el input)")
    p.add_argument("--voz",              default="es-ES-AlvaroNeural",
                   help="Voz de Edge TTS (por defecto: es-ES-AlvaroNeural)")
    p.add_argument("--lento",            action="store_true",
                   help="Velocidad reducida (-20%%)")
    p.add_argument("--velocidad",        default=None,
                   help="Ajuste de velocidad: +10%%, -20%%... (por defecto: +0%%)")
    p.add_argument("--pausa",            type=int, default=600,
                   help="Silencio entre párrafos en ms (por defecto: 600)")
    p.add_argument("--max-chars",        type=int, default=5000,
                   help="Máx. caracteres por fragmento (por defecto: 5000)")
    return p.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    args = parse_args()

    # Velocidad final: --velocidad tiene prioridad; --lento es -20%
    if args.velocidad:
        velocidad = args.velocidad
    elif args.lento:
        velocidad = "-20%"
    else:
        velocidad = "+0%"

    # Validar entrada
    input_path = os.path.abspath(args.input)
    if not os.path.isfile(input_path):
        print(f"❌ No se encontró el archivo: {input_path}")
        sys.exit(1)

    # Carpeta de salida
    if args.output:
        output_dir = os.path.abspath(args.output)
        os.makedirs(output_dir, exist_ok=True)
    else:
        output_dir = os.path.dirname(input_path)

    base_name   = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.mp3")

    # ── Info inicial ──────────────────────────────────────────────────────────
    print()
    print(f"  📖  Input      : {input_path}")
    print(f"  🎵  Output     : {output_path}")
    print(f"  🗣️  Voz        : {args.voz}")
    print(f"  ⚡  Velocidad  : {velocidad}")
    print(f"  ⏸   Pausa      : {args.pausa} ms entre párrafos")
    print()

    # ── Leer y dividir ────────────────────────────────────────────────────────
    print("  📄 Leyendo texto...", end=" ", flush=True)
    texto = leer_texto(input_path)
    print(f"{len(texto):,} caracteres")

    print("  ✂️  Dividiendo en fragmentos...", end=" ", flush=True)
    fragmentos = dividir_en_fragmentos(texto, args.max_chars)
    total      = len(fragmentos)
    print(f"{total} fragmentos")
    print()

    # ── Generar audio por fragmentos ──────────────────────────────────────────
    prog_total = total * 2
    progreso   = Progreso(prog_total)

    archivos_tmp = []
    tmpdir       = tempfile.mkdtemp(prefix="tts_")
    errores      = 0

    print("  🎙️  Generando audio...")
    for i, fragmento in enumerate(fragmentos, 1):
        tmp_path = os.path.join(tmpdir, f"frag_{i:04d}.mp3")
        try:
            await fragmento_a_audio(fragmento, args.voz, velocidad, tmp_path)
            archivos_tmp.append(tmp_path)
        except Exception as e:
            errores += 1
            print(f"\n  ⚠️  Error en fragmento {i}: {e}")
        progreso.tick(1, f"fragmento {i}/{total}")

    if not archivos_tmp:
        print("\n❌ No se generó ningún fragmento de audio.")
        shutil.rmtree(tmpdir, ignore_errors=True)
        sys.exit(1)

    # ── Unir fragmentos ───────────────────────────────────────────────────────
    print("\n  🔗 Uniendo fragmentos...")
    unir_audios(archivos_tmp, args.pausa, output_path, progreso)
    progreso.done()

    shutil.rmtree(tmpdir, ignore_errors=True)

    # ── Resumen final ─────────────────────────────────────────────────────────
    size_mb      = os.path.getsize(output_path) / (1024 * 1024)
    audio        = AudioSegment.from_mp3(output_path)
    duracion_min = len(audio) / 1000 / 60

    print()
    print(f"  ✅  MP3 generado : {output_path}")
    print(f"  ⏱   Duración     : {int(duracion_min)}m {int((duracion_min % 1)*60)}s")
    print(f"  💾  Tamaño       : {size_mb:.1f} MB")
    if errores:
        print(f"  ⚠️   Fragmentos con error: {errores}/{total}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
