require("dotenv").config();
const snoowrap = require("snoowrap");
const fs = require("fs");
const path = require("path");

const USER_ID = process.env.AUTOSUB_USER_ID;
const OFFER_TEXT = process.env.AUTOSUB_OFFER;
const KEYWORDS = (process.env.AUTOSUB_KEYWORDS || "").split(",").map(k => k.trim()).filter(Boolean);
const DM_SUBJECT = process.env.AUTOSUB_SUBJECT || "quick question";

const reddit = new snoowrap({
  userAgent: `AutoSub/1.0 u/${process.env.REDDIT_USERNAME}`,
  clientId: process.env.REDDIT_CLIENT_ID,
  clientSecret: process.env.REDDIT_CLIENT_SECRET,
  username: process.env.REDDIT_USERNAME,
  password: process.env.REDDIT_PASSWORD,
});

const logDir = path.resolve(__dirname, `../logs/${USER_ID}`);
if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });

const contactedPath = path.join(logDir, "contacted.json");
const statsPath = path.join(logDir, "stats.json");
const logPath = path.join(logDir, "bot.log");

function log(tag, msg) {
  const line = `[${new Date().toISOString()}] ${tag}: ${msg}`;
  console.log(line);
  try { fs.appendFileSync(logPath, line + "\n"); } catch(e) {}
}

function loadContacted() {
  if (!fs.existsSync(contactedPath)) return {};
  try { return JSON.parse(fs.readFileSync(contactedPath, "utf8")); } catch { return {}; }
}

function saveContacted(c) {
  try { fs.writeFileSync(contactedPath, JSON.stringify(c, null, 2)); } catch(e) { log("ERROR", "saveContacted: " + e.message); }
}

function loadStats() {
  if (!fs.existsSync(statsPath)) return { dms_sent: 0, replies: 0, last_run: null };
  try { return JSON.parse(fs.readFileSync(statsPath, "utf8")); } catch { return { dms_sent: 0, replies: 0, last_run: null }; }
}

function saveStats(s) {
  try { fs.writeFileSync(statsPath, JSON.stringify(s, null, 2)); } catch(e) { log("ERROR", "saveStats: " + e.message); }
}

function isFresh(post) {
  const ageHours = (Date.now() - post.created_utc * 1000) / 36e5;
  return ageHours <= 24;
}

const forHireBlockRegex = /\b(\[for hire\]|\[offering\]|offering my services|available for hire|hire me|starting at \$)\b/i;

const wait = ms => new Promise(r => setTimeout(r, ms));
const rand = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

async function runCycle() {
  const contacted = loadContacted();
  const sentThisSession = new Set();
  const stats = loadStats();
  stats.last_run = new Date().toISOString();
  saveStats(stats);
  let dmsSentThisCycle = 0;
  const MAX_DMS = 15;
  log("INFO", `Starting cycle. Keywords: ${KEYWORDS.join(", ")}`);
  for (const keyword of KEYWORDS) {
    if (dmsSentThisCycle >= MAX_DMS) break;
    try {
      await wait(2000);
      const posts = await reddit.search({ query: keyword, sort: "new", time: "day", limit: 25 });
      log("INFO", `"${keyword}" returned ${posts.length} posts`);
      for (const post of posts) {
        if (dmsSentThisCycle >= MAX_DMS) break;
        if (!post.author || !isFresh(post)) continue;
        if (forHireBlockRegex.test(`${post.title} ${post.selftext}`)) continue;
        const username = post.author.name;
        if (contacted[username.toLowerCase()] || sentThisSession.has(username.toLowerCase())) continue;
        if (username.toLowerCase() === (process.env.REDDIT_USERNAME || "").toLowerCase()) continue;
        try {
          await reddit.composeMessage({ to: username, subject: DM_SUBJECT, text: OFFER_TEXT });
          contacted[username.toLowerCase()] = new Date().toISOString();
          sentThisSession.add(username.toLowerCase());
          saveContacted(contacted);
          dmsSentThisCycle++;
          stats.dms_sent++;
          stats.last_run = new Date().toISOString();
          saveStats(stats);
          log("SENT", `u/${username} | keyword: "${keyword}"`);
          await wait(rand(2 * 60 * 1000, 4 * 60 * 1000));
        } catch (err) {
          log("ERROR", `DM failed u/${username}: ${err.message}`);
        }
      }
    } catch (err) {
      log("ERROR", `Search failed "${keyword}": ${err.message}`);
      await wait(15000);
    }
  }
  try {
    const unread = await reddit.getUnreadMessages({ limit: 25 });
    const toMark = [];
    for (const item of unread) {
      if (item.was_comment !== false) continue;
      if (!item.body || !item.author) continue;
      toMark.push(item);
      const sender = item.author.name.toLowerCase();
      if (sender === (process.env.REDDIT_USERNAME || "").toLowerCase()) continue;
      stats.replies++;
      saveStats(stats);
      log("REPLY", `u/${item.author.name} replied`);
    }
    if (toMark.length > 0) await reddit.markMessagesAsRead(toMark);
  } catch (err) {
    log("ERROR", `Inbox check failed: ${err.message}`);
  }
  log("INFO", `Cycle complete. Sent ${dmsSentThisCycle} DMs. Total: ${stats.dms_sent}`);
}

(async () => {
  log("INFO", `AutoSub bot started for user ${USER_ID}`);
  while (true) {
    await runCycle();
    const delay = rand(20, 30) * 60 * 1000;
    log("INFO", `Next cycle in ${Math.round(delay / 60000)} minutes`);
    await wait(delay);
  }
})();
