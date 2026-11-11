# Git workflow

- **No commit or push until the user has reviewed the finished work.** Leave changes
  uncommitted, say they're ready to review, and commit when the user says so. Approving
  a plan that mentions a commit is not that go-ahead.
- Steps that need the final commit hash wait for review too: the PCB board-ID stamp
  and the final `hardware/kicad/tools/export_fab.py` run. Uncommitted renders for
  review are fine.
- **Never push to `main`** and never force-push it. Commit on a new, descriptively
  named branch (e.g. `ina239-spi-migration`), push that, and tell the user the branch
  name. The user merges into `main` themselves.
- Only push when asked.
- Check `git status` before starting. Don't sweep unrelated changes the user has in
  progress into your commit.
