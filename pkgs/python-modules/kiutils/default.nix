{
  lib,
  buildPythonPackage,
  fetchPypi,
}:
buildPythonPackage (finalAttrs: {
  pname = "kiutils";
  version = "1.4.8";
  format = "setuptools";

  src = fetchPypi {
    inherit (finalAttrs) pname version;
    hash = "sha256-GMWAMoPlec/odylV53AlSNcTng/GMNqlee1rK3Z9uEY=";
  };

  patches = [ ./kicad10-pad-net-syntax.patch ];

  pythonImportsCheck = [ "kiutils" ];

  meta = {
    description = "Simple and SCM-friendly KiCad file parser for KiCad 6.0 and up";
    homepage = "https://github.com/mvnmgrx/kiutils";
    license = lib.licenses.gpl3Plus;
    maintainers = with lib.maintainers; [ cjshearer ];
  };
})
