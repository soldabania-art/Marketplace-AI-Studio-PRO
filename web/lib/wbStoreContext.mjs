export function createWbStoreContext(initialStoreId=''){
  let storeId=initialStoreId
  let generation=0
  let latestRequest=0

  return {
    switchStore(nextStoreId){
      if(nextStoreId===storeId)return false
      storeId=nextStoreId
      generation+=1
      latestRequest+=1
      return true
    },
    currentStore(){return storeId},
    beginRequest(){
      latestRequest+=1
      return {storeId,generation,requestId:latestRequest}
    },
    owns(request){
      return request?.storeId===storeId
        && request?.generation===generation
        && request?.requestId===latestRequest
    },
    bindPartialConsent(candidate){return {storeId,generation,candidate}},
    acceptsPartialConsent(consent,candidate){
      return consent?.storeId===storeId
        && consent?.generation===generation
        && consent?.candidate===candidate
    },
  }
}
