package com.davidbalasa.tankcommand;

import android.app.Activity;
import android.text.TextUtils;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.android.gms.games.GamesSignInClient;
import com.google.android.gms.games.PlayGames;
import com.google.android.gms.games.PlayGamesSdk;
import com.google.android.gms.games.SnapshotsClient;
import com.google.android.gms.games.snapshot.Snapshot;
import com.google.android.gms.games.snapshot.SnapshotMetadata;
import com.google.android.gms.games.snapshot.SnapshotMetadataChange;
import com.google.android.gms.tasks.Task;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * Google Play Games Services v2: optional sign-in and Saved Games (cloud saves).
 *
 * The game keeps its own save on the device and merges it with the cloud copy in JavaScript
 * (src/platform/cloudProgress.ts); this plugin only reads and writes one snapshot by name.
 * Until the Play Games project id is set at build time (PLAY_GAMES_APP_ID, see
 * docs/play-release.md) the SDK is not started and every call answers "not configured".
 */
@CapacitorPlugin(name = "PlayGames")
public class PlayGamesPlugin extends Plugin {

    /** Two devices that both saved offline: keep the snapshot that reports more progress. */
    private static final int MAX_CONFLICT_ROUNDS = 5;

    private boolean configured = false;

    @Override
    public void load() {
        String appId = "";
        try {
            appId = getContext().getString(R.string.game_services_project_id);
        } catch (Exception ignored) {
            // Resource missing: treated as not configured.
        }
        configured = !TextUtils.isEmpty(appId) && TextUtils.isDigitsOnly(appId);
        if (configured) {
            try {
                PlayGamesSdk.initialize(getContext().getApplicationContext());
            } catch (Exception error) {
                configured = false;
            }
        }
    }

    private boolean ready(PluginCall call) {
        if (!configured) {
            call.reject("Play Games is not configured in this build", "NOT_CONFIGURED");
            return false;
        }
        if (getActivity() == null) {
            call.reject("No activity", "NO_ACTIVITY");
            return false;
        }
        return true;
    }

    private static String message(Exception error) {
        return error == null || error.getMessage() == null ? "unknown error" : error.getMessage();
    }

    @PluginMethod
    public void status(PluginCall call) {
        if (!configured || getActivity() == null) {
            JSObject result = new JSObject();
            result.put("configured", false);
            result.put("signedIn", false);
            call.resolve(result);
            return;
        }
        GamesSignInClient client = PlayGames.getGamesSignInClient(getActivity());
        client.isAuthenticated().addOnCompleteListener(task -> {
            boolean signedIn = task.isSuccessful() && task.getResult() != null && task.getResult().isAuthenticated();
            answerWithPlayer(call, signedIn);
        });
    }

    @PluginMethod
    public void signIn(PluginCall call) {
        if (!ready(call)) {
            return;
        }
        GamesSignInClient client = PlayGames.getGamesSignInClient(getActivity());
        client.signIn().addOnCompleteListener(task -> {
            boolean signedIn = task.isSuccessful() && task.getResult() != null && task.getResult().isAuthenticated();
            answerWithPlayer(call, signedIn);
        });
    }

    private void answerWithPlayer(PluginCall call, boolean signedIn) {
        JSObject result = new JSObject();
        result.put("configured", true);
        result.put("signedIn", signedIn);
        Activity activity = getActivity();
        if (!signedIn || activity == null) {
            call.resolve(result);
            return;
        }
        PlayGames.getPlayersClient(activity).getCurrentPlayer().addOnCompleteListener(task -> {
            if (task.isSuccessful() && task.getResult() != null) {
                result.put("playerName", task.getResult().getDisplayName());
            }
            call.resolve(result);
        });
    }

