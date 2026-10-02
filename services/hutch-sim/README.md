# hutch-sim

`hutch-sim` is a development-only HTTP service for the repository's synthetic
HUTCH estate. It is not a real HUTCH system and does not describe confirmed
HUTCH APIs.

From the repository root, after `make setup`:

```shell
PYTHONPATH=backend/src .venv/bin/uvicorn main:app \
  --app-dir services/hutch-sim/src --host 127.0.0.1 --port 8090
```

The `lite` profile keeps the same adapters in process. The `full` profile uses
the HTTP drivers and defaults to `http://localhost:8090`.
