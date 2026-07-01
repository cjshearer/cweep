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
  version = "3.4.1";
  pyproject = true;

  src = fetchPypi {
    inherit (finalAttrs) version;
    pname = "ocp_tessellate";
    hash = "sha256-Y/84fWW3qNmgpUloq6dCC/2x029ii2KImpgcVVjxG5A=";
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
