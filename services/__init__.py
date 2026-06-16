# Stateless PDF services (Phase 4). Heavy dependencies (pypdf, reportlab,
# pyhanko) are imported lazily inside the functions, so importing this package
# never fails at module load even if a dependency is absent.
