/**
 * AI4S Knowledge Curator — DSH Native Bridge Plugin (SI-4-R6)
 *
 * Uses pinned @deepseek-ai/dsh-tools defineTool contract.
 * Real async spawn stdin transport.
 * Preset-scoped DSH-native tools: knowledge_curator_commit, knowledge_curator_revision.
 * NOT public MCP tools.
 */

import { spawn } from 'node:child_process'

const PYTHON_CMD = process.env.AI4S_KC_PYTHON || 'python'
const WORKSPACE = process.env.AI4S_KC_WORKSPACE || process.cwd()
const TIMEOUT_MS = 60000
const MAX_BUFFER = 1024 * 1024

function callBridge(action, payload, signal) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      PYTHON_CMD,
      ['-m', 'system.curator_agent_bridge_stdio', action],
      {
        cwd: WORKSPACE,
        env: { ...process.env, PYTHONPATH: WORKSPACE },
        stdio: ['pipe', 'pipe', 'pipe'],
      }
    )

    let stdout = ''
    let stderr = ''
    let settled = false

    const timer = setTimeout(() => {
      if (!settled) { settled = true; child.kill('SIGTERM'); reject(new Error(`bridge timeout after ${TIMEOUT_MS}ms`)) }
    }, TIMEOUT_MS)

    const onAbort = () => {
      if (!settled) { settled = true; clearTimeout(timer); child.kill('SIGTERM'); reject(new Error('bridge cancelled')) }
    }
    if (signal) {
      if (signal.aborted) { onAbort(); return }
      signal.addEventListener('abort', onAbort, { once: true })
    }

    child.stdout.on('data', (d) => {
      stdout += d.toString()
      if (stdout.length > MAX_BUFFER) {
        if (!settled) { settled = true; clearTimeout(timer); child.kill('SIGTERM'); reject(new Error('stdout buffer overflow')) }
      }
    })
    child.stderr.on('data', (d) => {
      stderr += d.toString()
      if (stderr.length > MAX_BUFFER) stderr = stderr.slice(-MAX_BUFFER)
    })

    child.on('error', (err) => {
      if (!settled) { settled = true; clearTimeout(timer); reject(err) }
    })

    child.on('close', (code) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      if (signal) signal.removeEventListener('abort', onAbort)

      if (code !== 0) {
        reject(new Error(`bridge exited ${code}: ${stderr.slice(0, 500)}`))
        return
      }
      try {
        const result = JSON.parse(stdout.trim())
        if (result.error) {
          reject(new Error(result.error))
        } else {
          resolve(result)
        }
      } catch {
        reject(new Error(`invalid JSON from bridge: ${stdout.slice(0, 200)}`))
      }
    })

    child.stdin.write(JSON.stringify(payload))
    child.stdin.end()
  })
}

// Lazy-load defineTool to handle module resolution in different contexts
let _defineTool = null
async function getDefineTool() {
  if (_defineTool) return _defineTool
  try {
    const mod = await import('@deepseek-ai/dsh-tools')
    _defineTool = mod.defineTool || mod.default?.defineTool
  } catch {
    // Fallback: identity function for environments where dsh-tools is not resolvable
    _defineTool = (opts) => opts
  }
  return _defineTool
}

export const name = 'curator-bridge'
export const inject = ['tools']

export async function apply(ctx) {
  if (!ctx.tools || typeof ctx.tools.register !== 'function') return

  const defineTool = await getDefineTool()

  const commitTool = defineTool({
    name: 'knowledge_curator_commit',
    description: 'Commit a publishable curated AssertionSet through the accepted application workflow.',
    parameters: {
      source_ref_id: { type: 'string', required: true },
      source_fingerprint: { type: 'string', required: true },
      assertion_set: { type: 'object', required: true, additionalProperties: true },
      metadata: { type: 'object', additionalProperties: true },
      trace: { type: 'object', additionalProperties: true },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          status: { type: 'string', required: true },
          commit_attempted: { type: 'boolean', required: true },
          blocked_reason: {
            required: true,
            oneOf: [{ type: 'string' }, { type: 'null' }],
          },
        },
      },
      render: (_args, value) => [
        { type: 'text', text: JSON.stringify(value) },
      ],
    },
    async execute(args, exec) {
      return await callBridge('curate_and_commit', args, exec?.signal)
    },
  })

  const revisionTool = defineTool({
    name: 'knowledge_curator_revision',
    description: 'Apply a prepared revision through RevisionPublicationWorkflow.',
    parameters: {
      package: { type: 'object', required: true, additionalProperties: true },
      target_commit_request: { type: 'object', required: true, additionalProperties: true },
      approval: { type: 'object', additionalProperties: true },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          status: { type: 'string', required: true },
          error: { type: 'string' },
        },
      },
      render: (_args, value) => [
        { type: 'text', text: JSON.stringify(value) },
      ],
    },
    async execute(args, exec) {
      return await callBridge('revise', args, exec?.signal)
    },
  })

  ctx.effect(() => ctx.tools.register(commitTool))
  ctx.effect(() => ctx.tools.register(revisionTool))
}
