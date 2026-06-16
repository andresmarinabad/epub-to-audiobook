{
  description = "epub-to-audiobook — conversor EPUB a audiolibro + stack web completo";

  inputs = {
    # nixos-24.11 trae Python 3.11, uv, y todas las dependencias modernas
    nixpkgs.url     = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

      in {
        # ── nix develop ───────────────────────────────────────────────────────
        devShells.default = pkgs.mkShell {
          name = "epub-to-audiobook";

          packages = [
            pkgs.python311          # Python 3.11 para el entorno virtual legacy
            pkgs.uv                 # Gestor de paquetes moderno (PEP 517/518)
            pkgs.ffmpeg             # Requerido para generar M4B
            pkgs.docker             # Para ejecutar el stack completo
            pkgs.docker-compose     # docker compose up
          ];

          shellHook = ''
            # ── Entorno virtual legacy (para epub2tts-edge CLI) ──────────────
            VENV_DIR="$HOME/.local/share/epub2tts-edge-env"
            if [ ! -d "$VENV_DIR" ]; then
              echo "Creando entorno virtual e instalando epub2tts-edge..."
              python3.11 -m venv "$VENV_DIR"
              "$VENV_DIR/bin/pip" install git+https://github.com/aedocw/epub2tts-edge edge-tts --quiet
            fi

            # ── Entorno uv para el backend del stack web ─────────────────────
            if [ -f "backend/pyproject.toml" ] && [ ! -d "backend/.venv" ]; then
              echo "Inicializando entorno uv del backend..."
              (cd backend && uv sync)
            fi

            # Datos NLTK
            export NLTK_DATA="$HOME/.nltk_data"
            python3.11 -c "
            import nltk, os
            nltk.download('punkt',     download_dir=os.environ['NLTK_DATA'], quiet=True)
            nltk.download('punkt_tab', download_dir=os.environ['NLTK_DATA'], quiet=True)
            " 2>/dev/null

            echo ""
            echo "  epub-to-audiobook dev shell"
            echo ""
            echo "  ── CLI clásico (epub2tts-edge) ─────────────────────────"
            echo "     source $VENV_DIR/bin/activate"
            echo "     epub2tts-edge libro.epub"
            echo "     epub2tts-edge libro.txt --speaker es-ES-AlvaroNeural"
            echo ""
            echo "  ── Stack web (Docker) ──────────────────────────────────"
            echo "     cp .env.example .env  # edita API_KEY"
            echo "     docker compose up --build"
            echo "     # Frontend → http://localhost:8080"
            echo ""
            echo "  ── Backend (desarrollo local) ──────────────────────────"
            echo "     cd backend"
            echo "     uv run uvicorn audiobook.infrastructure.api.main:app --reload"
            echo ""
          '';
        };
      });
}
