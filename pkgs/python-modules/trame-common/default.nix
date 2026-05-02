{
  lib,
  buildPythonPackage,
  fetchPypi,
  nix-update-script,

  # build
  hatchling,
}:
buildPythonPackage (finalAttrs: {
  pname = "trame-common";
  version = "1.1.3";
  pyproject = true;

  src = fetchPypi {
    inherit (finalAttrs) version;
    pname = "trame_common";
    hash = "sha256-JaOJSCO+v1CdO60rDFRfvu6e7V1jINlPeB7FlcGNgGg=";
  };

  build-system = [ hatchling ];

  pythonImportsCheck = [ "trame_common" ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Dependency less classes and functions for trame";
    homepage = "https://github.com/Kitware/trame-common";
    license = lib.licenses.asl20;
    maintainers = with lib.maintainers; [ cjshearer ];
  };
})
