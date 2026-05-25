{
  lib,
  buildPythonPackage,
  fetchFromGitHub,
  isPy3k,
  nix-update-script,

  # build-system
  setuptools,

  # dependencies
  cadquery-ocp,
  casadi,
  ezdxf,
  ipython,
  multimethod,
  nlopt,
  nptyping,
  numba,
  pyparsing,
  runtype,
  scipy,
  trame-components,
  trame-vtk,
  trame-vuetify,
  trame,
  typing-extensions,
  vtk,

  # tests
  docutils,
  pytest-xdist,
  pytestCheckHook,
}:
buildPythonPackage (finalAttrs: {
  pname = "cadquery";
  version = "8c17892ed68d4e5a19fe10fd0c0eb2a23f63db5a";
  pyproject = true;
  disabled = !isPy3k;

  src = fetchFromGitHub {
    owner = "CadQuery";
    repo = "cadquery";
    rev = "${finalAttrs.version}";
    hash = "sha256-+FoXWscnsY/x5yQGnRDTl6CDWH+Q/y9MFOctVncCH9E=";
  };

  build-system = [ setuptools ];

  propagatedBuildInputs = [
    cadquery-ocp
    casadi
    ezdxf
    ipython
    multimethod
    nlopt
    nptyping
    numba
    pyparsing
    runtype
    scipy
    trame
    trame-components
    trame-vtk
    trame-vuetify
    typing-extensions
    vtk
  ];

  nativeCheckInputs = [
    docutils
    pytest-xdist
    pytestCheckHook
  ];

  pythonRelaxDeps = [ "multimethod" ];
  pythonRemoveDeps = [
    "cadquery-ocp"
    "casadi"
  ];

  # This fails upstream: https://github.com/CadQuery/OCP/issues/192
  # OCP.Standard.Standard_Failure: BRepFill : The continuity is not G0 G1 or G2
  disabledTests = [ "test_cap" ];

  pythonImportsCheck = [ "cadquery" ];

  passthru.updateScript = nix-update-script { };

  meta = {
    description = "Parametric scripting language for creating and traversing CAD models";
    homepage = "https://github.com/CadQuery/cadquery";
    license = lib.licenses.asl20;
    maintainers = with lib.maintainers; [ cjshearer ];
  };
})
