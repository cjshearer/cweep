{
  inputs = {
    nixpkgs.url = "github:cjshearer/nixpkgs/feat/add-cadquery";

    zmk-nix.url = "github:lilyinstarlight/zmk-nix";
    zmk-nix.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    {
      self,
      nixpkgs,
      zmk-nix,
      ...
    }:
    let
      pythonModules = builtins.readDir ./pkgs/python-modules;
      builds = [
        {
          outputName = "cweep_left_central";
          shield = "cweep_left";
          enableZmkStudio = true;
        }
        {
          shield = "cweep_left";
          extraCmakeFlags = [ "-DCONFIG_ZMK_SPLIT_ROLE_CENTRAL=n" ];
        }
        { shield = "cweep_right"; }
        { shield = "settings_reset"; }
        {
          shield = "cweep_dongle";
          enableZmkStudio = true;
        }
      ];
      buildKeyboard =
        build: system:
        zmk-nix.legacyPackages.${system}.buildKeyboard (
          {
            src = nixpkgs.lib.sourceFilesBySuffices self [
              ".board"
              ".cmake"
              ".conf"
              ".defconfig"
              ".dts"
              ".dtsi"
              ".json"
              ".keymap"
              ".overlay"
              ".shield"
              ".yml"
              "_defconfig"
            ];
            board = "seeeduino_xiao_ble";
            zephyrDepsHash = "sha256-gsqiTDJLAihVyBXVFlgXwqRmlREcFJctKpl4tEWmVlY=";
            # enable USB logging for all builds
            # snippets = [ "zmk-usb-logging"];
            meta = {
              description = "ZMK firmware";
              license = nixpkgs.lib.licenses.mit;
              platforms = nixpkgs.lib.platforms.all;
            };
          }
          // build
        );
    in
    {
      devShells = nixpkgs.lib.genAttrs nixpkgs.lib.systems.flakeExposed (
        system:
        let
          pkgs = self.legacyPackages.${system};
        in
        {
          firmware = zmk-nix.devShells.${system}.default.override {
            extraPackages = with pkgs; [
              # used for debugging firmware and flashing
              tio
              usbutils
            ];
          };

          case = pkgs.mkShell {
            packages = [
              pkgs.bashInteractive
              pkgs.cq-editor
              pkgs.kicad
              pkgs.ruff
              (pkgs.python3.withPackages (
                p: with p; [
                  cadquery
                  kiutils
                  ocp-vscode
                  pyinstrument
                  watchdog
                ]
              ))
            ];
          };
        }
      );

      legacyPackages = nixpkgs.lib.genAttrs nixpkgs.lib.systems.flakeExposed (
        system:
        import nixpkgs {
          inherit system;
          overlays = [ self.overlays.packages ];
        }
      );

      overlays.packages = final: prev: {
        pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
          (
            python-final: python-prev:
            builtins.mapAttrs (
              name: _: (python-final.callPackage (./pkgs/python-modules + "/${name}") { })
            ) pythonModules
          )
        ];
      };

      packages = nixpkgs.lib.genAttrs nixpkgs.lib.systems.flakeExposed (
        system:
        let
          pkgs = import nixpkgs {
            inherit system;
            overlays = [ self.overlays.packages ];
          };
        in
        {
          firmware = pkgs.runCommandLocal "cweep-all-firmware" { } ''
            mkdir -p $out
            ${nixpkgs.lib.concatMapStringsSep "\n" (build: ''
              ln -s ${buildKeyboard build system}/zmk.uf2 $out/${build.outputName or build.shield}.uf2
            '') builds}
          '';

          flash = zmk-nix.packages.${system}.flash.override {
            firmware = self.packages.${system}.firmware // {
              parts = builtins.map (b: builtins.match "^[^_]+_(.+)$" (b.outputName or b.shield)) builds;
            };
          };
        }
      );
    };
}
