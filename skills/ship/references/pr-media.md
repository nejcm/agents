# PR media

How to attach live-verify screenshots or recordings to the PR. GitHub has no API for PR
attachments, so media goes on a `verify-media` orphan branch that is never merged and that
the comment links to.

## When

Only when the change can be seen: UI, rendered output, visual diffs. Backend, CLI, refactor
and config changes get the text comment alone.

- Before and after PNGs of the same view. The before shot comes from the default branch.
- A GIF only when the change involves motion or a multi-step interaction. Do not post mp4 or
  webm, because GitHub shows a player only for files uploaded in the browser. Convert:
  `ffmpeg -i in.webm -vf "fps=10,scale=960:-1" out.gif`. Keep each file under 5 MB.
- At most 6 files per PR.

Look at every frame before you push it. Never upload media that shows tokens, keys, real user
data or internal URLs, and use fixture data. On a public repo the branch is public.

## Upload

This pushes one commit to `verify-media` without touching the working tree or index. Files go
under `pr-<n>/`. Each run adds or replaces files and never removes them.

```bash
n=<pr number>; files=(<paths to png/gif>)
git fetch -q origin verify-media 2>/dev/null || true
parent=$(git rev-parse -q --verify origin/verify-media || true)
export GIT_INDEX_FILE=$(mktemp -u)
[ -n "$parent" ] && git read-tree "$parent"
for f in "${files[@]}"; do
  git update-index --add --cacheinfo "100644,$(git hash-object -w "$f"),pr-$n/$(basename "$f")"
done
sha=$(git commit-tree "$(git write-tree)" ${parent:+-p "$parent"} -m "chore: verify media for #$n")
unset GIT_INDEX_FILE
git push -q origin "$sha:refs/heads/verify-media"
echo "$sha"
```

If the push is rejected because someone else pushed to the branch, run the block again.

## Link

Pin links to the commit SHA printed above, so later uploads never change what an older
comment shows:

```markdown
| Before | After |
|---|---|
| ![before](https://github.com/<owner>/<repo>/blob/<sha>/pr-<n>/before.png?raw=true) | ![after](https://github.com/<owner>/<repo>/blob/<sha>/pr-<n>/after.png?raw=true) |
```

Put the media in the live-verify comment, below the text. When verify runs again, upload
again and edit that comment so it uses the new SHA.
