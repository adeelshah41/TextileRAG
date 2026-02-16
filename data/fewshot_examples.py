FEW_SHOT = [
    {
        "question": "what is the biggest weight available among the fabrics?",
        "sql": "SELECT MAX(TO_NUMBER(REGEXP_SUBSTR(OZ,'[0-9]+(\\.[0-9]+)?'))) AS MAX_OZ FROM fabric_specs"
    },
    {
        "question": "give me the list of all the fabrics having 7/1   RINGSLUB as warp item description",
        "sql": "SELECT STYLE, OZ, WEAVE, QUALITY, WARP_ITEM_DESC1 FROM fabric_specs WHERE TRIM(WARP_ITEM_DESC1) = '7/1   RINGSLUB' FETCH FIRST 200 ROWS ONLY"
    },
    {
        "question": "give the list of all the fabrics that weigh exactly 10 oz",
        "sql": "SELECT STYLE, OZ, WEAVE, QUALITY FROM fabric_specs WHERE TO_NUMBER(REGEXP_SUBSTR(OZ,'[0-9]+(\\.[0-9]+)?')) = 10 FETCH FIRST 200 ROWS ONLY"
    },


]
