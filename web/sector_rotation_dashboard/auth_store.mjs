import { createHash, randomBytes, scrypt as scryptCallback, timingSafeEqual } from "node:crypto";
import { chmodSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { promisify } from "node:util";

const scrypt = promisify(scryptCallback);
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000;

async function databaseConstructor() {
  try {
    const sqlite = await import("node:sqlite");
    return sqlite.DatabaseSync;
  } catch (_error) {
    const sqlite = await import("better-sqlite3");
    return sqlite.default;
  }
}

function usernameKey(username) {
  return String(username || "").normalize("NFKC").trim().toLowerCase();
}

function publicUser(row) {
  if (!row) return null;
  return {
    id: Number(row.id),
    username: row.username,
    createdAt: row.created_at,
  };
}

function tokenHash(token) {
  return createHash("sha256").update(String(token || "")).digest("hex");
}

async function passwordDigest(password, salt) {
  return Buffer.from(await scrypt(password, salt, 64));
}

export async function createAuthStore(dbPath) {
  mkdirSync(dirname(dbPath), { recursive: true });
  const Database = await databaseConstructor();
  const db = new Database(dbPath);
  chmodSync(dbPath, 0o600);
  db.exec("PRAGMA journal_mode = WAL");
  db.exec("PRAGMA foreign_keys = ON");
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL,
      username_key TEXT NOT NULL UNIQUE,
      password_salt TEXT NOT NULL,
      password_hash TEXT NOT NULL,
      created_at TEXT NOT NULL,
      last_login_at TEXT
    );
    CREATE TABLE IF NOT EXISTS sessions (
      token_hash TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      created_at TEXT NOT NULL,
      expires_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
    CREATE TABLE IF NOT EXISTS watchlist (
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      code TEXT NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY (user_id, code)
    );
  `);

  const insertUser = db.prepare(`
    INSERT INTO users (username, username_key, password_salt, password_hash, created_at)
    VALUES (?, ?, ?, ?, ?)
  `);
  const findUserByName = db.prepare("SELECT * FROM users WHERE username_key = ?");
  const findUserById = db.prepare("SELECT id, username, created_at FROM users WHERE id = ?");
  const updateLastLogin = db.prepare("UPDATE users SET last_login_at = ? WHERE id = ?");
  const insertSession = db.prepare(`
    INSERT INTO sessions (token_hash, user_id, created_at, expires_at)
    VALUES (?, ?, ?, ?)
  `);
  const findSession = db.prepare(`
    SELECT u.id, u.username, u.created_at
    FROM sessions s
    JOIN users u ON u.id = s.user_id
    WHERE s.token_hash = ? AND s.expires_at > ?
  `);
  const deleteSession = db.prepare("DELETE FROM sessions WHERE token_hash = ?");
  const deleteExpiredSessions = db.prepare("DELETE FROM sessions WHERE expires_at <= ?");
  const listWatchlist = db.prepare("SELECT code FROM watchlist WHERE user_id = ? ORDER BY created_at DESC");
  const insertWatch = db.prepare("INSERT OR IGNORE INTO watchlist (user_id, code, created_at) VALUES (?, ?, ?)");
  const deleteWatch = db.prepare("DELETE FROM watchlist WHERE user_id = ? AND code = ?");

  async function createUser(username, password) {
    const salt = randomBytes(16).toString("hex");
    const hash = await passwordDigest(password, salt);
    const createdAt = new Date().toISOString();
    const result = insertUser.run(username, usernameKey(username), salt, hash.toString("hex"), createdAt);
    return publicUser(findUserById.get(Number(result.lastInsertRowid)));
  }

  async function verifyUser(username, password) {
    const row = findUserByName.get(usernameKey(username));
    if (!row) {
      await passwordDigest(password, "00000000000000000000000000000000");
      return null;
    }
    const actual = await passwordDigest(password, row.password_salt);
    const expected = Buffer.from(row.password_hash, "hex");
    if (actual.length !== expected.length || !timingSafeEqual(actual, expected)) return null;
    updateLastLogin.run(new Date().toISOString(), row.id);
    return publicUser(row);
  }

  function createSession(userId) {
    deleteExpiredSessions.run(Date.now());
    const token = randomBytes(32).toString("base64url");
    const createdAt = new Date().toISOString();
    insertSession.run(tokenHash(token), userId, createdAt, Date.now() + SESSION_TTL_MS);
    return token;
  }

  return {
    async register(username, password) {
      const user = await createUser(username, password);
      return { user, token: createSession(user.id) };
    },
    async login(username, password) {
      const user = await verifyUser(username, password);
      return user ? { user, token: createSession(user.id) } : null;
    },
    sessionUser(token) {
      if (!token) return null;
      return publicUser(findSession.get(tokenHash(token), Date.now()));
    },
    logout(token) {
      if (token) deleteSession.run(tokenHash(token));
    },
    watchlist(userId) {
      return listWatchlist.all(userId).map((row) => row.code);
    },
    addWatch(userId, code) {
      insertWatch.run(userId, code, new Date().toISOString());
    },
    removeWatch(userId, code) {
      deleteWatch.run(userId, code);
    },
    close() {
      db.close();
    },
  };
}

export function validateUsername(value) {
  const username = String(value || "").normalize("NFKC").trim();
  if (!/^[\p{L}\p{N}_-]{3,24}$/u.test(username)) {
    return { ok: false, error: "用户名需为3-24位中文、字母、数字、下划线或短横线" };
  }
  return { ok: true, value: username };
}

export function validatePassword(value) {
  const password = String(value || "");
  if (password.length < 8 || password.length > 128) {
    return { ok: false, error: "密码长度需为8-128位" };
  }
  return { ok: true, value: password };
}

export function isUniqueConstraintError(error) {
  return /constraint/i.test(`${error?.code ?? ""} ${error?.message ?? ""}`) || error?.errcode === 2067;
}
