{
  lib,
  buildPythonPackage,
  fetchPypi,
  nix-update-script,

  # build-system
  setuptools,

  # dependencies
  trame-common,
}:
buildPythonPackage (finalAttrs: {
  pname = "trame-client";
  version = "3.11.4";
  pyproject = true;

  src = fetchPypi {
    inherit (finalAttrs) version;
    pname = "trame_client";
    hash = "sha256-RvjXTlz9jc8kCgNXp3uoBHrX6Por7OXKY+t6aNJF9+Q=";
  };

  build-system = [ setuptools ];

  dependencies = [ trame-common ];

  pythonImportsCheck = [ "trame_client" ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Internal client of trame";
    homepage = "https://github.com/Kitware/trame-client";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ cjshearer ];
  };
})
