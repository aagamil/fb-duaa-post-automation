# Daily Facebook image poster

Configured for https://www.facebook.com/profile.php?id=61574574579911.
The URL's ID is the configured target; authenticated verification is still required.

## What is ready

Python publisher, GitHub Actions workflow, persistent state, custom captions, offline tests,
and recovery protection. Includes 170 supplied JPEG images, ordered by original filename; image-manifest.json maps the names. No credentials are included. Facebook publication has not yet been tested.
Live posting is disabled until repository variable `FB_POSTING_ENABLED` is `true`.

Schedule: every day at 10:00 UTC (13:00 Riyadh). GitHub schedules are best-effort and can run late.
After image 170 it loops back to image 1. Change `total_images` to your actual image count.
Hosting costs depend on your GitHub plan and usage; free operation is not guaranteed.

## Deploy

1. The target repository is https://github.com/aagamil/fb-duaa-post-automation (public). Upload this folder's **contents** to its default branch,
   including the hidden `.github` folder. Do not upload the enclosing folder as a subfolder.
2. Put real JPEGs in `images`, named `image_1.jpg` through `image_170.jpg`.
   Optionally add UTF-8 `image_1.txt`, etc., for custom captions. Otherwise captions are `Daily Post #1`, etc.
3. In Settings > Secrets and variables > Actions, create the secret `FB_PAGE_ACCESS_TOKEN`.
   Never commit credentials. The Page ID is already configured in the script and workflow.
4. Add repository variable `FB_GRAPH_API_VERSION` using a currently supported version shown in your
   Meta app dashboard, in the form `vNN.0`. This is intentionally required rather than copying the
   old v19.0 value from the supplied example. Live Meta documentation was unavailable during implementation.
5. Ensure Actions has read/write repository contents permission and branch rules permit the bot's state commits.
6. Add repository variable `FB_POSTING_ENABLED` = `true`. This enables live scheduled and manual posting. Manual dry runs also work while disabled.
7. Under Actions > Daily Facebook Image Poster, run with `dry_run` checked to validate the next image.
   To publish a real first post, run again with `dry_run` unchecked. Check the Page and committed state.
8. To pause, set `FB_POSTING_ENABLED` = `false`.

## Meta credentials

Use a Meta developer app with the Pages API use case and a Page access token for this Page.
The account granting access must have permission to create Page content. The supplied setup calls for
`pages_show_list`, `pages_read_engagement`, and `pages_manage_posts`; verify requirements and access levels
in the current Meta dashboard. App review or additional business configuration may be required for your use case.
Use Meta's token tools and long-lived-token flow, then retrieve the Page token for this specific Page.
Do not treat a long-lived token as a guarantee of permanent access: check expiry and validity in Meta's debugger.
Store the Page token directly in GitHub Secrets, not in a browser URL, source file, or chat message.

Official references:
- https://developers.facebook.com/docs/pages-api/posts/
- https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/
- https://developers.facebook.com/tools/debug/accesstoken/
- https://developers.facebook.com/docs/graph-api/changelog/
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

## Validation and local use

Python 3.12 or later; no third-party packages needed.

```sh
python -m unittest discover -s tests -v
python auto_poster.py --dry-run
```

Dry runs validate the next local image and caption, without accessing Facebook or advancing state.
They do not verify permissions, token validity, or every future image. The workflow checks target identity
before attempting publication. API acceptance of your token and image still requires a real integration run.

## Failure recovery

The workflow commits a `pending` attempt **before** sending the photo. It advances the index only
after Meta returns a photo ID, then commits again. Workflow runs are serialized; HTTP POST is never retried.
If posting or the final push fails, subsequent runs stop on the durable pending record. This trades unattended
retries for duplicate protection. Exactly-once delivery across Facebook and GitHub cannot be guaranteed.

1. Pause the workflow using `FB_POSTING_ENABLED=false` and wait for any active run to finish.
2. Inspect the Page and the failing run's `posting-state` artifact. Confirm whether the pending photo was published.
3. If published, set `current_index` to the following index (wrap to 1 after `total_images`). If definitely not
   published, keep the current index. If uncertain, keep the workflow paused until reconciled.
4. Set `pending` to `null`, commit `state.json` to the default branch, and re-enable posting.

Do not run another copy of the script against the same Page/state concurrently. The workflow mutex only
covers this repository. A failed push before posting prevents publication; failed pushes after posting require
the reconciliation above. Artifacts contain state and photo IDs, never the token.

