{
  lib,
  buildPythonPackage,
  fetchPypi,
  nix-update-script,
  setuptools,
  trame-client,
}:
buildPythonPackage (finalAttrs: {
  pname = "trame-components";
  version = "2.5.0";
  pyproject = true;

  src = fetchPypi {
    inherit (finalAttrs) pname version;
    hash = "sha256-33odOHuYxd1xaZc3gE9SiJV8o3DrGmC75A6Jofn2KxI=";
  };

  build-system = [ setuptools ];

  dependencies = [ trame-client ];

  postPatch = ''
    # Ensure PEP 420 namespace package layout (split across trame-* packages)
    find trame -type f -name '__init__.py' -delete
  '';

  pythonImportsCheck = [ "trame_components" ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Core components for trame widgets";
    homepage = "https://github.com/Kitware/trame-components";
    license = lib.licenses.asl20;
    maintainers = with lib.maintainers; [ cjshearer ];
  };
})
