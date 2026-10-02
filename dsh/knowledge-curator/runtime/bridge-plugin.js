/**
 * AI4S Knowledge Curator — DSH Native Bridge Plugin
 *
 * Registers DSH-native tools (NOT MCP tools) for internal workflow access.
 * Calls Python CuratorAgentBridge via subprocess.
 *
 * This plugin is loaded by the knowledge-curator preset via cordis.patch.yml.
 */

import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

const execFileAsync = promisify(execFile)

const PYTHON_CMD = process.env.AI4S_KC_PYTHON || 'python'
const WORKSPACE = process.env.AI4S_KC_WORKSPACE || process.cwd()

/**
 * Call the Python CuratorAgentBridge via subprocess.
 */
async function callBridge(action, payload) {
  const script = `
import json, sys, asyncio
sys.path.insert(0, r'${WORKSPACE}')
sys.path.insert(0, r'${WORKSPACE}/dsh/knowledge-curator')

from system.curator_agent_bridge import CuratorAgentBridge
from system.workflows.curation_commit import CurationCommitWorkflow
from system.application_composition import _extract_commit_deps, _validate_commit_deps
from system.composition import CuratorDependencies, compose_system_runtime
from knowledge_curator.core.commit import DocumentCommitCoordinator

def build_bridge():
    import os
    os.environ.setdefault('AI4S_SYSTEM_ADAPTER_FACTORY', 'integration.system.fixtures.si2b_provider:create_si2a_provider_bundle')
    from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle
    bundle = create_si2a_provider_bundle()
    curator_raw = bundle['curator']
    commit_deps = _extract_commit_deps(bundle)
    _validate_commit_deps(commit_deps)
    curator_deps = CuratorDependencies(
        repository=curator_raw['repository'],
        ontology=curator_raw['ontology'],
        mechanism_validator=curator_raw['mechanism_validator'],
        provider_identity=curator_raw['provider_identity'],
    )
    system_rt = compose_system_runtime(curator_deps=curator_deps, evidence_deps=None)
    doc_commit = DocumentCommitCoordinator(
        commit_store=commit_deps.commit_store,
        structural_store=commit_deps.structural_store,
        vector_index=commit_deps.vector_index,
        usdo_store=commit_deps.usdo_store,
        version_store=commit_deps.version_store,
    )
    workflow = CurationCommitWorkflow(
        curator_runtime=system_rt.curator_runtime,
        commit_coordinator=doc_commit,
        provider_identity='test',
    )
    return CuratorAgentBridge(curation_workflow=workflow)

action = sys.argv[1] if len(sys.argv) > 1 else ''
payload = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
bridge = build_bridge()

if action == 'curate_and_commit':
    result = asyncio.run(bridge.curate_and_commit(
        source_ref_id=payload.get('source_ref_id', ''),
        source_fingerprint=payload.get('source_fingerprint', ''),
        assertion_set=payload.get('assertion_set', {}),
        metadata=payload.get('metadata', {}),
        trace=payload.get('trace', {}),
    ))
    print(json.dumps({'status': result.status, 'commit_attempted': result.commit_attempted}))
elif action == 'revise':
    result = asyncio.run(bridge.revise(
        package=payload.get('package', {}),
        target_commit_request=payload.get('target_commit_request', {}),
    ))
    print(json.dumps({'status': result.status}))
else:
    print(json.dumps({'error': 'unknown action'}))
`

  const scriptPath = `${WORKSPACE}/_bridge_call.py`
  const fs = await import('node:fs')
  fs.writeFileSync(scriptPath, script, 'utf-8')

  try {
    const { stdout } = await execFileAsync(PYTHON_CMD, [scriptPath, action, JSON.stringify(payload)], {
      cwd: WORKSPACE,
      timeout: 30000,
      env: { ...process.env, PYTHONPATH: WORKSPACE },
    })
    return JSON.parse(stdout.trim().split('\n').pop())
  } finally {
    try { fs.unlinkSync(scriptPath) } catch {}
  }
}

/**
 * DSH plugin entry — registers native tools for the knowledge-curator preset.
 */
export default class CuratorBridgePlugin {
  static inject = ['tools']

  constructor(ctx, config) {
    this.ctx = ctx
    this.config = config || {}
  }

  async [Symbol.asyncDispose]() {}

  async start() {
    // Register native DSH tool: curate_and_commit
    if (this.ctx.tools && typeof this.ctx.tools.register === 'function') {
      this.ctx.tools.register({
        name: 'curate_and_commit',
        description: 'Internal: Curate an AssertionSet and commit via CurationCommitWorkflow.',
        parameters: {
          type: 'object',
          properties: {
            source_ref_id: { type: 'string' },
            source_fingerprint: { type: 'string' },
            assertion_set: { type: 'object' },
          },
          required: ['source_ref_id', 'source_fingerprint', 'assertion_set'],
        },
        execute: async (args) => {
          const result = await callBridge('curate_and_commit', args)
          return { type: 'text', text: JSON.stringify(result) }
        },
      })

      // Register native DSH tool: revise
      this.ctx.tools.register({
        name: 'revise',
        description: 'Internal: Publish a revision via RevisionPublicationWorkflow.',
        parameters: {
          type: 'object',
          properties: {
            package: { type: 'object' },
            target_commit_request: { type: 'object' },
          },
          required: ['package', 'target_commit_request'],
        },
        execute: async (args) => {
          const result = await callBridge('revise', args)
          return { type: 'text', text: JSON.stringify(result) }
        },
      })
    }
  }
}
