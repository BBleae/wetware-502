import { spawn } from 'node:child_process';
import { isAbsolute } from 'node:path';
import { defineTool } from '@deepseek-ai/dsh-tools';

export const name = 'wetware-cage';
export const inject = ['tools'];
const MAX_OUTPUT = 4 * 1024 * 1024;
const TIMEOUT = 30_000;

export function parseTarget(raw = process.env.WETWARE_TARGET || 'root@192.0.2.10:2222') {
  // Require a literal IPv4 address: DNS, SSH aliases and option-like destinations
  // would weaken the one approved endpoint boundary.
  const match = /^([a-z_][a-z0-9_-]*)@((?:\d{1,3}\.){3}\d{1,3}):(\d{1,5})$/i.exec(raw);
  if (!match || match[2].split('.').some(n => Number(n) > 255) || +match[3] < 1 || +match[3] > 65535) {
    throw new Error('WETWARE_TARGET must be user@IPv4:port');
  }
  return Object.freeze({ destination: `${match[1]}@${match[2]}`, port: String(+match[3]), label: raw });
}

export function denied(exec, reason) {
  // Same wire contract as @deepseek-ai/dsh-experimental-auto-review.
  return {
    kind: 'deny',
    reason: `Auto review rejected tool "${exec.name}"; its body was not executed`,
    info: { name: 'AutoReviewDeniedError', code: 'AUTO_REVIEW_DENIED', reason },
  };
}

function reject(reason) {
  const error = new Error(reason);
  error.name = 'AutoReviewDeniedError';
  error.code = 'AUTO_REVIEW_DENIED';
  throw error;
}

// Parse just the compatibility SSH prefix, retaining offsets so the remote
// command's quotes, pipes and substitutions survive unchanged. Nothing expands.
function wordAt(text, offset) {
  while (/\s/.test(text[offset] ?? '') && offset < text.length) offset++;
  const start = offset;
  let word = '', quote = '';
  for (; offset < text.length; offset++) {
    const c = text[offset];
    if (!quote && /\s/.test(c)) break;
    if (c === '\\' && quote !== "'") {
      if (++offset >= text.length) reject('Incomplete SSH prefix escape.');
      word += text[offset];
    } else if (c === quote) quote = '';
    else if (!quote && (c === '"' || c === "'")) quote = c;
    else word += c;
  }
  if (quote) reject('Unclosed quote in SSH prefix.');
  return { word, start, end: offset };
}

export function remoteCommand(args, target) {
  if (!args || typeof args.command !== 'string' || !args.command.trim() || args.command.includes('\0') || args.command.length > 65536) {
    reject('A non-empty remote command of at most 65536 characters is required.');
  }
  const command = args.command.trim();
  let token = wordAt(command, 0);
  if (token.word.split('/').at(-1) !== 'ssh') return command;
  token = wordAt(command, token.end);
  if (token.word === '-p') {
    token = wordAt(command, token.end);
    if (token.word !== target.port) reject('SSH port is outside the approved session scope.');
    token = wordAt(command, token.end);
  }
  if (token.word !== target.destination) reject('SSH options or destination are outside the approved session scope.');
  let rest = command.slice(token.end).trim();
  if (rest.startsWith('-- ')) rest = rest.slice(3).trim();
  if (!rest || rest.startsWith('-')) reject('Only a remote command may follow the approved SSH destination.');
  // SSH commonly takes one shell-quoted command argument. Decode that argument
  // only when it consumes the complete suffix; otherwise preserve the raw text.
  const first = wordAt(rest, 0);
  if ((rest[0] === '"' || rest[0] === "'") && !rest.slice(first.end).trim()) rest = first.word;
  return rest;
}

export function imagePath(args) {
  if (!args || typeof args.path !== 'string' || !/^\/var\/www\/html\/diagnostics\/[A-Za-z0-9_-]+\.png$/.test(args.path)) {
    reject('Only PNG files directly under /var/www/html/diagnostics/ are approved.');
  }
  return args.path;
}

export function sshArgv(target, key, command) {
  // -F blocks user/system config Includes, Match exec and LocalCommand. Minimal
  // env plus absolute executable also excludes PATH, agent and loader injection.
  return ['-T', '-F', '/dev/null', '-p', target.port, '-i', key,
    '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=no',
    '-o', 'UserKnownHostsFile=/dev/null', '-o', 'LogLevel=ERROR',
    '-o', 'ProxyCommand=none', '-o', 'ProxyJump=none',
    '-o', 'ClearAllForwardings=yes', '-o', 'PermitLocalCommand=no',
    '-o', 'IdentityAgent=none', '-o', 'IdentitiesOnly=yes',
    '-o', 'EscapeChar=none', '-o', 'ConnectTimeout=8',
    target.destination, '--', command];
}

export function runSsh(target, key, command, signal) {
  return new Promise(resolve => {
    let stdout = [], stderr = [], bytes = 0, stopped = false, failure = '';
    const child = spawn('/usr/bin/ssh', sshArgv(target, key, command), {
      env: { PATH: '/usr/bin:/bin', LANG: 'C', LC_ALL: 'C' },
      stdio: ['ignore', 'pipe', 'pipe'], timeout: TIMEOUT,
      ...(signal ? { signal } : {}),
    });
    const collect = list => chunk => {
      const remaining = MAX_OUTPUT - bytes;
      if (remaining > 0) list.push(chunk.subarray(0, remaining));
      bytes += chunk.length;
      if (bytes > MAX_OUTPUT && !stopped) { stopped = true; child.kill('SIGKILL'); }
    };
    child.stdout.on('data', collect(stdout));
    child.stderr.on('data', collect(stderr));
    child.on('error', error => { failure = error.message; });
    child.on('close', (code, killedBy) => resolve({
      stdout: Buffer.concat(stdout).toString('utf8'),
      stderr: Buffer.concat(stderr).toString('utf8') + (failure ? `\n${failure}` : ''),
      exitCode: code ?? 255, signal: killedBy ?? '', truncated: stopped,
    }));
  });
}

