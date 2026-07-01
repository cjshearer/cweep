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

  # The wheel ships zero-byte __init__.py namespace markers under trame/ so that setuptools includes
  # the trame/widgets/ directory (needed for cadquery which imports `trame.widgets.trame`).
  # Deleting them postPatch would cause setuptools to omit the entire trame/ tree; instead clean
  # them up postInstall to avoid buildEnv conflicts with other trame-* packages that contribute to
  # the same PEP 420 namespace.
  postInstall = ''
    rm -rf $out/lib/*/site-packages/trame/__init__.py
    rm -rf $out/lib/*/site-packages/trame/modules
    find $out/lib/*/site-packages/trame -name '__init__.py' -delete
    find $out/lib/*/site-packages/trame -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
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
