// Minimal static server — index.html fetches data/games.json, which file:// blocks.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';

const ROOT = new URL('..', import.meta.url).pathname;
const PORT = Number(process.env.PORT) || 5173;
const TYPES = { '.html': 'text/html', '.json': 'application/json', '.js': 'text/javascript', '.css': 'text/css' };

const server = createServer(async (req, res) => {
  const path = normalize(decodeURIComponent(req.url.split('?')[0])).replace(/^(\.\.[/\\])+/, '');
  const file = join(ROOT, path === '/' ? 'index.html' : path);
  try {
    const body = await readFile(file);
    res.writeHead(200, { 'content-type': TYPES[extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch {
    res.writeHead(404, { 'content-type': 'text/plain' });
    res.end('not found');
  }
});

// A stale server from a previous run shouldn't be a crash; step to the next port.
server.on('error', (err) => {
  if (err.code !== 'EADDRINUSE' || server.tries++ > 10) throw err;
  console.log(`port ${server.port} busy, trying ${++server.port}`);
  server.listen(server.port);
});
server.tries = 0;
server.port = PORT;
server.listen(PORT);
server.on('listening', () => console.log(`http://localhost:${server.port}`));
