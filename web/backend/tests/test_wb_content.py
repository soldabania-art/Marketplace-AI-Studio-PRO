from app.wb_content import normalize_card


def test_normalize_card_keeps_real_content_fields():
    row=normalize_card({'nmID':123,'vendorCode':'SKU-1','title':'Товар','brand':'Brand','subjectID':42,'subjectName':'Органайзеры','description':'Описание','photos':[{'big':'x'}],'characteristics':[{'id':1,'name':'Цвет','value':['чёрный']}],'sizes':[{'skus':['460000000001']}],'updatedAt':'2026-09-07T10:00:00Z'})
    assert row['nm_id']==123
    assert row['vendor_code']=='SKU-1'
    assert row['brand']=='Brand'
    assert row['photo_count']==1
    assert row['skus']==['460000000001']
    assert row['characteristics'][0]['name']=='Цвет'
