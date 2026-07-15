import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createAuthStore, isUniqueConstraintError, validatePassword, validateUsername } from "./auth_store.mjs";

test("unique-constraint errors are recognized across SQLite drivers", () => {
  assert.equal(isUniqueConstraintError({ code: "SQLITE_CONSTRAINT_UNIQUE" }), true);
  assert.equal(isUniqueConstraintError({ code: "ERR_SQLITE_ERROR", message: "UNIQUE constraint failed: users.username_key" }), true);
  assert.equal(isUniqueConstraintError({ errcode: 2067 }), true);
  assert.equal(isUniqueConstraintError({ code: "ERR_SQLITE_ERROR", message: "database is locked" }), false);
});

test("register rejects duplicate usernames with a driver error the server can classify", async () => {
  const directory = await mkdtemp(join(tmpdir(), "lumenalpha-auth-dup-"));
  const store = await createAuthStore(join(directory, "users.sqlite"));

  try {
    await store.register("dupe_user", "StrongPass123!");
    // Exercises the *real* SQLite driver error (not a hand-crafted object), so
    // this fails if node:sqlite ever changes its unique-constraint error shape.
    await assert.rejects(
      () => store.register("dupe_user", "AnotherPass456!"),
      (error) => isUniqueConstraintError(error),
    );
    // Uniqueness is case-insensitive via username_key.
    await assert.rejects(
      () => store.register("DUPE_USER", "AnotherPass456!"),
      (error) => isUniqueConstraintError(error),
    );
  } finally {
    store.close();
    await rm(directory, { recursive: true, force: true });
  }
});

test("account sessions and watchlist persist in SQLite", async () => {
  const directory = await mkdtemp(join(tmpdir(), "lumenalpha-auth-"));
  const dbPath = join(directory, "users.sqlite");
  let store = await createAuthStore(dbPath);

  try {
    assert.equal(validateUsername("ab").ok, false);
    assert.equal(validateUsername("测试_user").ok, true);
    assert.equal(validatePassword("short").ok, false);

    const registered = await store.register("测试_user", "StrongPass123!");
    assert.equal(registered.user.username, "测试_user");
    assert.equal(store.sessionUser(registered.token)?.id, registered.user.id);
    assert.equal(await store.login("测试_USER", "wrong-password"), null);

    const loggedIn = await store.login("测试_USER", "StrongPass123!");
    assert.equal(loggedIn.user.id, registered.user.id);

    store.addWatch(loggedIn.user.id, "600519");
    store.addWatch(loggedIn.user.id, "600519");
    store.addWatch(loggedIn.user.id, "000001");
    assert.deepEqual(store.watchlist(loggedIn.user.id).sort(), ["000001", "600519"]);
    assert.deepEqual(
      store.watchlistEntries(loggedIn.user.id).map((item) => item.code).sort(),
      ["000001", "600519"],
    );
    assert.match(store.watchlistEntries(loggedIn.user.id)[0].createdAt, /^\d{4}-\d{2}-\d{2}T/);

    store.removeWatch(loggedIn.user.id, "000001");
    assert.deepEqual(store.watchlist(loggedIn.user.id), ["600519"]);

    store.close();
    store = await createAuthStore(dbPath);
    assert.deepEqual(store.watchlist(loggedIn.user.id), ["600519"]);

    store.logout(loggedIn.token);
    assert.equal(store.sessionUser(loggedIn.token), null);
  } finally {
    store.close();
    await rm(directory, { recursive: true, force: true });
  }
});
