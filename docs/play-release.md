# Google Play release checklist

What David does by hand to get TankCommand onto Google Play. Everything in the repo (Android
project, signing from secrets, the build workflow, the purchase, the bug-report endpoint and
the privacy policy) is already in place. The store name is not final; the app id is
`com.davidbalasa.tankcommand` and cannot change after the first upload.

## 1. Upload key and GitHub secrets

Play App Signing keeps the real app signing key at Google. You sign uploads with an
**upload key** that you create once and keep safe (losing it means asking Google for a reset).

1. Create the upload keystore on your own computer, not in the repo:
   `keytool -genkeypair -v -keystore tankcommand-upload.jks -alias upload -keyalg RSA -keysize 2048 -validity 10000`
2. Back it up (password manager plus an offline copy).
3. Add four repository secrets (GitHub → Settings → Secrets and variables → Actions, or `gh secret set`):
   - [ ] `ANDROID_KEYSTORE_BASE64`: output of `base64 -w0 tankcommand-upload.jks` (macOS: `base64 -i tankcommand-upload.jks`)
   - [ ] `ANDROID_KEYSTORE_PASSWORD`: the keystore password
   - [ ] `ANDROID_KEY_ALIAS`: `upload` (or the alias you chose)
   - [ ] `ANDROID_KEY_PASSWORD`: the key password (same as the keystore password unless you set another)

Without all four, the workflow still builds, but the AAB is unsigned and Play will refuse it.
The run summary says whether the AAB was signed.

## 2. Where the AAB comes from

- The **Android** workflow (`.github/workflows/android.yml`) runs on every push to `main`, on
  PRs that touch `android/`, `capacitor.config.ts` or `src/platform/`, and by hand (Actions →
  Android → Run workflow).
- Each run uploads two artifacts: `tankcommand-release-aab` (the `.aab` for Play) and
  `tankcommand-debug-apk` (to sideload for a quick check). Download them from the run page.
- **Version:** `versionName` and `versionCode` come from `package.json` `version`
  (`0.1.0` → code 100, `0.1.1` → 101, `0.2.0` → 200). Play refuses a code it has seen,
  so bump `version` before each build you upload.

## 3. Create the app in Play Console

- [ ] Create app: name (working name TankCommand), default language, **Game**, **Free**.
      Free is permanent: the paid part is the in-app purchase.
- [ ] Accept Play App Signing when you upload the first AAB (Google generates the app signing key;
      your key from step 1 becomes the upload key).
- [ ] Upload the first signed AAB to an **internal testing** release so Play knows the app uses
      billing (the in-app product can only be created after a build with billing is uploaded).

## 4. In-app product

- [ ] Monetize → Products → In-app products → Create product
  - Product ID: **`full_game_unlock`** (must match exactly; the code asks for this id)
  - Name and description, e.g. "Full game" / "Every campaign mission and every skirmish map."
  - Price: your choice (Play converts to local prices). The unlock screen shows Play's price.
  - Activate it.
- What is free is set in `src/data/fullGame.ts`: all training, the first 5 missions of each
  campaign, and the Cinder Basin and Lakeside Crossing skirmish maps.

## 5. Testers get the unlock free

- [ ] Settings (Play Console home) → **License testing**: add every tester's Google account.
      Their purchases are test purchases: Play shows a test card and nothing is charged. No
      code path is needed. Testers must install the app from the Play test track (not a
      sideloaded APK) for billing to work.
- [ ] Testers can use **Restore purchases** (Settings, or the unlock screen) after reinstalling.

## 6. Closed test (needed before production)

New personal developer accounts must run a closed test with **at least 12 testers opted in
for 14 days in a row** before they can apply for production access.

- [ ] Testing → Closed testing → create a track, add testers (an email list or a Google Group).
- [ ] Upload the signed AAB, roll out, and send testers the opt-in link.
- [ ] Keep at least 12 opted in for 14 continuous days, then apply for production access.

## 7. Store settings (App content)

- [ ] **Privacy policy URL:** `https://tankcommand.vercel.app/privacy.html`
      (fill in `[contact email]` in `public/privacy.html` first and redeploy the web build).
- [ ] **Ads:** No, the app contains no ads.
- [ ] **App access:** all functionality is available without special access (the Google Play
      Games sign-in is optional; nothing needs it).
