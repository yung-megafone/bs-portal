# Optional offline dependency cache

The normal B.S. Portal Setup executable does **not** redistribute MySQL. During installation it downloads the pinned MySQL 8.4 LTS Windows ZIP directly from Oracle over HTTPS and the Microsoft Visual C++ x64 redistributable from Microsoft.

`build_release.ps1 -BundleDependencies` can place these files here before compiling the installer:

- `mysql-8.4.11-winx64.zip`
- `vc_redist.x64.exe`

When present, Inno Setup embeds them so installation can run offline. Review the redistribution terms/licenses of third-party components before publishing an installer built this way. The default GitHub-release build should normally omit them.
