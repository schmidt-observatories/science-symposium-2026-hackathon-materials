# 2026-10-07: notebooks_fixed/ and the S3 bucket

## What was done

- `notebooks_fixed/tutorial_survey_data.ipynb`, `notebooks_fixed/tutorial_depth_calculation.ipynb`: copies of the
  `notebooks/` tutorials with three changes each. The hard-coded `STORE = "~/argussim_runs/..."` is replaced by a
  setup cell that uses the NFS mount `~/s3/argus/sim/argsim_5yr_beta_rho_uniform_v5.4` when its `index.json`
  exists and otherwise the S3 URI with the default AWS credential chain; `SurveyRun` gets `storage_options` only
  on the S3 path (the local path raises if any are passed); the redback import in Step 15 fails with an install
  hint instead of a bare `ImportError`. Outputs of unchanged cells are kept from the originals. Trailing empty
  cells dropped.
- `notebooks_fixed/tutorial_s3_access.ipynb` (new): boto3 listing / head / streamed read of the DSA mock FITS,
  256 px cutout, the same file through the `~/s3` mount, pyarrow listing of `argus/sim/`, and opening the Argus
  store from S3 with a GET-request count.
- Builder script (regenerate instead of editing JSON): scratchpad `build_fixed.py`; mock test `test_s3_nb.py`.
- No file outside `notebooks_fixed/` and `report/` was changed.

## Lessons

1. **The bucket is private; anonymous access is denied.** `curl` gives 403 (so the bucket exists), and both
   `pyarrow.fs.S3FileSystem(anonymous=True)` and boto3 with `UNSIGNED` fail with AccessDenied. Notebooks must rely on
   the default credential chain (hub role, `~/.aws`, env vars). This laptop has no AWS credentials and no `aws` CLI,
   so the real-data cells could not be executed here.
2. **What was verified, and how.** The S3 tutorial was executed end to end against a `moto` ThreadedMotoServer
   holding a synthetic 4-D FITS at the sample key and a fake mount directory: every cell passes except the
   `SurveyRun` open, which fails only because the mock has no visit store. boto3 picks up `AWS_ENDPOINT_URL` from
   the environment; pyarrow needs `endpoint_override`, `scheme="http"` and explicit keys. The two patched tutorials
   were validated with `nbformat.validate`, every code cell parsed, and the new STORE cell executed (falls back to
   the S3 URI here). **They have not been run against the real v5.4 store**; do one full run on the hub.
3. **pyarrow against moto is slow.** The `FileSelector` listing took about 45 s on the mock (region resolution
   retries). Irrelevant on real S3, but do not mistake it for a hang in tests.
4. **`nbformat` patching gotcha.** Setting `outputs`/`execution_count` on a markdown cell makes the notebook fail
   validation; only touch those on code cells.
5. **No visit-store fixture exists offline.** `tests/test_lightcurve_store.py` needs `ARGUS_LC_RUN`, a real run
   directory, so there is no small synthetic store to execute the tutorials against. Building one would be the way
   to make the tutorials CI-testable.
6. **redback is not in the environment** (and not a declared dependency), so Step 15 of the survey tutorial needs
   `%pip install redback` plus a kernel restart; the fixed notebook now says so.

## Addendum (same day): notebooks_jupyterhub/

- New folder `notebooks_jupyterhub/` with the same three notebooks, built by the same builder in `hub` mode. The
  store cell is now a fixed path with no fallback:
  `~/s3/schmidt-observatory-system/argus/sim/argsim_5yr_beta_rho_uniform_v5.4/store`, plus an `assert` on
  `index.json` that says "is the bucket mounted?". `SurveyRun(STORE)` with no storage options. The S3 tutorial
  opens the store from the mount too and uses `MOUNT = "~/s3/schmidt-observatory-system"`.
- `notebooks_fixed/` paths corrected to match: the mount root includes the bucket name, and the store is in a
  `store/` subfolder (the earlier guess `~/s3/argus/...` and the S3 URI without `/store/` were wrong).

### Lessons

7. **The hub mount includes the bucket name and the store has a `store/` suffix.** `~/s3/<bucket>/<key>`, so
   `MOUNT = "~/s3"` with a bare key would miss. Verify the mount layout with `ls` before hard-coding paths.
8. **Read-only mount is safe for `SurveyRun`.** `argus_sim.lightcurve` only reads (no cache or temp files in the
   store directory), so a root-owned, read-only NFS mount works as a local store path.
9. **Verified here**: both hub store cells run against a fake `$HOME/s3/...` layout and fail with the clear assert
   without it; the hub S3 tutorial runs end to end against the moto mock plus a fake mount, with only the real
   `SurveyRun` open failing for lack of a store. **Not verified**: a full run against the real v5.4 store, and
   whether `argus_sim` is installed in the hub kernel. Run on the hub once to confirm.
