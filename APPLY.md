# BAM v0.1 Overlay

1. Stop `runserver`.
2. Back up or commit your current Portal checkout.
3. Extract this ZIP into the repository root, preserving paths and allowing replacement of existing source files.
4. Activate the existing `.venv`.
5. Run from the repository root:

```powershell
.\scripts\enable_bam.ps1
```

6. If successful:

```powershell
python portal/manage.py runserver
```

7. Open `http://localhost:8000/bam/`.

The setup script intentionally runs `makemigrations bam` locally because this overlay was generated without access to your installed Django runtime. Review/commit the generated migration after it succeeds.

Your `.env`, MySQL database, existing users, and `.venv` are not included or replaced by this overlay.
