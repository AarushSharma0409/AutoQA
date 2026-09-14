import net from 'node:net';
import { spawn } from 'node:child_process';

// Studio binds to localhost inside its container. Forward only through the
// Compose port published on the host's loopback interface.
const child = spawn('npx', ['--yes', 'prisma@7.10.0', 'studio',
  '--url=postgresql://autoagent:autoagent@postgres:5432/autoagent',
  '--port=5556', '--browser=none'], { stdio: 'inherit' });
const server = net.createServer(client => {
  const upstream = net.connect(5556, '127.0.0.1');
  client.pipe(upstream).pipe(client);
  client.on('error', () => upstream.destroy());
  upstream.on('error', () => client.destroy());
  client.on('close', () => upstream.destroy());
});
server.listen(5555, '0.0.0.0');
child.on('exit', code => process.exit(code ?? 1));
child.on('error', error => { console.error(error.message); process.exit(1); });
for (const signal of ['SIGTERM', 'SIGINT']) {
  process.on(signal, () => { child.kill(signal); server.close(); });
}
