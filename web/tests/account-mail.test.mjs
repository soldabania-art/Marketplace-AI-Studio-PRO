import test from 'node:test'
import assert from 'node:assert/strict'
import { createEmailConfirmation, verificationRequestMessage } from '../lib/accountMail.mjs'

test('opening a mail confirmation does not consume it; double confirmation shares one POST', async () => {
  const calls = []
  let finish
  const controller = createEmailConfirmation('one-time-test-token', (...args) => {
    calls.push(args)
    return new Promise(resolve => { finish = resolve })
  })
  assert.equal(calls.length, 0)
  const first = controller.confirm()
  const second = controller.confirm()
  assert.equal(calls.length, 1)
  assert.equal(calls[0][1].method, 'POST')
  assert.deepEqual(JSON.parse(calls[0][1].body), { action: 'confirm', token: 'one-time-test-token' })
  finish({ ok: true, json: async () => ({ email_verified: true }) })
  assert.deepEqual(await first, { confirmed: true })
  assert.deepEqual(await second, { confirmed: true })
  await controller.confirm()
  assert.equal(calls.length, 1)
})

test('missing tokens never submit and uncertain responses never claim confirmation', async () => {
  let calls = 0
  const request = async () => { calls++; throw new Error('secret response body') }
  assert.ok((await createEmailConfirmation('', request).confirm()).error)
  assert.equal(calls, 0)
  const result = await createEmailConfirmation('token', request).confirm()
  assert.equal(result.confirmed, undefined)
  assert.ok(!result.error.includes('secret response body'))
  assert.equal(calls, 1)
  const malformed = await createEmailConfirmation('token', async () => ({ ok: true, json: async () => ({ ok: true }) })).confirm()
  assert.equal(malformed.confirmed, undefined)
})

test('queued and unknown delivery statuses do not claim mail was sent', () => {
  assert.match(verificationRequestMessage('queued'), /очередь/)
  assert.match(verificationRequestMessage('provider_accepted'), /не подтверждена/)
  assert.match(verificationRequestMessage('email_provider_not_configured'), /недоступна/)
  assert.match(verificationRequestMessage('not_required'), /уже подтверждён/)
})
