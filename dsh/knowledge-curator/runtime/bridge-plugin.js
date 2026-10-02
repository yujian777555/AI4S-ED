/**
 * AI4S Knowledge Curator — DSH Native Bridge Plugin (SI-4-R4)
 *
 * Registers DSH-native preset-scoped tools for internal workflow access.
 * Calls Python bridge via committed stdio entrypoint (no temp file generation).
 *
 * Tools: knowledge_curator_commit, knowledge_curator_revision
 * These are preset-scoped DSH-native tools, NOT public MCP tools.
 */

import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

const execFileAsync = promisify(execFile)

const PYTHON_CMD = process.env.AI4S_KC_PYTHON || 'python'
const WORKSPACE = process.env.AI4S_KC_WORKSPACE || process.cwd()

/**
 * Call the committed Python bridge entrypoint via stdio.
 */
async function callBridge(action, payload) {
  const { stdout, stderr } = await execFileAsync(
    PYTHON_CMD,
    ['-m', 'system.curator_agent_bridge_stdio', action],
    {
      cwd: WORKSPACE,
      timeout: 30000,
      env: { ...process.env, PYTHONPATH: WORKSPACE },
      input: JSON.stringify(payload),
      maxBuffer: 1024 * 1024,
    }
  )
  const result = JSON.parse(stdout.trim())
  if (result.error) {
    throw new Error(result.error)
  }
  return result
}

/**
 * DSH plugin entry — registers preset-scoped native tools.
 */
export default class CuratorBridgePlugin {
  static inject = ['tools']

  constructor(ctx, config) {
    this.ctx = ctx
    this.config = config || {}
  }

  async [Symbol.asyncDispose]() {}

  async start() {
    if (!this.ctx.tools || typeof this.ctx.tools.register !== 'function') {
      return
    }

    // Preset-scoped DSH-native tool: knowledge_curator_commit
    this.ctx.tools.register({
      name: 'knowledge_curator_commit',
      description: 'Preset-scoped: Curate an AssertionSet and commit via CurationCommitWorkflow.',
      parameters: {
        type: 'object',
        properties: {
          source_ref_id: { type: 'string', description: 'Source reference ID' },
          source_fingerprint: { type: 'string', description: 'Source fingerprint' },
          assertion_set: { type: 'object', description: 'AssertionSet to curate and commit' },
          metadata: { type: 'object', description: 'Optional metadata' },
          trace: { type: 'object', description: 'Optional trace context' },
        },
        required: ['source_ref_id', 'source_fingerprint', 'assertion_set'],
      },
      output: {
        type: 'object',
        properties: {
          status: { type: 'string' },
          commit_attempted: { type: 'boolean' },
          blocked_reason: { type: 'string' },
        },
      },
      execute: async (args) => {
        const result = await callBridge('curate_and_commit', args)
        return { type: 'text', text: JSON.stringify(result) }
      },
    })

    // Preset-scoped DSH-native tool: knowledge_curator_revision
    this.ctx.tools.register({
      name: 'knowledge_curator_revision',
      description: 'Preset-scoped: Publish a revision via RevisionPublicationWorkflow.',
      parameters: {
        type: 'object',
        properties: {
          package: { type: 'object', description: 'RevisionPackage' },
          target_commit_request: { type: 'object', description: 'Target CommitRequest' },
          approval: { type: 'object', description: 'Optional RevisionApproval' },
        },
        required: ['package', 'target_commit_request'],
      },
      output: {
        type: 'object',
        properties: {
          status: { type: 'string' },
          error: { type: 'string' },
        },
      },
      execute: async (args) => {
        const result = await callBridge('revise', args)
        return { type: 'text', text: JSON.stringify(result) }
      },
    })
  }
}
