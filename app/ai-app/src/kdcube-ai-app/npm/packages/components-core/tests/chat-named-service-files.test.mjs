import assert from 'node:assert/strict'
import { test } from 'node:test'
import { hydrateHistoricalConversation } from '../dist/chat/index.js'

test('historical named-service search results do not become downloadable files', () => {
  const turns = hydrateHistoricalConversation({
    conversation_id: 'conv-1',
    turns: [
      {
        turn_id: 'turn-1',
        artifacts: [
          {
            type: 'artifact:conv.artifacts.stream',
            ts: '2026-06-20T04:03:00.000Z',
            data: {
              payload: {
                items: [
                  {
                    marker: 'subsystem',
                    format: 'json',
                    artifact_name: 'named_service.search_results.mem.ns_123',
                    title: 'Named service search results',
                    extra: {
                      sub_type: 'named_service.search_results',
                      search_id: 'ns_123',
                    },
                    ts_first: 1781928180000,
                    text: JSON.stringify({
                      type: 'named_service.search_results',
                      namespace: 'mem',
                      search_scope: 'mem:record',
                      query: 'family son Timur born',
                      items: [
                        {
                          id: 'mem:record:mem_803986c10e324a16b05a3ba109237c7c',
                          kind: 'object.ref',
                          label: 'I was born in 1984. My son Timur was born in 2009',
                          ref: 'mem:record:mem_803986c10e324a16b05a3ba109237c7c',
                          object_ref: 'mem:record:mem_803986c10e324a16b05a3ba109237c7c',
                          namespace: 'mem',
                          search_scope: 'mem:record',
                          object_kind: 'memory.record',
                          mime: '',
                          filename: '',
                          data: {
                            source: 'named_services.search_result',
                            object_ref: 'mem:record:mem_803986c10e324a16b05a3ba109237c7c',
                          },
                        },
                      ],
                    }),
                  },
                ],
              },
            },
          },
        ],
      },
    ],
  })

  assert.equal(turns.length, 1)
  const searches = turns[0].artifacts.filter((artifact) => artifact.kind === 'named_service_search')
  assert.equal(searches.length, 1)
  assert.equal(searches[0].surface, 'artifacts')
  assert.equal(turns[0].artifacts.filter((artifact) => artifact.kind === 'file').length, 0)
})

test('historical timeline text stays on the timeline surface', () => {
  const turns = hydrateHistoricalConversation({
    conversation_id: 'conv-1',
    turns: [
      {
        turn_id: 'turn-1',
        artifacts: [
          {
            type: 'artifact:conv.timeline_text.stream',
            ts: '2026-06-20T04:04:00.000Z',
            data: {
              payload: {
                items: [
                  {
                    artifact_name: 'timeline_text.react.decision.1.0',
                    ts_first: 1781928240000,
                    text: 'Reading the current task to get its existing tags...',
                  },
                ],
              },
            },
          },
        ],
      },
    ],
  })

  const timelineArtifacts = turns[0].artifacts.filter((artifact) => artifact.kind === 'timeline')
  assert.equal(timelineArtifacts.length, 1)
  assert.equal(timelineArtifacts[0].surface, 'timeline')
  assert.equal(turns[0].artifacts.filter((artifact) => artifact.surface === 'artifacts').length, 0)
})

test('historical chat.files events still hydrate downloadable fi files', () => {
  const turns = hydrateHistoricalConversation({
    conversation_id: 'conv-1',
    turns: [
      {
        turn_id: 'turn-1',
        artifacts: [
          {
            type: 'artifact:conv.artifacts.events',
            ts: '2026-06-20T04:05:00.000Z',
            data: {
              payload: {
                items: [
                  {
                    type: 'chat.files',
                    event: {
                      step: 'files',
                      status: 'completed',
                    },
                    data: {
                      items: [
                        {
                          filename: 'report.pdf',
                          mime: 'application/pdf',
                          logical_path: 'fi:conv_conv-1.turn_2026-06-20.outputs/report.pdf',
                          description: 'Generated report',
                        },
                      ],
                    },
                  },
                ],
              },
            },
          },
        ],
      },
    ],
  })

  const files = turns[0].artifacts.filter((artifact) => artifact.kind === 'file')
  assert.equal(files.length, 1)
  assert.equal(files[0].surface, 'files')
  assert.equal(files[0].filename, 'report.pdf')
})
