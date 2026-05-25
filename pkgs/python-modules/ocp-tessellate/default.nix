{
  lib,
  buildPythonPackage,
  fetchPypi,
  nix-update-script,

  # build-system
  setuptools,

  # dependencies
  cachetools,
  cadquery,
  cadquery-ocp,
  imagesize,
  numpy,
  webcolors,
}:
buildPythonPackage (finalAttrs: {
  pname = "ocp-tessellate";
  version = "3.3.0";
  pyproject = true;

  src = fetchPypi {
    inherit (finalAttrs) version;
    pname = "ocp_tessellate";
    hash = "sha256-83AQMo9fqCHW0wEGENcN0gXrJgIK5CLM1EBajhrKjq0=";
  };

  build-system = [ setuptools ];

  dependencies = [
    cachetools
    cadquery
    cadquery-ocp
    imagesize
    numpy
    webcolors
  ];

  pythonRelaxDeps = [
    "webcolors"
    "cachetools"
  ];

  pythonImportsCheck = [ "ocp_tessellate" ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Tessellate OCP (https://github.com/cadquery/OCP) objects to use with threejs";
    homepage = "https://github.com/bernhard-42/ocp-tessellate";
    license = lib.licenses.asl20;
    maintainers = with lib.maintainers; [ cjshearer ];
  };
})
