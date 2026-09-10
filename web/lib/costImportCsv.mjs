const MAX_ROWS=500

function separatorFor(text){
  const first=(text.replace(/^\uFEFF/,'').split(/\r?\n/,1)[0]||'')
  const counts={';':0,',':0,'\t':0}
  let quoted=false
  for(const char of first){
    if(char==='"')quoted=!quoted
    else if(!quoted&&Object.hasOwn(counts,char))counts[char]+=1
  }
  return Object.entries(counts).sort((a,b)=>b[1]-a[1])[0][0]
}

export function parseCostCsv(source){
  const text=String(source||'').replace(/^\uFEFF/,'')
  if(!text.trim())throw new Error('Файл пуст.')
  const separator=separatorFor(text)
  const rows=[]; let row=[]; let cell=''; let quoted=false
  for(let index=0;index<text.length;index+=1){
    const char=text[index]
    if(char==='"'){
      if(quoted&&text[index+1]==='"'){cell+='"';index+=1}else quoted=!quoted
    }else if(char===separator&&!quoted){row.push(cell.trim());cell=''}
    else if((char==='\n'||char==='\r')&&!quoted){
      if(char==='\r'&&text[index+1]==='\n')index+=1
      row.push(cell.trim());cell=''
      if(row.some(value=>value!==''))rows.push(row)
      row=[]
    }else cell+=char
  }
  if(quoted)throw new Error('В CSV есть незакрытая кавычка.')
  row.push(cell.trim()); if(row.some(value=>value!==''))rows.push(row)
  if(rows.length<2)throw new Error('Нужны строка заголовков и минимум одна строка данных.')
  const headers=rows[0].map(value=>value.trim())
  if(headers.some(value=>!value))throw new Error('Все колонки должны иметь заголовки.')
  if(new Set(headers.map(value=>value.toLocaleLowerCase('ru-RU'))).size!==headers.length)throw new Error('Заголовки колонок не должны повторяться.')
  if(rows.length-1>MAX_ROWS)throw new Error(`За один раз можно проверить не более ${MAX_ROWS} строк.`)
  const records=rows.slice(1).map((values,index)=>({
    rowNumber:index+2,
    values:Object.fromEntries(headers.map((header,column)=>[header,values[column]??''])),
  }))
  return {separator,headers,records}
}

const normalized=value=>String(value||'').toLocaleLowerCase('ru-RU').replace(/ё/g,'е').replace(/[^a-zа-я0-9]+/g,'')

const aliases={
  nm_id:['nmid','nm','артикулwb','кодwb','номенклатураwb'],
  operating_model:['model','operatingmodel','модель','бизнесмодель','типтовара'],
  row_source:['source','document','источник','документ','основание'],
  purchase_price:['purchaseprice','закупочнаяцена','цена закупки','себестоимостьтовара'],
  inbound_logistics:['inboundlogistics','доставкадосклада','карго','входящаялогистика'],
  customs:['customs','таможня','пошлина','таможенныерасходы'],
  fulfillment_unit:['fulfillmentunit','фулфилмент','обработкаединицы','логистикаединицы'],
  packaging:['packaging','упаковка','маркировка'],
  materials:['materials','сырье','материалы','комплектующие'],
  direct_labor:['directlabor','работа','сдельнаяработа','оплататруда'],
  equipment:['equipment','оборудование','амортизация','энергия'],
  overhead:['overhead','накладные','цеховыерасходы','аренда'],
  net_purchase:['netpurchase','закупкапослескидок','чистаязакупка'],
  brand_fee:['brandfee','платежбренду','роялти'],
}

export function suggestCostMapping(headers,componentKeys=[]){
  const byNormalized=new Map(headers.map(header=>[normalized(header),header]))
  const find=key=>{
    for(const alias of [key,...(aliases[key]||[])]){
      const match=byNormalized.get(normalized(alias)); if(match)return match
    }
    return ''
  }
  return {nm_id:find('nm_id'),operating_model:find('operating_model'),row_source:find('row_source'),
    components:Object.fromEntries(componentKeys.map(key=>[key,find(key)]))}
}

export function normalizeMoney(value){
  const compact=String(value??'').replace(/[\s\u00a0₽]/g,'').replace(',','.')
  if(compact==='')return null
  if(!/^\d+(?:\.\d{1,2})?$/.test(compact))throw new Error('Ожидается неотрицательная сумма с точностью до копеек.')
  const numeric=Number(compact)
  if(!Number.isFinite(numeric)||numeric>100000000)throw new Error('Сумма вне допустимого диапазона.')
  return compact
}

export function normalizeCostModel(value){
  const key=normalized(value)
  if(['reseller','реселлер','импортер'].includes(key))return 'reseller'
  if(['manufacturer','производитель','производство'].includes(key))return 'manufacturer'
  if(['distributor','дистрибьютор'].includes(key))return 'distributor'
  return ''
}

export const COST_IMPORT_MAX_ROWS=MAX_ROWS