- [ ] **Target audience:** 13 and over recommended (lower ages bring the Families policy).
- [ ] **Data safety** (matches the privacy policy):
  - Does the app collect or share user data? **Yes** (bug reports the player chooses to send).
  - Data types collected, all **optional** (only when the player taps Send report),
    **not shared** with third parties (Vercel and GitHub are service providers), **not processed
    ephemerally** (they become a GitHub issue):
    - App info and performance → **Crash logs** and **Diagnostics** (log lines, freeze report).
      Purpose: App functionality, Analytics.
    - App info and performance → **Other app performance data** (version, platform, screen size).
      Purpose: App functionality.
    - App activity → **Other user-generated content** (the description; the save file if ticked).
      Purpose: App functionality.
    - Device or other IDs: **No** (no identifiers are sent; the browser identification string is
      not an ID).
    - Location, personal info, financial info, contacts, photos, messages: **No**. Purchases go
      through Google Play; the app only keeps an on-device flag.
    - **Google Play Games cloud save** (section 8): the progress goes to Google, not to us, but
      the Play Games Services SDK in the app counts for the form. Google publishes what that SDK
      collects ("Play Games Services" in Google's *data disclosure for Google Play services* page);
      declare those items as Google lists them, marked **optional** (sign-in is optional), purpose
      **App functionality**.
  - Encrypted in transit: **Yes** (HTTPS).
  - Users can request deletion: **Yes**, via the contact email in the policy.
- [ ] **Content rating** (IARC questionnaire): category **Game**. Violence: tanks, aircraft and
      alien craft destroy each other; no blood, no gore, no realistic people hurt (answer the
      fantasy/unrealistic violence questions yes, the rest no). No sexual content, profanity,
      drugs, alcohol, tobacco or gambling. Users can't interact or share content. Shares location:
      no. **Digital purchases: yes.** Expect a low age rating.
- [ ] **Government apps / news / health / financial features:** No to all.
- [ ] Store listing: short and full description, icon 512x512, feature graphic 1024x500,
      phone screenshots (landscape is fine).

## 8. Google Play Games sign-in and cloud saves

The Android app can keep campaign progress in the player's Google Play Games account (Saved
Games), so it follows them to a new phone. Sign-in is optional: the game always saves on the
device too, and the button is **Settings → Cloud save**. When both sides have progress, they are
merged: every mission won on either phone stays won, with the best time and hardest difficulty.
Google stores the saves; there is no server of ours. The web version keeps local saves only.

The code is in place (`android/app/.../PlayGamesPlugin.java`, `src/platform/cloudProgress.ts`).
It stays switched off until the build knows the Play Games project id. Steps, after the app
exists in Play Console (section 3) and one signed AAB is uploaded:

- [ ] Play Console → **Grow users → Play Games Services → Setup and management → Configuration**.
      Choose **No, my game doesn't use Google APIs** → create a new Play Games Services project
      (this makes a linked Google Cloud project for you).
- [ ] **Properties:** display name and category (Action or Strategy). Save.
- [ ] Turn **Saved games** **on** in the properties and save. (Without it the cloud save fails.)
- [ ] **Credentials → Add credential → Android**. Pick the app `com.davidbalasa.tankcommand`.
      Play Console offers to create the OAuth consent screen and OAuth client in the linked Google
      Cloud project: follow its links.
  - OAuth consent screen: app name, support email, **External**, publish it (no sensitive scopes,
    so no Google review).
  - OAuth client (type **Android**) needs a **package name** and a **SHA-1 fingerprint**. Make
    **two Android credentials**, one per fingerprint, or sign-in fails on one of the builds:
    1. **Play app signing key** (what testers and players get from Play): Play Console → **Test
       and release → App integrity → Play app signing → App signing key certificate → SHA-1**.
    2. **Upload key** (only if you sideload the release build you sign yourself):
       `keytool -list -v -keystore tankcommand-upload.jks -alias upload` → SHA-1. The same value
       is under App integrity → Upload key certificate.
    The debug APK from the workflow is signed with a throwaway key that changes on each build, so
    sign-in does not work there; test sign-in with an internal-testing install from Play.
- [ ] **Testers** (Play Games Services → Testers): add the testers' Google accounts. Until the
      Play Games Services project is **published**, only these accounts can sign in.
- [ ] Copy the **project id**: the number shown under the game's name on the Play Games Services
      Configuration page (e.g. `123456789012`).
- [ ] GitHub → repository → **Settings → Secrets and variables → Actions → Variables** → New
      repository variable `PLAY_GAMES_APP_ID` = that number. (A variable, not a secret: it is not
      sensitive.) Or send me the number and I will set it.
- [ ] Run the Android workflow. Its summary says **Google Play Games cloud saves: on**.
- [ ] **Review and publish** the Play Games Services configuration (Play Games Services → Publish)
      before the production release, so every player can sign in, not only testers.
- [ ] Check on a phone from the internal test track: open Settings → **Cloud save: sign in**,
      win a training mission, reinstall the app (or use a second phone with the same account),
      sign in, and the mission shows as won.

## 9. Bug reports (Vercel)

The game posts reports to `https://tankcommand.vercel.app/api/bug-report` (the `api/` folder of
this repo, deployed with the web build). Until both variables are set it answers 503 and the game
saves the report on the device and says it was not sent.

- [ ] Create a GitHub **fine-grained personal access token**: only the repository that should
      receive reports, permission **Issues: Read and write**, nothing else.
- [ ] Vercel → project → Settings → Environment Variables (Production):
  - `GITHUB_TOKEN` = the token
  - `GITHUB_REPO` = `owner/repo`, e.g. `davidbalasa-ui/TankCommand`
- [ ] Redeploy so the function picks them up.
- [ ] Check: in the game, Pause → Report bug → type a line → **Send report**. A new issue with the
      label `bug-report` should appear (GitHub creates the label on first use). If the repo is
      public, the issues are public too; consider a private repo for reports.

## 10. Before each release

- [ ] Bump `version` in `package.json`; merge to `main`.
- [ ] Wait for the Android workflow, check the summary says **signed**, download the AAB.
- [ ] Upload to the track, write release notes, roll out.
