{
  lib,
  buildPythonPackage,
  fetchPypi,
  nix-update-script,
  setuptools,
  numpy,
  pillow,
  platformdirs,
  pygltflib,
  requests,
}:
buildPythonPackage (finalAttrs: {
  pname = "threejs-materials";
  version = "1.2.1";
  pyproject = true;

  src = fetchPypi {
    inherit (finalAttrs) version;
    pname = "threejs_materials";
    hash = "sha256-FnnSSpVQRuL0DMMH7wY6TWPtEruu9VXODr3NKtLGBhc=";
  };

  build-system = [ setuptools ];

  dependencies = [
    numpy
    pillow
    platformdirs
    pygltflib
    requests
  ];

  pythonRelaxDeps = [
    "pillow"
    "platformdirs"
  ];

  pythonImportsCheck = [ "threejs_materials" ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Convert PBR materials into Three.js MeshPhysicalMaterial JSON";
    homepage = "https://github.com/bernhard-42/threejs-materials";
    license = lib.licenses.asl20;
    maintainers = with lib.maintainers; [ cjshearer ];
  };
})
