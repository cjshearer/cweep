{
  lib,
  buildPythonPackage,
  fetchPypi,
  nix-update-script,

  # build-system
  hatchling,

  # dependencies
  more-itertools,
  trame-common,
  wslink,
}:
buildPythonPackage (finalAttrs: {
  pname = "trame-server";
  version = "3.12.4";
  pyproject = true;

  src = fetchPypi {
    inherit (finalAttrs) version;
    pname = "trame_server";
    hash = "sha256-laDScy/VLrKRLKBYdOuobZHo1+p+SgqIge8/U5KTZF8=";
  };

  build-system = [ hatchling ];

  dependencies = [
    more-itertools
    trame-common
    wslink
  ];

  pythonRelaxDeps = [ "wslink" ];

  pythonImportsCheck = [ "trame_server" ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Internal server side implementation of trame";
    homepage = "https://github.com/Kitware/trame-server";
    license = lib.licenses.asl20;
    maintainers = with lib.maintainers; [ cjshearer ];
  };
})
