# Contributing

Bug reports and pull requests are welcome.

## Reporting a problem

Open an issue with the input you used (or a small file that shows the
problem), the command or the request you gave Claude, and what came out.

## Making a change

1. Fork the repository and create a branch.
2. Install the dependencies: `pip install -r requirements.txt`
3. Make the change. The skill lives in `skills/word-file-to-handwritten/`:
   `SKILL.md` is what Claude reads, `scripts/handwrite.py` is the renderer.
4. Run the smoke test and look at the output:
   ```bash
   python skills/word-file-to-handwritten/scripts/handwrite.py examples/sample.md -o /tmp/sample.pdf
   ```
5. Add a line to `CHANGELOG.md` under a new version heading.
6. Open a pull request that says what changed and why.

Keep `SKILL.md` and the script in step: if an option is added or renamed in
the script, update the table in `SKILL.md` and in `README.md`.

## Releasing

Publish a release on GitHub with a tag such as `v1.1.0`. The workflow packages
the skill folder as `word-file-to-handwritten.skill` and attaches it to that
release.

## Fonts

Only add fonts whose licence allows redistribution, and include the licence
text next to the font file. Do not add fonts made from a real person's
handwriting without that person's permission.