    /** Reads a snapshot: { exists, data } (data is the UTF-8 text the game wrote). */
    @PluginMethod
    public void read(PluginCall call) {
        if (!ready(call)) {
            return;
        }
        String name = call.getString("name");
        if (TextUtils.isEmpty(name)) {
            call.reject("name is required");
            return;
        }
        SnapshotsClient snapshots = PlayGames.getSnapshotsClient(getActivity());
        openResolved(snapshots, name, 0, (snapshot, error) -> {
            if (snapshot == null) {
                call.reject("Could not open the cloud save: " + message(error), "OPEN_FAILED");
                return;
            }
            JSObject result = new JSObject();
            try {
                byte[] bytes = snapshot.getSnapshotContents().readFully();
                result.put("exists", bytes != null && bytes.length > 0);
                result.put("data", bytes == null ? "" : new String(bytes, StandardCharsets.UTF_8));
            } catch (IOException readError) {
                snapshots.discardAndClose(snapshot);
                call.reject("Could not read the cloud save: " + message(readError), "READ_FAILED");
                return;
            }
            snapshots.discardAndClose(snapshot);
            call.resolve(result);
        });
    }

    /** Writes a snapshot: name, data (text), description, progress (a number; higher wins conflicts). */
    @PluginMethod
    public void write(PluginCall call) {
        if (!ready(call)) {
            return;
        }
        String name = call.getString("name");
        String data = call.getString("data");
        if (TextUtils.isEmpty(name) || data == null) {
            call.reject("name and data are required");
            return;
        }
        String description = call.getString("description", "TankCommand progress");
        Double progressNumber = call.getDouble("progress", 0.0);
        long progress = progressNumber == null ? 0L : Math.max(0L, Math.round(progressNumber));
        SnapshotsClient snapshots = PlayGames.getSnapshotsClient(getActivity());
        openResolved(snapshots, name, 0, (snapshot, error) -> {
            if (snapshot == null) {
                call.reject("Could not open the cloud save: " + message(error), "OPEN_FAILED");
                return;
            }
            snapshot.getSnapshotContents().writeBytes(data.getBytes(StandardCharsets.UTF_8));
            SnapshotMetadataChange change = new SnapshotMetadataChange.Builder()
                .setDescription(description)
                .setProgressValue(progress)
                .build();
            snapshots.commitAndClose(snapshot, change).addOnCompleteListener(task -> {
                if (task.isSuccessful()) {
                    call.resolve();
                } else {
                    call.reject("Could not write the cloud save: " + message(task.getException()), "WRITE_FAILED");
                }
            });
        });
    }

    private interface SnapshotCallback {
        void done(Snapshot snapshot, Exception error);
    }

    /**
     * Opens a snapshot, creating it when missing. Play resolves most conflicts itself (highest
     * progress value wins); one that still comes back is settled the same way here.
     */
    private void openResolved(SnapshotsClient snapshots, String name, int round, SnapshotCallback callback) {
        Task<SnapshotsClient.DataOrConflict<Snapshot>> open =
            snapshots.open(name, true, SnapshotsClient.RESOLUTION_POLICY_HIGHEST_PROGRESS);
        handleOpen(snapshots, open, name, round, callback);
    }

    private void handleOpen(
        SnapshotsClient snapshots,
        Task<SnapshotsClient.DataOrConflict<Snapshot>> task,
        String name,
        int round,
        SnapshotCallback callback
    ) {
        task.addOnCompleteListener(done -> {
            if (!done.isSuccessful() || done.getResult() == null) {
                callback.done(null, done.getException());
                return;
            }
            SnapshotsClient.DataOrConflict<Snapshot> result = done.getResult();
            if (!result.isConflict()) {
                callback.done(result.getData(), null);
                return;
            }
            SnapshotsClient.SnapshotConflict conflict = result.getConflict();
            if (conflict == null || round >= MAX_CONFLICT_ROUNDS) {
                callback.done(null, new Exception("unresolved save conflict"));
                return;
            }
            Snapshot server = conflict.getSnapshot();
            Snapshot local = conflict.getConflictingSnapshot();
            Snapshot keep = progressOf(local) > progressOf(server) ? local : server;
            handleOpen(snapshots, snapshots.resolveConflict(conflict.getConflictId(), keep), name, round + 1, callback);
        });
    }

    private static long progressOf(Snapshot snapshot) {
        if (snapshot == null) {
            return -1;
        }
        SnapshotMetadata metadata = snapshot.getMetadata();
        return metadata == null ? -1 : metadata.getProgressValue();
    }
}
