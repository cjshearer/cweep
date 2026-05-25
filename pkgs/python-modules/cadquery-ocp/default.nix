{
  lib,
  buildPythonPackage,
  fetchzip,
  isPy3k,
  python,

  # build
  cmake,
  mpi,
  pybind11,

  # dependencies
  fmt,
  fontconfig,
  freeglut,
  libGLU,
  opencascade-occt,
  rapidjson,
  vtk,
}:
buildPythonPackage (finalAttrs: {
  pname = "cadquery-ocp";
  version = "7.9.3.1.1";
  pyproject = false;
  disabled = !isPy3k;

  # While I would prefer to codegen this from source, the toolchain is truly hideous and I have
  # already spent several days trying to get it to work. For now, we use the pre-generated stubs.
  # See the following for efforts to get this upstreamed:
  # - https://github.com/NixOS/nixpkgs/pull/433247
  # - https://github.com/NixOS/nixpkgs/pull/486070
  # - https://github.com/NixOS/nixpkgs/pull/491280
  src = fetchzip {
    url = "https://github.com/CadQuery/OCP/releases/download/${finalAttrs.version}/OCP_src_stubs_Linux.zip";
    hash = "sha256-gfZFv/evrLHX5TSjAmc6ap45nCbAuNUGkb989BrfqhY=";
    stripRoot = true;
  };

  nativeBuildInputs = [
    cmake
    mpi
    pybind11
  ];

  buildInputs = [
    fmt
    fontconfig
    freeglut
    libGLU
    (opencascade-occt.override { withVtk = true; })
    rapidjson
    vtk
  ];

  installPhase = ''
    runHook preInstall

    install -D *.so -t $out/${python.sitePackages}

    runHook postInstall
  '';

  pythonImportsCheck = [ "OCP" ];

  meta = {
    description = "Python wrapper for OpenCASCADE generated using pywrap (CadQuery OCP)";
    homepage = "https://github.com/CadQuery/OCP";
    license = lib.licenses.asl20;
    platforms = lib.platforms.linux;
    maintainers = with lib.maintainers; [ cjshearer ];
  };
})
