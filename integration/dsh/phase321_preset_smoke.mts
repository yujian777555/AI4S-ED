/**
 * Phase 3.2.1 preset smoke — vitest entry (scaffold requires vitest context).
 * Run from DSH_SRC: pnpm exec vitest run --root . <this file>
 */
import { execFileSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const AI4S_ED_ROOT = resolve(HERE, '..', '..')
const DSH_SRC = process.env.DSH_SRC ?? 'C:/dsh-src'
const PRODUCT_BUNDLE = join(AI4S_ED_ROOT, 'dsh', 'knowledge-curator')
const RESULT_PATH = join(AI4S_ED_ROOT, 'results', 'phase-03-2-1-dsh-preset-live.json')
const EXPECTED_TOOL = 'mcp__knowledge_curator__curate_assertion_set'
const PRESET_ID = 'knowledge-curator'
const UPSTREAM_COMMIT = '4878cdabd87d4041bdaff61d04c966883b9fd07a'

const FIXTURE = {
  ref_id: 'ED-2025-0042',
  metadata: {
    title: 'Fixture Paper', authors: ['A. Author'], year: 2024,
    source: 'Journal', doi: '10.0000/fixture', stable_id: 'ST-FIXTURE',
  },
  quality_grade: 'B',
  assertions: [{
    id: 'AS-001', ref_id: 'ED-2025-0042',
    subject: { eddo_class: 'Membrane', resolved_entity: 'eddo:membrane:nafion117', original_mention: 'Nafion 117' },
    property: 'hasEnergyConsumption',
    object: { value: 1.42, unit: 'kWh/m3', value_type: 'number', uncertainty: 0.05 },
    conditions: [
      { eddo_class: 'Temperature', value: 298.15, unit: 'K' },
      { eddo_class: 'FeedNaCl', value: 0.05, unit: 'mol/L' },
    ],
    provenance: { locator: 'T12', sentence: 'Table 3 row2' },
    claim_type: 'measurement', source_claim_origin: 'primary',
    confidence: 'medium', quality: 0.87,
  }],
}

function git(args: string[]): string {
  return execFileSync('git', args, { cwd: DSH_SRC, encoding: 'utf8' }).trim()
}

async function runSmoke() {
  const errors: string[] = []
  const warnings: string[] = []
  const result: Record<string, unknown> = {
    upstream_commit: git(['rev-parse', 'HEAD']),
    dsh_version: '0.2.0-rc.1',
    product_bundle_profile_installed: false,
    bundle_install_method: 'NONE',
    runtime_preset_activation_passed: false,
    preset_broken: true,
    preset_mount_tested: false,
    preset_mount_passed: false,
    composed_preset_id: '',
    persona_visible: false,
    expected_tool_visible: false,
    live_test_attempted: false,
    live_test_passed: false,
    tool_call_count: 0,
    tool_result_count: 0,
    direct_core_summary: {},
    tool_result_summary: {},
    final_response_summary: {},
    summaries_match: false,
    credential_available: Boolean(process.env.DEEPSEEK_API_KEY?.trim()),
    secret_leaked: false,
    dsh_source_clean_before: git(['status', '--porcelain']).length === 0,
    dsh_source_clean_after: false,
    errors, warnings,
  }
  if (result.upstream_commit !== UPSTREAM_COMMIT) errors.push(`DSH commit mismatch: ${result.upstream_commit}`)
  if (!result.dsh_source_clean_before) errors.push('DSH source dirty before test')

  const { launchWebScaffold } = await import(pathToFileURL(join(DSH_SRC, 'apps', 'web', 'tests', 'scaffold.ts')).href)
  process.env.AI4S_KC_PYTHON = process.env.AI4S_KC_PYTHON ?? process.execPath
  process.env.AI4S_KC_WORKSPACE = process.env.AI4S_KC_WORKSPACE ?? AI4S_ED_ROOT
  const live = process.env.LIVE === '1' && result.credential_available

  let web: any
  try {
    // PROFILE_PACKAGE_INSTALL first; EXTRA_OVERLAY_FALLBACK if profile install rejects.
    try {
      web = await launchWebScaffold({
        profile: { packages: [{ dir: PRODUCT_BUNDLE, enabled: true }] },
      })
      result.product_bundle_profile_installed = true
      result.bundle_install_method = 'PROFILE_PACKAGE_INSTALL'
    } catch (pkgExc) {
      warnings.push(`profile.packages install failed: ${pkgExc}`)
      const bundlePatch = join(PRODUCT_BUNDLE, 'cordis.patch.yml')
      web = await launchWebScaffold({
        extraOverlayPath: bundlePatch,
      })
      result.product_bundle_profile_installed = true
      result.bundle_install_method = 'EXTRA_OVERLAY_FALLBACK'
    }
  } catch (exc) {
    errors.push(`launchWebScaffold failed: ${exc}`)
    result.dsh_source_clean_after = git(['status', '--porcelain']).length === 0
    writeResult(result)
    throw new Error(`boot failed: ${exc}`)
  }

  const ctx = web.ctx as any
  try {
    const roster = await ctx.agentPresets.list()
    const row = roster.find((r: any) => r.id === PRESET_ID)
    if (!row) errors.push(`preset not in roster: ${roster.map((r: any) => r.id).join(',')}`)
    else {
      result.runtime_preset_activation_passed = true
      result.preset_broken = Boolean(row.broken)
      if (row.broken) errors.push(`preset broken: ${row.broken}`)
    }

    const handle = await ctx.agents.create({
      sessionId: `kc-preset-${Date.now()}`,
      meta: { cwd: web.workspaceCwd, agentPreset: PRESET_ID },
      agentOptions: { provider: 'deepseek-official', model: process.env.DSH_MODEL ?? 'deepseek-chat' },
      setup: async (agentCtx: any) => { await ctx.agentPresets.mount(agentCtx, PRESET_ID) },
    })
    result.preset_mount_tested = true
    const composed = ctx.agentPresets.composedPreset(handle.agent.ctx)
    result.composed_preset_id = composed ?? ''
    result.preset_mount_passed = composed === PRESET_ID
    if (!result.preset_mount_passed) errors.push(`composedPreset=${composed}`)

    try {
      const messages = handle.agent.session.deriveMessages()
      const sys = messages.find((m: any) => m.role === 'system')
      const text = (sys?.content ?? []).flatMap((b: any) => (b.type === 'text' ? [b.text] : [])).join('')
      result.persona_visible = text.includes('You are the AI4S-ED knowledge_curator')
      if (!result.persona_visible) errors.push('persona text not found')
    } catch (exc) { errors.push(`persona check: ${exc}`) }

    try {
      const schemas = ctx.tools.schemas(handle.agent) ?? []
      const names = schemas.map((s: any) => s.name)
      result.expected_tool_visible = names.includes(EXPECTED_TOOL)
      if (!result.expected_tool_visible) errors.push(`tool missing: ${names.slice(0, 15).join(',')}`)
    } catch (exc) { errors.push(`tools.schemas: ${exc}`) }

    if (live) {
      result.live_test_attempted = true
      const llm = await import(pathToFileURL(join(DSH_SRC, 'node_modules', '@deepseek-ai', 'dsh-llm', 'lib', 'index.js')).href).catch(() => ({} as any))
      const createUserMessage = (llm as any).createUserMessage ?? ((x: any) => x)
      const prompt =
        `Call the tool ${EXPECTED_TOOL} with this assertion_set. ` +
        'Then reply with exactly three lines:\n' +
        'status=<value>\naction=<first decision action>\nconfidence=<first decision confidence>\n' +
        `assertion_set=${JSON.stringify(FIXTURE)}`
      handle.agent.followup(createUserMessage({ content: [{ type: 'text', text: prompt }], source: { kind: 'user' } }))
      await handle.agent.whenIdle()

      const events: any[] = handle.agent.session.snapshotEvents?.() ?? []
      const calls = events.filter((e) => e.type === 'tool/call' && e.data?.name === EXPECTED_TOOL)
      const callSeqs = new Set(calls.map((e) => String(e.seq)))
      const callIds = new Set(calls.map((e) => e.data?.callId).filter(Boolean))
      const results = events.filter((e) => {
        if (e.type !== 'tool/result') return false
        const src = e.sourceEventSeqs ?? e.data?.sourceEventSeqs ?? []
        const seqs = Array.isArray(src) ? src.map(String) : [String(src)]
        const cid = e.data?.message?.source?.callId ?? e.data?.callId
        return seqs.some((s: string) => callSeqs.has(s)) || (cid && callIds.has(cid))
      })
      result.tool_call_count = calls.length
      result.tool_result_count = results.length

      let toolSum: any = {}
      if (results.length) {
        const r = results[0]
        const content = r.data?.message?.content ?? []
        const texts: string[] = []
        for (const block of content) {
          if (block?.content) for (const sub of block.content) if (sub?.text) texts.push(sub.text)
          else if (block?.text) texts.push(block.text)
        }
        try {
          const parsed = JSON.parse(texts.join(''))
          const report = parsed.report ?? parsed
          toolSum = { status: report.status, action: report.decisions?.[0]?.action, confidence: report.decisions?.[0]?.confidence }
        } catch { toolSum = { raw: texts.join('').slice(0, 200) } }
      }
      result.tool_result_summary = toolSum

      const finals = events.filter((e) => String(e.type).includes('assistant') || String(e.type).includes('message'))
      let finalText = ''
      for (const last of finals.slice(-3)) {
        const t = (last.data?.content ?? []).map((b: any) => (b.type === 'text' ? b.text : '')).join('')
        if (t.trim()) finalText = t
      }
      const finalSum: any = {}
      for (const line of finalText.split(/\r?\n/)) {
        const m = line.match(/^(status|action|confidence)\s*[=:]\s*(\S+)/i)
        if (m) finalSum[m[1].toLowerCase()] = m[2]
      }
      result.final_response_summary = finalSum

      const py = process.env.AI4S_KC_PYTHON ?? 'python'
      const out = execFileSync(py, ['-c', `
import json,sys
sys.path.insert(0, r'${AI4S_ED_ROOT}')
import anyio
from knowledge_curator.mcp_server.codec import parse_assertion_set, serialize_curation_report
from knowledge_curator.mcp_server.runtime import create_default_runtime, run_curate
rep = anyio.run(lambda: run_curate(create_default_runtime(), parse_assertion_set(json.loads(sys.argv[1]))))
d = serialize_curation_report(rep)
print(json.dumps({"status": d["status"], "action": d["decisions"][0]["action"], "confidence": d["decisions"][0]["confidence"]}))
`, JSON.stringify(FIXTURE)], { encoding: 'utf8' })
      result.direct_core_summary = JSON.parse(out.trim())
      const keys = ['status', 'action', 'confidence']
      const a = result.direct_core_summary as any
      result.summaries_match = keys.every((k) => a?.[k] && a[k] === (toolSum as any)?.[k] && a[k] === (finalSum as any)?.[k])
      if (!result.summaries_match) errors.push(`A/B/C mismatch ${JSON.stringify({ a, toolSum, finalSum })}`)
      result.live_test_passed = Boolean(result.summaries_match && (result.tool_call_count as number) >= 1 && (result.tool_result_count as number) >= 1)
    } else {
      warnings.push('LIVE not enabled — live turn skipped')
    }
    await handle.dispose?.().catch(() => undefined)
  } finally {
    await web.close?.().catch(() => undefined)
    result.dsh_source_clean_after = git(['status', '--porcelain']).length === 0
    if (!result.dsh_source_clean_after) errors.push('DSH source dirty after test')
  }
  writeResult(result)
  return result
}

function writeResult(result: Record<string, unknown>) {
  writeFileSync(RESULT_PATH, JSON.stringify(result, null, 2) + '\n', 'utf8')
  console.log(JSON.stringify(result, null, 2))
}

// standalone entry
runSmoke().then((result) => {
  const ok = result.runtime_preset_activation_passed && result.preset_mount_passed && result.persona_visible && result.expected_tool_visible
  const live = result.live_test_attempted
  process.exit(ok && (live ? result.live_test_passed : true) ? 0 : 1)
}).catch((exc) => { console.error(exc); process.exit(1) })