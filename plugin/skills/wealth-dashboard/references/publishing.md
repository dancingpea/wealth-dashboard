# Publishing and updating the dashboard

The exact sequence of calls. Work in a scratch folder: `wealth.json` (the state), `out/` (dataset files), `store/`
(documents). Tool names below are what this skill means; your tools may spell them differently (an Artifact tool with
`publish` / `read` / `delete` actions, and a store tool for the dashboard's database with `get` / `set` / `batch`).

## First publish

1. **Find the Dashboard type.** List the artifact types you can create from (or run a quickstart for a dashboard) and
   take the one named **Dashboard**. No such type, or no artifact tool at all (Claude Code in a terminal)? Use
   "Without the Dashboard type" below.
2. **Create the dashboard**: one publish with the type's url, `title` "Wealth dashboard" (or their name for it),
   `auto_open: "after_first_write"`, nothing else. Note the new artifact's url.
3. **Write the dataset files**: `W datasets wealth.json out/`.
4. **Upload each file** in `out/` (all 15, not `manifest.json`) as an asset of the new dashboard, one call per file
   (publish with `url` = the dashboard, `asset: true`, `file_path`). Each reply gives a url like `/_blob/<32 hex>`.
   Write them into `urls.json`: `{"snapshots": "/_blob/...", "attribution": "/_blob/...", ...}` keyed by file name
   without `.json`.
5. **Write the documents**: `W store wealth.json store/ --urls urls.json` (add `--live ibkr --connector "<name>"` for
   the live tab). It writes one JSON file per document and `store/batch.json`, a list of writes.
6. **One batch write** to the dashboard's store with those writes as they are (each entry has `op`, `collection`,
   `doc_id`, `file_path`). New documents need no version.
7. **Check**: read `data/users/me` document `check` in the dashboard's store. `checking`: read again (5 reads at
   most). No document at first: read once more; still none means the page isn't open anywhere yet, which is fine.
   `failed`: the page reports a fault; this page is shipped tested, so the usual cause is a dataset with a wrong shape
   or url: re-run `W validate`, rewrite the datasets, and say what happened. Do not render or screenshot the dashboard.
8. **Record and save**: `W published wealth.json --manifest out/manifest.json --urls urls.json --dashboard-url <url>`.
   Upload `wealth.json` as an asset (same call as step 4), then set the store document `pipeline/state` to
   `{"state": "/_blob/<id>", "updated": "<YYYY-MM-DD>", "skill": "wealth-dashboard 2.0.0"}`.
9. **Hand over** (one short paragraph): what each tab shows (Overview, Cash & spending, Goals, Investments), that the
   dashboard and its files are private to them until they share it (anyone they share it with sees everything), and
   that they change goals and settings by asking you.

## Monthly or any later update

1. **Get the state**: read the store document `pipeline/state`; download its `state` asset (artifact read with
   `path` = the 32 hex characters after `/_blob/`) into the scratch folder as `wealth.json`.
2. Make the changes with `W` commands (the monthly flow is in SKILL.md).
3. `W datasets wealth.json out/` prints which datasets changed. Upload only those (one call each) into `urls.json`.
4. Read the current versions of the documents you will rewrite (list the `datasets` collection of the store; each
   document shows its version) and write them as `versions.json`: `{"datasets/snapshots": 3, ...}`.
5. `W store wealth.json store/ --urls urls.json --versions versions.json --only-changed --only-datasets`, then one
   batch write with `store/batch.json`. A version conflict means someone changed a document since you read it: read
   it again and redo that entry.
6. `W published ...` as above; it prints the replaced file urls: delete those assets (artifact delete with the asset
   id as `path`). Upload the new `wealth.json`, update `pipeline/state` (with its version), delete the previous state
   asset.
7. Read `data/users/me` documents `check` and `runs`. A `runs` entry with status `failed` for one of these file
   datasets usually means a file url is wrong: compare it with `urls.json`.

## Upgrade the page

When a newer version of this skill changes the page, write only the page: an empty `urls.json` (`{}`), the version of
`files/index.html` (and `dash/meta`, `dash/params`) in `versions.json`, then
`W store wealth.json store/ --urls urls.json --versions versions.json --only-changed`, and one batch write. The data
is untouched. Keep `--live ibkr` if the dashboard has the live tab (`settings.live` in the state says so).

## Without the Dashboard type

- Claude Code or any session with files: `W standalone wealth.json wealth-dashboard.html` and keep both files in a
  folder the person picks (default `~/wealth-dashboard/`). Offer git or a synced cloud folder as a backup. Each update
  rewrites the page from the state.
- A session that can publish plain HTML artifacts but has no Dashboard type: `W standalone wealth.json page.html
  --target artifact` and publish it as a private artifact; republish the same file each month. Keep `wealth.json`
  as the person's file (send it to them and ask for it back next month) or in a connected folder.
- The standalone page has the same tabs and charts. It loads d3 from cdnjs and fonts from Google Fonts.

## Demo

To show what they'll get before setup: `W standalone SKILL_DIR/assets/demo-state.json demo.html --target artifact`
and publish it, titled "Wealth dashboard demo". Say every person and number in it is invented. Or point them to the
live demo linked in the skill's README.

## Limits worth knowing

- Each dataset file must stay under 8 MB and each store document under 256 KB. The page is about 160 KB; snapshots
  grow by roughly 3 KB per month for 15 accounts, so years of history fit easily.
- Uploading a text file is one call per file. A full first publish is 15 uploads; a monthly update is usually 6 to 9.
- Live IBKR queries run with each viewer's own connection: someone the dashboard is shared with sees their own IBKR
  account there, or a sign-in prompt.
