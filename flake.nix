{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

    zmk-nix = {
      url = "github:lilyinstarlight/zmk-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      zmk-nix,
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
      packages = forAllSystems (system: rec {
        firmware = nixpkgs.legacyPackages.${system}.runCommand "cweep-all-firmware" { } ''
          mkdir -p $out
          ${nixpkgs.lib.concatMapStringsSep "\n" (build: ''
            ln -s ${buildKeyboard build system}/zmk.uf2 $out/${build.outputName or build.shield}.uf2
          '') builds}
        '';

        flash = zmk-nix.packages.${system}.flash.override {
          firmware = firmware // {
            parts = builtins.map (b: builtins.match "^[^_]+_(.+)$" (b.outputName or b.shield)) builds;
          };
        };
      });

      devShells = forAllSystems (system: {
        default = zmk-nix.devShells.${system}.default.override {
          extraPackages = with nixpkgs.legacyPackages.${system}; [
            usbutils
            tio
          ];
        };
      });
    };
}
