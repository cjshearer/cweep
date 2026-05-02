{
  lib,
  buildPythonPackage,
  fetchPypi,
  nix-update-script,
  setuptools,
  numpy,
  pillow,
  pygltflib,
  requests,
}:
buildPythonPackage (finalAttrs: {
  pname = "threejs-materials";
  version = "1.0.4";
  pyproject = true;

  src = fetchPypi {
    inherit (finalAttrs) version;
    pname = "threejs_materials";
    hash = "sha256-MVudu31bh9qjc1Mm91j6rPC5BspsSbc36R3/jRdo2/8=";
  };

  build-system = [ setuptools ];

  dependencies = [
    numpy
    pillow
    pygltflib
    requests
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
