# Version Badge and APP_VERSION Tracking Design

## Goal

Show a dynamic build/version badge in the app header while keeping `APP_VERSION` meaningful for user-visible releases instead of changing it on every deploy.

## Approved Direction

- Keep the top-right badge dynamic.
- Use `APP_VERSION` only for user-visible releases.
- Fall back to Railway branch/SHA metadata automatically when `APP_VERSION` is not set.

## Badge Format

The header badge shows the available parts in this order:

`<version-or-branch> | <short-sha> | <date>`

Examples:

- `v1.2.0 | d6a4d55 | 2026-07-21`
- `master | d6a4d55`

## Metadata Resolution

### Preferred values

1. `APP_VERSION`
2. `APP_GIT_SHA`
3. `APP_BUILD_DATE`

### Fallback values

1. `RAILWAY_GIT_BRANCH`
2. `RAILWAY_GIT_COMMIT_SHA` shortened to 7 characters
3. No generated date fallback; the date slot stays empty unless `APP_BUILD_DATE` is explicitly set

## Versioning Rule

`APP_VERSION` is the managed product release number and changes only when users would notice the difference.

### Patch bump

Increase patch version for:

- bug fixes visible to users
- small UI/UX improvements
- changes to notifications or messages users see

### Minor bump

Increase minor version for:

- new features
- new filters or controls
- new workflows
- meaningful behavior changes in scraping, results, or authentication flows

### No version bump

Do not change `APP_VERSION` for:

- internal refactors
- tests only
- docs only
- deployment-only or infrastructure-only changes

## Version Control Guidance Table

| Change type | Bump rule | Example |
| --- | --- | --- |
| User-facing bug fix | Patch | Fixing a broken email notification or correcting a wrong result shown in the UI |
| Small visible UI improvement | Patch | Adjusting labels, badge placement, progress text, or download messaging |
| New user-facing feature | Minor | Adding a new filter, a new scrape mode, or a new results capability |
| User-visible behavior change | Minor | Changing how results are grouped, how auth access works, or how scraping options behave |
| Internal refactor only | No bump | Extracting helpers, reorganizing modules, or cleaning up code without changing behavior |
| Tests or docs only | No bump | Adding unit tests or updating README/Copilot instructions |
| Deployment/config only | No bump | Railway variable changes, Docker tweaks, or secret rotation with no UI/feature impact |

### Decision shortcut

Use this quick rule before release:

- If a user would notice the change in normal usage, bump the version.
- If the user would not notice it without reading code or logs, do not bump the version.

### Semantic version examples

| Current version | Release type | Next version | When to use it |
| --- | --- | --- | --- |
| `1.2.0` | Patch | `1.2.1` | Visible bug fix or small user-facing polish with no new feature |
| `1.2.0` | Minor | `1.3.0` | New feature or noticeable behavior change that stays backward-compatible |
| `1.4.0` | Major | `2.0.0` | Breaking change, major redesign, or a release that changes user expectations materially |

Use standard semantic versioning with three parts: `major.minor.patch`. Avoid formats like `2.00`.

## Operational Workflow

1. Deploy code normally.
2. If the release is user-visible, update `APP_VERSION`.
3. If the release is not user-visible, leave `APP_VERSION` alone.
4. If `APP_VERSION` is unset, the app automatically shows Railway branch/SHA metadata instead.
5. Only set `APP_BUILD_DATE` when you have an explicit immutable build date you want displayed.

## UI Behavior

- Title stays left-aligned.
- Build badge stays top-right.
- If `APP_VERSION` is missing, branch name fills the first slot automatically.
- If `APP_BUILD_DATE` is missing, the date segment is omitted instead of fabricating a current date.
- Missing parts are omitted rather than shown as blank placeholders.

## Testing

- Unit test metadata resolution order.
- Unit test formatting output with full metadata.
- Unit test formatting output with missing values.

## Scope

This design covers the header version badge and version tracking rules only. It does not introduce automatic semantic version bumping from commit messages or tags.
