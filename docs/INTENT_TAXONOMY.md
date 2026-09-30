# Intent Taxonomy

Gold v1-derived allowed labels. Model outputs must normalize to one of these exact major/minor pairs.

## Allowed labels

- `不良反应`
  - `泛红刺痒`
  - `过敏就医`
- `产品咨询`
  - `优惠与赠品咨询`
  - `套装搭配推荐`
  - `正品鉴别咨询`
- `售后退货`
  - `仅退款疑似异常`
- `物流异常`
  - `包裹少件`
  - `包裹破损`
  - `显示签收未收到`
- `物流服务`
  - `物流查询`
- `补发换货`
  - `会员权益加赠补发`
  - `少发正装`
  - `漏发赠品`
  - `破损换货`
  - `错发色号`
- `订单服务`
  - `保价申请被拒`
  - `直播间承诺纠纷`
  - `退款迟迟不到账`
  - `预售尾款咨询`
- `退款打款`
  - `售后期关闭过敏退款`

## Normalization rules

- Trim leading/trailing whitespace and collapse internal whitespace.
- Exact major/minor pairs are accepted; invalid combinations are rejected.
- Alias matching may use exact normalized text or an unambiguous substring match.
- Unknown labels are not silently converted to a different intent; they remain unmapped.
- This taxonomy is derived from human Gold v1, not from model-generated labels.
