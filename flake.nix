{
  description = "Conversor de texto largo a MP3 usando Edge TTS (AlvaroNeural)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        pythonEnv = pkgs.python3.withPackages (ps: [
          ps.edge-tts
          ps.pydub
        ]);

      in {
        # ── nix develop ───────────────────────────────────────────────────────
        devShells.default = pkgs.mkShell {
          name = "texto-a-mp3";

          packages = [
            pythonEnv
            pkgs.ffmpeg
          ];

          shellHook = ''
            echo ""
            echo "  🎙️  Entorno texto_a_mp3 listo"
            echo ""
            echo "  Uso:"
            echo "    python3 texto_a_mp3.py -i capitulo1.txt"
            echo "    python3 texto_a_mp3.py -i libro.txt -o ~/audios/ --voz es-ES-AlvaroNeural"
            echo "    python3 texto_a_mp3.py --help"
            echo ""
          '';
        };

        # ── nix run ───────────────────────────────────────────────────────────
        apps.default = {
          type = "app";
          program = toString (pkgs.writeShellScript "texto-a-mp3" ''
            exec ${pythonEnv}/bin/python3 ${./texto_a_mp3.py} "$@"
          '');
        };

      });
}
