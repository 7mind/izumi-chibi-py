{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config = {};
        };

        python-env = pkgs.python313.withPackages (ps: with ps; [
        ]);

        env = pkgs.mkShell
          {
            buildInputs = with pkgs; [
              python-env
              python-env.pkgs.venvShellHook

              uv
              gitFull
            ];

            venvDir = ".venv";

            postShellHook = ''
              echo "${python-env}/${python-env.sitePackages}" > .venv/${python-env.sitePackages}/nix-packages.pth
              export LD_LIBRARY_PATH=${pkgs.lib.makeLibraryPath ( with pkgs; [stdenv.cc.cc.lib (pkgs.lib.getLib zlib) (pkgs.lib.getLib zstd)])}:$LD_LIBRARY_PATH

              export CPATH=${pkgs.glibc.dev}/include:$CPATH

              uv sync
            '';
          };
      in
      {
        devShells.default = env;
      });
}
