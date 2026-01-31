{
  inputs = {
    nixos-config.url = "github:cjshearer/nixos-config";
    nixpkgs.follows = "nixos-config/nixpkgs";

    zmk-nix = {
      url = "github:lilyinstarlight/zmk-nix";
      inputs.nixpkgs.follows = "nixos-config/nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      zmk-nix,
      ...
    }:
    let
      forAllSystems = nixpkgs.lib.genAttrs (nixpkgs.lib.attrNames zmk-nix.packages);
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
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          case =
            pkgs.runCommandLocal "case"
              {
                src =
                  with pkgs.lib.fileset;
                  (toSource {
                    root = ./.;
                    fileset = unions [
                      ./cweep.kicad_pcb
                      ./cweep.scad
                      ./generate-case.sh
                    ];
                  });
                nativeBuildInputs = with pkgs; [
                  entr
                  kicad-unstable-small
                  openscad-unstable
                  self.packages.${system}.dxf-fix
                ];
              }
              ''
                export HOME=$(pwd)
                ln -s $src/* .

                ${pkgs.bash}/bin/sh generate-case.sh

                mkdir -p $out
                mv case/cweep_plate_*.dxf $out/
              '';

          # The bezier curves in either the KiCad's DXF exporter or OpenSCAD's DXF importer result
          # in unclosed shapes, so we use this tool to snap endpoints together.
          dxf-fix = pkgs.stdenvNoCC.mkDerivation {
            name = "dxf-fix";
            version = "unstable";

            src = pkgs.fetchFromGitHub {
              owner = "wenzel-lab";
              repo = "dxf-fix";
              rev = "eba92432cce4930adc8ab823e1d4f2599a796d7a";
              hash = "sha256-svfQ/+oSB8C7NRh0cCf+ZTQ5yJb3xL72ymOn+T7buuo=";
            };

            postPatch = ''
              echo "#!${
                pkgs.python3.withPackages (
                  p: with p; [
                    ezdxf
                    matplotlib
                    scipy
                  ]
                )
              }/bin/python3" | cat - $src/fix_dxf.py > fix_dxf.py
            '';

            installPhase = ''
              install -Dm755 fix_dxf.py $out/bin/dxf-fix
            '';
          };

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

      devShells = forAllSystems (system: {
        default = zmk-nix.devShells.${system}.default.override {
          extraPackages = with nixpkgs.legacyPackages.${system}; [
            # used for ./generate-case.sh
            entr
            kicad
            openscad-unstable
            self.packages.${system}.dxf-fix
            # used for debugging firmware and flashing
            tio
            usbutils
          ];
        };
      });
    };
}
