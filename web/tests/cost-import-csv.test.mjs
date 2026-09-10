import test from 'node:test'
import assert from 'node:assert/strict'
import {normalizeCostModel,normalizeMoney,parseCostCsv,suggestCostMapping} from '../lib/costImportCsv.mjs'

test('parses semicolon CSV with quoted delimiters and Russian headers',()=>{
  const parsed=parseCostCsv('\uFEFFАртикул WB;Сырье;Источник\r\n123;"1 250,50";"Техкарта; №7"\r\n')
  assert.equal(parsed.separator,';')
  assert.equal(parsed.records[0].values['Источник'],'Техкарта; №7')
  assert.equal(normalizeMoney(parsed.records[0].values['Сырье']),'1250.50')
})

test('suggests only explicit known columns',()=>{
  assert.deepEqual(suggestCostMapping(['nmId','Материалы','Документ'],['materials']),{
    nm_id:'nmId',operating_model:'',row_source:'Документ',components:{materials:'Материалы'},
  })
})

test('rejects duplicate headers, too many rows and malformed money',()=>{
  assert.throws(()=>parseCostCsv('nmId;nmId\n1;2'),/повторяться/)
  const oversized=['nmId',...Array.from({length:501},(_,index)=>String(index+1))].join('\n')
  assert.throws(()=>parseCostCsv(oversized),/не более 500/)
  assert.throws(()=>normalizeMoney('-10'),/неотрицательная/)
})

test('normalizes supported Russian business models without guessing unknown values',()=>{
  assert.equal(normalizeCostModel('Производство'),'manufacturer')
  assert.equal(normalizeCostModel('непонятная модель'),'')
})