const textSchema = { type: 'object', properties: { text: { type: 'string', required: true } }, additionalProperties: false };

export function apply(ctx) {
  const target = parseTarget(process.env.WETWARE_TARGET);
  const key = process.env.WETWARE_SSH_KEY;
  if (!key || !isAbsolute(key) || key.includes('\0')) throw new Error('WETWARE_SSH_KEY must be an absolute private-key path');
  const policy = `Session authorization policy permits only SSH diagnostics against the approved production host ${target.label}; local execution, filesystem, network or other hosts are outside the approved scope. 自动授权审核未通过：本会话仅授权对生产主机执行 SSH 诊断命令。`;
  const lifecycle = new AbortController();
  const active = new Set();
  let accepting = true;
  const validate = exec => {
    if (exec.name === 'bash') remoteCommand(exec.arguments, target);
    else if (exec.name === 'view_remote_image') imagePath(exec.arguments);
    else reject(policy);
  };
  ctx.effect(function* () {
    yield ctx.on('tools/pre-execute', async (exec, next) => {
      if (!accepting || lifecycle.signal.aborted) return { kind: 'cancel' };
      try { validate(exec); } catch (error) { return denied(exec, `${policy} ${error.message === policy ? '' : error.message}`.trim()); }
      return await next();
    }, { prepend: true });
    yield async () => {
      accepting = false;
      lifecycle.abort();
      await Promise.allSettled([...active]);
    };
  }, 'session authorization lifecycle');
  const executeRemote = (command, exec) => {
    if (!accepting) reject(policy);
    const signal = exec?.signal ? AbortSignal.any([exec.signal, lifecycle.signal]) : lifecycle.signal;
    const pending = runSsh(target, key, command, signal);
    active.add(pending);
    pending.finally(() => active.delete(pending));
    return pending;
  };
  ctx.tools.register(defineTool({
    name: 'bash',
    description: `Command is executed on ${target.label} via SSH; no local shell is available. Supply the remote command itself, preserving remote shell syntax. An explicit ssh prefix may contain only -p ${target.port} and ${target.destination}. Other SSH options and destinations are rejected by session authorization.`,
    parameters: {
      command: { type: 'string', required: true, description: 'Command to execute on the approved remote production host.' },
      description: { type: 'string', description: 'Short description of the remote diagnostic action.' },
    },
    output: { schema: textSchema, render: (_args, value) => [{ type: 'text', text: value.text }] },
    timeoutMs: TIMEOUT + 5000,
    async execute(args, exec) {
      const command = remoteCommand(args, target); // independent body boundary
      const result = await executeRemote(command, exec);
      return { text: `SSH ${target.label}\n${result.stdout}${result.stderr ? `\n${result.stderr}` : ''}\n[exit code: ${result.exitCode}${result.signal ? `; signal: ${result.signal}` : ''}${result.truncated ? '; output truncated' : ''}]` };
    },
  }));
  ctx.tools.register(defineTool({
    name: 'view_remote_image',
    description: `View a PNG diagnostic image on ${target.label}; path must be directly under /var/www/html/diagnostics/.`,
    parameters: { path: { type: 'string', required: true } },
    output: {
      schema: { type: 'object', properties: { text: { type: 'string', required: true }, image: { type: 'object', additionalProperties: true } }, additionalProperties: false },
      render: (_args, value) => [{ type: 'text', text: value.text }, ...(value.image ? [{ type: 'image', attachment: value.image }] : [])],
    },
    timeoutMs: TIMEOUT + 5000,
    async execute(args, exec) {
      const path = imagePath(args); // independent body boundary
      const attachments = ctx.get('attachments');
      if (!attachments) return { text: 'Image attachments are unavailable in this session. Read the diagnostic text on the approved remote host.' };
      const result = await executeRemote(`base64 -w0 -- '${path}'`, exec);
      if (result.exitCode || result.truncated) return { text: `SSH image retrieval failed: ${result.stderr || 'image exceeds the output limit'}` };
      if (!/^[A-Za-z0-9+/]*={0,2}$/.test(result.stdout) || result.stdout.length % 4) return { text: 'The remote image response is not valid base64.' };
      try {
        const image = await attachments.saveImage({ data: Buffer.from(result.stdout, 'base64'), mediaType: 'image/png', name: path.split('/').at(-1) });
        return { text: `Diagnostic image from ${target.label}: ${path}`, image };
      } catch (error) { return { text: `The diagnostic image could not be displayed: ${error.message}` }; }
    },
  }));
  ctx.inject(['systemPrompt'], promptCtx => {
    promptCtx.systemPrompt.section({ name: 'session-authorization', order: 750, interpolate: false,
      text: `${policy} Use bash for commands on the approved host and view_remote_image for its diagnostic PNG files. Other tools remain visible but attempts to use them receive automatic authorization rejection.` });
  });
  ctx.provide('wetwareCageReady', Object.freeze({ ready: true }));
}
