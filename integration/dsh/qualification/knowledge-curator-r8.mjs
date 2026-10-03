// SI-4-R8 Real Pinned DSH Runtime Execution
// Run: node --experimental-vm-modules integration/dsh/qualification/knowledge-curator-r8.mjs

import { createHash } from 'node:crypto'
import { readFileSync, copyFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const ROOT = join(import.meta.dirname, '..', '..', '..')
const DSH_SRC = 'C:\\dsh-src'
const PLUGIN_PATH = join(ROOT, 'dsh', 'knowledge-curator', 'runtime', 'bridge-plugin.js')
const COPIED_PATH = join(DSH_SRC, 'packages', 'preset', 'agent-preset-registry', 'tests', 'fixtures', 'plugins', 'curator-bridge.js')

function sha256(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex')
}

async function main() {
  console.log('=== SI-4-R8 Exact Pinned DSH Runtime Execution ===')
  console.log('Pinned DSH: 0.2.0-rc.1')
  console.log('Pinned SHA: 4878cdabd87d4041bdaff61d04c966883b9fd07a')

  // Verify DSH HEAD
  const { execSync } = await import('node:child_process')
  const dshHead = execSync('git rev-parse HEAD', { cwd: DSH_SRC }).toString().trim()
  console.log('DSH HEAD:', dshHead)
  if (dshHead !== '4878cdabd87d4041bdaff61d04c966883b9fd07a') {
    console.error('FAIL: DSH HEAD mismatch')
    process.exit(1)
  }
  console.log('DSH HEAD equals pinned SHA: PASS')

  // Verify plugin SHA
  const shippedSha = sha256(PLUGIN_PATH)
  const copiedSha = sha256(COPIED_PATH)
  console.log('AI4S plugin SHA:', shippedSha)
  console.log('DSH copy SHA:  ', copiedSha)
  if (shippedSha !== copiedSha) {
    console.error('FAIL: plugin SHA mismatch')
    process.exit(1)
  }
  console.log('Plugin SHA equal: PASS')

  // Import DSH packages from pinned workspace
  process.chdir(DSH_SRC)
  const { Context } = await import('@deepseek-ai/cordis')
  const Loader = (await import('@deepseek-ai/cordis-plugin-loader')).default
  const Group = (await import('@deepseek-ai/cordis-plugin-group')).default
  const LlmRuntime = (await import('@deepseek-ai/dsh-llm')).default
  const SessionStore = (await import('@deepseek-ai/dsh-session')).default
  const SessionId = (await import('@deepseek-ai/dsh-session')).SessionId
  const SessionProjectionRegistry = (await import('@deepseek-ai/dsh-session-projection')).default
  const SystemPrompt = (await import('@deepseek-ai/dsh-system-prompt')).default
  const ToolRuntime = (await import('@deepseek-ai/dsh-tools')).default
  const AgentRegistry = (await import('@deepseek-ai/dsh-agent')).default
  const AgentLoop = (await import('@deepseek-ai/dsh-agent-loop')).default
  const AgentPresets = (await import('./packages/preset/agent-preset-registry/src/index.ts')).default

  console.log('Real DSH packages imported: PASS')

  // Create real Context
  const ctx = new Context()
  ctx.baseUrl = new URL('./packages/preset/agent-preset-registry/tests/fixtures/', import.meta.url).href

  await ctx.plugin(Loader)
  ctx.loader.builtins.group = Group
  await ctx.plugin(LlmRuntime)
  await ctx.plugin(SessionStore)
  await ctx.plugin(SessionProjectionRegistry)
  await ctx.plugin(SystemPrompt, { personaPrefix: '' })
  await ctx.plugin(ToolRuntime)
  await ctx.plugin(AgentRegistry)
  await ctx.plugin(AgentLoop, { agents: [] })
  await ctx.plugin(AgentPresets, { default: 'knowledge-curator' })

  console.log('Real Context started: PASS')
  console.log('Real ToolRuntime mounted: PASS')
  console.log('Real AgentPresetRegistry mounted: PASS')

  // Register preset with exact shipped plugin
  const pluginUrl = 'file:///' + COPIED_PATH.replace(/\\/g, '/')
  await ctx.plugin({
    inject: ['agentPresets'],
    async* apply(child) {
      yield await child.agentPresets.register({
        id: 'knowledge-curator',
        plugins: [{ name: pluginUrl, config: {} }],
      })
    },
  })

  console.log('knowledge-curator preset registered: PASS')

  // Create real Agent
  const handle = await ctx.agents.create({
    sessionId: SessionId('kc-r8'),
    setup: async (agentCtx) => {
      await ctx.agentPresets.mount(agentCtx, 'knowledge-curator')
    },
  })
  const agent = handle.agent

  console.log('knowledge-curator mounted into real Agent: PASS')

  // ctx.tools.schemas(agent)
  const scoped = ctx.tools.schemas(agent).map((row) => row.name)
  console.log('ctx.tools.schemas(agent):', JSON.stringify(scoped))

  const hasCommit = scoped.includes('knowledge_curator_commit')
  const hasRevision = scoped.includes('knowledge_curator_revision')
  console.log('native curator tools visible:', hasCommit && hasRevision ? 'PASS' : 'FAILED')

  // global schemas
  const global = ctx.tools.schemas().map((row) => row.name)
  console.log('ctx.tools.schemas() global:', JSON.stringify(global))

  // Execute commit via real ctx.tools
  const { ToolCallId } = await import('@deepseek-ai/dsh-llm')
  const commitPayload = {
    source_ref_id: 'ED-R8',
    source_fingerprint: 'fp-r8-001',
    assertion_set: {
      ref_id: 'ED-R8',
      metadata: { title: 'R8 Test', authors: ['A'], year: 2024, source: 'J', doi: '10.0/r8', stable_id: 'ST-R8' },
      assertions: [{
        id: 'AS-001', ref_id: 'ED-R8',
        subject: { eddo_class: 'Membrane', resolved_entity: 'eddo:membrane:bpm', original_mention: 'BPM' },
        property: 'hasEnergyConsumption',
        object: { value: 1.42, unit: 'kWh/m3', value_type: 'number', uncertainty: 0.05 },
        conditions: [{ eddo_class: 'Temperature', value: 298.15, unit: 'K' }],
        provenance: { locator: 'p.1', sentence: 'energy is 1.42' },
        claim_type: 'measurement', source_claim_origin: 'primary',
        confidence: 'medium', quality: 0.85,
      }],
    },
    metadata: {}, trace: {},
  }

  const commit = await ctx.tools.execute({
    signal: new AbortController().signal,
    callId: ToolCallId('kc-r8-commit'),
    name: 'knowledge_curator_commit',
    arguments: commitPayload,
    agent,
  })

  console.log('commit ToolExecutionResult:', JSON.stringify({ isError: commit.isError, value: commit.value }))
  if (!commit.isError && commit.value?.status === 'published' && commit.value?.commit_attempted === true) {
    console.log('native §5 canonical result: PASS')
  } else {
    console.log('native §5 canonical result: FAILED')
  }

  // Execute revision via real ctx.tools
  const revisionPayload = {
    package: {
      package_id: 'pkg-r8', work_id: 'w-r6',
      prior_source_version_id: 'sv-prior-r6', new_source_version_id: 'sv-new-r6',
      relation: 'preprint_to_journal', prior_ref_id: 'ED-PRIOR', new_ref_id: 'ED-NEW',
      target_assertions: [{
        id: 'AS-001', ref_id: 'ED-NEW',
        subject: { eddo_class: 'Membrane', resolved_entity: 'eddo:membrane:bpm', original_mention: 'BPM' },
        property: 'hasEnergyConsumption',
        object: { value: 1.5, unit: 'kWh/m3', value_type: 'number', uncertainty: 0.05 },
        conditions: [{ eddo_class: 'Temperature', value: 298.15, unit: 'K' }],
        provenance: { locator: 'p.1', sentence: 'energy is 1.5' },
        claim_type: 'measurement', source_claim_origin: 'primary',
        confidence: 'medium', quality: 0.85,
      }],
    },
    target_commit_request: {
      source: { ref_id: 'ED-NEW', source_fingerprint: 'fp-new-r6' },
      assertion_set: {
        ref_id: 'ED-NEW',
        metadata: { title: 'R8 J', authors: ['A'], year: 2024, source: 'J', doi: '10.0/j', stable_id: 'ST-J' },
        assertions: [{
          id: 'AS-001', ref_id: 'ED-NEW',
          subject: { eddo_class: 'Membrane', resolved_entity: 'eddo:membrane:bpm', original_mention: 'BPM' },
          property: 'hasEnergyConsumption',
          object: { value: 1.5, unit: 'kWh/m3', value_type: 'number', uncertainty: 0.05 },
          conditions: [{ eddo_class: 'Temperature', value: 298.15, unit: 'K' }],
          provenance: { locator: 'p.1', sentence: 'energy is 1.5' },
          claim_type: 'measurement', source_claim_origin: 'primary',
          confidence: 'medium', quality: 0.85,
        }],
      },
      report: {
        report_id: 'r-r8v', source_ref_id: 'ED-NEW', status: 'successful',
        completeness: { status: 'ok' },
        decisions: [{ assertion_id: 'AS-001', action: 'accept', confidence: 'medium', reason: 'valid' }],
      },
    },
  }

  const revision = await ctx.tools.execute({
    signal: new AbortController().signal,
    callId: ToolCallId('kc-r8-revision'),
    name: 'knowledge_curator_revision',
    arguments: revisionPayload,
    agent,
  })

  console.log('revision ToolExecutionResult:', JSON.stringify({ isError: revision.isError, value: revision.value }))
  if (!revision.isError && revision.value?.status === 'approval_required') {
    console.log('native §7 canonical result: PASS')
  } else {
    console.log('native §7 canonical result: FAILED')
  }

  // Cleanup
  await ctx.fiber.dispose()
  console.log('')
  console.log('=== R8 Qualification Complete ===')
}

main().catch((err) => {
  console.error('R8 qualification failed:', err.message)
  console.error(err.stack)
  process.exit(1)
})
