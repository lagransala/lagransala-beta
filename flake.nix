{
  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    pyproject-nix = {
      url = "github:nix-community/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs@{ flake-parts, pyproject-nix, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems =
        [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" "x86_64-darwin" ];
      perSystem = { config, pkgs, ... }:
        let
          python = pkgs.python3.override {
            packageOverrides =
              pkgs.lib.composeManyExtensions [ (import ./overlay.nix) ];
          };
          project =
            pyproject-nix.lib.project.loadPyproject { projectRoot = ./.; };

        in {
          packages = {
            default = config.packages.lagransala;
            lagransala = python.pkgs.buildPythonPackage
              (project.renderers.buildPythonPackage { inherit python; });
            inherit (python.pkgs) crawl4ai python-redis-cache;
          };

          devShells.default = config.devShells.lagransala-dev;

          devShells.lagransala-dev = let
            arg = project.renderers.withPackages {
              inherit python;
              extras = [ "test" "dev" ];
            };
            pythonEnv = python.withPackages arg;
          in pkgs.mkShell {
            packages = [
              pythonEnv
              # config.packages.lagransala 
            ];
          };
        };
    };
}
