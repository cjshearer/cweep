{
  lib,
  buildPythonPackage,
  fetchPypi,
  poetry-core,
}:
buildPythonPackage (finalAttrs: {
  pname = "runtype";
  version = "0.5.3";
  pyproject = true;

  src = fetchPypi {
    inherit (finalAttrs) pname version;
    hash = "sha256-zK7AXHT40hM0K5/CXjBFYNEUvE1y7BF2Oc0eevnF2x8=";
  };

  build-system = [ poetry-core ];

  pythonImportsCheck = [ "runtype" ];

  meta = {
    description = "Type dispatch and validation for run-time Python";
    homepage = "https://github.com/erezsh/runtype";
    license = lib.licenses.mit;
    maintainers = with lib.maintainers; [ cjshearer ];
  };
})
