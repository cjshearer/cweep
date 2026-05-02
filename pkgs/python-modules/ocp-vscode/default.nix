{
  lib,
  buildPythonPackage,
  fetchPypi,
  nix-update-script,
  
  # build-system
  setuptools,

  # dependencies
  click,
  flask-sock,
  flask,
  ipykernel,
  ocp-tessellate,
  orjson,
  pillow,
  pygltflib,
  pyperclip,
  pyaml,
  questionary,
  requests,
  threejs-materials,
  websockets,
}:
buildPythonPackage (finalAttrs: {
  pname = "ocp-vscode";
  version = "3.3.4";
  pyproject = true;

  src = fetchPypi {
    inherit (finalAttrs) version;
    pname = "ocp_vscode";
    hash = "sha256-tnimMG8VGtB6B/M3K1Tj0dNARwHyKxuglHZ8xzwNLXQ=";
  };

  build-system = [ setuptools ];

  dependencies = [
    click
    flask
    flask-sock
    ipykernel
    ocp-tessellate
    orjson
    pillow
    pygltflib
    pyperclip
    pyaml
    questionary
    requests
    threejs-materials
    websockets
  ];

  pythonRelaxDeps = [
    "pyperclip"
    "websockets"
  ];

  # pythonRemoveDeps = [ "pyaml" ];

  pythonImportsCheck = [ "ocp_vscode" ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "OCP CAD Viewer for VSCode";
    homepage = "https://github.com/bernhard-42/vscode-ocp-cad-viewer";
    license = lib.licenses.asl20;
    maintainers = with lib.maintainers; [ cjshearer ];
  };
})
