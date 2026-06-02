// Minimal zero-dependency server: reads .env, serves index.html,
// and proxies outbound-call requests to Vapi so the API key never
// reaches the browser. Run with: node server.js
const http = require("http");
const fs = require("fs");
const path = require("path");
const https = require("https");

// ---- Load .env (tiny parser, no dependencies) ----
function loadEnv(file) {
  const env = {};
  try {
    const raw = fs.readFileSync(file, "utf8");
    for (const line of raw.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eq = trimmed.indexOf("=");
      if (eq === -1) continue;
      const key = trimmed.slice(0, eq).trim();
      let val = trimmed.slice(eq + 1).trim();
      if (
        (val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))
      ) {
        val = val.slice(1, -1);
      }
      env[key] = val;
    }
  } catch (err) {
    console.error("Could not read .env:", err.message);
  }
  return env;
}

const env = loadEnv(path.join(__dirname, ".env"));
const { VAPI_API_KEY, VAPI_ASSISTANT_ID, VAPI_PHONE_NUMBER_ID } = env;
const PORT = process.env.PORT || 3000;

// ---- Forward a call request to the Vapi REST API ----
function placeVapiCall(number) {
  return new Promise((resolve) => {
    const payload = JSON.stringify({
      assistantId: VAPI_ASSISTANT_ID,
      phoneNumberId: VAPI_PHONE_NUMBER_ID,
      customer: { number },
    });

    const req = https.request(
      {
        hostname: "api.vapi.ai",
        path: "/call/phone",
        method: "POST",
        headers: {
          Authorization: "Bearer " + VAPI_API_KEY,
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(payload),
        },
      },
      (res) => {
        let body = "";
        res.on("data", (chunk) => (body += chunk));
        res.on("end", () => resolve({ status: res.statusCode, body }));
      }
    );

    req.on("error", (err) =>
      resolve({ status: 500, body: JSON.stringify({ message: err.message }) })
    );
    req.write(payload);
    req.end();
  });
}

// ---- Fetch the latest state of a call (status, transcript, summary) ----
function getVapiCall(id) {
  return new Promise((resolve) => {
    const req = https.request(
      {
        hostname: "api.vapi.ai",
        path: "/call/" + encodeURIComponent(id),
        method: "GET",
        headers: { Authorization: "Bearer " + VAPI_API_KEY },
      },
      (res) => {
        let body = "";
        res.on("data", (chunk) => (body += chunk));
        res.on("end", () => resolve({ status: res.statusCode, body }));
      }
    );

    req.on("error", (err) =>
      resolve({ status: 500, body: JSON.stringify({ message: err.message }) })
    );
    req.end();
  });
}

// ---- HTTP server ----
const server = http.createServer(async (req, res) => {
  // Serve the page
  if (req.method === "GET" && (req.url === "/" || req.url === "/index.html")) {
    fs.readFile(path.join(__dirname, "index.html"), (err, data) => {
      if (err) {
        res.writeHead(500);
        res.end("Could not load index.html");
        return;
      }
      res.writeHead(200, { "Content-Type": "text/html" });
      res.end(data);
    });
    return;
  }

  // Proxy the outbound call
  if (req.method === "POST" && req.url === "/call") {
    if (!VAPI_API_KEY || VAPI_API_KEY === "YOUR_VAPI_API_KEY") {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ message: "Credentials not set in .env" }));
      return;
    }

    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", async () => {
      let number;
      try {
        number = JSON.parse(body).number;
      } catch {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ message: "Invalid request body" }));
        return;
      }

      const result = await placeVapiCall(number);
      res.writeHead(result.status, { "Content-Type": "application/json" });
      res.end(result.body || "{}");
    });
    return;
  }

  // Poll a call's live status / transcript / summary
  if (req.method === "GET" && req.url.startsWith("/call-status")) {
    const id = new URL(req.url, "http://localhost").searchParams.get("id");
    if (!id) {
      res.writeHead(400, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ message: "Missing call id" }));
      return;
    }
    const result = await getVapiCall(id);
    res.writeHead(result.status, { "Content-Type": "application/json" });
    res.end(result.body || "{}");
    return;
  }

  res.writeHead(404);
  res.end("Not found");
});

server.listen(PORT, () => {
  console.log(`Vapi caller running at http://localhost:${PORT}`);
  const ready =
    VAPI_API_KEY && VAPI_API_KEY !== "YOUR_VAPI_API_KEY"
      ? "credentials loaded from .env"
      : "WARNING: fill in your credentials in .env";
  console.log(ready);
});
