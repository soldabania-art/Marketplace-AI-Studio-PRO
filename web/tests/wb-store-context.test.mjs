import test from 'node:test'
import assert from 'node:assert/strict'

import {createWbStoreContext} from '../lib/wbStoreContext.mjs'

test('a delayed store A result cannot update store B',()=>{
  const context=createWbStoreContext('store-a')
  const request=context.beginRequest()
  context.switchStore('store-b')
  assert.equal(context.owns(request),false)
})

test('a delayed store A result cannot update after A to B to A',()=>{
  const context=createWbStoreContext('store-a')
  const oldRequest=context.beginRequest()
  context.switchStore('store-b')
  context.switchStore('store-a')
  assert.equal(context.owns(oldRequest),false)
})

test('only the latest request in a store owns the result',()=>{
  const context=createWbStoreContext('store-a')
  const oldRequest=context.beginRequest()
  const latestRequest=context.beginRequest()
  assert.equal(context.owns(oldRequest),false)
  assert.equal(context.owns(latestRequest),true)
})

test('partial consent is bound to the exact store and candidate token',()=>{
  const context=createWbStoreContext('store-a')
  const consent=context.bindPartialConsent('candidate-a')
  assert.equal(context.acceptsPartialConsent(consent,'candidate-a'),true)
  assert.equal(context.acceptsPartialConsent(consent,'edited-candidate'),false)
  context.switchStore('store-b')
  assert.equal(context.acceptsPartialConsent(consent,'candidate-a'),false)
})
