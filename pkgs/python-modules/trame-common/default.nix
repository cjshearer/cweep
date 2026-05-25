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
  version = "1.2.3";
  pyproject = true;

  src = fetchPypi {
    inherit (finalAttrs) version;
    pname = "trame_common";
    hash = "sha256-Eltg13VF1zUvuOq8D24OEgcKpq2jHpkoYvFqSfNLc60=";
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
