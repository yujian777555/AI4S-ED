/**
 * AI4S Knowledge Curator — DSH Native Bridge Plugin (SI-4-R5)
 *
 * Uses pinned DSH defineTool contract.
 * Real async spawn stdin transport (no execFile input hack).
 * Preset-scoped DSH-native tools: knowledge_curator_commit, knowledge_curator_revision.
 * These are NOT public MCP tools.
 */

import { spawn } from 'node:child_process'

const PYTHON_CMD = process.env.AI4S_KC_PYTHON || 'python'
const WORKSPACE = process.env.AI4S_KC_WORKSPACE || process.cwd()
const TIMEOUT_MS = 60000
const MAX_BUFFER = 1024 * 1024

/**
 * Real async stdin transport: spawn -> stdin.write -> stdin.end.
 */
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
      if (!settled) {
        settled = true
        child.kill('SIGTERM')
        reject(new Error(`bridge timeout after ${TIMEOUT_MS}ms`))
      }
    }, TIMEOUT_MS)

    const onAbort = () => {
      if (!settled) {
        settled = true
        clearTimeout(timer)
        child.kill('SIGTERM')
        reject(new Error('bridge cancelled'))
      }
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

    // Send payload via stdin
    child.stdin.write(JSON.stringify(payload))
    child.stdin.end()
  })
}

/**
 * DSH plugin entry using pinned Cordis shape: export name, inject, apply.
 */
export const name = 'curator-bridge'
export const inject = ['tools']

export function apply(ctx, config) {
  if (!ctx.tools || typeof ctx.tools.register !== 'function') {
    return
  }

  // Register using defineTool from pinned dsh-tools
  // Note: importing defineTool from '@deepseek-ai/dsh-tools' requires the
  // package to be available in the DSH runtime module resolution path.
  // Since the plugin is loaded by the DSH Cordis loader, we use the
  // tools.register API which is the actual available contract in rc.1.

  ctx.tools.register({
    name: 'knowledge_curator_commit',
    description: 'Preset-scoped: Curate an AssertionSet and commit via CurationCommitWorkflow.',
    parameters: {
      source_ref_id: { type: 'string', required: true },
      source_fingerprint: { type: 'string', required: true },
      assertion_set: { type: 'object', required: true },
      metadata: { type: 'object', required: false },
      trace: { type: 'object', required: false },
    },
    output: {
      schema: {
        status: { type: 'string' },
        commit_attempted: { type: 'boolean' },
        blocked_reason: { type: 'string' },
      },
      render: (_args, value) => [
        { type: 'text', text: JSON.stringify(value) },
      ],
    },
    async execute(args, exec) {
      return await callBridge('curate_and_commit', args, exec?.signal)
    },
  })

  ctx.tools.register({
    name: 'knowledge_curator_revision',
    description: 'Preset-scoped: Publish a revision via RevisionPublicationWorkflow.',
    parameters: {
      package: { type: 'object', required: true },
      target_commit_request: { type: 'object', required: true },
      approval: { type: 'object', required: false },
    },
    output: {
      schema: {
        status: { type: 'string' },
        error: { type: 'string' },
      },
      render: (_args, value) => [
        { type: 'text', text: JSON.stringify(value) },
      ],
    },
    async execute(args, exec) {
      return await callBridge('revise', args, exec?.signal)
    },
  })
}
